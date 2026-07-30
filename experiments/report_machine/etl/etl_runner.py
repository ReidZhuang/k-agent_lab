"""
ETL 统一调度脚本 — 全量数据管道（新方案：单次全量取，无循环）

功能:
  1. 初始化数据库表结构
  2. 拉取 dc/ths/tdx 概念板块成分、分类、日行情（T-1，单次全量）
  3. 拉取腾讯财经 A 股全量快照（分批，无硬限制）
  4. 计算盘中板块行情（dc/ths/tdx 三套）
  5. 构建个股盘中宽表

运行:
  python etl_runner.py                    # 全量运行
  python etl_runner.py --init-only        # 仅建库
  python etl_runner.py --snapshot-only    # 仅拉腾讯快照
  python etl_runner.py --mid-only         # 仅计算中间层
"""

import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import tushare as ts
import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from config import *
from db_manager import DatabaseManager
from utils import setup_logger, chunk_list, batch_id, TokenBucket
import time

# 交易日历
sys.path.insert(0, str(MIDDAY_DIR))
from trade_calendar import prev_trading_day, get_calendar

logger = setup_logger("etl_runner", "etl_runner.log")
PRO = ts.pro_api()
db = DatabaseManager()

# 共享令牌桶限流器 — 所有线程共用一个，控制总 API 速率 ≤ 480次/分钟
_API_BUCKET = TokenBucket(rate=8, burst=20)


# ====================================================================
# 辅助
# ====================================================================

def tushare_trade_date() -> str:
    """Tushare 日终数据交易日：始终取 T-1（上一个交易日）"""
    return prev_trading_day(datetime.now().strftime("%Y%m%d"))


def today_trade_date() -> str:
    """当前交易日：今天如果是交易日则今天，否则上一个交易日（用于盘中快照）"""
    cal = get_calendar()
    today = datetime.now().strftime("%Y%m%d")
    if cal.is_trading_day(today):
        return today
    return cal.pretrade_date(today)


def _to_tencent(code: str) -> str:
    """ts_code → 腾讯格式（6→sh, 0/3/8→sz）"""
    c = code.split(".")[0]
    return f"sh{c}" if c.startswith("6") else f"sz{c}"


def _resolve_ts_code(symbol: str) -> str:
    """6位数字代码 → ts_code"""
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    elif symbol.startswith(("0", "3")):
        return f"{symbol}.SZ"
    return f"{symbol}.BJ"


# ====================================================================
# 安全调用包装（带限流 + 频率超限重试）
# ====================================================================

