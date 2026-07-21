"""
盘中数据取数脚本 — 午盘（11:30）数据获取

设计:
  - 腾讯财经实时行情 → 从本地数据库 mid_stock_intraday 查询（ETL 午间快照）
  - 昨日换手率 → Tushare daily_basic API（DB 暂未收录）
  - 融资融券 → Tushare margin_detail API（DB 暂未收录）
  - 资金博弈 → pysnowball API（实时数据，无法缓存）

输入: 个股名称列表 ['宁德时代', '比亚迪', '菲利华']
输出: {'宁德时代': '内容string', '比亚迪': '内容string', ...}

支持多股同时查询（数据库支持，API 也支持批量）。
"""

import sys
import json
from datetime import datetime, time
from pathlib import Path

import tushare as ts

# 数据库
ETL_DIR = Path(__file__).resolve().parent.parent.parent / "etl"
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))
from db_manager import DatabaseManager
from config import DB_PATH

# 交易日历
sys.path.insert(0, str(Path(__file__).parent))
from trade_calendar import last_trading_day, get_calendar, prev_trading_day

PRO = ts.pro_api()
db = DatabaseManager(str(DB_PATH))


# ──────────────────────────────────────────────────────────────
# 1. 个股实时行情 — 从 DB 取（ETL 午间快照）
# ──────────────────────────────────────────────────────────────

def fetch_quotes_from_db(stock_names: list[str]) -> dict[str, dict]:
    """从 mid_stock_intraday 查询个股实时行情（最新快照）

    Args:
        stock_names: 股票名称列表

    Returns:
        {ts_code: {name, price, chg_pct, turnover_rate, amount_wan, amplitude, ...}}
    """
    if not db.table_exists("mid_stock_intraday"):
        return {}

    # 获取最新快照时间
    times = db.execute(
        "SELECT DISTINCT fetch_time FROM mid_stock_intraday ORDER BY fetch_time DESC LIMIT 1"
    )
    if not times:
        return {}
    snap_time = times[0][0]

    # 名称匹配查（支持批量）
    placeholders = ",".join("?" * len(stock_names))
    rows = db.execute(f"""
        SELECT ts_code, name, price, prev_close, open, high, low,
               chg_pct, turnover_rate, amount_wan, amplitude, volume,
               volume_ratio, avg_price, market_cap_total, market_cap_flow,
               pe_dynamic, pb, limit_up, limit_down,
               dc_sectors, ths_sectors, tdx_sectors
        FROM mid_stock_intraday
        WHERE fetch_time=? AND name IN ({placeholders})
    """, (snap_time, *stock_names))

    result = {}
    for r in rows:
        result[r[1]] = {
            "ts_code": r[0], "name": r[1],
            "price": r[2], "prev_close": r[3],
            "open": r[4], "high": r[5], "low": r[6],
            "chg_pct": r[7],
            "turnover_rate": r[8],
            "amount_wan": r[9],
            "amplitude": r[10],
            "volume": r[11],
            "volume_ratio": r[12],
            "avg_price": r[13],
            "market_cap_total": r[14],
            "market_cap_flow": r[15],
            "pe_dynamic": r[16],
            "pb": r[17],
            "limit_up": r[18],
            "limit_down": r[19],
            "dc_sectors": r[20],
            "ths_sectors": r[21],
            "tdx_sectors": r[22],
        }
    return result


# ──────────────────────────────────────────────────────────────
# 2. 昨日换手率 — Tushare daily_basic
# ──────────────────────────────────────────────────────────────

def _tushare_trade_date() -> str:
    """Tushare 日终数据日期：T-1（上一个交易日）"""
    from datetime import datetime
    return prev_trading_day(datetime.now().strftime("%Y%m%d"))


def fetch_yesterday_turnover(ts_codes: list[str]) -> dict[str, dict]:
    """获取昨日换手率（Tushare daily_basic）"""
    td = _tushare_trade_date()
    result = {}
    for ts_code in ts_codes:
        try:
            df = PRO.daily_basic(ts_code=ts_code, trade_date=td)
            if df.empty:
                result[ts_code] = {"error": "no data", "trade_date": td}
            else:
                r = df.iloc[0]
                result[ts_code] = {
                    "trade_date": td,
                    "turnover_rate": r.get("turnover_rate"),
                    "turnover_rate_f": r.get("turnover_rate_f"),
                    "pe": r.get("pe"),
                    "pb": r.get("pb"),
                    "total_mv": r.get("total_mv"),
                    "circ_mv": r.get("circ_mv"),
                }
        except Exception as e:
            result[ts_code] = {"error": str(e), "trade_date": td}
    return result


# ──────────────────────────────────────────────────────────────
# 3. 融资融券 — Tushare margin_detail
# ──────────────────────────────────────────────────────────────

