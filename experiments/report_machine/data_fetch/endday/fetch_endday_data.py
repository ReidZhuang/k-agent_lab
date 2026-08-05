"""
盘中数据取数脚本 — 日终(15:00 收盘后,18:30 运行)数据获取

设计(对应 office/demand/endday_report/requirements.md):
  - 今日收盘行情   → DB stg_tencent_snapshot / mid_stock_intraday(ETL 18:00 快照)
  - 融资融券多日   → Tushare margin_detail(250日) + daily_basic(250日流通市值)
                     → 杠杆方向/拥挤度分位/融资盘成本区/背离/买卖结构/融券
  - 龙虎榜        → Tushare top_list + top_inst(T 日盘后,回退 T-1)
  - 个股资金流多日 → Tushare moneyflow(20日) + 雪球 capital_flow/capital_assort/capital_history
  - 机构持仓      → 同花顺 F10 org_holder 四端点(rate/tab/detail/rate_price)
  - 机构调研      → Tushare stk_surv(近180天)
  - 股东户数      → Tushare stk_holdernumber(最近4期)
  - 风险日历      → Tushare share_float(解禁) + pledge_stat(质押) + disclosure_date(披露计划)
  - 涨停/炸板     → Tushare kpl_list + levistock 涨停池/昨日涨停
  - 板块          → mid_sector_ths(最新快照,非收盘则回退 stg_ths_daily)
  - 技术面        → 新浪K线(收盘后日线完整,直接用最近20日)
  - 业绩趋势      → Tushare fina_indicator(最近4期)
  - 公告补充      → Tushare 业绩预告/快报/增减持/波动/分红/审计(T 日探测,回退 T-1)
  - 全市场情绪    → 财联社 levistock(收盘后)

输入: 个股名称列表 ['宁德时代', '比亚迪']
输出: {'宁德时代': '内容string', '比亚迪': '内容string', "warning": {...}}

约定: 任何数据块输出时附实际数据日期标签;T 日数据缺失时回退 T-1 并标注。
适用于交易日 18:30 左右调用。
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

def _fetch_margin_series(ts_code: str, ndays: int = 250) -> pd.DataFrame | None:
    """拉 margin_detail 历史序列 + daily_basic(流通市值/收盘价) 合并"""
    end = _tushare_trade_date()  # margin/daily_basic 为 T-1 数据
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=int(ndays * 1.8))).strftime("%Y%m%d")
    dfm = PRO.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
    if dfm is None or dfm.empty:
        return None
    dfd = PRO.daily_basic(ts_code=ts_code, start_date=start, end_date=end,
                          fields="trade_date,circ_mv,close")
    dfm = dfm.sort_values("trade_date")
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

def fetch_lhb(ts_codes: list[str]) -> dict[str, dict]:
    """龙虎榜: top_list(每日) + top_inst(席位明细)"""
    td, prev = _today(), _tushare_trade_date()
    result = {tc: {"date_used": prev} for tc in ts_codes}
    try:
        tl, tl_date = _try_then_prev(lambda d: PRO.top_list(trade_date=d), td, prev)
        if tl is not None and not tl.empty:
            tl_map = tl.set_index("ts_code")
            ti, ti_date = None, None
            try:
                ti, ti_date = _try_then_prev(lambda d: PRO.top_inst(trade_date=d), td, prev)
                if ti is not None and not ti.empty:
                    ti = ti[ti["side"].isin([0, 1])]  # 0=买入前5 1=卖出前5
            except Exception:
                pass
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
                if ti is not None and not ti.empty:
                    sub = ti[ti["ts_code"] == tc]
                    if not sub.empty:
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
                        if info["buy_seats"]:
                            top = max(info["buy_seats"], key=lambda s: s["net_wan"])
                            total = sum(s["net_wan"] for s in info["buy_seats"])
                            info["buy1_ratio"] = round(top["net_wan"] / total * 100, 1) if total else None
                            info["buy1_name"] = top["name"]
                            info["inst_buy_count"] = sum(1 for s in info["buy_seats"] if "机构专用" in s["name"])
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


def fetch_ths_institution(symbols: list[str]) -> dict[str, dict]:
    """同花顺 F10 机构持仓(二次开发): rate(8期)/tab(类型)/detail(最新期)/rate_price(占比+股价)

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
            # detail: 最新报告期分页
            latest = next((d for d in tab if d.get("is_updating")), tab[0] if tab else None)
            details = []
            if latest:
                page = 1
                while True:
                    d = _ths_fetch_json(
                        f"{_THS_BASE}/basicapi/holder/stock/org_holder/detail?code={sym}&date={latest['report']}&page={page}&size=15&type=all")["data"]
                    rows = d.get("data", [])
                    details.extend(rows)
                    if len(rows) < 15:
                        break
                    page += 1
            info["rate"] = rate          # [{date, org_num, total_rate, total_holder_change_rate}]
            info["tab"] = tab            # [{date, tab_list: [{name, rate, holder_num}]}]
            info["rate_price"] = rp      # [{date, rate, price}]
            info["report_date"] = latest["date"] if latest else None
            # 明细统计: 新进/增持/减持
            if details:
                def _chg(v):
                    try:
                        return float(v or 0)
                    except (TypeError, ValueError):
                        return 0.0
                inc = [d for d in details if d.get("is_new") or _chg(d.get("change")) > 0]
                dec = [d for d in details if not d.get("is_new") and _chg(d.get("change")) < 0]
                inc_amt = sum(_chg(d.get("holder_market_value")) for d in inc if d.get("is_new")) \
                    + sum(abs(_chg(d.get("change"))) * _chg(d.get("rate")) for d in inc if not d.get("is_new"))
                info["detail_count"] = len(details)
                info["detail_new"] = [{"name": d["org_name"], "mkt_wan": round(_chg(d.get("holder_market_value")) / 1e4, 2)}
                                      for d in details if d.get("is_new")][:10]
                info["detail_inc"] = [{"name": d["org_name"], "chg_wan": round(_chg(d.get("change")) / 1e4, 2)}
                                      for d in details if not d.get("is_new") and _chg(d.get("change")) > 0][:10]
                info["detail_dec"] = [{"name": d["org_name"], "chg_wan": round(abs(_chg(d.get("change"))) / 1e4, 2)}
                                      for d in details if not d.get("is_new") and _chg(d.get("change")) < 0][:10]
                info["dec_count"] = len(dec)
                info["new_count"] = sum(1 for d in details if d.get("is_new"))
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
        for d in rp[:6]:
            rate = _safe_float(d.get("rate"))
            chg = f"{rate - prev:+.2f}" if prev is not None else "-"
            rows.append(f"| {d['date']} | {rate} | {_safe_float(d.get('price'))} | {chg} |")
            prev = rate
        lines.extend(rows)
    if ins.get("inst_cost"):
        lines.append(f"机构持仓成本估算(近4期占比加权): {ins['inst_cost']}元")
    if ins.get("detail_count"):
        lines.append(f"最新期基金明细共 {ins['detail_count']} 条 | 新进 {ins.get('new_count', 0)} 只 | 减持 {ins.get('dec_count', 0)} 只")
        for label, key in (("新进", "detail_new"), ("增持", "detail_inc"), ("减持", "detail_dec")):
            items = ins.get(key) or []
            if items:
                lines.append(f"{label}前5: " + " | ".join(f"{x['name']}({_fmt_amount_wan(x['mkt_wan'] if 'mkt_wan' in x else x['chg_wan'])})" for x in items[:5]))
    lines.append("")
    return lines


