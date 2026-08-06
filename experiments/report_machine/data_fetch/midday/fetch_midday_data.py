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
import time as _time
from datetime import datetime, time
from pathlib import Path

import pandas as pd
import tushare as ts
import levistock as lk  # 财联社市场情绪 + 开盘红情绪
from neo4j import GraphDatabase  # 知识图谱

# 数据库
ETL_DIR = Path(__file__).resolve().parent.parent.parent / "etl"
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))
# 日终脚本目录(机构调研/筹码函数与日终同源, fetch_all 内延迟导入避免循环依赖)
ENDDAY_DIR = Path(__file__).resolve().parent.parent / "endday"
if str(ENDDAY_DIR) not in sys.path:
    sys.path.insert(0, str(ENDDAY_DIR))
from db_manager import DatabaseManager
from config import DB_PATH

# 交易日历
sys.path.insert(0, str(Path(__file__).parent))
from trade_calendar import last_trading_day, get_calendar, prev_trading_day

PRO = ts.pro_api()
db = DatabaseManager(str(DB_PATH))


# ══════════════════════════════════════════════════════════════
# 通用工具
# ══════════════════════════════════════════════════════════════

_ERROR_LOG_DB = None  # 惰性初始化


def _safe_float(v, default=0.0) -> float:
    """安全转 float，None/非数值→default"""
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def log_error(
    module: str = "fetch_midday_data",
    function: str = "",
    level: str = "ERROR",
    stock_name: str = "",
    ts_code: str = "",
    api_name: str = "",
    error_msg: str = "",
    detail: str = "",
    data_snapshot: str = "",
    # v3.0 扩展参数
    service_name: str = "",
    error_code: str = "",
    engine_name: str = "",
    session_id: str = "",
    worker_id: str = "",
):
    """将错误记录写入数据库 error_log 表"""
    global _ERROR_LOG_DB
    try:
        if _ERROR_LOG_DB is None:
            _ERROR_LOG_DB = DatabaseManager(str(DB_PATH))
        import uuid
        batch_id_val = uuid.uuid4().hex[:12]
        from datetime import datetime
        _ERROR_LOG_DB.execute(
            """INSERT INTO error_log
               (batch_id, timestamp, module, function, level,
                stock_name, ts_code, api_name, error_type, error_msg,
                detail, data_snapshot,
               service_name, error_code, engine_name, session_id, worker_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?)""",
            (
                batch_id_val,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                module[:64], function[:64], level[:16],
                stock_name[:32] if stock_name else None,
                ts_code[:32] if ts_code else None,
                api_name[:64] if api_name else None,
                error_msg.split(":")[0][:64] if ":" in error_msg else error_msg[:64],
                str(error_msg)[:1024],
                str(detail)[:2048] if detail else "",
                str(data_snapshot)[:2048] if data_snapshot else "",
                # v3.0 扩展字段
                str(service_name)[:64] if service_name else None,
                str(error_code)[:64] if error_code else None,
                str(engine_name)[:32] if engine_name else None,
                str(session_id)[:64] if session_id else None,
                str(worker_id)[:32] if worker_id else None,
            ),
        )
    except Exception:
        pass  # 错误日志自身失败不打断主流程


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
    """融资融券（T-1 日 + 较 T-2 变化率）: 读库 stg_margin 优先(ETL 11:31 增量), 失败回退实时"""
    td = _tushare_trade_date()
    cal = get_calendar()
    t2 = cal.prev_trading_day(td, n=1)

    result = {}
    for ts_code in ts_codes:
        info = {"trade_date_t1": td, "trade_date_t2": t2}
        try:
            # 1) 读库(11:31 增量后 T-1 已入库; T-2 由回填/前日增量覆盖)
            db_rows = {}
            try:
                rows = db.execute(
                    "SELECT trade_date, rzye, rqye, rzmre FROM stg_margin "
                    "WHERE ts_code=? AND trade_date IN (?, ?)", (ts_code, td, t2))
                db_rows = {r[0]: r for r in rows}
            except Exception:
                db_rows = {}
            r1 = db_rows.get(td)
            r2 = db_rows.get(t2)
            if r1 is None or r2 is None:
                # 2) 库缺任一 → 实时回退(与原逻辑一致, 逐股两日)
                df1 = PRO.margin_detail(ts_code=ts_code, trade_date=td)
                df2 = PRO.margin_detail(ts_code=ts_code, trade_date=t2)
                r1 = r1 or (None if df1 is None or df1.empty else
                            tuple(df1.iloc[0][["trade_date", "rzye", "rqye", "rzmre"]]))
                r2 = r2 or (None if df2 is None or df2.empty else
                            tuple(df2.iloc[0][["trade_date", "rzye", "rqye", "rzmre"]]))

            if r1 is not None:
                info["rzye"] = float(r1[1])
                info["rqye"] = float(r1[2])
                info["rzmre"] = float(r1[3] or 0)
            else:
                info.update({"rzye": None, "rqye": None, "rzmre": None})

            if r2 is not None:
                rzye_t2 = float(r2[1])
                rqye_t2 = float(r2[2])
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
        # 先尝试直接从 config 读取
        import json
        token_path = Path(__file__).parent / "config" / "snowball_token.json"
        xq, u = "", ""
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

        # Token 文件不存在或为空 → 尝试自动刷新
        print("[snowball] 未找到有效 Token，尝试自动刷新...", file=sys.stderr)
        _refresh_script = Path(__file__).resolve().parent.parent.parent / "snowball_token" / "refresh_token.py"
        if _refresh_script.exists():
            import subprocess
            import sys as _sys
            result = subprocess.run(
                [_sys.executable, str(_refresh_script), "--force"],
                capture_output=True, text=True, timeout=120,
            )
            print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            # 刷新后再读一次
            if token_path.exists():
                with open(token_path) as f:
                    cfg = json.load(f)
                xq = cfg.get("xq_a_token", "")
                u = cfg.get("u", "")
                if xq and u:
                    import pysnowball as ball
                    ball.set_token(f"xq_a_token={xq}; u={u}")
                    _SNOWBALL_INITED = True
                    print("[snowball] Token 自动刷新成功", file=sys.stderr)
                    return

        print("[snowball] Token 自动刷新失败，请手动运行 refresh_token.py", file=sys.stderr)
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
            if data is None or data.get("error_code") != 0:
                err_msg = data.get("error_description", "无数据") if data else "无数据"
                result[xq_code] = {"error": err_msg}
                continue
            items = data.get("data", {}).get("items", [])
            if not items:
                result[xq_code] = {"error": "无数据"}
                continue

            # 取累计值序列
            cum_values = [_safe_float(it.get("amount")) for it in items if isinstance(it, dict)]
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
            log_error(function="fetch_capital_flow", level="WARNING",
                      ts_code=xq_code, api_name="pysnowball.capital_flow", error_msg=str(e))
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
            if data is None or data.get("error_code") != 0:
                err_msg = data.get("error_description", "无数据") if data else "无数据"
                result[xq_code] = {"error": err_msg}
                continue
            d = data.get("data", {})
            bl = _safe_float(d.get("buy_large"))
            sl = _safe_float(d.get("sell_large"))
            bm = _safe_float(d.get("buy_medium"))
            sm = _safe_float(d.get("sell_medium"))
            bs = _safe_float(d.get("buy_small"))
            ss = _safe_float(d.get("sell_small"))
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
            log_error(
                module="fetch_midday_data", function="fetch_capital_assort",
                level="WARNING", stock_name="", ts_code=xq_code,
                api_name="pysnowball.capital_assort", error_msg=str(e),
            )
            result[xq_code] = {"error": str(e)}

    return result