def fetch_margin(ts_codes: list[str]) -> dict[str, dict]:
    """融资融券（T-1 日 + 较 T-2 变化率）"""
    td = _tushare_trade_date()
    cal = get_calendar()
    t2 = cal.prev_trading_day(td, n=1)

    result = {}
    for ts_code in ts_codes:
        try:
            df1 = PRO.margin_detail(ts_code=ts_code, trade_date=td)
            df2 = PRO.margin_detail(ts_code=ts_code, trade_date=t2)
            info = {"trade_date_t1": td, "trade_date_t2": t2}

            if not df1.empty:
                r1 = df1.iloc[0]
                info["rzye"] = float(r1["rzye"])
                info["rqye"] = float(r1["rqye"])
                info["rzmre"] = float(r1.get("rzmre", 0))
            else:
                info.update({"rzye": None, "rqye": None, "rzmre": None})

            if not df2.empty:
                r2 = df2.iloc[0]
                rzye_t2 = float(r2["rzye"])
                rqye_t2 = float(r2["rqye"])
                info["rzye_chg_pct"] = round(
                    (info["rzye"] - rzye_t2) / rzye_t2 * 100, 2
                ) if info.get("rzye") and rzye_t2 else None
                info["rqye_chg_pct"] = round(
                    (info["rqye"] - rqye_t2) / rqye_t2 * 100, 2
                ) if info.get("rqye") and rqye_t2 else None
            else:
                info["rzye_chg_pct"] = None
                info["rqye_chg_pct"] = None

            result[ts_code] = info
        except Exception as e:
            result[ts_code] = {"error": str(e)}

    return result


# ──────────────────────────────────────────────────────────────
# 4. 资金博弈 — pysnowball
# ──────────────────────────────────────────────────────────────

# 仅首次导入时加载
_SNOWBALL_INITED = False


def _init_snowball():
    global _SNOWBALL_INITED
    if _SNOWBALL_INITED:
        return
    try:
        # 直接导入 midday/config.py 读取 snowball token
        import json
        token_path = Path(__file__).parent / "config" / "snowball_token.json"
        if token_path.exists():
            with open(token_path) as f:
                cfg = json.load(f)
            xq = cfg.get("xq_a_token", "")
            u = cfg.get("u", "")
            if xq and u:
                import pysnowball as ball
                ball.set_token(f"xq_a_token={xq}; u={u}")
                _SNOWBALL_INITED = True
                return
        print("[snowball] 未找到有效 Token", file=sys.stderr)
        _SNOWBALL_INITED = True
    except Exception as e:
        print(f"[snowball] init failed: {e}", file=sys.stderr)
        _SNOWBALL_INITED = True


def fetch_capital_flow(xueqiu_codes: list[str]) -> dict[str, dict]:
    """上午资金净流向（pysnowball capital_flow）—— 含时序统计

    数据说明: capital_flow 返回逐分钟累计净额(amount)。
    本函数将其转为逐分钟净流量，计算多维度统计供 LLM 分析。
    """
    _init_snowball()
    import pysnowball as ball

    result = {}
    for xq_code in xueqiu_codes:
        try:
            data = ball.capital_flow(xq_code)
            if data.get("error_code") != 0:
                result[xq_code] = {"error": data.get("error_description", "")}
                continue
            items = data.get("data", {}).get("items", [])
            if not items:
                result[xq_code] = {"error": "无数据"}
                continue

            # 取累计值序列
            cum_values = [float(it.get("amount", 0)) for it in items if isinstance(it, dict)]
            if not cum_values:
                result[xq_code] = {"error": "无有效数据"}
                continue

            # 总净额（最后一个累计值）
            net_total = cum_values[-1]

            # 转为逐分钟净流量
            per_min = [cum_values[0]]  # 第一分钟就是起始值
            for i in range(1, len(cum_values)):
                per_min.append(cum_values[i] - cum_values[i-1])

            inflow_mins = [v for v in per_min if v > 0]
            outflow_mins = [v for v in per_min if v < 0]
            inflow_total = sum(inflow_mins) if inflow_mins else 0
            outflow_total = abs(sum(outflow_mins)) if outflow_mins else 0

            result[xq_code] = {
                "net_amount_yuan": round(net_total, 2),
                "net_amount_wan": round(net_total / 10000, 2),
                "tick_count": len(items),
                "inflow_minutes": len(inflow_mins),       # 资金流入的分钟数
                "outflow_minutes": len(outflow_mins),     # 资金流出的分钟数
                "inflow_total_yuan": round(inflow_total, 2),     # 总流入金额
                "outflow_total_yuan": round(outflow_total, 2),   # 总流出金额
                "peak_inflow_yuan": round(max(inflow_mins), 2) if inflow_mins else 0,   # 最大单分钟流入
                "peak_outflow_yuan": round(min(outflow_mins), 2) if outflow_mins else 0, # 最大单分钟流出
                "avg_per_min_yuan": round(net_total / len(per_min), 2),  # 每分钟平均净额
            }
        except Exception as e:
            result[xq_code] = {"error": str(e)}

    return result