def _safe_api_call(api_fn, bucket=_API_BUCKET, max_retries=5, **kwargs):
    """带令牌桶限流 + 频率超限重试的 API 调用

    Args:
        api_fn: PRO.xxx 方法（如 PRO.ths_member）
        bucket: 共享令牌桶
        max_retries: 频率超限重试次数
        **kwargs: 传给 api_fn 的参数

    Returns:
        DataFrame | None
    """
    for attempt in range(max_retries):
        bucket.acquire()               # 令牌桶限流（8次/秒全线程共享）
        try:
            df = api_fn(**kwargs)
            return df                  # 无论空数据还是 None，只透传不判断
        except Exception as e:
            if "频率超限" in str(e):
                wait = min(30 * (attempt + 1), 120)
                logger.warning(f"  ⚠ 频率超限({api_fn.__name__}), "
                               f"等待{wait}s后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                logger.error(f"  ❌ {api_fn.__name__} 调用失败: {e}")
                return None
    logger.error(f"  ❌ {api_fn.__name__} 重试{max_retries}次仍失败, 跳过")
    return None


def _verify_member_completeness(source_name, index_table, member_table):
    """校验板块成分是否完整：index 有而 member 无 → 警告"""
    sql = f"""
        SELECT i.ts_code FROM {index_table} i
        WHERE i.ts_code NOT IN (SELECT DISTINCT ts_code FROM {member_table})
    """
    missing = db.execute(sql)
    if missing:
        logger.warning(f"  ⚠ [{source_name}] {len(missing)} 个板块无成分数据: "
                       f"{[r[0] for r in missing[:5]]}...")
    else:
        logger.info(f"  ✅ [{source_name}] 全部板块成分完整")
    return missing


# ====================================================================
# 第 1 组: DC / THS / TDX（单次全量取）
# ====================================================================

def etl_dc(trade_date: str = None):
    """DC: index + member + daily"""
    td = trade_date or tushare_trade_date()
    logger.info(f"[DC] 拉取 {td} 数据...")
    n = 0

    # dc_index（循环全部分类：概念板块/行业板块/地域板块）
    for idx_type in ["概念板块", "行业板块", "地域板块"]:
        df = PRO.dc_index(trade_date=td, idx_type=idx_type)
        if df is not None and not df.empty:
            rows = [(td, r["ts_code"], r.get("name",""), r.get("idx_type",""),
                     r.get("leading",""), r.get("leading_code",""), r.get("pct_change"),
                     r.get("up_num"), r.get("down_num"), r.get("total_mv"),
                     r.get("turnover_rate"), r.get("level",""))
                    for _, r in df.iterrows()]
            db.insert_batch("stg_dc_index",
                ["trade_date","ts_code","name","idx_type","leading","leading_code",
                 "pct_change","up_num","down_num","total_mv","turnover_rate","level"], rows)
            n += len(rows)
            logger.info(f"  dc_index({idx_type}): {len(rows)}")

    # dc_member（按板块循环，令牌桶限流 + 频率超限重试）
    total_m = 0
    sectors = db.execute("SELECT ts_code FROM stg_dc_index WHERE trade_date=?", (td,))
    for i, (sc,) in enumerate(sectors, 1):
        df = _safe_api_call(PRO.dc_member, trade_date=td, ts_code=sc)
        if df is not None and not df.empty:
            rows = [(td, sc, r["con_code"], r.get("name","")) for _, r in df.iterrows()]
            db.insert_batch("stg_dc_member",
                ["trade_date","ts_code","con_code","con_name"], rows)
            total_m += len(rows)
        if i % 100 == 0:
            logger.info(f"  dc_member: {i}/{len(sectors)} sectors, {total_m} rows")
    n += total_m
    logger.info(f"  dc_member: {total_m} (循环)")
    _verify_member_completeness("DC", "stg_dc_index", "stg_dc_member")

    # dc_daily（单次全量）
    df = PRO.dc_daily(trade_date=td)
    if df is not None and not df.empty:
        rows = [(td, r["ts_code"], r.get("close"), r.get("open"), r.get("high"),
                 r.get("low"), r.get("change"), r.get("pct_change"),
                 r.get("vol"), r.get("amount"), r.get("swing"), r.get("turnover_rate"))
                for _, r in df.iterrows()]
        db.insert_batch("stg_dc_daily",
            ["trade_date","ts_code","close","open","high","low",
             "change","pct_change","vol","amount","swing","turnover_rate"], rows)
        n += len(rows)
        logger.info(f"  dc_daily: {len(rows)}")

    return n


def etl_ths(trade_date: str = None):
    """THS: index + member + daily，单次全量"""
    td = trade_date or tushare_trade_date()
    logger.info(f"[THS] 拉取数据...")
    n = 0

    # ths_index（加载全部分类：N概念/I行业/R地域/S特色/ST风格/TH主题/BB宽基）
    df = PRO.ths_index()
    if df is not None and not df.empty:
        rows = [(r["ts_code"], r.get("name",""), r.get("count"),
                 r.get("exchange",""), r.get("list_date",""), r.get("type",""))
                for _, r in df.iterrows()]
        db.insert_batch("stg_ths_index",
            ["ts_code","name","count","exchange","list_date","type"], rows)
        n += len(rows)
        logger.info(f"  ths_index: {len(rows)}")

    # ths_member（按板块循环，令牌桶限流 + 频率超限重试）
    total_m = 0
    sectors = db.execute("SELECT ts_code FROM stg_ths_index")
    for i, (sc,) in enumerate(sectors, 1):
        df = _safe_api_call(PRO.ths_member, ts_code=sc)
        if df is not None and not df.empty:
            rows = [(sc, r["con_code"], r.get("con_name","")) for _, r in df.iterrows()]
            db.insert_batch("stg_ths_member",
                ["ts_code","con_code","con_name"], rows)
            total_m += len(rows)
        if i % 100 == 0:
            logger.info(f"  ths_member: {i}/{len(sectors)} sectors, {total_m} rows")
    n += total_m
    logger.info(f"  ths_member: {total_m} (循环)")
    _verify_member_completeness("THS", "stg_ths_index", "stg_ths_member")

    # ths_daily
    df = PRO.ths_daily(trade_date=td)
    if df is not None and not df.empty:
        rows = [(r["ts_code"], r["trade_date"], r.get("close"), r.get("open"),
                 r.get("high"), r.get("low"), r.get("pre_close"), r.get("avg_price"),
                 r.get("change"), r.get("pct_change"), r.get("vol"),
                 r.get("turnover_rate"), r.get("total_mv"), r.get("float_mv"))
                for _, r in df.iterrows()]
        db.insert_batch("stg_ths_daily",
            ["ts_code","trade_date","close","open","high","low","pre_close",
             "avg_price","change","pct_change","vol","turnover_rate","total_mv","float_mv"], rows)
        n += len(rows)
        logger.info(f"  ths_daily: {len(rows)}")

    return n


def etl_tdx(trade_date: str = None):
    """TDX: index + member + daily，单次全量"""
    td = trade_date or tushare_trade_date()
    logger.info(f"[TDX] 拉取 {td} 数据...")
    n = 0

    # tdx_index（循环全部分类：概念板块/行业板块/风格板块/地区板块）
    for idx_type in ["概念板块", "行业板块", "风格板块", "地区板块"]:
        df = PRO.tdx_index(trade_date=td, idx_type=idx_type)
        if df is not None and not df.empty:
            rows = [(td, r["ts_code"], r.get("name",""), r.get("idx_type",""),
                     r.get("idx_count"), r.get("total_share"), r.get("float_share"),
                     r.get("total_mv"), r.get("float_mv"))
                    for _, r in df.iterrows()]
            db.insert_batch("stg_tdx_index",
                ["trade_date","ts_code","name","idx_type","idx_count",
                 "total_share","float_share","total_mv","float_mv"], rows)
            n += len(rows)
            logger.info(f"  tdx_index({idx_type}): {len(rows)}")

    # tdx_member（按板块循环，令牌桶限流 + 频率超限重试）
    total_m = 0
    sectors = db.execute("SELECT ts_code FROM stg_tdx_index WHERE trade_date=?", (td,))
    for i, (sc,) in enumerate(sectors, 1):
        df = _safe_api_call(PRO.tdx_member, trade_date=td, ts_code=sc)
        if df is not None and not df.empty:
            rows = [(td, sc, r["con_code"], r.get("con_name","")) for _, r in df.iterrows()]
            db.insert_batch("stg_tdx_member",
                ["trade_date","ts_code","con_code","con_name"], rows)
            total_m += len(rows)
        if i % 100 == 0:
            logger.info(f"  tdx_member: {i}/{len(sectors)} sectors, {total_m} rows")
    n += total_m
    logger.info(f"  tdx_member: {total_m} (循环)")
    _verify_member_completeness("TDX", "stg_tdx_index", "stg_tdx_member")

    # tdx_daily
    df = PRO.tdx_daily(trade_date=td)
    if df is not None and not df.empty:
        rows = [(td, r["ts_code"], r.get("close"), r.get("open"), r.get("high"),
                 r.get("low"), r.get("pre_close"), r.get("change"), r.get("pct_change"),
                 r.get("vol"), r.get("amount"), r.get("vol_ratio"), r.get("turnover_rate"),
                 r.get("swing"), r.get("up_num"), r.get("down_num"),
                 r.get("limit_up_num"), r.get("limit_down_num"),
                 r.get("total_share"), r.get("float_share"), r.get("float_mv"),
                 r.get("pe"), r.get("pb"))
                for _, r in df.iterrows()]
        db.insert_batch("stg_tdx_daily",
            ["trade_date","ts_code","close","open","high","low","pre_close",
             "change","pct_change","vol","amount","vol_ratio","turnover_rate",
             "swing","up_num","down_num","limit_up_num","limit_down_num",
             "total_share","float_share","float_mv","pe","pb"], rows)
        n += len(rows)
        logger.info(f"  tdx_daily: {len(rows)}")

    return n


# ====================================================================
# 第 2 组: 腾讯财经 A 股全量快照
# ====================================================================

def fetch_tencent_batch(codes: list[str]) -> list[dict]:
    """腾讯财经批量获取（解析全部 54 字段）"""
    url = f"{TENCENT_URL}{','.join(codes)}"
    try:
        r = requests.get(url, headers=TENCENT_HEADERS, timeout=15)
        r.encoding = "gbk"
        results = []
        for line in r.text.strip().split(";"):
            if "~" not in line:
                continue
            line = line.strip()
            if "=" in line:
                line = line.split("=", 1)[1].strip('"')
            fields = line.split("~")
            if len(fields) < 54:
                continue
            try:
                results.append({
                    "market_type": int(fields[0]) if fields[0] else None,
                    "name": fields[1], "symbol": fields[2],
                    "price": float(fields[3]) if fields[3] else None,
                    "prev_close": float(fields[4]) if fields[4] else None,
                    "open": float(fields[5]) if fields[5] else None,
                    "volume": int(fields[6]) if fields[6] else None,
                    "outer_disc": int(fields[7]) if fields[7] else None,
                    "inner_disc": int(fields[8]) if fields[8] else None,
                    "bid1_price": float(fields[9]) if fields[9] else None,
                    "bid1_vol": int(fields[10]) if fields[10] else None,
                    "bid2_price": float(fields[11]) if fields[11] else None,
                    "bid2_vol": int(fields[12]) if fields[12] else None,
                    "bid3_price": float(fields[13]) if fields[13] else None,
                    "bid3_vol": int(fields[14]) if fields[14] else None,
                    "bid4_price": float(fields[15]) if fields[15] else None,
                    "bid4_vol": int(fields[16]) if fields[16] else None,
                    "bid5_price": float(fields[17]) if fields[17] else None,
                    "bid5_vol": int(fields[18]) if fields[18] else None,
                    "ask1_price": float(fields[19]) if fields[19] else None,
                    "ask1_vol": int(fields[20]) if fields[20] else None,
                    "ask2_price": float(fields[21]) if fields[21] else None,
                    "ask2_vol": int(fields[22]) if fields[22] else None,
                    "ask3_price": float(fields[23]) if fields[23] else None,
                    "ask3_vol": int(fields[24]) if fields[24] else None,
                    "ask4_price": float(fields[25]) if fields[25] else None,
                    "ask4_vol": int(fields[26]) if fields[26] else None,
                    "ask5_price": float(fields[27]) if fields[27] else None,
                    "ask5_vol": int(fields[28]) if fields[28] else None,
                    "time_stamp": fields[30] if len(fields) > 30 else None,
                    "chg": float(fields[31]) if fields[31] else None,
                    "chg_pct": float(fields[32]) if fields[32] else None,
                    "high": float(fields[33]) if fields[33] else None,
                    "low": float(fields[34]) if fields[34] else None,
                    "amount_detail": fields[35] if len(fields) > 35 else None,
                    "volume_dup": int(fields[36]) if fields[36] else None,
                    "amount_wan": float(fields[37]) if fields[37] else None,
                    "turnover_rate": float(fields[38]) if fields[38] else None,
                    "pe": float(fields[39]) if fields[39] else None,
                    "high_dup": float(fields[41]) if len(fields) > 41 and fields[41] else None,
                    "low_dup": float(fields[42]) if len(fields) > 42 and fields[42] else None,
                    "amplitude": float(fields[43]) if len(fields) > 43 and fields[43] else None,
                    "market_cap_flow": float(fields[44]) if len(fields) > 44 and fields[44] else None,
                    "market_cap_total": float(fields[45]) if len(fields) > 45 and fields[45] else None,
                    "pb": float(fields[46]) if len(fields) > 46 and fields[46] else None,
                    "limit_up": float(fields[47]) if len(fields) > 47 and fields[47] else None,
                    "limit_down": float(fields[48]) if len(fields) > 48 and fields[48] else None,
                    "volume_ratio": float(fields[49]) if len(fields) > 49 and fields[49] else None,
                    "diff_weicha": float(fields[50]) if len(fields) > 50 and fields[50] else None,
                    "avg_price": float(fields[51]) if len(fields) > 51 and fields[51] else None,
                    "pe_dynamic": float(fields[52]) if len(fields) > 52 and fields[52] else None,
                    "pe_static": float(fields[53]) if len(fields) > 53 and fields[53] else None,
                })
            except (ValueError, IndexError):
                continue
        return results
    except Exception as e:
        logger.warning(f"  批量请求失败: {e}")
        return []


def etl_tencent_snapshot():
    """腾讯财经全量快照（分批从 member 表收集代码 → 批量调腾讯接口）"""
    logger.info("[tencent_snapshot] 收集全量股票代码...")

    stocks = set()
    for tbl in ["stg_dc_member", "stg_ths_member", "stg_tdx_member"]:
        if db.table_exists(tbl):
            rows = db.execute(f"SELECT DISTINCT con_code FROM {tbl}")
            for r in rows:
                if r[0]:
                    stocks.add(r[0])

    if not stocks:
        df = PRO.stock_basic(exchange="", list_status="L", fields="ts_code")
        if df is not None:
            stocks = set(df["ts_code"])

    all_ts_codes = sorted(stocks)
    logger.info(f"  共 {len(all_ts_codes)} 只股票")

    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = 0

    for batch in chunk_list(all_ts_codes, 200):
        tcodes = [_to_tencent(c) for c in batch]
        prices = fetch_tencent_batch(tcodes)
        if not prices:
            continue

        symbol_map = {c.split(".")[0]: c for c in batch}
        rows = []
        for p in prices:
            sym = p.get("symbol", "")
            ts_code = symbol_map.get(sym) or _resolve_ts_code(sym)
            rows.append((
                fetch_time, ts_code,
                p.get("market_type"), p.get("name"), sym,
                p.get("price"), p.get("prev_close"), p.get("open"),
                p.get("volume"), p.get("outer_disc"), p.get("inner_disc"),
                p.get("bid1_price"), p.get("bid1_vol"),
                p.get("bid2_price"), p.get("bid2_vol"),
                p.get("bid3_price"), p.get("bid3_vol"),
                p.get("bid4_price"), p.get("bid4_vol"),
                p.get("bid5_price"), p.get("bid5_vol"),
                p.get("ask1_price"), p.get("ask1_vol"),
                p.get("ask2_price"), p.get("ask2_vol"),
                p.get("ask3_price"), p.get("ask3_vol"),
                p.get("ask4_price"), p.get("ask4_vol"),
                p.get("ask5_price"), p.get("ask5_vol"),
                None,
                p.get("time_stamp"),
                p.get("chg"), p.get("chg_pct"), p.get("high"), p.get("low"),
                p.get("amount_detail"), p.get("volume_dup"), p.get("amount_wan"),
                p.get("turnover_rate"), p.get("pe"), None,
                p.get("high_dup"), p.get("low_dup"), p.get("amplitude"),
                p.get("market_cap_flow"), p.get("market_cap_total"),
                p.get("pb"), p.get("limit_up"), p.get("limit_down"),
                p.get("volume_ratio"), p.get("diff_weicha"),
                p.get("avg_price"), p.get("pe_dynamic"), p.get("pe_static"),
            ))
            total += 1

        if rows:
            cols = ["fetch_time","ts_code","market_type","name","symbol",
                    "price","prev_close","open","volume","outer_disc","inner_disc",
                    "bid1_price","bid1_vol","bid2_price","bid2_vol",
                    "bid3_price","bid3_vol","bid4_price","bid4_vol",
                    "bid5_price","bid5_vol",
                    "ask1_price","ask1_vol","ask2_price","ask2_vol",
                    "ask3_price","ask3_vol","ask4_price","ask4_vol",
                    "ask5_price","ask5_vol","field_29","time_stamp",
                    "chg","chg_pct","high","low","amount_detail","volume_dup",
                    "amount_wan","turnover_rate","pe","field_40",
                    "high_dup","low_dup","amplitude","market_cap_flow",
                    "market_cap_total","pb","limit_up","limit_down",
                    "volume_ratio","diff_weicha","avg_price","pe_dynamic","pe_static"]
            db.insert_batch("stg_tencent_snapshot", cols, rows)

    logger.info(f"  ✅ 共获取 {total} 只股票快照")
    return total


# ====================================================================
# 第 3 组: 中间层
# ====================================================================

def _calc_sector_mid(sector_table, member_table, name_table, name_sql):
    """通用盘中板块行情计算"""
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    td = today_trade_date()

    snap = db.execute(
        "SELECT DISTINCT fetch_time FROM stg_tencent_snapshot ORDER BY fetch_time DESC LIMIT 1")
    if not snap:
        logger.warning("  无腾讯快照")
        return 0
    snap_time = snap[0][0]

    sql = f"""
        SELECT m.ts_code,
               COUNT(DISTINCT m.con_code) as mc,
               COUNT(DISTINCT CASE WHEN s.price IS NOT NULL THEN m.con_code END) as vc,
               ROUND(AVG(s.chg_pct),2) as avg_c,
               ROUND(MAX(s.chg_pct),2) as max_c,
               ROUND(MIN(s.chg_pct),2) as min_c,
               SUM(CASE WHEN s.chg_pct>0 THEN 1 ELSE 0 END) as up,
               SUM(CASE WHEN s.chg_pct<0 THEN 1 ELSE 0 END) as dn,
               ROUND(SUM(s.amount_wan),2) as amt,
               ROUND(SUM(s.market_cap_total*10000),2) as tmv,
               ROUND(AVG(s.turnover_rate),2) as tr
        FROM {member_table} m
        LEFT JOIN stg_tencent_snapshot s ON m.con_code=s.ts_code AND s.fetch_time=?
        WHERE s.price IS NOT NULL
        GROUP BY m.ts_code
        ORDER BY avg_c DESC
    """
    rows = db.execute(sql, (snap_time,))
    name_map = dict(db.execute(name_sql)) if name_table else {}

    insert = []
    for r in rows:
        insert.append((
            fetch_time, td, r[0], name_map.get(r[0], ""),
            r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10],
        ))

    if insert:
        db.insert_batch(sector_table, [
            "fetch_time","trade_date","ts_code","name",
            "member_count","valid_count","avg_chg_pct",
            "max_chg_pct","min_chg_pct","up_count","down_count",
            "total_amount","total_mv","turnover_rate",
        ], insert)

    logger.info(f"  {sector_table}: {len(insert)} 条")
    return len(insert)