# ══════════════════════════════════════════════════════════════
# Part2: 板块排名（来自 mid_sector_ths）
# ══════════════════════════════════════════════════════════════

def fetch_sector_ranking(stock_names: list[str], class_brief: bool = True) -> dict[str, dict]:
    """从 mid_sector_ths 获取个股所属板块排名

    Args:
        class_brief: True 时只保留概念(N)和行业(I)分类，默认 True

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

        # class_brief 时只保留概念(N)和行业(I)
        if class_brief:
            by_type = {tp: v for tp, v in by_type.items() if tp in ("N", "I")}

        result[name] = {"by_type": by_type, "total_sectors": total_sectors, "class_brief": class_brief}
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
# 补充信息 — Tushare 昨日公告 + 昨日波动（字段名转中文）
# ══════════════════════════════════════════════════════════════

# ── 各接口输出参数字段名 → 中文名映射 ──

_FINA_AUDIT_CN = {
    "ts_code": "TS股票代码", "ann_date": "公告日期", "end_date": "报告期",
    "audit_result": "审计结果", "audit_fees": "审计总费用（元）",
    "audit_agency": "会计事务所", "audit_sign": "签字会计师",
}

_FORECAST_CN = {
    "ts_code": "TS股票代码", "ann_date": "公告日期", "end_date": "报告期",
    "type": "业绩预告类型", "p_change_min": "预告净利润变动幅度下限（%）",
    "p_change_max": "预告净利润变动幅度上限（%）",
    "net_profit_min": "预告净利润下限（万元）",
    "net_profit_max": "预告净利润上限（万元）",
    "last_parent_net": "上年同期归属母公司净利润",
    "first_ann_date": "首次公告日", "summary": "业绩预告摘要",
    "change_reason": "业绩变动原因",
}

_EXPRESS_CN = {
    "ts_code": "TS股票代码", "ann_date": "公告日期", "end_date": "报告期",
    "revenue": "营业收入（元）", "operate_profit": "营业利润（元）",
    "total_profit": "利润总额（元）", "n_income": "净利润（元）",
    "total_assets": "总资产（元）",
    "total_hldr_eqy_exc_min_int": "股东权益合计(不含少数股东权益)（元）",
    "diluted_eps": "每股收益(摊薄)（元）", "diluted_roe": "净资产收益率(摊薄)（%）",
    "yoy_net_profit": "去年同期修正后净利润", "bps": "每股净资产",
    "yoy_sales": "同比增长率:营业收入", "yoy_op": "同比增长率:营业利润",
    "yoy_tp": "同比增长率:利润总额", "yoy_dedu_np": "同比增长率:归属母公司股东的净利润",
    "yoy_eps": "同比增长率:基本每股收益", "yoy_roe": "同比增减:加权平均净资产收益率",
    "growth_assets": "比年初增长率:总资产", "yoy_equity": "比年初增长率:归属母公司的股东权益",
    "growth_bps": "比年初增长率:归属于母公司股东的每股净资产",
    "or_last_year": "去年同期营业收入", "op_last_year": "去年同期营业利润",
    "tp_last_year": "去年同期利润总额", "np_last_year": "去年同期净利润",
    "eps_last_year": "去年同期每股收益", "open_net_assets": "期初净资产",
    "open_bps": "期初每股净资产", "perf_summary": "业绩简要说明",
    "is_audit": "是否审计", "remark": "备注",
}

_DIVIDEND_CN = {
    "ts_code": "TS代码", "end_date": "分红年度", "ann_date": "预案公告日",
    "div_proc": "实施进度", "stk_div": "每股送转", "stk_bo_rate": "每股送股比例",
    "stk_co_rate": "每股转增比例", "cash_div": "每股分红（税后）",
    "cash_div_tax": "每股分红（税前）", "record_date": "股权登记日",
    "ex_date": "除权除息日", "pay_date": "派息日",
    "div_listdate": "红股上市日", "imp_ann_date": "实施公告日",
}

_FINA_INDICATOR_EXPORT = [
    "ts_code", "ann_date", "end_date", "eps", "dt_eps",
    "total_revenue_ps", "revenue_ps", "capital_rese_ps", "surplus_rese_ps",
    "undist_profit_ps", "extra_item", "profit_dedt", "gross_margin",
    "current_ratio", "quick_ratio", "cash_ratio",
    "inv_turn", "ar_turn", "ca_turn", "fa_turn", "assets_turn",
    "op_income", "ebit", "ebitda", "fcff", "fcfe",
    "current_exint", "noncurrent_exint", "interestdebt", "netdebt",
    "tangible_asset", "working_capital", "networking_capital", "invest_capital",
    "retained_earnings", "diluted2_eps", "bps", "ocfps", "retainedps", "cfps",
    "ebit_ps", "fcff_ps", "fcfe_ps",
    "netprofit_margin", "grossprofit_margin", "cogs_of_sales", "expense_of_sales",
    "profit_to_gr", "saleexp_to_gr", "adminexp_of_gr", "finaexp_of_gr",
    "roe", "roe_waa", "roe_dt", "roa", "npta", "roic", "roe_yearly",
    "debt_to_assets", "assets_to_eqt",
    "turn_days", "fixed_assets", "rd_exp", "update_flag",
]

_FINA_INDICATOR_CN = {
    "ts_code": "TS代码", "ann_date": "公告日期", "end_date": "报告期",
    "eps": "基本每股收益", "dt_eps": "稀释每股收益",
    "total_revenue_ps": "每股营业总收入", "revenue_ps": "每股营业收入",
    "capital_rese_ps": "每股资本公积", "surplus_rese_ps": "每股盈余公积",
    "undist_profit_ps": "每股未分配利润", "extra_item": "非经常性损益",
    "profit_dedt": "扣除非经常性损益后的净利润（扣非净利润）",
    "gross_margin": "毛利", "current_ratio": "流动比率", "quick_ratio": "速动比率",
    "cash_ratio": "保守速动比率", "inv_turn": "存货周转率", "ar_turn": "应收账款周转率",
    "ca_turn": "流动资产周转率", "fa_turn": "固定资产周转率", "assets_turn": "总资产周转率",
    "op_income": "经营活动净收益", "ebit": "息税前利润", "ebitda": "息税折旧摊销前利润",
    "fcff": "企业自由现金流量", "fcfe": "股权自由现金流量",
    "current_exint": "无息流动负债", "noncurrent_exint": "无息非流动负债",
    "interestdebt": "带息债务", "netdebt": "净债务", "tangible_asset": "有形资产",
    "working_capital": "营运资金", "networking_capital": "营运流动资本",
    "invest_capital": "全部投入资本", "retained_earnings": "留存收益",
    "diluted2_eps": "期末摊薄每股收益", "bps": "每股净资产",
    "ocfps": "每股经营活动产生的现金流量净额", "retainedps": "每股留存收益",
    "cfps": "每股现金流量净额", "ebit_ps": "每股息税前利润",
    "fcff_ps": "每股企业自由现金流量", "fcfe_ps": "每股股东自由现金流量",
    "netprofit_margin": "销售净利率", "grossprofit_margin": "销售毛利率",
    "cogs_of_sales": "销售成本率", "expense_of_sales": "销售期间费用率",
    "profit_to_gr": "净利润/营业总收入", "saleexp_to_gr": "销售费用/营业总收入",
    "adminexp_of_gr": "管理费用/营业总收入", "finaexp_of_gr": "财务费用/营业总收入",
    "roe": "净资产收益率", "roe_waa": "加权平均净资产收益率",
    "roe_dt": "净资产收益率(扣除非经常损益)", "roa": "总资产报酬率",
    "npta": "总资产净利润", "roic": "投入资本回报率", "roe_yearly": "年化净资产收益率",
    "debt_to_assets": "资产负债率", "assets_to_eqt": "权益乘数",
    "turn_days": "营业周期", "fixed_assets": "固定资产合计", "rd_exp": "研发投入合计",
    "update_flag": "更新标识",
}

_INCOME_CN = {
    "ts_code": "TS代码", "ann_date": "公告日期", "f_ann_date": "实际公告日期",
    "end_date": "报告期", "report_type": "报告类型", "comp_type": "公司类型",
    "end_type": "报告期类型", "basic_eps": "基本每股收益", "diluted_eps": "稀释每股收益",
    "total_revenue": "营业总收入", "revenue": "营业收入",
    "int_income": "利息收入", "prem_earned": "已赚保费",
    "comm_income": "手续费及佣金收入", "n_commis_income": "手续费及佣金净收入",
    "n_oth_income": "其他经营净收益", "n_oth_b_income": "加:其他业务净收益",
    "prem_income": "保险业务收入", "out_prem": "减:分出保费",
    "une_prem_reser": "提取未到期责任准备金", "reins_income": "其中:分保费收入",
    "n_sec_tb_income": "代理买卖证券业务净收入", "n_sec_uw_income": "证券承销业务净收入",
    "n_asset_mg_income": "受托客户资产管理业务净收入", "oth_b_income": "其他业务收入",
    "fv_value_chg_gain": "加:公允价值变动净收益", "invest_income": "加:投资净收益",
    "ass_invest_income": "其中:对联营企业和合营企业的投资收益",
    "forex_gain": "加:汇兑净收益", "total_cogs": "营业总成本",
    "oper_cost": "减:营业成本", "int_exp": "减:利息支出",
    "comm_exp": "减:手续费及佣金支出", "biz_tax_surchg": "减:营业税金及附加",
    "sell_exp": "减:销售费用", "admin_exp": "减:管理费用",
    "fin_exp": "减:财务费用", "assets_impair_loss": "减:资产减值损失",
    "prem_refund": "退保金", "compens_payout": "赔付总支出",
    "reser_insur_liab": "提取保险责任准备金", "div_payt": "保户红利支出",
    "reins_exp": "分保费用", "oper_exp": "营业支出",
    "compens_payout_refu": "减:摊回赔付支出",
    "insur_reser_refu": "减:摊回保险责任准备金",
    "reins_cost_refund": "减:摊回分保费用", "other_bus_cost": "其他业务成本",
    "operate_profit": "营业利润", "non_oper_income": "加:营业外收入",
    "non_oper_exp": "减:营业外支出",
    "nca_disploss": "其中:减:非流动资产处置净损失",
    "total_profit": "利润总额", "income_tax": "所得税费用",
    "n_income": "净利润(含少数股东损益)",
    "n_income_attr_p": "净利润(不含少数股东损益)",
    "minority_gain": "少数股东损益", "oth_compr_income": "其他综合收益",
    "t_compr_income": "综合收益总额",
    "compr_inc_attr_p": "归属于母公司(或股东)的综合收益总额",
    "compr_inc_attr_m_s": "归属于少数股东的综合收益总额",
    "ebit": "息税前利润", "ebitda": "息税折旧摊销前利润",
    "insurance_exp": "保险业务支出", "undist_profit": "年初未分配利润",
    "distable_profit": "可分配利润", "rd_exp": "研发费用",
    "fin_exp_int_exp": "财务费用:利息费用",
    "fin_exp_int_inc": "财务费用:利息收入",
    "transfer_surplus_rese": "盈余公积转入",
    "transfer_housing_imprest": "住房周转金转入", "transfer_oth": "其他转入",
    "adj_lossgain": "调整以前年度损益",
    "withdra_legal_surplus": "提取法定盈余公积",
    "withdra_legal_pubfund": "提取法定公益金",
    "withdra_biz_devfund": "提取企业发展基金", "withdra_rese_fund": "提取储备基金",
    "withdra_oth_ersu": "提取任意盈余公积金", "workers_welfare": "职工奖金福利",
    "distr_profit_shrhder": "可供股东分配的利润",
    "prfshare_payable_dvd": "应付优先股股利",
    "comshare_payable_dvd": "应付普通股股利",
    "capit_comstock_div": "转作股本的普通股股利",
    "net_after_nr_lp_correct": "扣除非经常性损益后的净利润（更正前）",
    "credit_impa_loss": "信用减值损失",
    "net_expo_hedging_benefits": "净敞口套期收益",
    "oth_impair_loss_assets": "其他资产减值损失",
    "total_opcost": "营业总成本（二）",
    "amodcost_fin_assets": "以摊余成本计量的金融资产终止确认收益",
    "oth_income": "其他收益", "asset_disp_income": "资产处置收益",
    "continued_net_profit": "持续经营净利润", "end_net_profit": "终止经营净利润",
    "update_flag": "更新标识",
}

_BALANCESHEET_CN = {
    "ts_code": "TS股票代码", "ann_date": "公告日期", "f_ann_date": "实际公告日期",
    "end_date": "报告期", "report_type": "报表类型", "comp_type": "公司类型",
    "end_type": "报告期类型", "total_share": "期末总股本",
    "cap_rese": "资本公积金", "undistr_porfit": "未分配利润",
    "surplus_rese": "盈余公积金", "special_rese": "专项储备",
    "money_cap": "货币资金", "trad_asset": "交易性金融资产",
    "notes_receiv": "应收票据", "accounts_receiv": "应收账款",
    "oth_receiv": "其他应收款", "prepayment": "预付款项",
    "div_receiv": "应收股利", "int_receiv": "应收利息",
    "inventories": "存货", "amor_exp": "待摊费用",
    "nca_within_1y": "一年内到期的非流动资产", "sett_rsrv": "结算备付金",
    "loanto_oth_bank_fi": "拆出资金", "premium_receiv": "应收保费",
    "reinsur_receiv": "应收分保账款", "reinsur_res_receiv": "应收分保合同准备金",
    "pur_resale_fa": "买入返售金融资产", "oth_cur_assets": "其他流动资产",
    "total_cur_assets": "流动资产合计",
    "fa_avail_for_sale": "可供出售金融资产", "htm_invest": "持有至到期投资",
    "lt_eqt_invest": "长期股权投资", "invest_real_estate": "投资性房地产",
    "time_deposits": "定期存款", "oth_assets": "其他资产",
    "lt_rec": "长期应收款", "fix_assets": "固定资产",
    "cip": "在建工程", "const_materials": "工程物资",
    "fixed_assets_disp": "固定资产清理", "produc_bio_assets": "生产性生物资产",
    "oil_and_gas_assets": "油气资产", "intan_assets": "无形资产",
    "r_and_d": "研发支出", "goodwill": "商誉",
    "lt_amor_exp": "长期待摊费用", "defer_tax_assets": "递延所得税资产",
    "decr_in_disbur": "发放贷款及垫款", "oth_nca": "其他非流动资产",
    "total_nca": "非流动资产合计", "cash_reser_cb": "现金及存放中央银行款项",
    "depos_in_oth_bfi": "存放同业和其它金融机构款项", "prec_metals": "贵金属",
    "deriv_assets": "衍生金融资产",
    "rr_reins_une_prem": "应收分保未到期责任准备金",
    "rr_reins_outstd_cla": "应收分保未决赔款准备金",
    "rr_reins_lins_liab": "应收分保寿险责任准备金",
    "rr_reins_lthins_liab": "应收分保长期健康险责任准备金",
    "refund_depos": "存出保证金", "ph_pledge_loans": "保户质押贷款",
    "refund_cap_depos": "存出资本保证金", "indep_acct_assets": "独立账户资产",
    "client_depos": "其中：客户资金存款", "client_prov": "其中：客户备付金",
    "transac_seat_fee": "其中:交易席位费", "invest_as_receiv": "应收款项类投资",
    "total_assets": "资产总计", "lt_borr": "长期借款", "st_borr": "短期借款",
    "cb_borr": "向中央银行借款", "depos_ib_deposits": "吸收存款及同业存放",
    "loan_oth_bank": "拆入资金", "trading_fl": "交易性金融负债",
    "notes_payable": "应付票据", "acct_payable": "应付账款",
    "adv_receipts": "预收款项", "sold_for_repur_fa": "卖出回购金融资产款",
    "comm_payable": "应付手续费及佣金", "payroll_payable": "应付职工薪酬",
    "taxes_payable": "应交税费", "int_payable": "应付利息",
    "div_payable": "应付股利", "oth_payable": "其他应付款",
    "acc_exp": "预提费用", "deferred_inc": "递延收益",
    "st_bonds_payable": "应付短期债券",
    "payable_to_reinsurer": "应付分保账款",
    "rsrv_insur_cont": "保险合同准备金", "acting_trading_sec": "代理买卖证券款",
    "acting_uw_sec": "代理承销证券款",
    "non_cur_liab_due_1y": "一年内到期的非流动负债",
    "oth_cur_liab": "其他流动负债", "total_cur_liab": "流动负债合计",
    "bond_payable": "应付债券", "lt_payable": "长期应付款",
    "specific_payables": "专项应付款", "estimated_liab": "预计负债",
    "defer_tax_liab": "递延所得税负债",
    "defer_inc_non_cur_liab": "递延收益-非流动负债",
    "oth_ncl": "其他非流动负债", "total_ncl": "非流动负债合计",
    "depos_oth_bfi": "同业和其它金融机构存放款项",
    "deriv_liab": "衍生金融负债", "depos": "吸收存款",
    "agency_bus_liab": "代理业务负债", "oth_liab": "其他负债",
    "prem_receiv_adva": "预收保费", "depos_received": "存入保证金",
    "ph_invest": "保户储金及投资款", "reser_une_prem": "未到期责任准备金",
    "reser_outstd_claims": "未决赔款准备金", "reser_lins_liab": "寿险责任准备金",
    "reser_lthins_liab": "长期健康险责任准备金",
    "indept_acc_liab": "独立账户负债", "pledge_borr": "其中:质押借款",
    "indem_payable": "应付赔付款", "policy_div_payable": "应付保单红利",
    "total_liab": "负债合计", "treasury_share": "减:库存股",
    "ordin_risk_reser": "一般风险准备", "forex_differ": "外币报表折算差额",
    "invest_loss_unconf": "未确认的投资损失", "minority_int": "少数股东权益",
    "total_hldr_eqy_exc_min_int": "股东权益合计(不含少数股东权益)",
    "total_hldr_eqy_inc_min_int": "股东权益合计(含少数股东权益)",
    "total_liab_hldr_eqy": "负债及股东权益总计",
    "lt_payroll_payable": "长期应付职工薪酬",
    "oth_comp_income": "其他综合收益", "oth_eqt_tools": "其他权益工具",
    "oth_eqt_tools_p_shr": "其他权益工具(优先股)",
    "lending_funds": "融出资金", "acc_receivable": "应收款项",
    "st_fin_payable": "应付短期融资款", "payables": "应付款项",
    "hfs_assets": "持有待售的资产", "hfs_sales": "持有待售的负债",
    "cost_fin_assets": "以摊余成本计量的金融资产",
    "fair_value_fin_assets": "以公允价值计量且其变动计入其他综合收益的金融资产",
    "cip_total": "在建工程(合计)(元)", "oth_pay_total": "其他应付款(合计)(元)",
    "long_pay_total": "长期应付款(合计)(元)", "debt_invest": "债权投资(元)",
    "oth_debt_invest": "其他债权投资(元)",
    "oth_eq_invest": "其他权益工具投资(元)",
    "oth_illiq_fin_assets": "其他非流动金融资产(元)",
    "oth_eq_ppbond": "其他权益工具:永续债(元)",
    "receiv_financing": "应收款项融资", "use_right_assets": "使用权资产",
    "lease_liab": "租赁负债", "contract_assets": "合同资产",
    "contract_liab": "合同负债", "accounts_receiv_bill": "应收票据及应收账款",
    "accounts_pay": "应付票据及应付账款",
    "oth_rcv_total": "其他应收款(合计)（元）",
    "fix_assets_total": "固定资产(合计)(元)", "update_flag": "更新标识",
}

_CASHFLOW_CN = {
    "ts_code": "TS股票代码", "ann_date": "公告日期", "f_ann_date": "实际公告日期",
    "end_date": "报告期", "comp_type": "公司类型", "report_type": "报表类型",
    "end_type": "报告期类型", "net_profit": "净利润", "finan_exp": "财务费用",
    "c_fr_sale_sg": "销售商品、提供劳务收到的现金",
    "recp_tax_rends": "收到的税费返还",
    "n_depos_incr_fi": "客户存款和同业存放款项净增加额",
    "n_incr_loans_cb": "向中央银行借款净增加额",
    "n_inc_borr_oth_fi": "向其他金融机构拆入资金净增加额",
    "prem_fr_orig_contr": "收到原保险合同保费取得的现金",
    "n_incr_insured_dep": "保户储金净增加额",
    "n_reinsur_prem": "收到再保业务现金净额",
    "n_incr_disp_tfa": "处置交易性金融资产净增加额",
    "ifc_cash_incr": "收取利息和手续费净增加额",
    "n_incr_disp_faas": "处置可供出售金融资产净增加额",
    "n_incr_loans_oth_bank": "拆入资金净增加额",
    "n_cap_incr_repur": "回购业务资金净增加额",
    "c_fr_oth_operate_a": "收到其他与经营活动有关的现金",
    "c_inf_fr_operate_a": "经营活动现金流入小计",
    "c_paid_goods_s": "购买商品、接受劳务支付的现金",
    "c_paid_to_for_empl": "支付给职工以及为职工支付的现金",
    "c_paid_for_taxes": "支付的各项税费",
    "n_incr_clt_loan_adv": "客户贷款及垫款净增加额",
    "n_incr_dep_cbob": "存放央行和同业款项净增加额",
    "c_pay_claims_orig_inco": "支付原保险合同赔付款项的现金",
    "pay_handling_chrg": "支付手续费的现金",
    "pay_comm_insur_plcy": "支付保单红利的现金",
    "oth_cash_pay_oper_act": "支付其他与经营活动有关的现金",
    "st_cash_out_act": "经营活动现金流出小计",
    "n_cashflow_act": "经营活动产生的现金流量净额",
    "oth_recp_ral_inv_act": "收到其他与投资活动有关的现金",
    "c_disp_withdrwl_invest": "收回投资收到的现金",
    "c_recp_return_invest": "取得投资收益收到的现金",
    "n_recp_disp_fiolta": "处置固定资产、无形资产和其他长期资产收回的现金净额",
    "n_recp_disp_sobu": "处置子公司及其他营业单位收到的现金净额",
    "stot_inflows_inv_act": "投资活动现金流入小计",
    "c_pay_acq_const_fiolta": "购建固定资产、无形资产和其他长期资产支付的现金",
    "c_paid_invest": "投资支付的现金",
    "n_disp_subs_oth_biz": "取得子公司及其他营业单位支付的现金净额",
    "oth_pay_ral_inv_act": "支付其他与投资活动有关的现金",
    "n_incr_pledge_loan": "质押贷款净增加额",
    "stot_out_inv_act": "投资活动现金流出小计",
    "n_cashflow_inv_act": "投资活动产生的现金流量净额",
    "c_recp_borrow": "取得借款收到的现金",
    "proc_issue_bonds": "发行债券收到的现金",
    "oth_cash_recp_ral_fnc_act": "收到其他与筹资活动有关的现金",
    "stot_cash_in_fnc_act": "筹资活动现金流入小计",
    "free_cashflow": "企业自由现金流量",
    "c_prepay_amt_borr": "偿还债务支付的现金",
    "c_pay_dist_dpcp_int_exp": "分配股利、利润或偿付利息支付的现金",
    "incl_dvd_profit_paid_sc_ms": "其中:子公司支付给少数股东的股利、利润",
    "oth_cashpay_ral_fnc_act": "支付其他与筹资活动有关的现金",
    "stot_cashout_fnc_act": "筹资活动现金流出小计",
    "n_cash_flows_fnc_act": "筹资活动产生的现金流量净额",
    "eff_fx_flu_cash": "汇率变动对现金的影响",
    "n_incr_cash_cash_equ": "现金及现金等价物净增加额",
    "c_cash_equ_beg_period": "期初现金及现金等价物余额",
    "c_cash_equ_end_period": "期末现金及现金等价物余额",
    "c_recp_cap_contrib": "吸收投资收到的现金",
    "incl_cash_rec_saims": "其中:子公司吸收少数股东投资收到的现金",
    "uncon_invest_loss": "未确认投资损失",
    "prov_depr_assets": "加:资产减值准备",
    "depr_fa_coga_dpba": "固定资产折旧、油气资产折耗、生产性生物资产折旧",
    "amort_intang_assets": "无形资产摊销",
    "lt_amort_deferred_exp": "长期待摊费用摊销",
    "decr_deferred_exp": "待摊费用减少", "incr_acc_exp": "预提费用增加",
    "loss_disp_fiolta": "处置固定、无形资产和其他长期资产的损失",
    "loss_scr_fa": "固定资产报废损失", "loss_fv_chg": "公允价值变动损失",
    "invest_loss": "投资损失",
    "decr_def_inc_tax_assets": "递延所得税资产减少",
    "incr_def_inc_tax_liab": "递延所得税负债增加",
    "decr_inventories": "存货的减少",
    "decr_oper_payable": "经营性应收项目的减少",
    "incr_oper_payable": "经营性应付项目的增加",
    "others": "其他",
    "im_net_cashflow_oper_act": "经营活动产生的现金流量净额(间接法)",
    "conv_debt_into_cap": "债务转为资本",
    "conv_copbonds_due_within_1y": "一年内到期的可转换公司债券",
    "fa_fnc_leases": "融资租入固定资产",
    "im_n_incr_cash_equ": "现金及现金等价物净增加额(间接法)",
    "net_dism_capital_add": "拆出资金净增加额",
    "net_cash_rece_sec": "代理买卖证券收到的现金净额(元)",
    "credit_impa_loss": "信用减值损失",
    "use_right_asset_dep": "使用权资产折旧",
    "oth_loss_asset": "其他资产减值损失",
    "end_bal_cash": "现金的期末余额",
    "beg_bal_cash": "减:现金的期初余额",
    "end_bal_cash_equ": "加:现金等价物的期末余额",
    "beg_bal_cash_equ": "减:现金等价物的期初余额",
    "update_flag": "更新标志",
}

_SHOCK_CN = {
    "ts_code": "股票代码", "trade_date": "公告日期", "name": "股票名称",
    "trade_market": "交易所", "reason": "异常说明", "period": "异常期间",
}

_HOLDERTRADE_CN = {
    "ts_code": "TS代码", "ann_date": "公告日期", "holder_name": "股东名称",
    "holder_type": "股东类型", "in_de": "类型",
    "change_vol": "变动数量", "change_ratio": "占流通比例（%）",
    "after_share": "变动后持股", "after_ratio": "变动后占流通比例（%）",
    "avg_price": "平均价格", "total_share": "持股总数",
    "begin_date": "增减持开始日期", "close_date": "增减持结束日期",
}


def _df_to_lines(df, mapping, indent=0) -> list[str]:
    """将 DataFrame 转为缩进的行列表（字段名→中文）"""
    if df is None or df.empty:
        return []
    lines = []
    prefix = " " * indent
    df_cn = df.rename(columns=mapping)
    for _, row in df_cn.iterrows():
        parts = []
        for col_cn in df_cn.columns:
            val = row[col_cn]
            if val is not None and not (isinstance(val, float) and val != val):  # 跳过 NaN
                parts.append(f"{col_cn}: {val}")
        if parts:
            lines.append(f"{prefix}  {' | '.join(parts[:8])}")
            if len(parts) > 8:
                lines.append(f"{prefix}    {' | '.join(parts[8:])}")
    return lines


def fetch_supplementary_info(
    stock_names: list[str],
    ts_codes: list[str],
    start_date: str | None,
    end_date: str | None,
) -> dict[str, dict]:
    """获取补充信息：上一个交易日的公告 + 波动

    Tushare 日终数据均为 T-1，所以批量查询和逐股票查询都只用 start_date。
    end_date 仅用于展示标题中的范围（"上一个交易日至今日"），不参与实际取数。

    Args:
        start_date: 起始日期 YYYYMMDD，上一个交易日（实际取数日）
        end_date: 截止日期 YYYYMMDD，今日（仅用于标题展示）

    Returns:
        {name: [lines]}  # lines 为含补充信息文本行的列表
    """
    result = {}
    if not start_date or not end_date:
        return result

    # ── 批量查询（循环范围内每一天，跳过今日——Tushare 无今日数据） ──
    from datetime import datetime as _supp_dt, timedelta as _tdelta

    def _list_dates(d1: str, d2: str) -> list[str]:
        """YYYYMMDD 日期列表 [d1, d2]"""
        dates = []
        cur = _supp_dt.strptime(d1, "%Y%m%d")
        end = _supp_dt.strptime(d2, "%Y%m%d")
        while cur <= end:
            dates.append(cur.strftime("%Y%m%d"))
            cur += _tdelta(days=1)
        return dates

    query_dates = [d for d in _list_dates(start_date, end_date) if d != end_date]

    forecast_all = {}
    shock_all = {}
    high_shock_all = {}
    holdertrade_all = {}

    for qd in query_dates:
        # 业绩预告 forecast
        try:
            df = PRO.forecast(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    forecast_all[row["ts_code"]] = row.to_dict()
        except Exception as e:
            print(f"[supp] forecast({qd}) 查询失败: {e}", file=sys.stderr)

        # 个股异常波动 stk_shock
        try:
            df = PRO.stk_shock(trade_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    shock_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception as e:
            print(f"[supp] stk_shock({qd}) 查询失败: {e}", file=sys.stderr)

        # 个股严重异常波动 stk_high_shock
        try:
            df = PRO.stk_high_shock(trade_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    high_shock_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception as e:
            print(f"[supp] stk_high_shock({qd}) 查询失败: {e}", file=sys.stderr)

        # 股东增减持 stk_holdertrade
        try:
            df = PRO.stk_holdertrade(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    holdertrade_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception as e:
            print(f"[supp] stk_holdertrade({qd}) 查询失败: {e}", file=sys.stderr)

    # ── 逐只股票查询（需 ts_code 的接口，按子栏目聚合多日数据） ──
    for name, ts_code in zip(stock_names, ts_codes):
        supp_lines = []
        if not start_date or not end_date:
            result[name] = {}
            continue

        def _q_one(title: str, api_fn, mapping, check_kw, **extra_kw):
            """对 query_dates 逐日查询并聚合成一行"""
            all_lines = []
            seen = set()
            date_arg_name = extra_kw.pop("_date_arg", "start_date")  # 默认用 start_date/end_date
            for qd in query_dates:
                try:
                    kwargs = dict(extra_kw)
                    if date_arg_name == "ann_date":
                        kwargs["ann_date"] = qd
                    else:
                        kwargs["start_date"] = qd
                        kwargs["end_date"] = qd
                    df = api_fn(ts_code=ts_code, **kwargs)
                    lines = _df_to_lines(df, mapping, indent=2)
                    for l in lines:
                        if l not in seen:
                            all_lines.append(l)
                            seen.add(l)
                except Exception:
                    pass
            check = [check_kw] if isinstance(check_kw, str) else (check_kw or [])
            clean = [l for l in all_lines if l.strip()]
            has_data = any(kw in l for l in clean for kw in check) if check else bool(clean)
            return title, all_lines, has_data

        # ---------- 昨日公告部分 ----------
        ann_items = []

        ann_items.append(_q_one("财务审计意见", PRO.fina_audit, _FINA_AUDIT_CN, "审计结果"))
        ann_items.append(_q_one("财务指标数据", PRO.fina_indicator, _FINA_INDICATOR_CN,
                                "基本每股收益", fields=_FINA_INDICATOR_EXPORT))
        ann_items.append(_q_one("分红送股", PRO.dividend, _DIVIDEND_CN, "实施进度", _date_arg="ann_date"))
        ann_items.append(_q_one("业绩快报", PRO.express, _EXPRESS_CN, "营业收入"))

        # 业绩预告（来自全量批量查，无需逐日查）
        fc = forecast_all.get(ts_code)
        if fc:
            fc_lines = _df_to_lines(pd.DataFrame([fc]), _FORECAST_CN, indent=2)
            ann_items.append(("业绩预告", fc_lines, True))
        else:
            ann_items.append(("业绩预告", [], False))

        ann_items.append(_q_one("现金流量表", PRO.cashflow, _CASHFLOW_CN, "净利润"))
        ann_items.append(_q_one("资产负债表", PRO.balancesheet, _BALANCESHEET_CN, ["资产总计", "期末总股本"]))
        ann_items.append(_q_one("利润表", PRO.income, _INCOME_CN, ["营业总收入", "基本每股收益"]))

        has_ann = False
        for title, lines, has_data in ann_items:
            if has_data:
                if not has_ann:
                    has_ann = True
                supp_lines.append(f"## 【{title}】")
                supp_lines.extend(lines)
                supp_lines.append("")

        # ---------- 昨日波动部分（日期范围 start_date ~ end_date） ----------
        has_vol = False
        vol_sections = []

        sl = shock_all.get(ts_code, [])
        if sl:
            vol_lines = []
            for s in sl:
                vol_lines.extend(_df_to_lines(pd.DataFrame([s]), _SHOCK_CN, indent=2))
            vol_sections.append(("个股异常波动", vol_lines))

        hsl = high_shock_all.get(ts_code, [])
        if hsl:
            vol_lines = []
            for hs in hsl:
                vol_lines.extend(_df_to_lines(pd.DataFrame([hs]), _SHOCK_CN, indent=2))
            vol_sections.append(("个股严重异常波动", vol_lines))

        htl = holdertrade_all.get(ts_code, [])
        if htl:
            vol_lines = []
            for ht in htl:
                vol_lines.extend(_df_to_lines(pd.DataFrame([ht]), _HOLDERTRADE_CN, indent=2))
            vol_sections.append(("股东增减持", vol_lines))

        for title, lines in vol_sections:
            if not has_vol:
                has_vol = True
                supp_lines.append(f"## 【{title}】")
            supp_lines.extend(lines)
            supp_lines.append("")

        result[name] = supp_lines

    return result


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# 财联社市场情绪（全市场统一数据，所有个股共用）
# ──────────────────────────────────────────────────────────────

_DEGREE_TAG = {15: "极低", 30: "低", 50: "一般", 70: "高"}


def fetch_market_emotion() -> str:
    """获取财联社市场情绪 + 开盘红情绪，格式化为范例文本

    两条数据只取一次，全市场共用。
    在 fetch_all 中，该结果会拼在每个个股输出最前面，同时通过 'all' 键单独返回。
    """
    lines = []

    try:
        emotion = lk.market_emotion_cls()
    except Exception as e:
        lines.append(f"❌ 财联社市场情绪获取失败: {e}")
        emotion = {}

    if emotion:
        # ── 市场热度 + 等级标签 ──
        try:
            degree = int(emotion.get("market_degree", 0))
        except (ValueError, TypeError):
            degree = 0
        tag = "极高"
        for threshold, label in sorted(_DEGREE_TAG.items()):
            if degree <= threshold:
                tag = label
                break
        lines.append(f"- 市场热度: {degree}（{tag}）")

        # ── 成交额 ──
        balance = emotion.get("shsz_balance", "N/A")
        bal_chg = emotion.get("shsz_balance_change_px", "")
        if bal_chg:
            # 确保符号是 +/-
            bal_chg = bal_chg.replace("--", "-").replace("+-", "-")
            if not bal_chg.startswith(("+", "-")):
                bal_chg = f"+{bal_chg}" if float(bal_chg.replace("亿", "").replace("万", "")) >= 0 else bal_chg
            lines.append(f"- 成交额: {balance}（{bal_chg}）")
        else:
            lines.append(f"- 成交额: {balance}")

        # ── 上涨占比 | 赚钱效应 ──
        up_ratio = emotion.get("up_ratio", "N/A")
        profit_ratio = emotion.get("profit_ratio", "N/A")
        lines.append(f"- 上涨占比: {up_ratio} | 赚钱效应: {profit_ratio}")

        # ── 涨停梯队 ──
        board = emotion.get("limit_up_board", {})
        board_parts = []
        for level in ("一板", "二板", "三板", "高度板"):
            info = board.get(level, {})
            count = info.get("count", "0")
            rate = info.get("continuous_rate", "")
            if rate and rate != "-":
                board_parts.append(f"{level}{count}只(晋级率{rate})")
            else:
                board_parts.append(f"{level}{count}只")
        if board_parts:
            lines.append(f"- 涨停梯队: {' / '.join(board_parts)}")

        # ── 涨跌分布 ──
        dis = emotion.get("up_down_dis", {})
        if dis:
            rise_n = dis.get("rise_num", "N/A")
            fall_n = dis.get("fall_num", "N/A")
            up_n = dis.get("up_num", "N/A")
            down_n = dis.get("down_num", "N/A")
            lines.append(f"- 涨跌分布: 上涨{rise_n} / 下跌{fall_n} / 涨停{up_n} / 跌停{down_n}")

    lines.append("")

    # ── 开盘红情绪 ──
    try:
        kph = lk.market_emotion_kph()
    except Exception as e:
        lines.append(f"❌ 开盘红情绪获取失败: {e}")
        kph = {}

    if kph:
        zt = kph.get("zt", "N/A")
        dt = kph.get("dt", "N/A")
        rise_k = kph.get("rise_num", "N/A")
        fall_k = kph.get("fall_num", "N/A")
        sign = kph.get("sign", "")
        lines.append(f"- 涨停{zt} / 跌停{dt} / 上涨{rise_k} / 下跌{fall_k}")
        lines.append(f"- 信号: {sign}")

        # ── 涨跌幅分布集中区间 ──
        rise_dist = kph.get("rise_dist", {})
        fall_dist = kph.get("fall_dist", {})

        def _conc_range(dist):
            items = sorted([(int(k), int(v)) for k, v in dist.items()])
            if not items:
                return "N/A"
            total = sum(v for _, v in items)
            if total == 0:
                return "N/A"
            # 按数量降序取前 N 个，累计 >= 60% 即止
            top_keys = set()
            cum = 0
            for k, v in sorted(items, key=lambda x: -x[1]):
                top_keys.add(k)
                cum += v
                if cum / total >= 0.6:
                    break
            ks = sorted(top_keys)
            return f"{ks[0]}%~{ks[-1]}%"

        rise_range = _conc_range(rise_dist)
        fall_range = _conc_range(fall_dist)
        lines.append(f"- 涨跌幅分布：涨幅集中在 {rise_range}，跌幅集中在 {fall_range}")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# 知识图谱：个股行业关键词（Neo4j）
# ──────────────────────────────────────────────────────────────

_NEO4J_CONFIG = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "kg_route_2026",
}
_KW_CACHE = {}  # {ts_code: [keyword, ...]}


def fetch_stock_industry_keywords(ts_code: str) -> list[str]:
    """从 Neo4j 知识图谱查询个股行业类 MG 关键词

    查询条件: categories 包含 '行业' 且 match_class == 'MG'

    Returns:
        [keyword, ...] 按关键词字母顺序排列
    """
    if ts_code in _KW_CACHE:
        return _KW_CACHE[ts_code]

    try:
        driver = GraphDatabase.driver(
            _NEO4J_CONFIG["uri"],
            auth=(_NEO4J_CONFIG["user"], _NEO4J_CONFIG["password"]),
        )
        with driver.session() as session:
            result = session.run(
                """MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword)
                   WHERE '行业' IN k.categories AND k.match_class = 'MG'
                   RETURN k.keyword AS keyword
                   ORDER BY k.keyword""",
                code=ts_code,
            )
            keywords = [r["keyword"] for r in result]
    except Exception:
        keywords = []
    finally:
        try:
            driver.close()
        except Exception:
            pass

    _KW_CACHE[ts_code] = keywords
    return keywords


def fetch_stock_industry_keywords_batch(ts_codes: list[str]) -> dict[str, list[str]]:
    """批量查询个股行业 MG 关键词

    一次 Neo4j 会话查完所有 ts_code，减少连接开销

    Returns:
        {ts_code: [keyword, ...]}
    """
    # 先检查缓存
    result = {}
    uncached = []
    for code in ts_codes:
        if code in _KW_CACHE:
            result[code] = _KW_CACHE[code]
        else:
            uncached.append(code)

    if not uncached:
        return result

    try:
        driver = GraphDatabase.driver(
            _NEO4J_CONFIG["uri"],
            auth=(_NEO4J_CONFIG["user"], _NEO4J_CONFIG["password"]),
        )
        with driver.session() as session:
            for code in uncached:
                rows = session.run(
                    """MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword)
                       WHERE '行业' IN k.categories AND k.match_class = 'MG'
                       RETURN k.keyword AS keyword
                       ORDER BY k.keyword""",
                    code=code,
                )
                keywords = [r["keyword"] for r in rows]
                _KW_CACHE[code] = keywords
                result[code] = keywords
    except Exception:
        # 查询失败时对未缓存股票返回空列表
        for code in uncached:
            if code not in result:
                _KW_CACHE[code] = []
                result[code] = []
    finally:
        try:
            driver.close()
        except Exception:
            pass

    return result


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


# ══════════════════════════════════════════════════════════════
# 数据完整性检查 & 重试
# ══════════════════════════════════════════════════════════════

_SECTION_NAMES = {
    1: "全市场情绪", 2: "行业关键词",
    3: "今日11:30收盘数据", 4: "上一个交易日日终",
    5: "融资融券", 6: "资金流向",
    7: "资金细分", 8: "板块排名",
    9: "技术面关键位置",
}


def _market_emotion_is_empty(text: str) -> bool:
    """全市场情绪是否整版为空（全部为空行或全部为错误信息）"""
    if not text or not text.strip():
        return True
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return True
    # 排除纯分隔符行
    content_lines = [l for l in lines if l != "---"]
    if not content_lines:
        return True
    error_lines = [l for l in content_lines if "获取失败" in l]
    return len(error_lines) == len(content_lines)


def _fetch_with_retry(
    fetch_fn, is_empty_fn,
    max_retries: int = 3,
    delay: float = 1.0,
    prepare_retry_fn=None,
):
    """通用重试包装器：数据为空时重试，最多 max_retries 次

    Args:
        fetch_fn: 取数函数
        is_empty_fn: 判断结果是否为空的函数，返回 True 表示空（需重试）
        prepare_retry_fn: 每次重试前的准备（如清除缓存）
    """
    for attempt in range(max_retries):
        if attempt > 0 and prepare_retry_fn:
            prepare_retry_fn()
        result = fetch_fn()
        if not is_empty_fn(result):
            return result
        if attempt < max_retries - 1:
            _time.sleep(delay * (attempt + 1))
    return result  # 重试耗尽，返回最后结果


def _check_stock_data_completeness(
    name: str,
    ts_code: str,
    *,
    market_emotion_text: str,
    industry_keywords: list,
    quote_data: dict,
    yesterday_data: dict,
    margin_data: dict,
    capital_flow: dict,
    capital_assort: dict,
    sector_ranking: dict,
    tech_analysis: dict,
) -> dict | None:
    """检查单只股票的9个数据部分完整性

    Returns:
        {"critical": [section_names], "non_critical": [section_names]} 或 None
    """
    critical_empty = []
    non_critical_empty = []

    # 1. 全市场情绪（全局数据，只查第一只股票时带完整结果）
    if market_emotion_text and _market_emotion_is_empty(market_emotion_text):
        critical_empty.append(_SECTION_NAMES[1])

    # 2. 行业关键词
    if not industry_keywords:
        critical_empty.append(_SECTION_NAMES[2])

    # 3. 今日11:30收盘数据
    q = quote_data
    if not q or "error" in q:
        critical_empty.append(_SECTION_NAMES[3])

    # 4. 上一个交易日日终
    yd = yesterday_data
    if "error" in yd or yd.get("turnover_rate") is None:
        critical_empty.append(_SECTION_NAMES[4])

    # 5. 融资融券
    mg = margin_data
    if "error" in mg or (mg.get("rzye") is None and mg.get("rqye") is None):
        non_critical_empty.append(_SECTION_NAMES[5])

    # 6. 资金流向
    cf = capital_flow
    if "error" in cf:
        non_critical_empty.append(_SECTION_NAMES[6])

    # 7. 资金细分
    ca = capital_assort
    if "error" in ca:
        non_critical_empty.append(_SECTION_NAMES[7])

    # 8. 板块排名
    sr = sector_ranking
    if not sr.get("by_type"):
        non_critical_empty.append(_SECTION_NAMES[8])

    # 9. 技术面关键位置
    ta = tech_analysis
    if not ta or "error" in ta or not ta.get("ma5"):
        non_critical_empty.append(_SECTION_NAMES[9])

    if not critical_empty and not non_critical_empty:
        return None

    result = {}
    if critical_empty:
        result["critical"] = critical_empty
    if non_critical_empty:
        result["non_critical"] = non_critical_empty
    return result


def fetch_all(stock_names: list[str]) -> dict:
    """统一取数入口

    Args:
        stock_names: ['宁德时代', '比亚迪']

    Returns:
        {name: formatted_string, "warning": {ts_code: {"critical": [], "non_critical": []}}}
        warning 为关键/非关键数据完整性检查结果，空 dict 表示全部正常
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

    # 8. 机构调研 + 筹码(与日终同源实现, 延迟导入避免循环依赖)
    try:
        from fetch_endday_data import fetch_survey as _fd_survey, _fmt_survey_section as _fd_fmt_survey
        survey_data = _fd_survey(ts_codes)
    except Exception:
        survey_data = {}
    try:
        from fetch_endday_data import fetch_cyq_db as _fd_cyq, _fmt_cyq_section as _fd_fmt_cyq
        cyq_data = _fd_cyq(ts_codes)
    except Exception:
        cyq_data = {}

    # 7b. 补充信息 — 日期范围（上一交易日 ~ 今日）
    from datetime import datetime as _dt
    _today_str = _dt.now().strftime("%Y%m%d")
    _prev_td = _tushare_trade_date()  # 上一个交易日
    supp_data = fetch_supplementary_info(names, ts_codes, _prev_td, _today_str)

    # 7c. 财联社市场情绪（全市场共用，只取一次）— 关键数据，空时重试最多3次
    market_emotion_text = _fetch_with_retry(
        fetch_market_emotion,
        _market_emotion_is_empty,
        max_retries=3, delay=1.0,
    )

    # 7d. 知识图谱行业关键词（批量查询 Neo4j）— 关键数据，空时重试最多3次
    _retry_kw_attempt = 0

    def _fetch_keywords():
        return fetch_stock_industry_keywords_batch(ts_codes)

    def _keywords_is_empty(kw_map: dict) -> bool:
        # 所有股票的关键词都为空才算整版为空
        if not kw_map:
            return True
        return all(len(v) == 0 for v in kw_map.values())

    def _clear_kw_cache():
        nonlocal _retry_kw_attempt
        _retry_kw_attempt += 1
        print(f"  行业关键词查询为空，第{_retry_kw_attempt}次重试（清除缓存）...", file=sys.stderr)
        # 清除缓存以便重新查询 Neo4j
        global _KW_CACHE
        _KW_CACHE.clear()

    industry_kw_map = _fetch_with_retry(
        _fetch_keywords,
        _keywords_is_empty,
        max_retries=3, delay=1.0,
        prepare_retry_fn=_clear_kw_cache,
    )

    # 8. 组装结果 dict
    result = {}
    warnings = {}
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

        lines = []

        # ── 全市场情绪（财联社，每个个股前均展示） ──
        if market_emotion_text:
            lines.append("## 【今日全市场情绪】")
            lines.append("")
            lines.append(market_emotion_text)
            lines.append("---")
            lines.append("")

        # ── 知识图谱行业关键词 ──
        industry_kws = industry_kw_map.get(ts_code, [])
        if industry_kws:
            kw_text = ", ".join(industry_kws)
            lines.append("## 【📌 股票涉及行业关键词】")
            lines.append(kw_text)
            lines.append("")

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
            lines.append("## 【今日11:30收盘数据】")
            lines.append(" | ".join(raw_items[:16]))
            lines.append("                     " + " | ".join(raw_items[16:]) if raw_items[16:] else "")
        lines.append("")

        # ── 上一个交易日日终 ──
        if "error" in yd:
            lines.append(f"❌（上一个交易日日终）换手率: {yd.get('error', '获取失败')}")
        else:
            yd_tro = yd.get("turnover_rate", "N/A")
            yd_tro_f = yd.get("turnover_rate_f", "N/A")
            lines.append("## 【上一个交易日日终】")
            lines.append(f"换手率: {yd_tro}% | "
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
            lines.append("## 【上一个交易日日终融资融券】")
            if rzye is None and rqye is None:
                lines.append(f"          无融资融券信息，股票可能非融资融券标的")
            else:
                rzye_s = f"{rzye/100000000:.2f}亿" if rzye else "N/A"
                rqye_s = f"{rqye/100000000:.2f}亿" if rqye else "N/A"
                rzye_c = mg.get("rzye_chg_pct")
                rqye_c = mg.get("rqye_chg_pct")
                if rzye_c is not None:
                    lines.append(f"          融资余额: {rzye_s}（较前日: {rzye_c:+.2f}%）")
                else:
                    lines.append(f"          融资余额: {rzye_s}")
                if rqye_c is not None:
                    lines.append(f"          融券余额: {rqye_s}（较前日: {rqye_c:+.2f}%）")
                else:
                    lines.append(f"          融券余额: {rqye_s}")
        lines.append("")

        # ── 机构调研(与日终同格式) ──
        sv = survey_data.get(ts_code, {})
        if sv:
            sv_sec = _fd_fmt_survey(ts_code, sv)
            lines.extend(sv_sec)
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

            lines.append("## 【今日午间收盘资金流向（逐分钟统计）】")
            lines.append(f"          净流向: {direction} {net_s}（统计分钟数: {ticks}）")
            lines.append(f"          资金流入 {inflow_mins} 分钟 / 流出 {outflow_mins} 分钟 | "
                         f"最大单分钟流入: {peak_in_s} / 最大单分钟流出: {peak_out_s}")
        lines.append("")

        # ── 上一个交易日日终资金细分 ──
        if "error" in ca:
            lines.append(f"❌（上一个交易日日终）资金细分: {ca.get('error', '获取失败')}")
        else:
            lines.append("## 【上一个交易日日终资金细分（元）】")
            lines.append(f"          大单净额: {ca.get('large_net', 0):+.2f}（买入: {ca.get('buy_large', 0):.0f} / 卖出: {ca.get('sell_large', 0):.0f}）")
            lines.append(f"          中单净额: {ca.get('medium_net', 0):+.2f}（买入: {ca.get('buy_medium', 0):.0f} / 卖出: {ca.get('sell_medium', 0):.0f}）")
            lines.append(f"          小单净额: {ca.get('small_net', 0):+.2f}（买入: {ca.get('buy_small', 0):.0f} / 卖出: {ca.get('sell_small', 0):.0f}）")
            lines.append(f"          合计净额: {ca.get('total_net', 0):+.2f}")
        lines.append("")

        # ── 板块排名（按类型分组展示） ──
        if sr.get("by_type"):
            lines.append("## 【今日午间收盘板块排名（同花顺概念和行业板块）】")
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
            lines.append("## 【上一个交易日日终板块涨跌幅基准（同花顺板块）】")
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
            lines.append("## 【技术面关键位置】")
            lines.append(f"当前价: {price}")
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

        # ── 筹码成本(午间用 T-1 数据, 与日终同格式) ──
        cq = cyq_data.get(ts_code, {})
        if cq:
            cq_sec = _fd_fmt_cyq(ts_code, cq)
            lines.extend(cq_sec)
            lines.append("")

        # ── 补充信息（仅在有数据时展示） ──
        supp = supp_data.get(name, [])
        if supp:
            lines.append(f"## 【补充信息——{_prev_td}至{_today_str}】")
            lines.append("")
            ann_header_shown = False
            vol_header_shown = False
            _VOL_SECTIONS = {"个股异常波动", "个股严重异常波动", "股东增减持"}
            for l in supp:
                stripped = l.strip()
                # 判断是否进入波动部分的section header
                in_vol = any(v in stripped for v in _VOL_SECTIONS)
                if in_vol:
                    if not vol_header_shown:
                        if ann_header_shown:
                            lines.append("")
                        lines.append("## 【昨日波动】")
                        vol_header_shown = True
                    lines.append(l)
                else:
                    if not ann_header_shown:
                        lines.append("## 【昨日公告】")
                        ann_header_shown = True
                    lines.append(l)
            lines.append("")

        result[name] = "\n".join(lines)

        # ── 数据完整性检查 ──
        stock_warn = _check_stock_data_completeness(
            name, ts_code,
            market_emotion_text=market_emotion_text,
            industry_keywords=industry_kws,
            quote_data=q,
            yesterday_data=yd,
            margin_data=mg,
            capital_flow=cf,
            capital_assort=ca,
            sector_ranking=sr,
            tech_analysis=ta,
        )
        if stock_warn:
            warnings[ts_code] = stock_warn

    result["warning"] = warnings
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
    result.pop("warning", {})

    if fmt == "json":
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = "\n---\n".join(result.values())

    print(output)


if __name__ == "__main__":
    main()