def fetch_capital_assort(xueqiu_codes: list[str]) -> dict[str, dict]:
    """昨日资金细分（pysnowball capital_assort）"""
    _init_snowball()
    from pysnowball.capital import capital_assort
    import pysnowball as ball

    result = {}
    for xq_code in xueqiu_codes:
        try:
            data = capital_assort(xq_code)
            if data.get("error_code") != 0:
                result[xq_code] = {"error": data.get("error_description", "")}
                continue
            d = data.get("data", {})
            bl = float(d.get("buy_large", 0))
            sl = float(d.get("sell_large", 0))
            bm = float(d.get("buy_medium", 0))
            sm = float(d.get("sell_medium", 0))
            bs = float(d.get("buy_small", 0))
            ss = float(d.get("sell_small", 0))
            result[xq_code] = {
                "large_net": round(bl - sl, 2),
                "buy_large": bl, "sell_large": sl,
                "medium_net": round(bm - sm, 2),
                "buy_medium": bm, "sell_medium": sm,
                "small_net": round(bs - ss, 2),
                "buy_small": bs, "sell_small": ss,
                "total_net": round((bl - sl) + (bm - sm) + (bs - ss), 2),
            }
        except Exception as e:
            result[xq_code] = {"error": str(e)}

    return result


# ══════════════════════════════════════════════════════════════
# Part2: 板块排名（来自 mid_sector_ths）
# ══════════════════════════════════════════════════════════════

def fetch_sector_ranking(stock_names: list[str]) -> dict[str, dict]:
    """从 mid_sector_ths 获取个股所属板块排名

    Returns:
        {name: {sectors: [{ts_code, name, rank, total, avg_chg}], best: ...}}
    """
    if not db.table_exists("mid_sector_ths"):
        return {}

    times = db.execute(
        "SELECT DISTINCT fetch_time FROM mid_sector_ths ORDER BY fetch_time DESC LIMIT 1"
    )
    if not times:
        return {}
    snap_time = times[0][0]

    total_sectors = db.count_rows("mid_sector_ths",
                                   f"fetch_time='{snap_time}'")

    # 预取全量板块排名，避免每只股票逐条查
    all_ranked = db.execute(f"""
        SELECT ts_code, name, avg_chg_pct, up_count, down_count
        FROM mid_sector_ths
        WHERE fetch_time='{snap_time}'
        ORDER BY avg_chg_pct DESC
    """)
    rank_map = {}
    for idx, r in enumerate(all_ranked, 1):
        rank_map[r[0]] = {
            "ts_code": r[0], "name": r[1],
            "avg_chg_pct": r[2], "up_count": r[3], "down_count": r[4],
            "rank": idx, "total": total_sectors,
        }

    # 获取当前价和 ts_code 映射
    name_to_ts = {}
    for nm in stock_names:
        row = db.execute(
            "SELECT ts_code, price FROM mid_stock_intraday WHERE name=? LIMIT 1", (nm,)
        )
        if row:
            name_to_ts[nm] = {"ts_code": row[0][0], "price": row[0][1]}

    # 获取快照中全量股票价格（用于板块内排名）
    snap_ts = db.execute(
        "SELECT DISTINCT fetch_time FROM stg_tencent_snapshot ORDER BY fetch_time DESC LIMIT 1"
    )
    stock_price_map = {}
    if snap_ts:
        all_p = db.execute(
            "SELECT ts_code, name, chg_pct, price FROM stg_tencent_snapshot WHERE fetch_time=?",
            (snap_ts[0][0],)
        )
        for r in all_p:
            stock_price_map[r[0]] = {"name": r[1], "chg_pct": r[2], "price": r[3]}

    # 获取 THS 板块的类型（只保留概念 N + 行业 I 为主，其他标注）
    sector_type_map = {}
    stypes = db.execute("SELECT ts_code, type FROM stg_ths_index")
    for r in stypes:
        sector_type_map[r[0]] = r[1]

    TYPE_LABEL = {"N":"概念","I":"行业","TH":"主题","S":"特色","ST":"风格","R":"地域","BB":"宽基"}
    TYPE_ORDER = ["N","I","TH","S","ST","R","BB"]

    result = {}
    for name in stock_names:
        my_info = name_to_ts.get(name, {})
        my_ts_code = my_info.get("ts_code", "")
        my_price = my_info.get("price")

        # 直接查 stg_ths_member 获取该股所属全部板块，按类型分组
        all_my_codes = db.execute("""
            SELECT DISTINCT m.ts_code, i.type
            FROM stg_ths_member m
            JOIN stg_ths_index i ON m.ts_code=i.ts_code
            WHERE m.con_code=?
        """, (my_ts_code,))
        codes_by_type = {}
        for sc, tp in all_my_codes:
            codes_by_type.setdefault(tp, []).append(sc)

        by_type = {}
        for tp in TYPE_ORDER:
            codes = codes_by_type.get(tp, [])
            if not codes:
                continue
            label = TYPE_LABEL.get(tp, tp)

            type_sectors = []
            for sc in codes[:6]:
                rm = rank_map.get(sc)
                if not rm:
                    continue
                info = dict(rm)

                members = db.execute(
                    "SELECT DISTINCT con_code FROM stg_ths_member WHERE ts_code=?", (sc,)
                )
                sector_stocks = []
                for (con_code,) in members:
                    sp = stock_price_map.get(con_code)
                    if sp and sp["chg_pct"] is not None:
                        sector_stocks.append({"ts_code": con_code, "name": sp["name"], "chg_pct": sp["chg_pct"]})
                sector_stocks.sort(key=lambda x: x["chg_pct"], reverse=True)

                my_pos = next((idx for idx, stk in enumerate(sector_stocks) if stk["ts_code"] == my_ts_code), None)

                info.update({
                    "total_in_sector": len(sector_stocks),
                    "my_position": my_pos,
                    "my_price": my_price,
                    "my_chg_pct": sector_stocks[my_pos]["chg_pct"] if my_pos is not None else None,
                    "sector_type": tp,
                    "top3": sector_stocks[:3],
                    "bottom3": sector_stocks[-3:] if len(sector_stocks) > 3 else [],
                    "neighbors": sector_stocks[max(0, my_pos-2):min(len(sector_stocks), my_pos+3)] if my_pos is not None else [],
                    "all_stocks": sector_stocks if len(sector_stocks) <= 20 else [],
                })
                type_sectors.append(info)

            by_type[tp] = {"label": label, "sectors": type_sectors}

        result[name] = {"by_type": by_type, "total_sectors": total_sectors}
    return result


