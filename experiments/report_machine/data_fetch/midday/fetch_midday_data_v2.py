"""午间盘中取数脚本 v2 — 11:35 运行,决策触发型午间报告数据层

设计(对应 office/demand/midday_report/requirements.md):
  - 半日行情(11:30 快照)    → DB mid_stock_intraday + stg_tencent_snapshot
  - 融资融券多日(T-1,250日) → Tushare margin_detail + daily_basic(endday 复用)
                             → 杠杆方向/拥挤度分位/融资盘成本区(与日终同等级)
  - 龙虎榜(T-1)             → Tushare top_list + top_inst(午间时点 T 日未出,自动回退 T-1)
  - 个股资金流(T-1 角色)     → Tushare moneyflow(20日) + 雪球 capital_flow/assort/history
  - 机构持仓/调研/股东户数    → 同花顺 F10 四端点 + stk_surv + stk_holdernumber(与日终同等级)
  - 风险日历(解禁/质押/披露) → share_float + pledge_stat + disclosure_date(与日终同等级)
  - 业绩趋势                → fina_indicator(与日终同等级)
  - 涨停/异动/快讯(盘中)     → 由 office/fetcher 的 message 路(fetch_message)提供, 本脚本不含
  - 板块地位                → 同花顺板块排名 + 基准
  - 技术面+成本地图(半日)    → 新浪K线(MA 按昨日收盘基准) + 融资/机构成本锚点
  - 公告补充                → Tushare 业绩预告/快报/增减持/波动/分红/审计
  - 全市场情绪              → 财联社 levistock

与旧版 fetch_midday_data.py 的关系:
  - 旧版 11 节保留(行情/板块/技术/公告/情绪/关键词/旧融资单日)
  - 新增 endday 慢数据:融资融券多日(替代旧单日)/机构持仓/机构调研/股东户数/风险日历/业绩趋势
  - 消息数据(快讯/异动/跌停/热门板块原因)由 message 路(fetch_message)独立提供,
    本脚本与 fetch_endday_data 一样只含数据, 供通用化后的 fetcher 注册表调度

输入: 个股名称列表 ['宁德时代', '比亚迪']
输出: {'宁德时代': '内容string', '比亚迪': '内容string', "warning": {...}}

约定: 与 endday 相同——任何数据块输出时附实际数据日期标签;T 日数据缺失时回退 T-1 并标注。
适用于交易日 11:35 左右调用。
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

# ── 目录与导入路径: midday(本目录) + endday + etl ──
MIDDAY_DIR = Path(__file__).resolve().parent
ENDDAY_DIR = MIDDAY_DIR.parent / "endday"
ETL_DIR = MIDDAY_DIR.parent.parent / "etl"
for d in [str(MIDDAY_DIR), str(ENDDAY_DIR), str(ETL_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)  # ETL 最后插入 → sys.path[0],etl/config.py 优先

from db_manager import DatabaseManager
from config import DB_PATH

PRO = ts.pro_api()
db = DatabaseManager(str(DB_PATH))

# ── 复用旧版午间脚本: 通用工具 + 午间独有取数 ──
from fetch_midday_data import (
    log_error, _safe_float, _tushare_trade_date,
    fetch_quotes_from_db, fetch_yesterday_turnover,
    fetch_capital_flow, fetch_capital_assort,
    fetch_sector_ranking, fetch_ths_daily_benchmark, fetch_technical_analysis,
    fetch_supplementary_info, fetch_market_emotion,
    fetch_stock_industry_keywords_batch, _name_to_codes,
    _fetch_with_retry, _market_emotion_is_empty,
)

# ── 复用 endday 脚本: 慢数据函数(与日终同等级) + 格式化器 ──
from fetch_endday_data import (
    fetch_margin_analysis, fetch_lhb, fetch_moneyflow_multi, fetch_snowball_flow,
    fetch_ths_institution, fetch_survey, fetch_holdernumber,
    fetch_risk_calendar, fetch_finance_trend, fetch_blocktrade,
    fetch_report_rc,
    _fmt_margin_section, _fmt_lhb_section, _fmt_moneyflow_section,
    _fmt_institution_section, _fmt_survey_section, _fmt_holdernumber_section,
    _fmt_risk_section, _fmt_finance_section, _fmt_blocktrade_section,
    _fmt_report_rc_section,
)

_SECTION_NAMES = {
    1: "全市场情绪", 2: "行业关键词", 3: "半日行情",
    4: "融资融券多日", 5: "龙虎榜", 6: "资金流",
    7: "机构持仓", 8: "机构调研", 9: "股东户数",
    10: "风险日历", 11: "板块地位",
    12: "技术面成本地图", 13: "业绩趋势", 14: "公告补充", 15: "大宗交易",
    16: "券商评级",
}
_CRITICAL_SECTIONS = {1, 3, 4, 6, 12}


# ══════════════════════════════════════════════════════════════
# 午间版格式化器(与 endday 差异: 时段/成本锚点按午间口径)
# ══════════════════════════════════════════════════════════════

def _fmt_moneyflow_section_midday(name: str, mf: dict, sf: dict) -> list[str]:
    """午间版资金流: moneyflow(T-1) + 雪球半日时段(仅早盘桶有值)"""
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
        b = sf.get("day_buckets") or {}
        if b.get("早盘(<11:30)"):
            lines.append(f"今日早盘净额(雪球, 9:30-11:30): {_fmt_amount_wan(b.get('早盘(<11:30)', 0))}")
        if sf.get("assort"):
            a = sf["assort"]
            lines.append(f"今日半日大单净额: {_fmt_amount_wan(a.get('large_net_wan', 0))} | "
                         f"中单: {_fmt_amount_wan(a.get('medium_net_wan', 0))} | "
                         f"小单: {_fmt_amount_wan(a.get('small_net_wan', 0))}")
        if sf.get("hist_5d_wan") is not None:
            lines.append(f"雪球日度净额累计: 3日 {_fmt_amount_wan(sf.get('hist_3d_wan', 0))} | "
                         f"5日 {_fmt_amount_wan(sf.get('hist_5d_wan', 0))} | 10日 {_fmt_amount_wan(sf.get('hist_10d_wan', 0))}")
    lines.append("")
    return lines


def _fmt_technical_section_midday(name: str, ta: dict) -> list[str]:
    """午间技术面+成本地图: 半日现价 + MA/BOLL + 四锚点(与 endday 结构一致, 标题改现价)"""
    if "error" in ta:
        return [f"❌ 技术面: {ta['error']}"]
    lines = [f"## 【技术面与成本地图】(现价 {ta.get('price')} 元, 半日数据)"]
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


def _fmt_quote_section_midday(name: str, ts_code: str, q: dict, raw: dict, yd: dict) -> list[str]:
    """午间半日行情: 11:30 快照 + 腾讯全量字段 + 昨日对比"""
    if not q or "error" in q:
        return [f"❌ 半日行情: {q.get('error', '无数据')}"]
    lines = [f"## 【今日11:30收盘 {name} ({ts_code})情况】(快照)"]
    _FOCUS_FIELDS = [
        ("price", "当前价"), ("chg_pct", "涨跌幅%"), ("prev_close", "昨收"),
        ("open", "开盘"), ("high", "最高"), ("low", "最低"),
        ("amount_wan", "成交额(万元)"), ("turnover_rate", "换手率%"),
        ("amplitude", "振幅%"), ("volume_ratio", "量比"), ("volume", "成交量(手)"),
        ("avg_price", "均价"), ("pe_dynamic", "动态市盈率"), ("pb", "市净率"),
        ("market_cap_total", "总市值(亿元)"), ("market_cap_flow", "流通市值(亿元)"),
        ("limit_up", "涨停价"), ("limit_down", "跌停价"),
    ]
    items = []
    for key, label in _FOCUS_FIELDS:
        val = (raw or {}).get(key)
        if val is not None:
            items.append(f"{label}: {val}")
    if not items:
        items = [f"当前价: {q.get('price')} | 涨跌幅%: {q.get('chg_pct')} | 成交额(万元): {q.get('amount_wan')}"]
    lines.append(" | ".join(items))
    # 昨日对比
    if "error" not in yd and yd.get("turnover_rate") is not None:
        yd_tro = yd.get("turnover_rate")
        today_tro = q.get("turnover_rate")
        if isinstance(today_tro, (int, float)) and isinstance(yd_tro, (int, float)) and yd_tro:
            ratio = today_tro / yd_tro
            tag = "放量" if ratio > 0.8 else "缩量"
            lines.append(f"【上一个交易日日终】换手率: {yd_tro}% | PE: {yd.get('pe', 'N/A')} | PB: {yd.get('pb', 'N/A')}")
            lines.append(f"          → 半日换手 {today_tro}% / 昨日全换手 {yd_tro}% = {ratio:.2f}({tag})")
    lines.append("")
    return lines


def _fmt_sector_section_midday(name: str, sr: dict, bm: list) -> list[str]:
    """午间板块地位: 排名 + 基准(热门板块原因由 message 路提供)"""
    lines = []
    if sr.get("by_type"):
        lines.append("## 【板块排名】(今日午间, 同花顺概念/行业)")
        for tp, group in sr["by_type"].items():
            label = group.get("label", tp)
            secs = group.get("sectors", [])
            if secs:
                parts = []
                for s in secs[:4]:
                    my = ""
                    if s.get("my_position") is not None:
                        my = f"[本股第{s['my_position']+1}名 {s.get('my_chg_pct')}%]"
                    parts.append(f"{s.get('name')}(涨{s.get('avg_chg_pct')}%){my}")
                lines.append(f"  {label}: " + " | ".join(parts))
        lines.append("")
    if bm:
        lines.append("## 【板块涨跌幅基准】(同花顺, 上一交易日日终)")
        for b in bm:
            if isinstance(b, dict):
                pct = b.get("pct_change", "")
                lines.append(f"  {b.get('name', '')}: {pct}%" if pct is not None and pct != "" else f"  {b.get('name', '')}")
            else:
                lines.append(f"  {b}")
        lines.append("")
    if not lines:
        return []
    return lines


def _fmt_supp_section_midday(name: str, supp: list) -> list[str]:
    """公告补充(昨日~今日上午, P0级事件)"""
    if not supp:
        return []
    lines = [f"## 【公告补充】(T-1至今日上午)"]
    lines.extend(supp)
    lines.append("")
    return lines


def _fmt_amount_wan(v):
    """复用 endday 的金额格式化(亿/万 自适应)"""
    if v is None:
        return "N/A"
    v = float(v)
    if abs(v) >= 10000:
        return f"{v/10000:.2f}亿"
    return f"{v:.0f}万"


# ══════════════════════════════════════════════════════════════
# 数据完整性检查
# ══════════════════════════════════════════════════════════════

def _check_completeness_midday(sec_ok: dict) -> dict | None:
    """基于 15 节的完整性检查"""
    critical_empty = [ _SECTION_NAMES[k] for k, v in sec_ok.items()
                       if not v and k in _CRITICAL_SECTIONS ]
    non_critical_empty = [ _SECTION_NAMES[k] for k, v in sec_ok.items()
                           if not v and k not in _CRITICAL_SECTIONS ]
    if not critical_empty and not non_critical_empty:
        return None
    result = {}
    if critical_empty:
        result["critical"] = critical_empty
    if non_critical_empty:
        result["non_critical"] = non_critical_empty
    return result


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

def fetch_all(stock_names: list[str]) -> dict:
    """统一取数入口(午间 v2)

    Args:
        stock_names: ['宁德时代', '比亚迪']

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

    # 2. 并行取数(慢数据来自 endday 复用;SQLite 任务留在主线程)
    def _task(key, fn, *args):
        try:
            return key, fn(*args)
        except Exception as e:
            log_error(function="fetch_all_v2", level="WARNING", api_name=key, error_msg=str(e))
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
            pool.submit(_task, "finance", fetch_finance_trend, ts_codes),
            pool.submit(_task, "blocktrade", fetch_blocktrade, ts_codes),
            pool.submit(_task, "report_rc", fetch_report_rc, ts_codes),
        ]
        data = {}
        for fut in as_completed(futures):
            key, val = fut.result()
            data[key] = val

    # 2b. moneyflow 日期标注修正: 范围查询在 T 日无数据时仍非空,
    #     以实际最后一行日期为准(午间时点 T 日 moneyflow 晚间才更新)
    mf_data = data.get("moneyflow") or {}
    for tc, info in mf_data.items():
        if info and info.get("dates"):
            real_last = info["dates"][-1]
            if real_last != datetime.now().strftime("%Y%m%d"):
                info["date_used"] = real_last

    # 3. SQLite 相关任务(主线程)
    quotes = fetch_quotes_from_db(names)
    # 昨日换手率(T-1, 用于半日放量对比)
    yesterday_data = fetch_yesterday_turnover(ts_codes)
    # 腾讯全量字段快照(54字段, 含内外盘)
    raw_snap = {}
    if db.table_exists("stg_tencent_snapshot"):
        for tc in ts_codes:
            rr = db.execute(
                "SELECT * FROM stg_tencent_snapshot WHERE ts_code=? ORDER BY fetch_time DESC LIMIT 1",
                (tc,)
            )
            if rr:
                cols = [d[1] for d in db.execute("PRAGMA table_info(stg_tencent_snapshot)")]
                raw_snap[tc] = dict(zip(cols, rr[0]))

    # 4. 慢数据(板块/技术/公告/情绪/关键词)
    # 注: 快讯/异动/跌停/热门板块原因由 office/fetcher 的 message 路(fetch_message)独立提供
    prev_td = _tushare_trade_date()
    today_str = datetime.now().strftime("%Y%m%d")
    sector_rankings = fetch_sector_ranking(names)
    benchmark_data = fetch_ths_daily_benchmark(names)
    tech_data = fetch_technical_analysis(list(zip(names, ts_codes)))
    supp_data = fetch_supplementary_info(names, ts_codes, prev_td, today_str)
    market_emotion_text = _fetch_with_retry(
        fetch_market_emotion, _market_emotion_is_empty, max_retries=3, delay=1.0,
    )

    def _fetch_keywords():
        return fetch_stock_industry_keywords_batch(ts_codes)

    def _keywords_is_empty(kw_map: dict) -> bool:
        if not kw_map:
            return True
        return all(len(v) == 0 for v in kw_map.values())

    industry_kw_map = _fetch_with_retry(_fetch_keywords, _keywords_is_empty, max_retries=3, delay=1.0)

    # 6. 技术面成本地图: 注入融资/机构成本锚点(数据键: margin 按 ts_code, inst 按 symbol)
    margin_data = data.get("margin") or {}
    inst_data = data.get("institution") or {}
    inst_by_ts = {tc: inst_data.get(sym, {}) for tc, sym in zip(ts_codes, symbols)}
    for name, tc in zip(names, ts_codes):
        ta = tech_data.get(name, {})
        if not ta or "error" in ta:
            continue
        mg = margin_data.get(tc, {})
        inst = inst_by_ts.get(tc, {})
        if mg.get("cost_mid") is not None:
            ta["margin_cost_mid"] = mg.get("cost_mid")
            ta["margin_cost_low"] = mg.get("cost_low")
            ta["margin_cost_high"] = mg.get("cost_high")
        if inst.get("inst_cost") is not None:
            ta["inst_cost"] = inst.get("inst_cost")

    # 7. 组装
    result, warnings = {}, {}
    for info in infos:
        name, ts_code, xq_code = info["name"], info["ts_code"], info["xueqiu"]
        sec_ok = {}
        # 首节为全市场情绪(所有股票共享一份市场数据), 标题用"全市场情况"而非股票名
        lines = [f"## 全市场情况", ""]

        # 1. 全市场情绪
        if market_emotion_text:
            lines.append(market_emotion_text)
            lines.append("---")
            lines.append("")
        sec_ok[1] = bool(market_emotion_text and market_emotion_text.strip())

        # 2. 行业关键词
        kws = industry_kw_map.get(ts_code, [])
        if kws:
            lines.append(f"📌 股票涉及行业关键词: {', '.join(kws)}")
            lines.append("")
        sec_ok[2] = bool(kws)

        # 3. 半日行情
        qsec = _fmt_quote_section_midday(name, ts_code, quotes.get(name, {}),
                                         raw_snap.get(ts_code, {}),
                                         yesterday_data.get(ts_code, {}))
        lines.extend(qsec)
        sec_ok[3] = not qsec[0].startswith("❌")

        # 4. 融资融券多日(与日终同等级)
        msec = _fmt_margin_section(ts_code, name, margin_data.get(ts_code, {"error": "无数据"}))
        lines.extend(msec)
        sec_ok[4] = not msec[0].startswith("❌")
        lines.append("")

        # 5. 龙虎榜(T-1)
        lsec = _fmt_lhb_section(name, data.get("lhb", {}).get(ts_code, {"listed": False}))
        lines.extend(lsec)
        sec_ok[5] = data.get("lhb", {}).get(ts_code, {}).get("listed", False)
        lines.append("")

        # 6. 资金流(moneyflow T-1 + 雪球半日)
        fsec = _fmt_moneyflow_section_midday(name, data.get("moneyflow", {}).get(ts_code, {}),
                                             data.get("snowball", {}).get(xq_code, {}))
        lines.extend(fsec)
        sec_ok[6] = not fsec[0].startswith("❌")
        lines.append("")

        # 7. 机构持仓
        isec = _fmt_institution_section(name, ts_code, inst_data.get(symbols[infos.index(info)], {}))
        lines.extend(isec)
        sec_ok[7] = bool(inst_data.get(symbols[infos.index(info)], {}).get("rate"))
        lines.append("")

        # 8. 机构调研(午间不输出纪要全文, 只出概要+名单; 2026-08-11)
        ssec = _fmt_survey_section(ts_code, data.get("survey", {}).get(ts_code, {}),
                                   with_minutes=False)
        lines.extend(ssec)
        sec_ok[8] = bool(data.get("survey", {}).get(ts_code, {}).get("count"))
        lines.append("")

        # 9. 股东户数
        hsec = _fmt_holdernumber_section(data.get("holdernumber", {}).get(ts_code, {}))
        lines.extend(hsec)
        sec_ok[9] = bool(data.get("holdernumber", {}).get(ts_code, {}).get("periods"))
        lines.append("")

        # 10. 风险日历
        rsec = _fmt_risk_section(data.get("risk", {}).get(ts_code, {}))
        lines.extend(rsec)
        sec_ok[10] = bool(data.get("risk", {}).get(ts_code, {}))
        lines.append("")

        # 11. 板块地位(热门板块原因由 message 路提供)
        gsec = _fmt_sector_section_midday(name, sector_rankings.get(name, {}),
                                          benchmark_data.get(name, []))
        lines.extend(gsec)
        sec_ok[11] = bool(gsec)

        # 12. 技术面+成本地图(半日)
        tsec = _fmt_technical_section_midday(name, tech_data.get(name, {}))
        lines.extend(tsec)
        sec_ok[12] = not tsec[0].startswith("❌")
        lines.append("")

        # 13. 业绩趋势
        fsec2 = _fmt_finance_section(ts_code, data.get("finance", {}).get(ts_code, {}))
        lines.extend(fsec2)
        sec_ok[13] = bool(data.get("finance", {}).get(ts_code, {}).get("periods"))
        lines.append("")

        # 14. 公告补充
        supp_sec = _fmt_supp_section_midday(name, supp_data.get(name, []))
        lines.extend(supp_sec)
        sec_ok[14] = bool(supp_sec)

        # 15. 大宗交易(实锤级, 有则写无则略; 午间时点 T-1 窗口)
        bsec = _fmt_blocktrade_section(name, data.get("blocktrade", {}).get(ts_code, {"count": 0}))
        lines.extend(bsec)
        sec_ok[15] = bool(data.get("blocktrade", {}).get(ts_code, {}).get("count"))
        lines.append("")

        # 16. 券商评级与盈利预测(逐条研报, 与日终同源; 无数据不阻塞)
        rcsec = _fmt_report_rc_section(ts_code, data.get("report_rc", {}).get(ts_code, {}))
        lines.extend(rcsec)
        sec_ok[16] = bool(data.get("report_rc", {}).get(ts_code, {}).get("n_reports"))
        lines.append("")

        result[name] = "\n".join(lines)
        w = _check_completeness_midday(sec_ok)
        if w:
            warnings[ts_code] = w

    result["warning"] = warnings
    return result


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="午间 v2 取数(批量)")
    parser.add_argument("stocks", nargs="+", help="股票名称列表, 如: 宁德时代 比亚迪")
    parser.add_argument("--out", default=None, help="输出 JSON 文件路径(可选)")
    args = parser.parse_args()

    result = fetch_all(args.stocks)
    warning = result.pop("warning", {})
    for name, text in result.items():
        print(f"\n{'='*70}\n{name}\n{'='*70}\n{text}")
    if warning:
        print(f"\n⚠️ 完整性警告: {json.dumps(warning, ensure_ascii=False, indent=2)}", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(json.dumps({"data": result, "warning": warning}, ensure_ascii=False, indent=2))
        print(f"\n✅ 已输出到 {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
