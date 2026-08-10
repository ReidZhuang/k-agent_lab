"""
盘中数据取数脚本 — 日终(15:00 收盘后,19:30 运行)数据获取

设计(对应 office/demand/endday_report/requirements.md + 缺失数据补齐方案 20260805):
  - 今日收盘行情   → DB stg_tencent_snapshot / mid_stock_intraday(ETL 18:00 快照)
  - 融资融券多日   → DB stg_margin(ETL 11:31 T-1 增量,读库优先) + daily_basic(250日流通市值)
                     → 杠杆方向/拥挤度分位/融资盘成本区/背离/买卖结构/融券
  - 龙虎榜        → DB stg_top_list(ETL 19:10 当天入库,读库优先) + top_inst 席位(实时)
  - 个股资金流多日 → Tushare moneyflow(20日) + 雪球 capital_flow/capital_assort/capital_history
  - 机构持仓      → 同花顺 F10 org_holder(rate 8期 + tab + rate_price 8期 + detail 近3期基金 type=015003)
  - 北向持股      → DB stg_hk_hold(季度披露, 港交所 2024-08 停发日度)
  - 十大流通股东  → DB stg_top10_floatholder(季度披露)
  - 机构调研      → Tushare stk_surv(730天, 显式 fields, 名单+纪要2500截断)
  - 券商评级      → DB stg_report_rc(ETL 22:00 全市场入库,仅读库;接口停用中,库空提示等待)
  - 股东户数      → Tushare stk_holdernumber(最近4期)
  - 风险日历      → Tushare share_float(解禁) + pledge_stat(质押) + disclosure_date(披露计划)
  - 涨停/炸板     → Tushare kpl_list + levistock 涨停池/昨日涨停
  - 板块          → mid_sector_ths(最新快照,非收盘则回退 stg_ths_daily)
  - 技术面        → 新浪K线(收盘后日线完整,直接用最近20日) + 筹码加权成本锚点(DB stg_cyq_perf)
  - 筹码成本分布  → DB stg_cyq_perf / stg_cyq_chips(ETL 19:10 当天入库,探测回退 T-1)
  - 业绩趋势      → Tushare fina_indicator(最近4期)
  - 公告补充      → Tushare 业绩预告/快报/增减持/波动/分红/审计(T 日探测,回退 T-1)
  - 大宗交易      → DB stg_block_trade(ETL 22:00 入库,近90天;库空→实时回退)
  - 全市场情绪    → 财联社 levistock(收盘后)

输入: 个股名称列表 ['宁德时代', '比亚迪']
输出: {'宁德时代': '内容string', '比亚迪': '内容string', "warning": {...}}

约定: 任何数据块输出时附实际数据日期标签;T 日数据缺失时回退 T-1 并标注。
适用于交易日 19:30 左右调用(龙虎榜+筹码 19:10 已入库;大宗/研报用昨日入库数据标注)。
"""

import sys
import json
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import tushare as ts
import levistock as lk

# ── 数据库与交易日历 ──
ETL_DIR = Path(__file__).resolve().parent.parent.parent / "etl"
MIDDAY_DIR = Path(__file__).resolve().parent.parent / "midday"
for d in [str(MIDDAY_DIR), str(ETL_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)  # ETL 最后插入 → 在 sys.path[0],etl/config.py 优先于 midday/config.py

from db_manager import DatabaseManager
from config import DB_PATH
from trade_calendar import prev_trading_day, get_calendar

# ── 复用午间脚本的通用工具与映射表(不复制大字典) ──
from fetch_midday_data import (
    log_error, _safe_float, _df_to_lines,
    _FINA_AUDIT_CN, _FORECAST_CN, _EXPRESS_CN, _DIVIDEND_CN,
    _SHOCK_CN, _HOLDERTRADE_CN,
    _tushare_trade_date, fetch_market_emotion,
    _sina_kline, _calc_ma, _init_snowball,  # 雪球 token 初始化(含自动刷新)
)

PRO = ts.pro_api()
db = DatabaseManager(str(DB_PATH))

_SECTION_NAMES = {
    1: "全市场情绪", 2: "今日收盘行情", 3: "融资融券多日",
    4: "龙虎榜", 5: "个股资金流", 6: "机构持仓", 7: "机构调研",
    8: "股东户数", 9: "风险日历", 10: "涨停炸板", 11: "板块地位",
    12: "技术面成本地图", 13: "业绩趋势", 14: "公告补充", 15: "大宗交易",
    16: "北向持股", 17: "十大流通股东", 18: "券商评级", 19: "筹码成本",
}
_CRITICAL_SECTIONS = {1, 2, 3, 5, 12, 13}


# ══════════════════════════════════════════════════════════════
# 通用工具
# ══════════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _try_then_prev(fetch_fn, td: str, prev_td: str, *args, **kwargs):
    """T 日探测取数,空则回退 T-1。返回 (result, date_used)"""
    try:
        r = fetch_fn(td, *args, **kwargs)
        if r is not None and not (hasattr(r, "empty") and r.empty):
            return r, td
    except Exception as e:
        log_error(function=fetch_fn.__name__, level="WARNING",
                  api_name="endday_probe", error_msg=f"T日失败回退T-1: {str(e)[:200]}")
    try:
        r = fetch_fn(prev_td, *args, **kwargs)
        if r is not None:
            return r, prev_td
    except Exception:
        pass
    return None, prev_td


def _fetch_with_retry(fetch_fn, is_empty_fn, max_retries: int = 3, delay: float = 1.0):
    """通用重试包装器:数据为空时重试"""
    result = None
    for attempt in range(max_retries):
        result = fetch_fn()
        if not is_empty_fn(result):
            return result
        if attempt < max_retries - 1:
            _time.sleep(delay * (attempt + 1))
    return result


def _pct(cur, base) -> float | None:
    if cur is None or base in (None, 0):
        return None
    return round((cur - base) / base * 100, 2)


def _wan2yi(v) -> float:
    return round(_safe_float(v) / 10000, 2)  # 万元 → 亿元


def _fmt_amount_wan(v: float) -> str:
    """金额格式化:≥1亿 显示亿,否则万"""
    if abs(v) >= 10000:
        return f"{v/10000:.2f}亿"
    return f"{v:.0f}万"


# ══════════════════════════════════════════════════════════════
# 2. 今日收盘行情 — DB 快照(ETL 18:00 全量后为收盘数据)
# ══════════════════════════════════════════════════════════════

def fetch_quotes_endday(stock_names: list[str]) -> tuple[dict[str, dict], str]:
    """从 stg_tencent_snapshot 最新快照取收盘行情(回退 mid_stock_intraday)

    Returns:
        ({name: {...}}, snap_time_str)
    """
    snap_time, rows = None, []
    # 优先 stg_tencent_snapshot(ETL 全量必刷新)
    if db.table_exists("stg_tencent_snapshot"):
        t = db.execute("SELECT DISTINCT fetch_time FROM stg_tencent_snapshot ORDER BY fetch_time DESC LIMIT 1")
        if t:
            snap_time = t[0][0]
            placeholders = ",".join("?" * len(stock_names))
            rows = db.execute(
                f"SELECT ts_code, name, price, prev_close, open, high, low, chg_pct, "
                f"turnover_rate, amount_wan, amplitude, volume, volume_ratio, avg_price, "
                f"market_cap_total, market_cap_flow, pe_dynamic, pb, limit_up, limit_down, "
                f"outer_disc, inner_disc, fetch_time "
                f"FROM stg_tencent_snapshot WHERE fetch_time=? AND name IN ({placeholders})",
                (snap_time, *stock_names))

    # 回退 mid_stock_intraday
    if not rows and db.table_exists("mid_stock_intraday"):
        t = db.execute("SELECT DISTINCT fetch_time FROM mid_stock_intraday ORDER BY fetch_time DESC LIMIT 1")
        if t:
            snap_time = t[0][0]
            placeholders = ",".join("?" * len(stock_names))
            rows = db.execute(
                f"SELECT ts_code, name, price, prev_close, open, high, low, chg_pct, "
                f"turnover_rate, amount_wan, amplitude, volume, volume_ratio, avg_price, "
                f"market_cap_total, market_cap_flow, pe_dynamic, pb, limit_up, limit_down, "
                f"0, 0, fetch_time FROM mid_stock_intraday WHERE fetch_time=? AND name IN ({placeholders})",
                (snap_time, *stock_names))

    keys = ["ts_code", "name", "price", "prev_close", "open", "high", "low", "chg_pct",
            "turnover_rate", "amount_wan", "amplitude", "volume", "volume_ratio", "avg_price",
            "market_cap_total", "market_cap_flow", "pe_dynamic", "pb", "limit_up", "limit_down",
            "outer_disc", "inner_disc"]
    result = {}
    for r in rows:
        result[r[1]] = dict(zip(keys, list(r[:len(keys)]) + [None] * (len(keys) - len(r[:len(keys)]))))
    return result, (snap_time or "")


def _fmt_quote_section(name: str, ts_code: str, q: dict, snap_time: str) -> list[str]:
    if not q or "error" in q:
        return [f"❌ 收盘行情获取失败: {q.get('error', '无数据')}"]
    lines = [f"## 【今日收盘 {name} ({ts_code})情况】(快照时间: {snap_time})"]
    items = [
        f"收盘价: {q.get('price')}", f"涨跌幅: {q.get('chg_pct')}%",
        f"开盘: {q.get('open')}", f"最高: {q.get('high')}", f"最低: {q.get('low')}",
        f"昨收: {q.get('prev_close')}", f"成交额: {_wan2yi(q.get('amount_wan'))}亿元",
        f"换手率: {q.get('turnover_rate')}%", f"量比: {q.get('volume_ratio')}",
        f"振幅: {q.get('amplitude')}%", f"外盘/内盘: {q.get('outer_disc')}/{q.get('inner_disc')}",
        f"动态PE: {q.get('pe_dynamic')}", f"PB: {q.get('pb')}",
        f"总市值: {q.get('market_cap_total')}亿", f"流通市值: {q.get('market_cap_flow')}亿",
        f"涨停价: {q.get('limit_up')}", f"跌停价: {q.get('limit_down')}",
    ]
    lines.append(" | ".join(items))
    # 盘中形态描述
    try:
        price, high, low, open_, prev = (float(q.get(k, 0) or 0) for k in ("price", "high", "low", "open", "prev_close"))
        if high and low:
            pos = (price - low) / (high - low) if high > low else 0.5
            if pos > 0.7:
                shape = "收于全天高位附近(强势收盘)"
            elif pos < 0.3:
                shape = "收于全天低位附近(弱势收盘)"
            else:
                shape = "收于全天中段(多空均衡)"
            lines.append(f"形态: {shape}(日内位置 {pos:.0%}, 高 {high} / 低 {low})")
    except Exception:
        pass
    return lines


# ══════════════════════════════════════════════════════════════
# 3. 融资融券多日分析(杠杆章)— margin_detail 250日 + daily_basic 250日
# ══════════════════════════════════════════════════════════════

_MARGIN_COLS = ["trade_date", "ts_code", "name", "rzye", "rqye", "rzmre",
                "rqyl", "rzche", "rqchl", "rqmcl", "rzrqye"]


def _fetch_margin_series(ts_code: str, ndays: int = 250) -> pd.DataFrame | None:
    """融资融券序列: 读库 stg_margin 优先(ETL 11:31 全市场 T-1 增量 + 回填), 不足则实时回退

    + daily_basic(流通市值/收盘价) 实时合并(行情未入 stg_ 表)
    """
    end = _tushare_trade_date()  # margin/daily_basic 为 T-1 数据
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=int(ndays * 1.8))).strftime("%Y%m%d")
    # 1) 读库
    try:
        rows = db.execute(
            f"SELECT {','.join(_MARGIN_COLS)} FROM stg_margin "
            "WHERE ts_code=? AND trade_date<=? ORDER BY trade_date", (ts_code, end))
        if rows:
            dfm = pd.DataFrame(rows, columns=_MARGIN_COLS)
            if len(dfm) < 40:
                # 库数据不足(如增量缺失), 实时补齐
                dfr = PRO.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
                if dfr is not None and not dfr.empty:
                    dfm = dfr.sort_values("trade_date")
            dfm = dfm.sort_values("trade_date")
        else:
            dfm = PRO.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
            if dfm is None or dfm.empty:
                return None
            dfm = dfm.sort_values("trade_date")
    except Exception:
        # 2) 库异常 → 实时回退
        dfm = PRO.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
        if dfm is None or dfm.empty:
            return None
        dfm = dfm.sort_values("trade_date")
    dfd = PRO.daily_basic(ts_code=ts_code, start_date=start, end_date=end,
                          fields="trade_date,circ_mv,close")
    if dfd is not None and not dfd.empty:
        dfm = dfm.merge(dfd[["trade_date", "circ_mv", "close"]], on="trade_date", how="left")
    return dfm