# ══════════════════════════════════════════════════════════════
# Part2: 板块涨跌幅基准（来自 DB stg_ths_daily，T-1 日板块全天涨跌幅）
# ══════════════════════════════════════════════════════════════

def fetch_ths_daily_benchmark(stock_names: list[str]) -> dict[str, dict]:
    """从 stg_ths_daily 获取 T-1 日同花顺板块全天涨跌幅

    Returns:
        {name: [{ts_code, name, pct_change, close}, ...]}
    """
    if not db.table_exists("stg_ths_daily"):
        return {}

    # 最新交易日
    tds = db.execute(
        "SELECT DISTINCT trade_date FROM stg_ths_daily ORDER BY trade_date DESC LIMIT 1"
    )
    if not tds:
        return {}
    td = tds[0][0]

    # 获取该股所属板块（直接查 stg_ths_member，确保全部分类）
    TYPE_LABEL = {"N":"概念","I":"行业","TH":"主题","S":"特色","ST":"风格","R":"地域","BB":"宽基"}
    TYPE_ORDER = ["N","I","TH","S","ST","R","BB"]

    result = {}
    for name in stock_names:
        my_info = db.execute(
            "SELECT ts_code FROM mid_stock_intraday WHERE name=? LIMIT 1", (name,)
        )
        if not my_info:
            continue
        my_ts_code = my_info[0][0]

        # 查全部所属板块
        all_codes = db.execute("""
            SELECT DISTINCT m.ts_code, i.type
            FROM stg_ths_member m
            JOIN stg_ths_index i ON m.ts_code=i.ts_code
            WHERE m.con_code=?
        """, (my_ts_code,))

        by_type = {}
        for sc, tp in all_codes:
            by_type.setdefault(tp, []).append(sc)

        benchmarks = []
        for tp in TYPE_ORDER:
            codes = by_type.get(tp, [])
            if not codes:
                continue
            label = TYPE_LABEL.get(tp, tp)
            for sc in codes[:3]:  # 每类最多3个
                r = db.execute(
                    "SELECT close, pct_change FROM stg_ths_daily WHERE ts_code=? AND trade_date=?",
                    (sc, td)
                )
                if r:
                    nm = db.execute("SELECT name FROM stg_ths_index WHERE ts_code=?", (sc,))
                    sname = nm[0][0] if nm else sc
                    benchmarks.append({
                        "ts_code": sc, "name": sname,
                        "type_label": label, "trade_date": td,
                        "close": r[0][0], "pct_change": r[0][1],
                    })
        result[name] = benchmarks
    return result