def etl_mid_sector():
    """计算盘中板块行情（三套）"""
    logger.info("[mid_sector] 计算盘中板块行情...")
    _calc_sector_mid("mid_sector_dc", "stg_dc_member", "stg_dc_index",
                     "SELECT DISTINCT ts_code, name FROM stg_dc_index")
    _calc_sector_mid("mid_sector_ths", "stg_ths_member", "stg_ths_index",
                     "SELECT DISTINCT ts_code, name FROM stg_ths_index")
    _calc_sector_mid("mid_sector_tdx", "stg_tdx_member", "stg_tdx_index",
                     "SELECT DISTINCT ts_code, name FROM stg_tdx_index")


def etl_mid_stock_intraday():
    """个股盘中宽表（含所属板块）"""
    logger.info("[mid_stock_intraday] 构建个股宽表...")
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    td = today_trade_date()

    snap = db.execute(
        "SELECT DISTINCT fetch_time FROM stg_tencent_snapshot ORDER BY fetch_time DESC LIMIT 1")
    if not snap:
        return 0
    snap_time = snap[0][0]

    stocks = db.execute("""
        SELECT ts_code, name, price, prev_close, open, high, low,
               chg_pct, turnover_rate, amount_wan, amplitude, volume, volume_ratio,
               avg_price, market_cap_total, market_cap_flow, pe_dynamic, pb,
               limit_up, limit_down
        FROM stg_tencent_snapshot
        WHERE fetch_time=? AND price IS NOT NULL
    """, (snap_time,))

    def _sec(con_code, tbl):
        if not db.table_exists(tbl):
            return ""
        r = db.execute(f"SELECT DISTINCT ts_code FROM {tbl} WHERE con_code=? LIMIT 10",
                       (con_code,))
        return ",".join(x[0] for x in r)

    total = 0
    batch = []
    for r in stocks:
        ts_code = r[0]
        dc = _sec(ts_code, "stg_dc_member")
        ths = _sec(ts_code, "stg_ths_member")
        tdx = _sec(ts_code, "stg_tdx_member")
        if not dc and not ths and not tdx:
            continue
        batch.append((
            fetch_time, td, ts_code, r[1], r[2], r[3], r[4], r[5], r[6],
            r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14], r[15],
            r[16], r[17], r[18], r[19], dc, ths, tdx,
        ))
        total += 1
        if len(batch) >= 500:
            db.insert_batch("mid_stock_intraday", [
                "fetch_time","trade_date","ts_code","name",
                "price","prev_close","open","high","low",
                "chg_pct","turnover_rate","amount_wan","amplitude","volume",
                "volume_ratio","avg_price","market_cap_total","market_cap_flow",
                "pe_dynamic","pb","limit_up","limit_down",
                "dc_sectors","ths_sectors","tdx_sectors",
            ], batch)
            batch = []
    if batch:
        db.insert_batch("mid_stock_intraday", [
            "fetch_time","trade_date","ts_code","name",
            "price","prev_close","open","high","low",
            "chg_pct","turnover_rate","amount_wan","amplitude","volume",
            "volume_ratio","avg_price","market_cap_total","market_cap_flow",
            "pe_dynamic","pb","limit_up","limit_down",
            "dc_sectors","ths_sectors","tdx_sectors",
        ], batch)

    logger.info(f"  mid_stock_intraday: {total} 条")
    return total