# ══════════════════════════════════════════════════════════════
# 7. 机构调研 — Tushare stk_surv(近180天)
# ══════════════════════════════════════════════════════════════

def fetch_survey(ts_codes: list[str], days: int = 365) -> dict[str, dict]:
    """机构调研: stk_surv 近365天(月度频次趋势需长窗口;180天在调研低频股上仅1-2次,无法判'骤增')"""
    end = _today()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=days)).strftime("%Y%m%d")
    result = {}
    for tc in ts_codes:
        info = {}
        try:
            df = PRO.stk_surv(ts_code=tc, start_date=start, end_date=end)
            if df is None or df.empty:
                info["count"] = 0
            else:
                df["month"] = df["surv_date"].str[:6]
                info["count"] = len(df)
                info["by_month"] = {m: int(c) for m, c in df["month"].value_counts().sort_index().items()}
                info["org_type_dist"] = {k: int(v) for k, v in df["org_type"].value_counts().head(5).items()}
                # 按调研日去重取最近3次调研(每次展示机构数/方式/地点)
                last_dates = df["surv_date"].drop_duplicates().tail(3)
                info["recent"] = [
                    {"date": d, "org_count": int(df[df["surv_date"] == d].shape[0]),
                     "mode": df[df["surv_date"] == d]["rece_mode"].iloc[0],
                     "place": df[df["surv_date"] == d]["rece_place"].iloc[0]}
                    for d in last_dates]
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
    od = sv.get("org_type_dist", {})
    if od:
        lines.append("机构类型: " + " | ".join(f"{k}:{v}" for k, v in od.items() if k not in ("--",)))
    for r in (sv.get("recent") or [])[-3:]:
        lines.append(f"  [{r['date']}] 接待机构 {r.get('org_count')}家 ({r.get('mode')}, {r.get('place')})")
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