# ══════════════════════════════════════════════════════════════
# Part2: 技术面关键位置（新浪 K-line → MA5/MA10/BOLL）
# ══════════════════════════════════════════════════════════════

import requests as _kreq

_KLINE_CACHE = {}


def _sina_kline(tencent_code: str) -> list[dict] | None:
    """新浪前复权日线（最近640个交易日）"""
    if tencent_code in _KLINE_CACHE:
        return _KLINE_CACHE[tencent_code]

    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,1900-1-1,2099-12-31,2000,qfq"
    try:
        r = _kreq.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.encoding = "utf-8"
        data = r.json()
        for key in data.get("data", {}):
            if key == tencent_code:
                for k in ["qfqday", "day"]:
                    if k in data["data"][key]:
                        records = data["data"][key][k]
                        result = [
                            {"date": r[0], "close": float(r[1]),
                             "open": float(r[2]), "high": float(r[3]),
                             "low": float(r[4]), "volume": float(r[5])}
                            for r in records if len(r) >= 6
                        ]
                        _KLINE_CACHE[tencent_code] = result
                        return result
        return None
    except Exception:
        return None


def _calc_ma(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 2)


def fetch_technical_analysis(names_codes: list[tuple]) -> dict[str, dict]:
    """技术面分析: MA5/MA10/MA20/BOLL + 当前价偏离度

    Args:
        names_codes: [(名称, ts_code), ...]

    Returns:
        {name: {ma5, ma10, ma20, boll_upper, boll_lower, deviation: {...}}}
    """
    import numpy as np

    result = {}
    for name, ts_code in names_codes:
        symbol = ts_code.split(".")[0]
        tcode = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"

        kline = _sina_kline(tcode)
        if not kline or len(kline) < 20:
            result[name] = {"error": "K线数据不足"}
            continue

        # 取最近20个完整交易日（跳过今日可能的不完整日线）
        closes = [k["close"] for k in kline[-21:-1]]
        if len(closes) < 20:
            closes = [k["close"] for k in kline[-20:]]

        ma5 = _calc_ma(closes, 5)
        ma10 = _calc_ma(closes, 10)
        ma20 = _calc_ma(closes, 20)

        if ma20 is not None and len(closes) >= 20:
            std20 = round(float(np.std(closes[-20:])), 2)
            boll_upper = round(ma20 + 2 * std20, 2)
            boll_lower = round(ma20 - 2 * std20, 2)
        else:
            boll_upper = boll_lower = None

        # 当前价
        price = None
        if db.table_exists("mid_stock_intraday"):
            r = db.execute("SELECT price FROM mid_stock_intraday WHERE name=? LIMIT 1", (name,))
            if r:
                price = r[0][0]

        deviation = {}
        for label, val in [("ma5", ma5), ("ma10", ma10), ("ma20", ma20)]:
            if price and val:
                dev = (price - val) / val * 100
                tag = "贴近" if abs(dev) <= 1 else ("上方" if dev > 0 else "下方")
                deviation[label] = {"pct": round(dev, 2), "tag": tag}

        result[name] = {
            "price": price, "ma5": ma5, "ma10": ma10, "ma20": ma20,
            "boll_upper": boll_upper, "boll_lower": boll_lower,
            "deviation": deviation, "kline_records": len(closes),
        }
    return result


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

def _name_to_codes(name: str) -> dict:
    """通过 DB 或 Tushare 获取股票代码"""
    # 先从 DB 的 mid_stock_intraday 查（最新快照）
    if db.table_exists("mid_stock_intraday"):
        row = db.execute(
            "SELECT ts_code FROM mid_stock_intraday WHERE name=? LIMIT 1", (name,)
        )
        if row:
            ts_code = row[0][0]
            symbol = ts_code.split(".")[0]
            xq = f"SZ{symbol}" if symbol.startswith(("0", "3")) else f"SH{symbol}"
            return {"ts_code": ts_code, "symbol": symbol, "xueqiu": xq}

    # 回退到 Tushare stock_basic
    try:
        df = PRO.stock_basic(name=name, list_status="L", fields="ts_code")
        if not df.empty:
            return _format_codes(df.iloc[0]["ts_code"])
    except Exception:
        pass
    # 再回退到本地 name_to_code
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from name_to_code import name_info
        return name_info(name)
    except Exception:
        return None


def _format_codes(ts_code: str) -> dict:
    symbol = ts_code.split(".")[0]
    xq = f"SZ{symbol}" if symbol.startswith(("0", "3")) else f"SH{symbol}"
    return {"ts_code": ts_code, "symbol": symbol, "xueqiu": xq}