# ====================================================================
# 第 4 组: 股票基础信息
# ====================================================================

def etl_stock_basic():
    """刷新 stg_stock_basic（全量替换）"""
    logger.info("[stock_basic] 拉取股票基础信息...")

    today = datetime.now().strftime("%Y%m%d")

    # 检查是否今日已更新
    rows = db.execute("SELECT update_date FROM stg_stock_basic LIMIT 1")
    if rows and rows[0][0] == today:
        logger.info("  ✅ 今日已更新，跳过")
        return 0

    df = PRO.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    if df is None or df.empty:
        logger.warning("  ⚠️  Tushare stock_basic 返回空")
        return 0

    insert_rows = []
    for _, r in df.iterrows():
        insert_rows.append((
            r.get("ts_code", ""),
            r.get("symbol", ""),
            r.get("name", ""),
            r.get("area", ""),
            r.get("industry", ""),
            r.get("market", ""),
            r.get("list_date", ""),
            today,
        ))

    # 全量替换
    db.execute("DELETE FROM stg_stock_basic")
    db.insert_batch("stg_stock_basic",
        ["ts_code", "symbol", "name", "area", "industry", "market", "list_date", "update_date"],
        insert_rows)

    logger.info(f"  ✅ 股票基础信息已更新: {len(insert_rows)} 只")
    return len(insert_rows)