def fetch_blocktrade(ts_codes: list[str], lookback_days: int = 5) -> dict[str, dict]:
    """大宗交易: block_trade 全市场单次拉取 → 按股过滤

    策略: 大宗为低频事件, 从 T 日起向前探测 lookback_days 个自然日,
    取最近有记录的一天(单日无记录是常态, 不视为缺失)。
    折溢价率需与收盘价对比, 在此用 daily_basic(T-1) 收盘价近似计算。

    Returns:
        {ts_code: {date_used, count, items: [{date, price, amount_wan, premium_pct,
                                              buyer, seller, is_inst_buy, is_inst_sell}],
                   total_wan} } 或 {ts_code: {date_used, count: 0}}
    """
    result = {tc: {"date_used": None, "count": 0, "items": []} for tc in ts_codes}
    try:
        # 最近 lookback_days 个自然日全市场大宗(单次调用覆盖, 避免逐日多次)
        end = _today()
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
        df = PRO.block_trade(start_date=start, end_date=end)
        if df is None or df.empty:
            return result
        df = df.sort_values("trade_date", ascending=False)
        # 收盘价基准(最近交易日 daily_basic, 用于折溢价)
        ref_prices = {}
        try:
            pbd = PRO.daily_basic(trade_date=_tushare_trade_date(),
                                  fields="ts_code,close")
            if pbd is not None and not pbd.empty:
                ref_prices = dict(zip(pbd["ts_code"], pbd["close"]))
        except Exception:
            pass
        for tc in ts_codes:
            sub = df[df["ts_code"] == tc]
            if sub.empty:
                continue
            items = []
            for _, r in sub.head(5).iterrows():  # 最多5条
                price = _safe_float(r.get("price"))
                ref = ref_prices.get(tc)
                premium = None
                if price and ref:
                    premium = round((price - ref) / ref * 100, 2)
                buyer = r.get("buyer") or ""
                seller = r.get("seller") or ""
                items.append({
                    "date": str(r.get("trade_date")),
                    "price": price,
                    "amount_wan": round(_safe_float(r.get("amount")), 2),  # block_trade.amount 单位=万元
                    "premium_pct": premium,
                    "buyer": buyer,
                    "seller": seller,
                    "is_inst_buy": "机构专用" in buyer,
                    "is_inst_sell": "机构专用" in seller,
                })
            result[tc] = {
                "date_used": str(sub.iloc[0]["trade_date"]),
                "count": len(sub),
                "items": items,
                "total_wan": round(float(sub["amount"].sum()), 2),
            }
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
        return [f"## 【大宗交易】\n近5个交易日无大宗交易记录。"]
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
                           inst_costs: dict[str, dict]) -> dict[str, dict]:
    """MA5/10/20/BOLL(收盘完整日线) + 成本地图锚点(机构成本/融资盘成本)"""
    import numpy as np
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
                # 成本地图锚点
                "inst_cost": inst_costs.get(ts_code, {}).get("inst_cost"),
                "margin_cost_low": margin_costs.get(ts_code, {}).get("cost_low"),
                "margin_cost_high": margin_costs.get(ts_code, {}).get("cost_high"),
                "margin_cost_mid": margin_costs.get(ts_code, {}).get("cost_mid"),
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
    lines.append(f"    MA20: {ta.get('ma20')} 元")
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

    # 技术面(依赖 margin 成本 + 机构成本;机构数据按 symbol 键,转为 ts_code 键)
    inst_by_ts = {tc: inst_data.get(sym, {}) for tc, sym in zip(ts_codes, symbols)}
    tech_data = fetch_technical_endday(list(zip(names, ts_codes)), margin_data, inst_by_ts)
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

        # 7. 机构调研
        ssec = _fmt_survey_section(ts_code, sv_data.get(ts_code, {}))
        lines.extend(ssec)
        sec_ok[7] = bool(sv_data.get(ts_code, {}).get("count"))
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