def fetch_margin_analysis(ts_codes: list[str]) -> dict[str, dict]:
    """融资融券多日分析: 方向/拥挤度分位/成本区/背离/买卖结构/融券

    Returns:
        {ts_code: {trade_date, rzye_5d_pct, rzye_10d_pct, rzye_20d_pct,
                   net_buy_5d_wan, net_buy_20d_wan, crowd_ratio, crowd_pctile,
                   cost_low, cost_high, cost_mid, price, diverge, rqye_20d_pct, ...}}
    """
    result = {}
    for tc in ts_codes:
        info = {"trade_date": _tushare_trade_date()}
        try:
            df = _fetch_margin_series(tc, 250)
            if df is None or len(df) < 40:
                result[tc] = {**info, "error": "margin数据不足"}
                continue

            rzye = df["rzye"]
            info["rzye"] = round(float(rzye.iloc[-1]) / 1e8, 2)          # 亿
            info["rqye"] = round(float(df["rqye"].iloc[-1]) / 1e8, 4)
            for n in (5, 10, 20):
                if len(df) > n:
                    info[f"rzye_{n}d_pct"] = _pct(float(rzye.iloc[-1]), float(rzye.iloc[-n - 1]))
            # 净买入(买入-偿还)累计
            df["net_buy"] = df["rzmre"] - df["rzche"]
            for n in (5, 20):
                if len(df) > n:
                    info[f"net_buy_{n}d_wan"] = round(float(df["net_buy"].iloc[-n:].sum()) / 1e4, 2)  # 万
            # 拥挤度 = 融资余额 / 流通市值,近一年分位
            if "circ_mv" in df.columns:
                ratio = rzye / df["circ_mv"] / 1e4  # circ_mv 万元 → 与 rzye(元) 同单位
                cur_ratio = float(ratio.iloc[-1])
                pctile = (ratio <= cur_ratio).mean() * 100
                info["crowd_ratio"] = round(cur_ratio * 100, 2)   # %
                info["crowd_pctile"] = round(pctile, 1)
            # 融资盘成本区: 融资余额净增日的收盘价,按净增额加权
            if "close" in df.columns:
                delta = rzye.diff().fillna(0)
                pos = df[delta > 0]
                if len(pos) >= 10:
                    w = pos["close"] * delta[pos.index]
                    wavg = float(w.sum() / delta[pos.index].sum())
                    lo = float(pos["close"].quantile(0.25))
                    hi = float(pos["close"].quantile(0.75))
                    info["cost_mid"] = round(wavg, 2)
                    info["cost_low"], info["cost_high"] = round(lo, 2), round(hi, 2)
                    info["price"] = round(float(df["close"].iloc[-1]), 2)
            # 背离: 20日 余额方向 vs 价格方向
            if len(df) > 20 and "close" in df.columns:
                rzye_dir = float(rzye.iloc[-1]) - float(rzye.iloc[-21])
                close_dir = float(df["close"].iloc[-1]) - float(df["close"].iloc[-21])
                info["diverge"] = "余额升价跌/平" if (rzye_dir > 0 and close_dir <= 0) else (
                    "余额降价升" if (rzye_dir < 0 and close_dir > 0) else "同向")
            # 融券 20日方向
            if len(df) > 20:
                info["rqye_20d_pct"] = _pct(float(df["rqye"].iloc[-1]), float(df["rqye"].iloc[-21]))
        except Exception as e:
            log_error(function="fetch_margin_analysis", level="WARNING",
                      ts_code=tc, api_name="margin_detail", error_msg=str(e))
            result[tc] = {**info, "error": str(e)[:200]}
        result[tc] = info
    return result


def _fmt_margin_section(ts_code: str, name: str, m: dict) -> list[str]:
    if "error" in m:
        return [f"❌ 融资融券: {m['error']}"]
    lines = [f"## 【融资融券多日分析】(数据日期: {m['trade_date']}, T-1)"]
    rzye_s = f"{m.get('rzye')}亿" if m.get("rzye") else "N/A"
    rqye_s = f"{m.get('rqye')}亿" if m.get("rqye") else "N/A"
    rows = [
        f"融资余额: {rzye_s} | 5日 {m.get('rzye_5d_pct')}% | 10日 {m.get('rzye_10d_pct')}% | 20日 {m.get('rzye_20d_pct')}%",
        f"融资净买入(买入-偿还): 5日 {_fmt_amount_wan(m.get('net_buy_5d_wan', 0))} | 20日 {_fmt_amount_wan(m.get('net_buy_20d_wan', 0))}",
        f"杠杆拥挤度: 融资余额/流通市值 {m.get('crowd_ratio')}% | 近一年分位 {m.get('crowd_pctile')}%(>80%高拥挤)",
        f"融券余额: {rqye_s} | 20日变化 {m.get('rqye_20d_pct')}%",
    ]
    if m.get("cost_mid"):
        rows.append(f"融资盘成本区: {m.get('cost_low')}-{m.get('cost_high')}元(加权成本 {m.get('cost_mid')}元) | "
                    f"现价 {m.get('price')}元,位于成本区{'上方' if m.get('price', 0) > m.get('cost_high', 9e9) else '下方' if m.get('price', 9e9) < m.get('cost_low', 0) else '之内'}")
    if m.get("diverge"):
        rows.append(f"20日量价关系: {m['diverge']}")
    lines.extend(rows)
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 4. 龙虎榜 — top_list + top_inst(T日探测)
# ══════════════════════════════════════════════════════════════

def _lhb_from_rows(rows: list, date_used: str) -> dict:
    """stg_top_list 行 → 龙虎榜 info(同一股票同日多 reason 合并)"""
    r0 = rows[0]
    info = {
        "date_used": date_used, "listed": True,
        "reason": " | ".join(r[14] or "" for r in rows if r[14]),
        "close": r0[3], "pct_change": r0[4], "turnover_rate": r0[5],
        "net_amount_wan": round(float(r0[11] or 0) / 1e4, 2),
        "l_buy_wan": round(float(r0[9] or 0) / 1e4, 2),
        "l_sell_wan": round(float(r0[8] or 0) / 1e4, 2),
    }
    return info


def fetch_lhb(ts_codes: list[str]) -> dict[str, dict]:
    """龙虎榜: DB stg_top_list 读库优先(ETL 19:10 当天入库) + top_inst 席位(实时)

    库无数据(ETL 失败/未回填) → 实时回退原逻辑(T 日探测, 回退 T-1)
    """
    td, prev = _today(), _tushare_trade_date()
    result = {tc: {"date_used": prev} for tc in ts_codes}
    try:
        # 1) 读库: 最新 trade_date(≤今天)
        try:
            r = db.execute("SELECT MAX(trade_date) FROM stg_top_list WHERE trade_date<=?", (td,))
            db_latest = r[0][0] if r and r[0][0] else None
        except Exception:
            db_latest = None
        db_data = {}
        if db_latest:
            rows = db.execute(
                "SELECT ts_code, trade_date, name, close, pct_change, turnover_rate, amount,"
                " l_sell, l_buy, l_amount, net_amount, net_rate, amount_rate, float_values, reason"
                " FROM stg_top_list WHERE trade_date=?", (db_latest,))
            for row in rows:
                db_data.setdefault(row[0], []).append(row)

        # 2) top_inst 席位(实时, 全市场单次; 与库最新日对齐)
        ti, ti_date = None, None
        try:
            ti, ti_date = _try_then_prev(lambda d: PRO.top_inst(trade_date=d), td, prev)
            if ti is not None and not ti.empty:
                ti = ti[ti["side"].isin([0, 1])]  # 0=买入前5 1=卖出前5
        except Exception:
            pass

        def _attach_seats(info, tc):
            """给 info 挂买卖席位(机构专用标记)"""
            if ti is None or ti.empty:
                return
            sub = ti[ti["ts_code"] == tc]
            if sub.empty:
                return
            buys, sells = sub[sub["side"] == 0], sub[sub["side"] == 1]
            info["buy_seats"] = [
                {"name": x["exalter"], "net_wan": round(float(x.get("net_buy", 0)) / 1e4, 2),
                 "buy_wan": round(float(x.get("buy", 0)) / 1e4, 2),
                 "sell_wan": round(float(x.get("sell", 0)) / 1e4, 2)}
                for _, x in buys.head(5).iterrows()]
            info["sell_seats"] = [
                {"name": x["exalter"], "net_wan": round(float(x.get("net_buy", 0)) / 1e4, 2),
                 "buy_wan": round(float(x.get("buy", 0)) / 1e4, 2),
                 "sell_wan": round(float(x.get("sell", 0)) / 1e4, 2)}
                for _, x in sells.head(5).iterrows()]
            if info.get("buy_seats"):
                top = max(info["buy_seats"], key=lambda s: s["net_wan"])
                total = sum(s["net_wan"] for s in info["buy_seats"])
                info["buy1_ratio"] = round(top["net_wan"] / total * 100, 1) if total else None
                info["buy1_name"] = top["name"]
                info["inst_buy_count"] = sum(1 for s in info["buy_seats"] if "机构专用" in s["name"])

        if db_latest and db_data:
            # 读库路径: 标注库数据日期(当天 19:10 入库 = 当天实锤)
            for tc in ts_codes:
                if tc not in db_data:
                    result[tc] = {"date_used": db_latest, "listed": False}
                    continue
                info = _lhb_from_rows(db_data[tc], db_latest)
                _attach_seats(info, tc)
                result[tc] = info
            return result

        # 3) 库空 → 实时回退(原逻辑)
        tl, tl_date = _try_then_prev(lambda d: PRO.top_list(trade_date=d), td, prev)
        if tl is not None and not tl.empty:
            tl_map = tl.set_index("ts_code")
            for tc in ts_codes:
                if tc not in tl_map.index:
                    result[tc] = {"date_used": tl_date, "listed": False}
                    continue
                r = tl_map.loc[tc]
                info = {
                    "date_used": tl_date, "listed": True,
                    "reason": r.get("reason"), "close": r.get("close"),
                    "pct_change": r.get("pct_change"),
                    "net_amount_wan": round(float(r.get("net_amount", 0)) / 1e4, 2),
                    "l_buy_wan": round(float(r.get("l_buy", 0)) / 1e4, 2),
                    "l_sell_wan": round(float(r.get("l_sell", 0)) / 1e4, 2),
                    "turnover_rate": r.get("turnover_rate"),
                }
                _attach_seats(info, tc)
                result[tc] = info
    except Exception as e:
        log_error(function="fetch_lhb", level="WARNING", api_name="top_list", error_msg=str(e))
        for tc in ts_codes:
            result[tc] = {**result[tc], "error": str(e)[:200]}
    return result