def fetch_all(stock_names: list[str]) -> dict:
    """统一取数入口

    Args:
        stock_names: ['宁德时代', '比亚迪']

    Returns:
        {name: formatted_string, ...}
    """
    # 1. 股票代码
    infos = []
    for name in stock_names:
        info = _name_to_codes(name)
        if info:
            infos.append({**info, "name": name})
        else:
            print(f"❌ 未找到: {name}", file=sys.stderr)

    if not infos:
        return {n: f"【{n}】未找到股票信息" for n in stock_names}

    names = [i["name"] for i in infos]
    ts_codes = [i["ts_code"] for i in infos]
    symbols = [i["symbol"] for i in infos]
    xq_codes = [i["xueqiu"] for i in infos]

    # 2. 实时行情 — DB 优先
    quotes = fetch_quotes_from_db(names)

    # 3. 昨日换手率
    yesterday_data = fetch_yesterday_turnover(ts_codes)

    # 4. 融资融券
    margin_data = fetch_margin(ts_codes)

    # 5. 资金流向
    capital_flow_data = fetch_capital_flow(xq_codes)

    # 6. 资金细分
    capital_assort_data = fetch_capital_assort(xq_codes)

    # 7. Part2: 板块排名 + 基准 + 技术面
    sector_rankings = fetch_sector_ranking(names)

    benchmark_data = fetch_ths_daily_benchmark(names)
    tech_data = fetch_technical_analysis(list(zip(names, ts_codes)))

    # 8. 组装结果 dict
    result = {}
    for info in infos:
        name = info["name"]
        ts_code = info["ts_code"]
        symbol = info["symbol"]
        xq_code = info["xueqiu"]

        q = quotes.get(name, {})
        yd = yesterday_data.get(ts_code, {})
        mg = margin_data.get(ts_code, {})
        cf = capital_flow_data.get(xq_code, {})
        ca = capital_assort_data.get(xq_code, {})
        sr = sector_rankings.get(name, {})
        bm = benchmark_data.get(name, [])
        ta = tech_data.get(name, {})

        lines = [f"## {name} ({ts_code})", ""]

        # ── 腾讯财经全量字段快照（54字段） ──
        raw = {}
        if db.table_exists("stg_tencent_snapshot"):
            rr = db.execute(
                "SELECT * FROM stg_tencent_snapshot WHERE ts_code=? ORDER BY fetch_time DESC LIMIT 1",
                (ts_code,)
            )
            if rr:
                # PRAGMA table_info 返回: (cid, name, type, notnull, dflt, pk)
                cols = [d[1] for d in db.execute("PRAGMA table_info(stg_tencent_snapshot)")]
                raw = dict(zip(cols, rr[0]))

        _FOCUS_FIELDS = [
            ("name","股票名称"),("symbol","代码"),("price","当前价"),("prev_close","昨收"),
            ("open","开盘"),("high","最高"),("low","最低"),("chg_pct","涨跌幅%"),
            ("volume","成交量(手)"),("amount_wan","成交额(万元)"),("turnover_rate","换手率%"),
            ("amplitude","振幅%"),("volume_ratio","量比"),("avg_price","均价"),
            ("pe_dynamic","动态市盈率"),("pb","市净率"),
            ("market_cap_total","总市值(亿元)"),("market_cap_flow","流通市值(亿元)"),
            ("limit_up","涨停价"),("limit_down","跌停价"),
            ("bid1_price","买一价"),("ask1_price","卖一价"),
            ("outer_disc","外盘(手)"),("inner_disc","内盘(手)"),
        ]
        raw_items = []
        for key, label in _FOCUS_FIELDS:
            val = raw.get(key)
            if val is not None:
                raw_items.append(f"{label}: {val}")
        if raw_items:
            lines.append("【今日11:30收盘数据】" + " | ".join(raw_items[:16]))
            lines.append("                     " + " | ".join(raw_items[16:]) if raw_items[16:] else "")
        lines.append("")

        # ── 实时行情 ──
        lines.append(f"【今日11:30收盘行情】")
        # 金额格式化辅助
        amt_s = "N/A"
        if "error" not in q:
            amt = q.get("amount_wan", 0)
            if isinstance(amt, (int, float)) and amt:
                amt_s = f"{amt/10000:.2f}亿" if abs(amt) >= 10000 else f"{amt:.0f}万"
        if "error" in q:
            lines.append("          数据暂不可用")
        else:
            chg = q.get("chg_pct", "N/A")
            chg_s = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else str(chg)
            lines.append(f"          （今日午间收盘）价格: {q.get('price', 'N/A')} | "
                         f"涨跌幅: {chg_s} | "
                         f"换手率: {q.get('turnover_rate', 'N/A')}% | "
                         f"振幅: {q.get('amplitude', 'N/A')}% | "
                         f"成交额: {amt_s}")
            lines.append(f"          （今日午间收盘）最高: {q.get('high', 'N/A')} | "
                         f"最低: {q.get('low', 'N/A')} | "
                         f"开盘: {q.get('open', 'N/A')} | "
                         f"量比: {q.get('volume_ratio', 'N/A')}")
        lines.append("")

        # ── 上一个交易日日终 ──
        if "error" in yd:
            lines.append(f"❌（上一个交易日日终）换手率: {yd.get('error', '获取失败')}")
        else:
            yd_tro = yd.get("turnover_rate", "N/A")
            yd_tro_f = yd.get("turnover_rate_f", "N/A")
            lines.append(f"【上一个交易日日终】换手率: {yd_tro}% | "
                         f"自由流通换手率: {yd_tro_f}% | "
                         f"PE: {yd.get('pe', 'N/A')} | PB: {yd.get('pb', 'N/A')}")
            # 对比今日换手
            today_tro = q.get("chg_pct") if "error" not in q else None
            if today_tro is not None and isinstance(yd_tro, (int, float)):
                ratio = q.get("turnover_rate", 0) / yd_tro if yd_tro else 0
                tag = "放量" if ratio > 0.8 else "缩量"
                lines.append(f"          → （今日午间收盘换手率{q.get('turnover_rate', 'N/A')}%）/（上一个交易日日终换手率{yd_tro}%）"
                             f"= {ratio:.2f}（{tag}）")
        lines.append("")

        # ── 融资融券 ──
        if "error" in mg:
            lines.append(f"❌（上一个交易日日终）融资融券: {mg.get('error', '获取失败')}")
        else:
            rzye = mg.get("rzye")
            rqye = mg.get("rqye")
            rzye_s = f"{rzye/100000000:.2f}亿" if rzye else "N/A"
            rqye_s = f"{rqye/100000000:.2f}亿" if rqye else "N/A"
            rzye_c = mg.get("rzye_chg_pct")
            rqye_c = mg.get("rqye_chg_pct")
            lines.append(f"【上一个交易日日终融资融券】")
            if rzye_c is not None:
                lines.append(f"          融资余额: {rzye_s}（较前日: {rzye_c:+.2f}%）")
            else:
                lines.append(f"          融资余额: {rzye_s}")
            if rqye_c is not None:
                lines.append(f"          融券余额: {rqye_s}（较前日: {rqye_c:+.2f}%）")
            else:
                lines.append(f"          融券余额: {rqye_s}")
        lines.append("")

        # ── 资金流向（今日午间） ──
        if "error" in cf:
            lines.append(f"❌（今日午间收盘）资金流向: {cf.get('error', '获取失败')}")
        else:
            net_wan = cf.get("net_amount_wan", 0)
            ticks = cf.get("tick_count", 0)
            if isinstance(net_wan, (int, float)) and abs(net_wan) >= 10000:
                net_s = f"{abs(net_wan)/10000:.2f}亿"
            else:
                net_s = f"{abs(net_wan):.2f}万元"
            direction = "净流入" if (isinstance(net_wan, (int, float)) and net_wan > 0) else "净流出"

            inflow_mins = cf.get("inflow_minutes", 0)
            outflow_mins = cf.get("outflow_minutes", 0)
            peak_in = cf.get("peak_inflow_yuan", 0)
            peak_out = cf.get("peak_outflow_yuan", 0)
            peak_in_s = f"{peak_in/10000:.1f}万" if isinstance(peak_in, (int, float)) else str(peak_in)
            peak_out_s = f"{abs(peak_out)/10000:.1f}万" if isinstance(peak_out, (int, float)) else str(peak_out)

            lines.append(f"【今日午间收盘资金流向（逐分钟统计）】")
            lines.append(f"          净流向: {direction} {net_s}（统计分钟数: {ticks}）")
            lines.append(f"          资金流入 {inflow_mins} 分钟 / 流出 {outflow_mins} 分钟 | "
                         f"最大单分钟流入: {peak_in_s} / 最大单分钟流出: {peak_out_s}")
        lines.append("")

        # ── 上一个交易日日终资金细分 ──
        if "error" in ca:
            lines.append(f"❌（上一个交易日日终）资金细分: {ca.get('error', '获取失败')}")
        else:
            lines.append(f"【上一个交易日日终资金细分（元）】")
            lines.append(f"          大单净额: {ca.get('large_net', 0):+.2f}（买入: {ca.get('buy_large', 0):.0f} / 卖出: {ca.get('sell_large', 0):.0f}）")
            lines.append(f"          中单净额: {ca.get('medium_net', 0):+.2f}（买入: {ca.get('buy_medium', 0):.0f} / 卖出: {ca.get('sell_medium', 0):.0f}）")
            lines.append(f"          小单净额: {ca.get('small_net', 0):+.2f}（买入: {ca.get('buy_small', 0):.0f} / 卖出: {ca.get('sell_small', 0):.0f}）")
            lines.append(f"          合计净额: {ca.get('total_net', 0):+.2f}")
        lines.append("")

        # ── 板块排名（按类型分组展示） ──
        if sr.get("by_type"):
            lines.append(f"【今日午间收盘板块排名（同花顺全部分类）】")
            for tp, group in sr["by_type"].items():
                label = group["label"]
                s_list = group["sectors"]
                lines.append(f"  [{label}]")
                for s in s_list[:4]:  # 每类最多4个
                    rank_str = f"第 {s['rank']}/{s['total']} 位"
                    my_pos = s.get("my_position")
                    my_price = s.get("my_price")
                    pos_str = f" | 该股排名: {my_pos+1}/{s['total_in_sector']}" if my_pos is not None else ""
                    price_str = f" | 股价: {my_price}" if my_price else ""
                    lines.append(f"          {s['name']}（{s['ts_code']}）: {s['avg_chg_pct']:+.2f}% | "
                                 f"{rank_str} | 涨{s['up_count']}/跌{s['down_count']}{pos_str}{price_str}")
                    top3 = s.get("top3", [])
                    bottom3 = s.get("bottom3", [])
                    neighbors = s.get("neighbors", [])
                    if top3:
                        top3_str = " | ".join(f"{x['name']}({x['ts_code']}){x['chg_pct']:+.2f}%" for x in top3)
                        lines.append(f"            【领涨前3】{top3_str}")
                    if bottom3:
                        bot3_str = " | ".join(f"{x['name']}({x['ts_code']}){x['chg_pct']:+.2f}%" for x in bottom3)
                        lines.append(f"            【领跌前3】{bot3_str}")
                    if neighbors and my_pos is not None:
                        items = " | ".join(f"{x['name']}({x['ts_code']}){x['chg_pct']:+.2f}%" for x in neighbors if x['ts_code'] != ts_code)
                        if items:
                            lines.append(f"            【该股前后各2只】{items}")
            lines.append("")

        # ── 上一个交易日板块全天涨跌幅基准 ──
        if bm:
            lines.append("【上一个交易日日终板块涨跌幅基准（同花顺板块）】")
            # 按类型分组展示
            cur_label = ""
            for b in bm:
                bl = b.get("type_label", "")
                if bl != cur_label:
                    lines.append(f"  [{bl}]")
                    cur_label = bl
                pct = b.get("pct_change")
                nm = b.get("name","")
                scode = b.get("ts_code","")
                if pct is not None:
                    lines.append(f"          {nm}（{scode}）: 收盘 {b.get('close','N/A')} | 涨跌幅 {pct:+.2f}%")
                else:
                    lines.append(f"          {nm}（{scode}）: 收盘 {b.get('close','N/A')}")
        lines.append("")

        # ── 技术面关键位置 ──
        if "error" not in ta and ta.get("ma5"):
            price = ta.get("price")
            lines.append(f"【技术面关键位置】当前价: {price}")
            for label, display in [("ma5", "MA5"), ("ma10", "MA10"), ("ma20", "MA20/布林中轨")]:
                val = ta.get(label)
                dev = ta.get("deviation", {}).get(label, {})
                if val and dev:
                    lines.append(f"          {display}: 约 {val:.2f} 元 | "
                                 f"当前价格位于其{dev['tag']} {abs(dev['pct']):.1f}%")
            bu = ta.get("boll_upper")
            bl = ta.get("boll_lower")
            if bu and bl:
                lines.append(f"          布林带上轨: {bu:.2f} | 布林带下轨: {bl:.2f}")
        elif "error" in ta:
            lines.append(f"❌ 技术面: {ta['error']}")
        lines.append("")

        result[name] = "\n".join(lines)

    return result


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args or not args:
        print("用法: python fetch_midday_data.py <名称1> [名称2 ...]")
        print("示例: python fetch_midday_data.py 宁德时代 比亚迪 菲利华")
        print("       python fetch_midday_data.py --format json 宁德时代")
        sys.exit(0)

    fmt = "text"
    stock_names = []
    for a in args:
        if a == "--format":
            continue  # 下一个参数是格式
        elif a in ("json", "text"):
            fmt = a
        else:
            stock_names.append(a)

    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1]

    if not stock_names:
        print("❌ 请指定股票名称")
        sys.exit(1)

    result = fetch_all(stock_names)

    if fmt == "json":
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = "\n---\n".join(result.values())

    print(output)


if __name__ == "__main__":
    main()