# ====================================================================
# 日志
# ====================================================================

def log_it(api, tbl, rows, start, end, status="SUCCESS", err=""):
    db.log_update(batch_id(), api, tbl, tushare_trade_date(),
                  start, end, status, rows, rows, err)


# ====================================================================
# 全量运行
# ====================================================================

def run_all():
    bid = batch_id()
    td = tushare_trade_date()
    logger.info(f"🚀 ETL 开始 | 批次={bid} | 交易日={td}")
    t0 = time.time()

    def _run_one(grp, fn):
        """单个数据源 ETL（线程内执行）"""
        s = datetime.now().isoformat()
        try:
            n = fn(td)
            log_it(f"{grp.lower()}_all", f"stg_{grp.lower()}_*", n, s, datetime.now().isoformat())
            return grp, n, None
        except Exception as e:
            log_it(f"{grp.lower()}_all", f"stg_{grp.lower()}_*", 0, s, datetime.now().isoformat(), "FAILED", str(e))
            return grp, 0, e

    sources = [("DC", etl_dc), ("THS", etl_ths), ("TDX", etl_tdx)]
    logger.info(f" ═══ 并行取数: {' / '.join(g for g, _ in sources)} ═══")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_run_one, grp, fn): grp for grp, fn in sources}
        for fut in as_completed(futures):
            grp, n, err = fut.result()
            if err:
                logger.error(f"  ❌ {grp} 失败: {err}")
            else:
                logger.info(f"  ✅ {grp}: {n} 行")

    logger.info(f"\n═══ 股票基础信息 ═══")
    s = datetime.now().isoformat()
    try:
        n = etl_stock_basic()
        log_it("stock_basic", "stg_stock_basic", n, s, datetime.now().isoformat())
    except Exception as e:
        log_it("stock_basic", "stg_stock_basic", 0, s, datetime.now().isoformat(), "FAILED", str(e))

    logger.info(f"\n═══ 腾讯快照 ═══")
    s = datetime.now().isoformat()
    try:
        n = etl_tencent_snapshot()
        log_it("tencent_snapshot", "stg_tencent_snapshot", n, s, datetime.now().isoformat())
    except Exception as e:
        log_it("tencent_snapshot", "stg_tencent_snapshot", 0, s, datetime.now().isoformat(), "FAILED", str(e))

    logger.info(f"\n═══ 中间层 ═══")
    s = datetime.now().isoformat()
    try:
        etl_mid_sector()
        log_it("mid_sector", "mid_sector_*", 0, s, datetime.now().isoformat())
    except Exception as e:
        log_it("mid_sector", "mid_sector_*", 0, s, datetime.now().isoformat(), "FAILED", str(e))

    s = datetime.now().isoformat()
    try:
        n = etl_mid_stock_intraday()
        log_it("mid_stock_intraday", "mid_stock_intraday", n, s, datetime.now().isoformat())
    except Exception as e:
        log_it("mid_stock_intraday", "mid_stock_intraday", 0, s, datetime.now().isoformat(), "FAILED", str(e))

    elapsed = time.time() - t0
    logger.info(f"\n✅ ETL 完成！总耗时 {elapsed:.1f}s ({elapsed/60:.1f}min)")


# ====================================================================
# CLI
# ====================================================================

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--init-only" in args:
        db.init_schema()
        sys.exit(0)
    if "--snapshot-only" in args:
        etl_tencent_snapshot()
        sys.exit(0)
    if "--mid-only" in args:
        etl_mid_sector()
        etl_mid_stock_intraday()
        sys.exit(0)
    if "--stock-basic-only" in args:
        etl_stock_basic()
        sys.exit(0)

    db.init_schema()
    run_all()