def _fmt_lhb_section(name: str, l: dict) -> list[str]:
    if "error" in l:
        return [f"❌ 龙虎榜: {l['error']}"]
    if not l.get("listed"):
        return [f"## 【龙虎榜】(数据日期 {l['date_used']})\n该股未上榜。"]
    lines = [f"## 【龙虎榜】(数据日期 {l['date_used']}, 盘后实锤数据)"]
    lines.append(f"上榜原因: {l.get('reason')} | 涨跌幅 {l.get('pct_change')}% | 换手率 {l.get('turnover_rate')}%")
    lines.append(f"龙虎榜净买入: {_fmt_amount_wan(l.get('net_amount_wan', 0))} "
                 f"(买入 {_fmt_amount_wan(l.get('l_buy_wan', 0))} / 卖出 {_fmt_amount_wan(l.get('l_sell_wan', 0))})")
    seats = l.get("buy_seats") or []
    if seats:
        inst = sum(1 for s in seats if "机构专用" in s["name"])
        lines.append(f"买方前5席位({len(seats)}席, 机构专用{inst}席):")
        for s in seats:
            tag = " [机构]" if "机构专用" in s["name"] else ""
            lines.append(f"  - {s['name']}{tag} 净买 {_fmt_amount_wan(s['net_wan'])} (买 {_fmt_amount_wan(s['buy_wan'])}/卖 {_fmt_amount_wan(s['sell_wan'])})")
        if l.get("buy1_name"):
            lines.append(f"买一集中度: {l.get('buy1_name')} 占买方净额 {l.get('buy1_ratio')}%")
    sell_seats = l.get("sell_seats") or []
    if sell_seats:
        lines.append("卖方前5席位:")
        for s in sell_seats[:3]:
            tag = " [机构]" if "机构专用" in s["name"] else ""
            lines.append(f"  - {s['name']}{tag} 净卖 {_fmt_amount_wan(-s['net_wan'])}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 5. 个股资金流 — Tushare moneyflow(20日) + 雪球当日/历史
# ══════════════════════════════════════════════════════════════

def fetch_moneyflow_multi(ts_codes: list[str]) -> dict[str, dict]:
    """Tushare moneyflow 20日: 主力(超大+大)净额序列 + 资金强度 + 小单方向"""
    end = _today()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=45)).strftime("%Y%m%d")
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            df, date_used = _try_then_prev(
                lambda d: PRO.moneyflow(ts_code=tc, start_date=start, end_date=d),
                end, _tushare_trade_date())
            if df is None or df.empty or len(df) < 5:
                result[tc] = {"error": "moneyflow无数据"}
                continue
            df = df.sort_values("trade_date").tail(20)
            df["main"] = df["buy_elg_amount"] - df["sell_elg_amount"] + df["buy_lg_amount"] - df["sell_lg_amount"]
            df["small"] = df["buy_sm_amount"] - df["sell_sm_amount"]
            # moneyflow 买卖双边均计入,总成交额 ≈ 8 项之和 / 2
            df["total_amt"] = (df["buy_elg_amount"] + df["buy_lg_amount"] + df["buy_md_amount"] + df["buy_sm_amount"]
                               + df["sell_elg_amount"] + df["sell_lg_amount"] + df["sell_md_amount"] + df["sell_sm_amount"]) / 2
            # 日期标注修正: 范围查询在 T 日无数据时返回的 df 非空(数据到 T-1),
            # 以实际最后一行日期为准(18:30 时点 T 日 moneyflow 可能未更新)
            real_last = str(df["trade_date"].iloc[-1])
            if real_last != _today():
                date_used = real_last
            info["date_used"] = date_used
            info["main_daily_wan"] = [round(v, 2) for v in df["main"].tolist()]
            info["dates"] = df["trade_date"].tolist()
            info["main_3d_wan"] = round(float(df["main"].tail(3).sum()), 2)
            info["main_5d_wan"] = round(float(df["main"].tail(5).sum()), 2)
            info["main_10d_wan"] = round(float(df["main"].tail(10).sum()), 2)
            info["small_5d_wan"] = round(float(df["small"].tail(5).sum()), 2)
            info["amount_5d_wan"] = round(float(df["total_amt"].tail(5).sum()), 2)
            if info["amount_5d_wan"]:
                info["main_strength_5d"] = round(info["main_5d_wan"] / info["amount_5d_wan"] * 100, 2)
        except Exception as e:
            log_error(function="fetch_moneyflow_multi", level="WARNING",
                      ts_code=tc, api_name="moneyflow", error_msg=str(e))
            result[tc] = {"error": str(e)[:200]}
        result[tc] = info
    return result


def fetch_snowball_flow(xueqiu_codes: list[str]) -> dict[str, dict]:
    """雪球当日资金: capital_flow(逐分钟→时段拆分) + capital_assort(大中小单) + capital_history(20日)"""
    _init_snowball()  # 无返回值;token 不可用时下方接口调用会返回 error_code
    import pysnowball as ball
    from pysnowball.capital import capital_history, capital_assort

    result = {}
    for xq in xueqiu_codes:
        info = {}
        try:
            # 当日逐分钟 → 时段拆分(早盘/午盘/尾盘)
            d = ball.capital_flow(xq)
            if d and d.get("error_code") == 0:
                items = d.get("data", {}).get("items", [])
                if items:
                    buckets = {"早盘(<11:30)": 0.0, "午盘(13:00-14:30)": 0.0, "尾盘(14:30-15:00)": 0.0}
                    prev_cum, prev_ts = 0.0, None
                    for it in items:
                        amt, ts = _safe_float(it.get("amount")), it.get("timestamp")
                        if prev_ts is None:
                            prev_cum, prev_ts = amt, ts
                            continue
                        delta = amt - prev_cum
                        dt = datetime.fromtimestamp(ts / 1000)
                        hm = dt.strftime("%H:%M")
                        key = "早盘(<11:30)" if hm < "11:30" else ("午盘(13:00-14:30)" if hm < "14:30" else "尾盘(14:30-15:00)")
                        buckets[key] += delta
                        prev_cum, prev_ts = amt, ts
                    info["day_buckets"] = {k: round(v / 1e4, 2) for k, v in buckets.items()}  # 万元
                    info["day_net_wan"] = round(float(items[-1]["amount"]) / 1e4, 2)
            # 当日大中小单
            ca = capital_assort(xq)
            if ca and ca.get("error_code") == 0:
                dd = ca.get("data", {})
                info["assort"] = {
                    "large_net_wan": round((_safe_float(dd.get("buy_large")) - _safe_float(dd.get("sell_large"))) / 1e4, 2),
                    "medium_net_wan": round((_safe_float(dd.get("buy_medium")) - _safe_float(dd.get("sell_medium"))) / 1e4, 2),
                    "small_net_wan": round((_safe_float(dd.get("buy_small")) - _safe_float(dd.get("sell_small"))) / 1e4, 2),
                }
            # 20日日度历史(自算3/5/10累计)
            ch = capital_history(xq, count=20)
            if ch and ch.get("error_code") == 0:
                items = ch.get("data", {}).get("items", [])
                if items:
                    vals = [_safe_float(it.get("amount")) for it in items]
                    info["hist_net_wan"] = [round(v / 1e4, 2) for v in vals[-20:]]
                    info["hist_3d_wan"] = round(sum(vals[-3:]) / 1e4, 2)
                    info["hist_5d_wan"] = round(sum(vals[-5:]) / 1e4, 2)
                    info["hist_10d_wan"] = round(sum(vals[-10:]) / 1e4, 2)
        except Exception as e:
            log_error(function="fetch_snowball_flow", level="WARNING",
                      ts_code=xq, api_name="pysnowball", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[xq] = info
    return result


def _fmt_moneyflow_section(name: str, mf: dict, sf: dict) -> list[str]:
    if "error" in mf and "error" in sf:
        return [f"❌ 资金流: {mf.get('error', sf.get('error'))}"]
    lines = [f"## 【个股资金流】(Tushare moneyflow 数据日期: {mf.get('date_used', '?')})"]
    if "error" not in mf:
        lines.append(f"主力净额(超大单+大单, 万元): 3日 {_fmt_amount_wan(mf.get('main_3d_wan', 0))} | "
                     f"5日 {_fmt_amount_wan(mf.get('main_5d_wan', 0))} | 10日 {_fmt_amount_wan(mf.get('main_10d_wan', 0))}")
        if mf.get("main_strength_5d") is not None:
            lines.append(f"主力资金强度(5日主力净额/5日成交额): {mf['main_strength_5d']}%")
        small = mf.get("small_5d_wan")
        if small is not None:
            lines.append(f"散户小单 5日净额: {_fmt_amount_wan(small)}")
        daily = mf.get("main_daily_wan")
        if daily:
            ds = mf.get("dates")
            pairs = [f"{d[4:]}:{v:+.0f}" for d, v in zip(ds, daily)]
            lines.append("主力净额逐日(近10日): " + " | ".join(pairs[-10:]))
    if "error" not in sf:
        if sf.get("day_buckets"):
            b = sf["day_buckets"]
            lines.append(f"今日时段净额(雪球): 早盘 {_fmt_amount_wan(b.get('早盘(<11:30)', 0))} | "
                         f"午盘 {_fmt_amount_wan(b.get('午盘(13:00-14:30)', 0))} | "
                         f"尾盘 {_fmt_amount_wan(b.get('尾盘(14:30-15:00)', 0))}")
        if sf.get("assort"):
            a = sf["assort"]
            lines.append(f"今日大单净额: {_fmt_amount_wan(a.get('large_net_wan', 0))} | "
                         f"中单: {_fmt_amount_wan(a.get('medium_net_wan', 0))} | "
                         f"小单: {_fmt_amount_wan(a.get('small_net_wan', 0))}")
        if sf.get("hist_5d_wan") is not None:
            lines.append(f"雪球日度净额累计: 3日 {_fmt_amount_wan(sf.get('hist_3d_wan', 0))} | "
                         f"5日 {_fmt_amount_wan(sf.get('hist_5d_wan', 0))} | 10日 {_fmt_amount_wan(sf.get('hist_10d_wan', 0))}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 6. 机构持仓 — 同花顺 F10 org_holder(二次开发自 fetch_position.py)
# ══════════════════════════════════════════════════════════════

import requests as _req

_THS_BASE = "https://basic.10jqka.com.cn"
_THS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _ths_fetch_json(url: str) -> dict:
    r = _req.get(url, headers=_THS_HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("status_code") != 0:
        raise RuntimeError(f"同花顺接口异常: {data.get('status_code')}")
    return data


def _chg(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_passive_fund(org_name: str) -> bool:
    """被动基金判定: 名称含 指数/ETF/联接 等被动跟踪标识"""
    return any(k in org_name for k in ("指数", "ETF", "联接"))


def _fetch_ths_detail(sym: str, report: str, type_code: str = "015003") -> list:
    """同花顺 detail 单报告期全量分页(默认基金 type=015003)"""
    rows_all = []
    page = 1
    while True:
        d = _ths_fetch_json(
            f"{_THS_BASE}/basicapi/holder/stock/org_holder/detail?code={sym}&date={report}&page={page}&size=15&type={type_code}")["data"]
        rows = d.get("data", [])
        rows_all.extend(rows)
        if len(rows) < 15:
            break
        page += 1
    return rows_all


def fetch_ths_institution(symbols: list[str]) -> dict[str, dict]:
    """同花顺 F10 机构持仓(增强): rate(8期)/tab(类型)/rate_price(8期占比+股价)
    + detail 近3期基金明细(type=015003): 主动/被动拆分、增减持 Top3、主动净变动、增量建仓成本

    Args:
        symbols: 纯数字代码列表 ['300750']
    """
    result = {}
    for sym in symbols:
        info = {}
        try:
            rate = _ths_fetch_json(f"{_THS_BASE}/basicapi/holder/stock/org_holder/rate?code={sym}&limit=8&year=0")["data"]
            tab = _ths_fetch_json(f"{_THS_BASE}/basicapi/holder/stock/org_holder/tab?code={sym}&year=0&limit=5")["data"]
            rp = _ths_fetch_json(f"{_THS_BASE}/basicapi/holder/stock/org_holder/rate_price?code={sym}&cate=fund&limit=8&year=0")["data"]
            info["rate"] = rate          # [{date, org_num, total_rate, total_holder_change_rate}]
            info["tab"] = tab            # [{date, tab_list: [{name, rate, holder_num}]}]
            info["rate_price"] = rp      # [{date, rate, price}]
            latest = next((d for d in tab if d.get("is_updating")), tab[0] if tab else None)
            info["report_date"] = latest["date"] if latest else None

            # 近3期基金明细(仅披露过的报告期)
            rp_price_map = {str(d.get("date")): _safe_float(d.get("price")) for d in rp}
            detail_3q = []
            for t in (tab[:3] if tab else []):
                report = t.get("report")
                if not report:
                    continue
                try:
                    details = _fetch_ths_detail(sym, report, "015003")
                except Exception:
                    details = []
                if not details:
                    continue
                active = [d for d in details if not _is_passive_fund(d.get("org_name", ""))]
                passive = [d for d in details if _is_passive_fund(d.get("org_name", ""))]
                inc = [d for d in active if not d.get("is_new") and _chg(d.get("change")) > 0]
                dec = [d for d in active if not d.get("is_new") and _chg(d.get("change")) < 0]
                newf = [d for d in active if d.get("is_new")]
                # 增量建仓成本: Σ(增持股数×当期价)/Σ增持股数(仅主动基金)
                price_q = rp_price_map.get(str(report))
                inc_cost = None
                tot_inc = sum(_chg(d.get("change")) for d in inc)
                if tot_inc > 0 and price_q:
                    inc_cost = round(sum(_chg(d.get("change")) * price_q for d in inc) / tot_inc, 2)
                detail_3q.append({
                    "date": report,
                    "price": price_q,
                    "total": len(details),
                    "active_count": len(active),
                    "passive_count": len(passive),
                    "new_top": [{"name": d["org_name"], "mkt_wan": round(_chg(d.get("holder_market_value")) / 1e4, 2)}
                                for d in newf][:3],
                    "inc_top": [{"name": d["org_name"], "chg_wan": round(_chg(d.get("change")) / 1e4, 2)}
                                for d in sorted(inc, key=lambda x: -_chg(x.get("change")))[:3]],
                    "dec_top": [{"name": d["org_name"], "chg_wan": round(abs(_chg(d.get("change"))) / 1e4, 2)}
                                for d in sorted(dec, key=lambda x: _chg(x.get("change")))[:3]],
                    "active_net": round(sum(_chg(d.get("change")) for d in active) / 1e4, 2),  # 万股
                    "inc_cost": inc_cost,
                })
            info["detail_3q"] = detail_3q
            info["detail_count"] = sum(q["total"] for q in detail_3q)
            # 机构成本估算: 近4期 rate_price 按占比加权
            if rp:
                recent = rp[:4]
                wsum = sum(_safe_float(d.get("rate")) * _safe_float(d.get("price")) for d in recent)
                w = sum(_safe_float(d.get("rate")) for d in recent)
                info["inst_cost"] = round(wsum / w, 2) if w else None
        except Exception as e:
            log_error(function="fetch_ths_institution", level="WARNING",
                      ts_code=sym, api_name="ths_f10_org_holder", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[sym] = info
    return result


def _fmt_institution_section(name: str, ts_code: str, ins: dict) -> list[str]:
    if "error" in ins:
        return [f"❌ 机构持仓(同花顺F10): {ins['error']}"]
    if not ins.get("rate"):
        return ["## 【机构持仓】\n无数据"]
    lines = [f"## 【机构持仓】(同花顺F10, 最新报告期 {ins.get('report_date')})"]
    rp = ins.get("rate_price") or []
    if rp:
        rows = [f"| 报告期 | 基金占比% | 对应股价 | 环比 |"]
        rows.append("|---|---|---|---|")
        prev = None
        for d in rp[:8]:  # 全 8 期
            rate = _safe_float(d.get("rate"))
            chg = f"{rate - prev:+.2f}" if prev is not None else "-"
            rows.append(f"| {d['date']} | {rate} | {_safe_float(d.get('price'))} | {chg} |")
            prev = rate
        lines.extend(rows)
    if ins.get("inst_cost"):
        lines.append(f"机构持仓成本估算(近4期占比加权): {ins['inst_cost']}元")
    # 近3期基金明细(主动/被动拆分)
    for q in (ins.get("detail_3q") or []):
        lines.append(f"  [{q['date']}] 基金明细 {q['total']} 家(主动 {q['active_count']}/被动指数ETF {q['passive_count']})"
                     f" | 主动基金净变动 {q['active_net']}万股")
        if q.get("inc_cost"):
            lines.append(f"      主动增量建仓成本(增持加权): {q['inc_cost']}元 | 当期价 {q.get('price')}元")
        for label, key in (("新进", "new_top"), ("增持", "inc_top"), ("减持", "dec_top")):
            items = q.get(key) or []
            if items:
                lines.append(f"      {label}Top3: " + " | ".join(
                    f"{x['name']}({_fmt_amount_wan(x['mkt_wan'] if 'mkt_wan' in x else x['chg_wan'])})" for x in items[:3]))
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 7. 机构调研 — Tushare stk_surv(近180天)
# ══════════════════════════════════════════════════════════════

_SURV_FIELDS = "ts_code,name,surv_date,fund_visitors,rece_place,rece_mode,rece_org,org_type,comp_rece,content"
_SURV_CONTENT_CUT = 2500


def fetch_survey(ts_codes: list[str], days: int = 730) -> dict[str, dict]:
    """机构调研(定稿): stk_surv 730天, 显式 fields(content/rece_org 必须显式请求)

    - 近 365 天用于频次趋势+概要+名单+纪要; 前 365 天只用于同比对照
    - 单次限量 100 条, limit/offset 循环
    - rece_org 机构级行粒度; 业绩说明会类为聚合披露(org_type='--', rece_org 如 '与会投资者约1100人')
    """
    end = _today()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=days)).strftime("%Y%m%d")
    cutoff = (datetime.strptime(end, "%Y%m%d") - timedelta(days=365)).strftime("%Y%m%d")
    yoy_start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=365 + 90)).strftime("%Y%m%d")
    yoy_mid = (datetime.strptime(end, "%Y%m%d") - timedelta(days=365)).strftime("%Y%m%d")
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            all_rows = []
            offset = 0
            while True:
                df = PRO.stk_surv(ts_code=tc, start_date=start, end_date=end,
                                  fields=_SURV_FIELDS, limit=100, offset=offset)
                if df is None or df.empty:
                    break
                all_rows.extend(df.to_dict("records"))
                if len(df) < 100:
                    break
                offset += 100
            if not all_rows:
                info["count"] = 0
                result[tc] = info
                continue

            recent = [r for r in all_rows if r["surv_date"] >= cutoff]
            prev365 = [r for r in all_rows if r["surv_date"] < cutoff]
            info["count"] = len(recent)
            info["count_prev365"] = len(prev365)
            # 月度频次(近12自然月)
            months = {}
            for r in recent:
                m = r["surv_date"][:6]
                months[m] = months.get(m, 0) + 1
            info["by_month"] = {m: months[m] for m in sorted(months)}
            # 同比: 近3月 vs 去年同期
            cur3m = [r for r in recent if r["surv_date"] >= (datetime.strptime(end, "%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")]
            prev3m = [r for r in all_rows if yoy_start <= r["surv_date"] < yoy_mid]
            info["qoq_3m"] = len(cur3m)
            info["qoq_3m_prev_year"] = len(prev3m)
            # 机构类型分布(近365天)
            od = {}
            for r in recent:
                t = r.get("org_type") or "--"
                if t == "--":
                    continue
                od[t] = od.get(t, 0) + 1
            info["org_type_dist"] = od
            # 最近3次调研(按调研日去重): 概要 + 接待名单
            seen_dates = []
            for r in sorted(recent, key=lambda x: x["surv_date"], reverse=True):
                d = r["surv_date"]
                if d in seen_dates:
                    continue
                seen_dates.append(d)
                day_rows = [x for x in recent if x["surv_date"] == d]
                names = []
                for x in day_rows:
                    org = (x.get("rece_org") or "").strip()
                    if org and org not in names:
                        names.append(org)
                info.setdefault("recent", []).append({
                    "date": d,
                    "org_count": len(day_rows),
                    "mode": day_rows[0].get("rece_mode") or "",
                    "place": day_rows[0].get("rece_place") or "",
                    "comp_rece": day_rows[0].get("comp_rece") or "",
                    "names": names,
                })
                if len(seen_dates) >= 3:
                    break
            # 最新1次纪要: content 前 2500 字符
            latest_rows = [r for r in recent if r["surv_date"] == seen_dates[0]]
            content = (latest_rows[0].get("content") or "").strip()
            if content:
                info["minutes"] = content[:_SURV_CONTENT_CUT]
                info["minutes_truncated"] = len(content) > _SURV_CONTENT_CUT
        except Exception as e:
            log_error(function="fetch_survey", level="WARNING", ts_code=tc,
                      api_name="stk_surv", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_survey_section(ts_code: str, sv: dict) -> list[str]:
    if "error" in sv:
        return [f"❌ 机构调研: {sv['error']}"]
    if not sv.get("count"):
        return ["## 【机构调研】\n近365天无调研记录。"]
    lines = [f"## 【机构调研】(近365天, Tushare stk_surv)"]
    by_month = sv.get("by_month", {})
    if by_month:
        lines.append("月度频次: " + " | ".join(f"{m[:4]}-{m[4:]}: {c}条" for m, c in by_month.items()))
    if sv.get("qoq_3m") is not None:
        lines.append(f"近3月调研 {sv['qoq_3m']} 次 | 去年同期 {sv['qoq_3m_prev_year']} 次"
                     f"({'同比骤增' if sv['qoq_3m'] > sv['qoq_3m_prev_year'] * 2 else '同比减少' if sv['qoq_3m'] < sv['qoq_3m_prev_year'] else '同比持平'})")
    od = sv.get("org_type_dist", {})
    if od:
        lines.append("机构类型: " + " | ".join(f"{k}:{v}" for k, v in od.items()))
    for r in (sv.get("recent") or [])[-3:]:
        lines.append(f"  [{r['date']}] {r.get('mode')} 接待机构 {r.get('org_count')}家 | {r.get('place')}"
                     f"{(' | 接待人: ' + r['comp_rece']) if r.get('comp_rece') else ''}")
    # 最近3次接待名单(org_type 分组在数据层已完成按机构名去重)
    for r in (sv.get("recent") or [])[-3:]:
        names = r.get("names") or []
        if not names:
            continue
        if any(("与会" in n or "投资者" in n or "社会公众" in n) for n in names):
            lines.append(f"    [{r['date']}] 名单: 聚合披露无逐机构名单({len(names)}条)")
        else:
            lines.append(f"    [{r['date']}] 名单: " + " | ".join(names[:15]))
    # 最新1次纪要(2500字符截断)
    if sv.get("minutes"):
        lines.append(f"最新调研纪要({sv['recent'][0]['date']}, 前2500字符):")
        lines.append(sv["minutes"].replace("\n", " "))
        if sv.get("minutes_truncated"):
            lines.append("…(纪要后续省略)")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 8. 股东户数 — stk_holdernumber 最近4期
# ══════════════════════════════════════════════════════════════

def fetch_holdernumber(ts_codes: list[str]) -> dict[str, dict]:
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            df = PRO.stk_holdernumber(ts_code=tc)
            if df is not None and not df.empty:
                # 过滤缺失记录: end_date 为空 或 holder_num 为 NaN 的期不得进入序列
                df = df[df["end_date"].notna() & df["holder_num"].notna()]
                df = df.sort_values("end_date").drop_duplicates("end_date", keep="last").tail(4)
                info["periods"] = [{"end_date": r["end_date"], "holder_num": r["holder_num"]}
                                   for _, r in df.iterrows()]
                if len(df) >= 2:
                    cur, prev = float(df["holder_num"].iloc[-1]), float(df["holder_num"].iloc[-2])
                    info["chg_pct"] = round((cur - prev) / prev * 100, 2)
                if len(df) >= 1:
                    last_end = str(df["end_date"].iloc[-1])
                    days = (datetime.strptime(_today(), "%Y%m%d")
                            - datetime.strptime(last_end, "%Y%m%d")).days
                    quarter_end = last_end[4:6] + last_end[6:8] in ("0331", "0630", "0930", "1231")
                    info["staleness_days"] = max(days, 0)
                    info["disclosure_type"] = "季度披露" if quarter_end else "月度披露"
        except Exception as e:
            log_error(function="fetch_holdernumber", level="WARNING", ts_code=tc,
                      api_name="stk_holdernumber", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_holdernumber_section(hn: dict) -> list[str]:
    if "error" in hn:
        return [f"❌ 股东户数: {hn['error']}"]
    if not hn.get("periods"):
        return ["## 【股东户数】\n暂无数据。"]
    lines = [f"## 【股东户数】"]
    for p in hn["periods"]:
        lines.append(f"  {p['end_date']}: {p['holder_num']:,.0f} 户")
    if hn.get("chg_pct") is not None:
        trend = "筹码集中(户数减少)" if hn["chg_pct"] < 0 else "筹码分散(户数增加)"
        lines.append(f"最新期变化: {hn['chg_pct']:+.2f}% → {trend}")
    if hn.get("staleness_days") is not None:
        d = hn["staleness_days"]
        if d <= 30:
            flag = "数据较新,可作为近期筹码信号"
        elif d <= 90:
            flag = "数据一般,作参考并与期内股价走势结合判断"
        else:
            flag = "数据滞后,仅作趋势背景,不作近期判断依据"
        lines.append(f"⚠️ 数据时效: 最新期 {hn['periods'][-1]['end_date']},"
                     f"距今 {d} 天({hn.get('disclosure_type', '')}),{flag}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 9. 风险日历 — 解禁/质押/披露计划
# ══════════════════════════════════════════════════════════════

def fetch_risk_calendar(ts_codes: list[str], horizon_days: int = 90) -> dict[str, dict]:
    today = _today()
    end = (datetime.now() + timedelta(days=horizon_days)).strftime("%Y%m%d")
    result = {}
    for tc in ts_codes:
        info = {}
        # 解禁
        try:
            df = PRO.share_float(ts_code=tc, start_date=today, end_date=end)
            if df is not None and not df.empty:
                info["unlock"] = {
                    "total_share": round(float(df["float_share"].sum()), 0),
                    "max_ratio": round(float(df["float_ratio"].max()), 2),
                    "dates": sorted(df["float_date"].unique().tolist()),
                    "top": [{"date": r["float_date"], "share": r["float_share"], "ratio": r["float_ratio"], "holder": r["holder_name"]}
                            for _, r in df.sort_values("float_share", ascending=False).head(3).iterrows()],
                }
        except Exception as e:
            log_error(function="fetch_risk_calendar", level="WARNING", ts_code=tc,
                      api_name="share_float", error_msg=str(e))
            info["unlock_error"] = str(e)[:150]
        # 质押
        try:
            df2 = PRO.pledge_stat(ts_code=tc)
            if df2 is not None and not df2.empty:
                last = df2.sort_values("end_date").iloc[-1]
                info["pledge"] = {"end_date": last["end_date"], "ratio": round(float(last["pledge_ratio"]), 2)}
        except Exception as e:
            log_error(function="fetch_risk_calendar", level="WARNING", ts_code=tc,
                      api_name="pledge_stat", error_msg=str(e))
            info["pledge_error"] = str(e)[:150]
        # 披露计划
        try:
            df3 = PRO.disclosure_date(ts_code=tc)
            if df3 is not None and not df3.empty:
                future = df3[(df3["pre_date"] >= today) & (df3["pre_date"] <= end)]
                if not future.empty:
                    info["disclosure"] = [
                        {"end_date": r["end_date"], "pre_date": r["pre_date"]}
                        for _, r in future.sort_values("pre_date").head(3).iterrows()]
        except Exception as e:
            log_error(function="fetch_risk_calendar", level="WARNING", ts_code=tc,
                      api_name="disclosure_date", error_msg=str(e))
            info["disclosure_error"] = str(e)[:150]
        result[tc] = info
    return result


def _fmt_risk_section(rc: dict) -> list[str]:
    lines = ["## 【风险日历】"]
    u = rc.get("unlock")
    if u:
        lines.append(f"解禁(未来90天): 共 {u['total_share']:,.0f} 股, 最大单笔占比 {u['max_ratio']}% | 日期: {', '.join(u['dates'])}")
        for t in u["top"][:3]:
            lines.append(f"  - {t['date']} {t['holder']} 解禁 {t['share']:,.0f}股({t['ratio']}%)")
    else:
        lines.append("解禁: 未来90天无解禁")
    p = rc.get("pledge")
    if p:
        flag = "⚠️ 高质押" if p["ratio"] > 50 else ("中质押" if p["ratio"] > 30 else "低质押")
        lines.append(f"质押比例: {p['ratio']}%({flag}, 数据日期 {p['end_date']})")
    d = rc.get("disclosure")
    if d:
        lines.append("财报披露计划: " + " | ".join(f"{x['end_date']}报告期→{x['pre_date']}预约" for x in d))
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 10. 涨停/炸板 — kpl_list + levistock 涨停池/昨日涨停
# ══════════════════════════════════════════════════════════════

def fetch_limit_board(stocks: dict[str, dict]) -> dict[str, dict]:
    """stocks: {name: {ts_code, symbol}} → {name: {...}}"""
    td, prev = _today(), _tushare_trade_date()
    result = {n: {} for n in stocks}
    try:
        kpl, kpl_date = _try_then_prev(lambda d: PRO.kpl_list(trade_date=d), td, prev)
        if kpl is not None and not kpl.empty:
            kpl_map = kpl.set_index("ts_code")
            for name, info in stocks.items():
                tc = info["ts_code"]
                if tc in kpl_map.index:
                    r = kpl_map.loc[tc]
                    if isinstance(r, pd.DataFrame):
                        r = r.iloc[0]
                    result[name] = {
                        "date_used": kpl_date, "in_list": True,
                        "lu_time": r.get("lu_time"), "open_time": r.get("open_time"),
                        "status": r.get("status"), "lu_desc": r.get("lu_desc"),
                        "limit_order_wan": round(float(r.get("limit_order", 0)) / 1e4, 2) if r.get("limit_order") else None,
                        "theme": r.get("theme"),
                        "tag": r.get("tag"),
                    }
                else:
                    result[name] = {"date_used": kpl_date, "in_list": False}
    except Exception as e:
        log_error(function="fetch_limit_board", level="WARNING", api_name="kpl_list", error_msg=str(e))
        for n in stocks:
            result[n]["kpl_error"] = str(e)[:150]
    # 昨日涨停今日表现(levistock)
    try:
        yz = lk.stock_yesterday_zt_em()
        if yz:
            for name, info in stocks.items():
                sym = info.get("symbol")
                hit = next((x for x in yz if str(x.get("stock_code")) == sym), None)
                if hit:
                    result[name]["yesterday_zt"] = {
                        "code": hit.get("stock_code"),
                        "status": hit.get("status"),
                        "chg_pct": hit.get("chg"),
                        "price": hit.get("price"),
                    }
    except Exception as e:
        log_error(function="fetch_limit_board", level="WARNING", api_name="stock_yesterday_zt_em", error_msg=str(e))
    return result


def _fmt_limit_board_section(name: str, lb: dict) -> list[str]:
    if lb.get("kpl_error"):
        return [f"❌ 涨停数据: {lb['kpl_error']}"]
    lines = [f"## 【涨停/炸板】(kpl_list 数据日期: {lb.get('date_used', '?')})"]
    if lb.get("in_list"):
        r = lb
        lines.append(f"涨停状态: {r.get('status', '?')}({r.get('tag', '')}) | 首封 {r.get('lu_time')} | 开板 {r.get('open_time') or '未开板'} | "
                     f"封单 {_fmt_amount_wan(r.get('limit_order_wan', 0))}")
        if r.get("lu_desc"):
            lines.append(f"涨停原因: {r['lu_desc']}")
        if r.get("theme"):
            lines.append(f"所属主题: {r['theme']}")
    else:
        lines.append("今日未上涨停/炸板榜。")
    yz = lb.get("yesterday_zt")
    if yz:
        lines.append(f"昨日涨停今日表现: 涨跌幅 {yz.get('chg_pct')}% | 状态 {yz.get('status', '?')}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 10b. 大宗交易 — Tushare block_trade(席位实名, 实锤级证据)
# ══════════════════════════════════════════════════════════════

def fetch_blocktrade(ts_codes: list[str], lookback_days: int = 90) -> dict[str, dict]:
    """大宗交易: DB stg_block_trade 读库优先(ETL 22:00 全市场入库, 近90天, 最多10条)

    库空(ETL 未跑) → 实时回退(全市场近 lookback_days 天单次拉取, 按股过滤)。
    折溢价率需与收盘价对比, 在此用 daily_basic(T-1) 收盘价近似计算。
    注意: 当天大宗 22:00 才入库, 19:30 报告用 T-1 数据(标题标注 date_used)。

    Returns:
        {ts_code: {date_used, count, items: [{date, price, amount_wan, premium_pct,
                                              buyer, seller, is_inst_buy, is_inst_sell}],
                   total_wan} } 或 {ts_code: {date_used, count: 0}}
    """
    result = {tc: {"date_used": None, "count": 0, "items": []} for tc in ts_codes}
    try:
        # 收盘价基准(最近交易日 daily_basic, 用于折溢价; 全市场单次, 各股共享)
        ref_prices = {}
        try:
            pbd = PRO.daily_basic(trade_date=_tushare_trade_date(),
                                  fields="ts_code,close")
            if pbd is not None and not pbd.empty:
                ref_prices = dict(zip(pbd["ts_code"], pbd["close"]))
        except Exception:
            pass

        def _to_items(rows_iter, code, limit=10) -> list:
            items = []
            for r in rows_iter:
                price = _safe_float(r["price"])
                ref = ref_prices.get(code)
                premium = None
                if price and ref:
                    premium = round((price - ref) / ref * 100, 2)
                buyer = r["buyer"] or ""
                seller = r["seller"] or ""
                items.append({
                    "date": str(r["trade_date"]),
                    "price": price,
                    "amount_wan": round(_safe_float(r["amount"]), 2),  # block_trade.amount 单位=万元
                    "premium_pct": premium,
                    "buyer": buyer,
                    "seller": seller,
                    "is_inst_buy": "机构专用" in buyer,
                    "is_inst_sell": "机构专用" in seller,
                })
                if len(items) >= limit:
                    break
            return items

        start_db = (datetime.strptime(_today(), "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
        for tc in ts_codes:
            # 1) 读库: 近 lookback_days 天, 最多 10 条
            try:
                db_rows = db.execute(
                    "SELECT trade_date, price, vol, amount, buyer, seller FROM stg_block_trade "
                    "WHERE ts_code=? AND trade_date>=? ORDER BY trade_date DESC LIMIT 10", (tc, start_db))
                if db_rows:
                    items = _to_items(
                        [dict(zip(["trade_date", "price", "vol", "amount", "buyer", "seller"], r))
                         for r in db_rows], tc, limit=10)
                    if items:
                        result[tc] = {
                            "date_used": items[0]["date"],
                            "count": len(db_rows),
                            "items": items,
                            "total_wan": round(float(sum(r[3] or 0 for r in db_rows)), 2),
                        }
                        continue
            except Exception:
                pass
            # 2) 库空/异常 → 实时回退(全市场近 lookback_days 天单次拉取)
            try:
                end = _today()
                start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
                df = PRO.block_trade(start_date=start, end_date=end)
                if df is None or df.empty:
                    continue
                df = df.sort_values("trade_date", ascending=False)
                sub = df[df["ts_code"] == tc]
                if sub.empty:
                    continue
                items = _to_items(
                    ({k: r.get(k) for k in ("trade_date", "price", "vol", "amount", "buyer", "seller")}
                     for _, r in sub.iterrows()), tc, limit=10)
                result[tc] = {
                    "date_used": str(sub.iloc[0]["trade_date"]),
                    "count": len(sub),
                    "items": items,
                    "total_wan": round(float(sub["amount"].sum()), 2),
                }
            except Exception:
                continue
    except Exception as e:
        log_error(function="fetch_blocktrade", level="WARNING",
                  api_name="block_trade", error_msg=str(e))
        for tc in ts_codes:
            result[tc] = {**result[tc], "error": str(e)[:200]}
    return result


def _fmt_blocktrade_section(name: str, bt: dict) -> list[str]:
    """大宗交易格式化: 有则 2-4 行(席位定性/折溢价/金额), 无则一行"""
    if "error" in bt:
        return [f"❌ 大宗交易: {bt['error']}"]
    if not bt.get("count"):
        return [f"## 【大宗交易】\n近90天无大宗交易记录。"]
    lines = [f"## 【大宗交易】(数据日期 {bt.get('date_used')}, 盘后实锤数据)"]
    lines.append(f"近期大宗: {bt.get('count')} 笔, 合计 {_fmt_amount_wan(bt.get('total_wan', 0))}")
    for it in bt.get("items", []):
        prem = f"{it['premium_pct']:+.2f}%" if it.get("premium_pct") is not None else "折溢价N/A"
        side = ""
        if it.get("is_inst_buy") or it.get("is_inst_sell"):
            side = " [机构参与]"
        lines.append(f"  - {it['date']} 成交 {it.get('price')}元({prem}) | "
                     f"{_fmt_amount_wan(it.get('amount_wan'))} | "
                     f"买:{it.get('buyer')} 卖:{it.get('seller')}{side}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 11. 板块地位 — mid_sector_ths 最新快照(非收盘则回退 stg_ths_daily)
# ══════════════════════════════════════════════════════════════

def fetch_sector_endday(stock_names: list[str]) -> dict[str, dict]:
    """板块排名(收盘快照, 若最新快照仍为午间则标注) + 板块日涨跌基准"""
    from fetch_midday_data import fetch_sector_ranking, fetch_ths_daily_benchmark
    result = {}
    try:
        sr = fetch_sector_ranking(stock_names)
        for n in stock_names:
            result[n] = {"ranking": sr.get(n, {})}
    except Exception as e:
        log_error(function="fetch_sector_endday", level="WARNING", api_name="mid_sector_ths", error_msg=str(e))
        for n in stock_names:
            result[n] = {"error": str(e)[:150]}
    try:
        bm = fetch_ths_daily_benchmark(stock_names)
        for n in stock_names:
            result.setdefault(n, {})["benchmark"] = bm.get(n, [])
    except Exception:
        pass
    return result


def _fmt_sector_section(name: str, sec: dict) -> list[str]:
    if "error" in sec:
        return [f"❌ 板块: {sec['error']}"]
    lines = [f"## 【板块地位】"]
    rk = sec.get("ranking", {}).get("by_type", {})
    for tp, group in rk.items():
        label = group.get("label", tp)
        for s in group.get("sectors", [])[:3]:
            lines.append(f"  [{label}] {s['name']}: 板块涨幅 {s['avg_chg_pct']:+.2f}% | 排名 {s['rank']}/{s['total']} | 涨{s['up_count']}/跌{s['down_count']}")
    bm = sec.get("benchmark", [])
    if bm:
        cur = ""
        for b in bm[:6]:
            if b.get("type_label") != cur:
                cur = b.get("type_label", "")
                lines.append(f"  [{cur}] 昨日板块涨跌幅基准:")
            lines.append(f"    {b.get('name')}: {b.get('pct_change')}%")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 12. 技术面(收盘版)— 新浪K线, 当日日线已完整, 直接用最近20日
# ══════════════════════════════════════════════════════════════

def fetch_technical_endday(names_codes: list[tuple], margin_costs: dict[str, dict],
                           inst_costs: dict[str, dict], cyq_costs: dict[str, dict] | None = None) -> dict[str, dict]:
    """MA5/10/20/BOLL(收盘完整日线) + 成本地图三锚(机构成本/融资盘成本/筹码加权成本)"""
    import numpy as np
    cyq_costs = cyq_costs or {}
    result = {}
    for name, ts_code in names_codes:
        symbol = ts_code.split(".")[0]
        tcode = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        try:
            kline = _sina_kline(tcode)
            if not kline or len(kline) < 20:
                result[name] = {"error": "K线数据不足"}
                continue
            closes = [k["close"] for k in kline[-20:]]  # 收盘后今日日线完整
            ma5, ma10, ma20 = _calc_ma(closes, 5), _calc_ma(closes, 10), _calc_ma(closes, 20)
            std20 = round(float(np.std(closes[-20:])), 2) if ma20 else None
            boll_upper = round(ma20 + 2 * std20, 2) if ma20 and std20 else None
            boll_lower = round(ma20 - 2 * std20, 2) if ma20 and std20 else None
            price = closes[-1]
            deviation = {}
            for label, val in [("ma5", ma5), ("ma10", ma10), ("ma20", ma20)]:
                if price and val:
                    dev = (price - val) / val * 100
                    tag = "贴近" if abs(dev) <= 1 else ("上方" if dev > 0 else "下方")
                    deviation[label] = {"pct": round(dev, 2), "tag": tag}
            result[name] = {
                "price": price, "ma5": ma5, "ma10": ma10, "ma20": ma20,
                "boll_upper": boll_upper, "boll_lower": boll_lower,
                "deviation": deviation,
                # 成本地图三锚
                "inst_cost": inst_costs.get(ts_code, {}).get("inst_cost"),
                "margin_cost_low": margin_costs.get(ts_code, {}).get("cost_low"),
                "margin_cost_high": margin_costs.get(ts_code, {}).get("cost_high"),
                "margin_cost_mid": margin_costs.get(ts_code, {}).get("cost_mid"),
                "cyq_cost": cyq_costs.get(ts_code, {}).get("weight_avg"),
                "cyq_cost_mid": cyq_costs.get(ts_code, {}).get("cost_50pct"),
                "cyq_date": cyq_costs.get(ts_code, {}).get("trade_date"),
            }
        except Exception as e:
            result[name] = {"error": str(e)[:150]}
    return result


def _fmt_technical_section(name: str, ta: dict) -> list[str]:
    if "error" in ta:
        return [f"❌ 技术面: {ta['error']}"]
    lines = [f"## 【技术面与成本地图】(收盘价 {ta.get('price')} 元)"]
    for label, display in [("ma5", "MA5"), ("ma10", "MA10"), ("ma20", "MA20")]:
        val = ta.get(label)
        dev = ta.get("deviation", {}).get(label, {})
        if val and dev:
            lines.append(f"  {display}: {val}元 | 现价{dev['tag']} {abs(dev['pct'])}%")
    if ta.get("boll_upper") and ta.get("boll_lower"):
        lines.append(f"  BOLL: 上轨 {ta['boll_upper']} / 下轨 {ta['boll_lower']}")
    lines.append("  成本地图(心理价位锚点):")
    lines.append(f"    机构持仓成本(估算): {ta.get('inst_cost') or 'N/A'} 元")
    if ta.get("margin_cost_mid"):
        lines.append(f"    融资盘成本区: {ta.get('margin_cost_low')}-{ta.get('margin_cost_high')}元(加权 {ta.get('margin_cost_mid')}元)")
    if ta.get("cyq_cost"):
        cyq_tag = f"(筹码数据日期 {ta['cyq_date']})"
        lines.append(f"    筹码加权成本: {ta['cyq_cost']}元 | 中位成本 {ta.get('cyq_cost_mid')}元 {cyq_tag}")
    lines.append(f"    MA20: {ta.get('ma20')} 元")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 19. 筹码成本分布 — DB stg_cyq_perf / stg_cyq_chips(ETL 19:10 当天入库, 探测回退 T-1)
# ══════════════════════════════════════════════════════════════

def fetch_cyq_db(ts_codes: list[str]) -> dict[str, dict]:
    """读库: 筹码加权成本/中位成本/90%成本带/获利比例/当日密集价位 top"""
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            r = db.execute("SELECT MAX(trade_date) FROM stg_cyq_perf WHERE ts_code=?", (tc,))
            td = r[0][0] if r and r[0][0] else None
            if not td:
                info["error"] = "库中无筹码数据"
                result[tc] = info
                continue
            rows = db.execute(
                "SELECT trade_date, cost_5pct, cost_50pct, cost_95pct, weight_avg, winner_rate "
                "FROM stg_cyq_perf WHERE ts_code=? AND trade_date=?", (tc, td))
            if not rows:
                info["error"] = "库中无筹码数据"
                result[tc] = info
                continue
            r0 = rows[0]
            info = {
                "trade_date": r0[0],
                "cost_5pct": r0[1], "cost_50pct": r0[2], "cost_95pct": r0[3],
                "weight_avg": r0[4], "winner_rate": r0[5],
            }
            chips = db.execute(
                "SELECT price, percent FROM stg_cyq_chips WHERE ts_code=? AND trade_date=? "
                "ORDER BY percent DESC LIMIT 3", (tc, td))
            info["dense"] = [{"price": c[0], "percent": c[1]} for c in chips]
        except Exception as e:
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_cyq_section(ts_code: str, cyq: dict) -> list[str]:
    if "error" in cyq:
        return [f"❌ 筹码成本: {cyq['error']}"]
    lines = [f"## 【筹码成本分布】(数据日期 {cyq.get('trade_date')}, Tushare cyq; 当天18~19点更新)"]
    lines.append(f"筹码加权平均成本: {cyq.get('weight_avg')}元 | 中位成本(50分位): {cyq.get('cost_50pct')}元")
    lines.append(f"90%成本带: {cyq.get('cost_5pct')} ~ {cyq.get('cost_95pct')}元 | 获利比例: {cyq.get('winner_rate')}%")
    dense = cyq.get("dense") or []
    if dense:
        lines.append("筹码密集价位 top: " + " | ".join(f"{d['price']}元({d['percent']}%)" for d in dense))
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 16. 北向持股 — DB stg_hk_hold(季度披露, 港交所 2024-08 停发日度)
# ══════════════════════════════════════════════════════════════

def fetch_northbound_db(ts_codes: list[str]) -> dict[str, dict]:
    """读库: 北向持股近 8 期序列(vol/ratio + 逐期变化 + 趋势)"""
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            rows = db.execute(
                "SELECT trade_date, vol, ratio FROM stg_hk_hold WHERE ts_code=? "
                "ORDER BY trade_date DESC LIMIT 8", (tc,))
            if not rows:
                info["error"] = "库中无北向数据"
                result[tc] = info
                continue
            seq = [{"trade_date": r[0], "vol": r[1], "ratio": r[2]} for r in rows]
            seq.reverse()
            info["seq"] = seq
            info["latest"] = seq[-1]["trade_date"]
            # 逐期变化 + 趋势(近3期方向)
            if len(seq) >= 2:
                info["ratio_chg"] = [
                    round(float(seq[i]["ratio"] or 0) - float(seq[i - 1]["ratio"] or 0), 3)
                    for i in range(1, len(seq))]
            if len(seq) >= 3:
                d1 = float(seq[-1]["ratio"] or 0) - float(seq[-2]["ratio"] or 0)
                d2 = float(seq[-2]["ratio"] or 0) - float(seq[-3]["ratio"] or 0)
                info["trend"] = ("连续增持" if d1 > 0 and d2 > 0 else
                                 "连续减持" if d1 < 0 and d2 < 0 else
                                 "增持放缓" if d1 > 0 and d2 <= 0 else
                                 "减持收窄" if d1 < 0 and d2 >= 0 else "波动")
        except Exception as e:
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_northbound_section(ts_code: str, nb: dict) -> list[str]:
    if "error" in nb:
        return [f"❌ 北向持股: {nb['error']}"]
    lines = [f"## 【北向持股】(季度披露, 港交所 2024-08 起停发日度; 数据截至 {nb.get('latest')})"]
    seq = nb.get("seq") or []
    if seq:
        rows = [f"| 披露日 | 持股(亿股) | 占比% | 环比 |"]
        rows.append("|---|---|---|---|")
        chgs = nb.get("ratio_chg") or [None] * len(seq)
        for i, s in enumerate(seq):
            chg = f"{chgs[i - 1]:+.3f}" if i > 0 and chgs[i - 1] is not None else "-"
            rows.append(f"| {s['trade_date']} | {float(s['vol'] or 0) / 1e8:.2f} | {s['ratio']} | {chg} |")
        lines.extend(rows)
        if nb.get("trend"):
            lines.append(f"趋势: {nb['trend']}")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 17. 十大流通股东 — DB stg_top10_floatholder(季度披露)
# ══════════════════════════════════════════════════════════════

_HOLDER_TYPE_CN = {"Fund": "公募", "HKSCC": "外资HKSCC", "Private": "私募",
                   "Industry": "产业资本", "Individual": "自然人"}


def fetch_top10_db(ts_codes: list[str]) -> dict[str, dict]:
    """读库: 十大流通股东近 4 期(每期前5 + 类型分布 + 变动 Top3)"""
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            rows = db.execute(
                "SELECT end_date, holder_name, hold_amount, hold_ratio, hold_change, holder_type "
                "FROM stg_top10_floatholder WHERE ts_code=? "
                "ORDER BY end_date DESC, hold_amount DESC LIMIT 40", (tc,))
            if not rows:
                info["error"] = "库中无十大股东数据"
                result[tc] = info
                continue
            periods = []
            for r in rows:
                p = r[0]
                if not periods or periods[-1]["period"] != p:
                    periods.append({"period": p, "holders": []})
                periods[-1]["holders"].append({
                    "name": r[1], "amount": r[2], "ratio": r[3], "change": r[4], "htype": r[5],
                })
            periods = periods[:4]
            info["periods"] = periods
            # 类型分布(最新期)
            latest = periods[0]
            dist = {}
            for h in latest["holders"]:
                t = _HOLDER_TYPE_CN.get(h["htype"], h["htype"] or "其他")
                dist[t] = dist.get(t, 0) + 1
            info["type_dist"] = dist
            # 变动 Top3(最新期, 变动绝对值)
            chg = [h for h in latest["holders"] if h["change"] is not None]
            chg.sort(key=lambda x: abs(float(x["change"])), reverse=True)
            info["change_top3"] = chg[:3]
        except Exception as e:
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_top10_section(ts_code: str, tp: dict) -> list[str]:
    if "error" in tp:
        return [f"❌ 十大流通股东: {tp['error']}"]
    lines = [f"## 【十大流通股东】(近4期, 季度披露)"]
    periods = tp.get("periods") or []
    for p in periods:
        lines.append(f"  [{p['period']}] 前5:")
        for h in p["holders"][:5]:
            chg_s = ""
            if h.get("change") is not None:
                v = float(h["change"])
                chg_s = f" 变动 {v/1e4:.0f}万股" if abs(v) >= 1e4 else f" 变动 {v:.0f}股"
            lines.append(f"    - {h['name']}({_HOLDER_TYPE_CN.get(h['htype'], h['htype'] or '其他')}, "
                         f"占比 {h['ratio']}%){chg_s}")
    if tp.get("type_dist"):
        lines.append("类型分布(最新期): " + " | ".join(f"{k} {v}席" for k, v in tp["type_dist"].items()))
    for h in (tp.get("change_top3") or []):
        if h.get("change") is not None:
            v = float(h["change"])
            tag = "增持" if v > 0 else "减持"
            lines.append(f"  {tag}Top: {h['name']} {abs(v)/1e4:.0f}万股")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 18. 券商评级与盈利预测 — DB stg_report_rc 读库优先(ETL 22:00 全市场)
#     库空 → 实时单股拉取 + 写回库(幂等) + warning
# ══════════════════════════════════════════════════════════════

# report_rc 接口已【全面停用】(2026-08-06 用户指示): 禁止任何调用, 报告侧纯读库。
# 实时回退逻辑已删除(用户明确表示不需要回退); 库空 → 输出提示等待 ETL 数据。
# 恢复接入见 office/demand/report_rc_dev_log_20260806.md
_REPORT_RC_DISABLED_MSG = "评级数据缺失(报告侧不实时拉取): 等待 ETL 回填/增量入库"


def fetch_report_rc(ts_codes: list[str], lookback_days: int = 365) -> dict[str, dict]:
    """券商评级: 仅读库 stg_report_rc 近 12 月(ETL 22:00 全市场入库)

    停用说明(2026-08-06): 原实时回退逻辑已删除, 库空直接提示等待 ETL 数据,
    不调用 report_rc 接口(试用额度已耗尽, 用户要求全面停用)。
    """
    end = _today()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            rows = db.execute(
                "SELECT ts_code, name, report_date, report_title, org_name, quarter,"
                " np, eps, rating, max_price, min_price "
                "FROM stg_report_rc WHERE ts_code=? AND report_date>=? "
                "ORDER BY report_date DESC", (tc, start))
            if not rows:
                info["error"] = _REPORT_RC_DISABLED_MSG
                result[tc] = info
                continue
            # 统计
            latest_date = max(r[2] for r in rows)
            # 评级分布(近12月)
            rating_dist = {}
            for r in rows:
                rt = (r[8] or "未知").strip()
                rating_dist[rt] = rating_dist.get(rt, 0) + 1
            # 目标价共识(近3月, max_price 非空)
            start3m = (datetime.strptime(end, "%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")
            tp_rows = [r for r in rows if r[2] >= start3m and r[9] is not None]
            tp_vals = [float(r[9]) for r in tp_rows]
            tp_consensus = None
            if tp_vals:
                tp_consensus = {
                    "avg": round(sum(tp_vals) / len(tp_vals), 2),
                    "max": max(tp_vals), "min": min(tp_vals), "n": len(tp_vals),
                }
            # 分季度净利/EPS 共识(最新一份研报的预测)
            quarter_rows = {}
            for r in rows:
                q = r[5]
                if q and r[6] is not None:
                    quarter_rows.setdefault(q, []).append(r)
            q_consensus = {}
            for q, qr in sorted(quarter_rows.items(), key=lambda x: x[0]):
                nps = [float(x[6]) for x in qr if x[6] is not None]
                epss = [float(x[7]) for x in qr if x[7] is not None]
                if nps:
                    q_consensus[q] = {
                        "np_yi": round(sum(nps) / len(nps) / 1e4, 2),  # 万元 → 亿元
                        "eps": round(sum(epss) / len(epss), 3) if epss else None,
                        "n": len(nps),
                    }
            # 最新 3 份研报(不同 report_date)
            seen_dates = []
            reports = []
            for r in rows:
                if r[2] not in seen_dates:
                    seen_dates.append(r[2])
                    reports.append({"date": r[2], "title": (r[3] or "")[:60],
                                    "org": r[4], "rating": r[8] or ""})
                if len(seen_dates) >= 3:
                    break
            info = {
                "latest_report_date": latest_date,
                "n": len(rows),
                "rating_dist": rating_dist,
                "tp_consensus": tp_consensus,
                "quarter_consensus": q_consensus,
                "reports": reports,
            }
        except Exception as e:
            log_error(function="fetch_report_rc", level="WARNING", ts_code=tc,
                      api_name="report_rc", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_report_rc_section(ts_code: str, rc: dict) -> list[str]:
    if "error" in rc:
        return [f"❌ 券商评级: {rc['error']}"]
    lines = [f"## 【券商评级与盈利预测】(近12月研报 {rc.get('n', 0)} 条, 研报截至 {rc.get('latest_report_date')}; 22点增量次日生效)"]
    rd = rc.get("rating_dist", {})
    if rd:
        top = sorted(rd.items(), key=lambda x: -x[1])[:4]
        lines.append("评级分布: " + " | ".join(f"{k} {v}" for k, v in top))
    tp = rc.get("tp_consensus")
    if tp:
        lines.append(f"目标价共识(近3月 {tp['n']} 家): {tp['min']} ~ {tp['max']}元(均值 {tp['avg']}元)")
    qc = rc.get("quarter_consensus", {})
    if qc:
        qs = " | ".join(f"{q}: 净利 {v['np_yi']}亿 EPS {v['eps']}元({v['n']}家)" for q, v in list(qc.items())[:3])
        lines.append(f"盈利预测共识: {qs}")
    for rep in (rc.get("reports") or [])[:3]:
        lines.append(f"  [{rep['date']}] {rep['title']} — {rep['org']}({rep['rating']})")
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 13. 业绩趋势 — fina_indicator 最近4期
# ══════════════════════════════════════════════════════════════

def fetch_finance_trend(ts_codes: list[str]) -> dict[str, dict]:
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            df = PRO.fina_indicator(ts_code=tc, start_date="20250101", end_date=_today())
            if df is not None and not df.empty:
                df = df.drop_duplicates("end_date").sort_values("end_date").tail(4)
                info["periods"] = [
                    {"end_date": r["end_date"], "eps": r.get("eps"), "roe": r.get("roe"),
                     "gross_margin": r.get("grossprofit_margin"), "net_margin": r.get("netprofit_margin"),
                     "debt": r.get("debt_to_assets")}
                    for _, r in df.iterrows()]
        except Exception as e:
            log_error(function="fetch_finance_trend", level="WARNING", ts_code=tc,
                      api_name="fina_indicator", error_msg=str(e))
            info["error"] = str(e)[:200]
        result[tc] = info
    return result


def _fmt_finance_section(ts_code: str, ft: dict) -> list[str]:
    if "error" in ft:
        return [f"❌ 业绩趋势: {ft['error']}"]
    if not ft.get("periods"):
        return ["## 【业绩趋势】\n暂无数据。"]
    lines = [f"## 【业绩趋势】(fina_indicator 最近{len(ft['periods'])}期)"]
    rows = ["| 报告期 | EPS | ROE% | 毛利率% | 净利率% | 负债率% |", "|---|---|---|---|---|---|"]
    for p in ft["periods"]:
        rows.append(f"| {p['end_date']} | {p.get('eps')} | {p.get('roe')} | {p.get('gross_margin')} | {p.get('net_margin')} | {p.get('debt')} |")
    lines.extend(rows)
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 14. 公告补充 — 业绩预告/快报/增减持/波动/分红/审计(T日探测)
# ══════════════════════════════════════════════════════════════

def fetch_supplementary_endday(stock_names: list[str], ts_codes: list[str]) -> dict[str, list[str]]:
    """精简版补充信息: 只取 P0 级事件(业绩预告/快报/增减持/异常波动/分红/审计)"""
    today = _today()
    prev = _tushare_trade_date()
    result = {}
    forecast_all, shock_all, holdertrade_all = {}, {}, {}
    express_all, dividend_all, audit_all = {}, {}, {}
    for qd in (prev, today):  # T-1 必有, T 日探测
        try:
            df = PRO.forecast(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    forecast_all[row["ts_code"]] = row.to_dict()
        except Exception:
            pass
        try:
            df = PRO.express(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    express_all[row["ts_code"]] = row.to_dict()
        except Exception:
            pass
        try:
            df = PRO.dividend(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    dividend_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception:
            pass
        try:
            df = PRO.fina_audit(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    audit_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception:
            pass
        try:
            df = PRO.stk_shock(trade_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    shock_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception:
            pass
        try:
            df = PRO.stk_holdertrade(ann_date=qd)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    holdertrade_all.setdefault(row["ts_code"], []).append(row.to_dict())
        except Exception:
            pass

    for name, tc in zip(stock_names, ts_codes):
        lines = []
        sections = [
            ("业绩预告", forecast_all.get(tc), _FORECAST_CN),
            ("业绩快报", express_all.get(tc), _EXPRESS_CN),
            ("分红送股", dividend_all.get(tc), _DIVIDEND_CN),
            ("财务审计意见", audit_all.get(tc), _FINA_AUDIT_CN),
        ]
        for title, data, mapping in sections:
            if data:
                items = data if isinstance(data, list) else [data]
                lines.append(f"【{title}】")
                for it in items[:1]:
                    lines.extend(_df_to_lines(pd.DataFrame([it]), mapping, indent=1))
        sl = shock_all.get(tc, [])
        if sl:
            lines.append("【异常波动】")
            for s in sl[:2]:
                lines.extend(_df_to_lines(pd.DataFrame([s]), _SHOCK_CN, indent=1))
        hl = holdertrade_all.get(tc, [])
        if hl:
            lines.append("【股东增减持】")
            for h in hl[:2]:
                lines.extend(_df_to_lines(pd.DataFrame([h]), _HOLDERTRADE_CN, indent=1))
        result[name] = lines
    return result


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

def _name_to_codes(name: str) -> dict | None:
    """名称 → ts_code/symbol/xueqiu(复用午间脚本)"""
    from fetch_midday_data import _name_to_codes as _mtc
    return _mtc(name)


def _check_completeness(stock_data: dict) -> dict:
    """按章节检查数据完整性 → {ts_code: {"critical": [...], "non_critical": [...]}}"""
    critical_empty, non_critical_empty = [], []
    for sec_id, sec_name in _SECTION_NAMES.items():
        flag = stock_data.get(sec_id)
        is_critical = sec_id in _CRITICAL_SECTIONS
        if flag is False or (isinstance(flag, str) and flag.startswith("❌")):
            (critical_empty if is_critical else non_critical_empty).append(sec_name)
    if not critical_empty and not non_critical_empty:
        return {}
    return {"critical": critical_empty, "non_critical": non_critical_empty}


def fetch_all(stock_names: list[str]) -> dict:
    """统一取数入口(日终)

    Returns:
        {name: formatted_string, "warning": {ts_code: {...}}}
    """
    # 1. 代码解析
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
    symbol_map = {n: {"ts_code": tc, "symbol": sym} for n, tc, sym in zip(names, ts_codes, symbols)}

    # 2. 并行取数(各组独立;SQLite 相关任务留在主线程,避免跨线程连接)
    def _task(key, fn, *args):
        try:
            return key, fn(*args)
        except Exception as e:
            log_error(function="fetch_all", level="WARNING", api_name=key, error_msg=str(e))
            return key, {}

    with ThreadPoolExecutor(max_workers=min(6, len(infos) * 2 or 1)) as pool:
        futures = [
            pool.submit(_task, "margin", fetch_margin_analysis, ts_codes),
            pool.submit(_task, "lhb", fetch_lhb, ts_codes),
            pool.submit(_task, "moneyflow", fetch_moneyflow_multi, ts_codes),
            pool.submit(_task, "snowball", fetch_snowball_flow, xq_codes),
            pool.submit(_task, "institution", fetch_ths_institution, symbols),
            pool.submit(_task, "survey", fetch_survey, ts_codes),
            pool.submit(_task, "holdernumber", fetch_holdernumber, ts_codes),
            pool.submit(_task, "risk", fetch_risk_calendar, ts_codes),
            pool.submit(_task, "limitboard", fetch_limit_board, symbol_map),
            pool.submit(_task, "finance", fetch_finance_trend, ts_codes),
            pool.submit(_task, "blocktrade", fetch_blocktrade, ts_codes),
        ]
        data = {}
        for fut in as_completed(futures):
            key, val = fut.result()
            data[key] = val

    # SQLite 相关任务(主线程执行,避免跨线程连接问题)
    quotes, snap_time = fetch_quotes_endday(names)
    data["sector"] = fetch_sector_endday(names)
    data["cyq"] = fetch_cyq_db(ts_codes)              # 筹码读库
    data["northbound"] = fetch_northbound_db(ts_codes)  # 北向读库
    data["top10"] = fetch_top10_db(ts_codes)          # 十大流通股东读库
    data["report_rc"] = fetch_report_rc(ts_codes)     # 券商评级仅读库(接口停用中)
    margin_data = data.get("margin") or {}
    lhb_data = data.get("lhb") or {}
    mf_data = data.get("moneyflow") or {}
    sf_data = data.get("snowball") or {}
    inst_data = data.get("institution") or {}
    sv_data = data.get("survey") or {}
    hn_data = data.get("holdernumber") or {}
    risk_data = data.get("risk") or {}
    lb_data = data.get("limitboard") or {}
    sec_data = data.get("sector") or {}
    fin_data = data.get("finance") or {}
    bt_data = data.get("blocktrade") or {}
    cyq_data = data.get("cyq") or {}
    nb_data = data.get("northbound") or {}
    top10_data = data.get("top10") or {}
    rc_data = data.get("report_rc") or {}

    # 技术面(依赖 margin 成本 + 机构成本 + 筹码成本;机构数据按 symbol 键,转为 ts_code 键)
    inst_by_ts = {tc: inst_data.get(sym, {}) for tc, sym in zip(ts_codes, symbols)}
    tech_data = fetch_technical_endday(list(zip(names, ts_codes)), margin_data, inst_by_ts, cyq_data)
    # 公告补充
    supp_data = fetch_supplementary_endday(names, ts_codes)
    # 全市场情绪(收盘后, 重试3次)
    emotion_text = _fetch_with_retry(fetch_market_emotion, lambda t: not t or not t.strip(), max_retries=3)

    # 3. 组装
    result, warnings = {}, {}
    for info in infos:
        name, ts_code, xq_code = info["name"], info["ts_code"], info["xueqiu"]
        sec_ok = {}  # 供完整性检查
        lines = []

        # 1. 情绪
        if emotion_text:
            lines.append("## 【今日全市场情绪】")
            lines.append("")
            lines.append(emotion_text)
            lines.append("---")
            lines.append("")
            sec_ok[1] = bool(emotion_text.strip())

        # 2. 收盘行情
        q = quotes.get(name, {})
        qsec = _fmt_quote_section(name, ts_code, q, snap_time)
        lines.extend(qsec)
        sec_ok[2] = not (not q or "error" in q)
        lines.append("")

        # 3. 融资融券
        msec = _fmt_margin_section(ts_code, name, margin_data.get(ts_code, {"error": "无数据"}))
        lines.extend(msec)
        sec_ok[3] = not msec[0].startswith("❌")
        lines.append("")

        # 4. 龙虎榜
        lsec = _fmt_lhb_section(name, lhb_data.get(ts_code, {"listed": False}))
        lines.extend(lsec)
        sec_ok[4] = lhb_data.get(ts_code, {}).get("listed", False)
        lines.append("")

        # 5. 资金流
        fsec = _fmt_moneyflow_section(name, mf_data.get(ts_code, {}), sf_data.get(xq_code, {}))
        lines.extend(fsec)
        sec_ok[5] = not fsec[0].startswith("❌")
        lines.append("")

        # 6. 机构持仓
        isec = _fmt_institution_section(name, ts_code, inst_data.get(symbols[infos.index(info)], {}))
        lines.extend(isec)
        sec_ok[6] = bool(inst_data.get(symbols[infos.index(info)], {}).get("rate"))
        lines.append("")

        # 16. 北向持股(读库, 季度披露)
        nsec = _fmt_northbound_section(ts_code, nb_data.get(ts_code, {}))
        lines.extend(nsec)
        sec_ok[16] = bool(nb_data.get(ts_code, {}).get("seq"))
        lines.append("")

        # 17. 十大流通股东(读库, 季度披露)
        psec = _fmt_top10_section(ts_code, top10_data.get(ts_code, {}))
        lines.extend(psec)
        sec_ok[17] = bool(top10_data.get(ts_code, {}).get("periods"))
        lines.append("")

        # 7. 机构调研
        ssec = _fmt_survey_section(ts_code, sv_data.get(ts_code, {}))
        lines.extend(ssec)
        sec_ok[7] = bool(sv_data.get(ts_code, {}).get("count"))
        lines.append("")

        # 18. 券商评级与盈利预测(读库, 22点增量次日生效)
        rsec = _fmt_report_rc_section(ts_code, rc_data.get(ts_code, {}))
        lines.extend(rsec)
        sec_ok[18] = bool(rc_data.get(ts_code, {}).get("n"))
        lines.append("")

        # 8. 股东户数
        hsec = _fmt_holdernumber_section(hn_data.get(ts_code, {}))
        lines.extend(hsec)
        sec_ok[8] = bool(hn_data.get(ts_code, {}).get("periods"))
        lines.append("")

        # 9. 风险日历
        rsec = _fmt_risk_section(risk_data.get(ts_code, {}))
        lines.extend(rsec)
        sec_ok[9] = bool(risk_data.get(ts_code, {}).get("unlock") or risk_data.get(ts_code, {}).get("pledge"))
        lines.append("")

        # 10. 涨停/炸板
        bsec = _fmt_limit_board_section(name, lb_data.get(name, {}))
        lines.extend(bsec)
        sec_ok[10] = bool(lb_data.get(name, {}).get("in_list") or lb_data.get(name, {}).get("yesterday_zt"))
        lines.append("")

        # 11. 板块地位
        gsec = _fmt_sector_section(name, sec_data.get(name, {}))
        lines.extend(gsec)
        sec_ok[11] = bool(sec_data.get(name, {}).get("ranking", {}).get("by_type"))
        lines.append("")

        # 12. 技术面与成本地图
        tsec = _fmt_technical_section(name, tech_data.get(name, {}))
        lines.extend(tsec)
        sec_ok[12] = not tsec[0].startswith("❌")
        lines.append("")

        # 19. 筹码成本分布(读库, 当天19:10入库)
        csec = _fmt_cyq_section(ts_code, cyq_data.get(ts_code, {}))
        lines.extend(csec)
        sec_ok[19] = bool(cyq_data.get(ts_code, {}).get("weight_avg"))
        lines.append("")

        # 13. 业绩趋势
        fsec2 = _fmt_finance_section(ts_code, fin_data.get(ts_code, {}))
        lines.extend(fsec2)
        sec_ok[13] = bool(fin_data.get(ts_code, {}).get("periods"))
        lines.append("")

        # 14. 公告补充
        supp = supp_data.get(name, [])
        if supp:
            lines.append("## 【公告补充】(T-1~今日, P0级事件)")
            lines.extend(supp)
            lines.append("")
            sec_ok[14] = True

        # 15. 大宗交易(实锤级, 有则写无则略)
        bsec = _fmt_blocktrade_section(name, bt_data.get(ts_code, {"count": 0}))
        lines.extend(bsec)
        sec_ok[15] = bool(bt_data.get(ts_code, {}).get("count"))
        lines.append("")

        result[name] = "\n".join(lines)
        w = _check_completeness(sec_ok)
        if w:
            warnings[ts_code] = w

    result["warning"] = warnings
    return result


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args or not args:
        print("用法: python fetch_endday_data.py <名称1> [名称2 ...]")
        print("示例: python fetch_endday_data.py 宁德时代 比亚迪")
        print("       python fetch_endday_data.py --format json 宁德时代")
        sys.exit(0)

    fmt = "text"
    stock_names = []
    for a in args:
        if a in ("json", "text"):
            fmt = a
        else:
            stock_names.append(a)
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1]

    result = fetch_all(stock_names)
    warnings = result.pop("warning", {})
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n---\n".join(result.values()))
    if warnings:
        print(f"\n[warning] 数据完整性: {json.dumps(warnings, ensure_ascii=False)}", file=sys.stderr)


if __name__ == "__main__":
    main()
