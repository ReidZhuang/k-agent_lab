"""共享数据后端 — 东方财富 API 搜索

注意：这个后端是当前实验的"具体实现"。
如果要测试不同类型的数据（代码、文本、结构化数据），
替换这里的数据源即可，不影响上层的引用系统和压缩逻辑。
"""

import os, sys, time, requests

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY")
    sys.exit(1)

EMONEY_HEADERS = {"User-Agent": "Mozilla/5.0"}

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 4000
API_BASE_URL = "https://api.deepseek.com"

USER_QUERY = "请研究宁德时代的财务状况，然后与比亚迪进行对比分析。你可以多步搜索，每步基于上一步发现继续深入。目标：全面了解两者的盈利能力、成长性和财务健康状况。"

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def safe_float(v, default=0):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def fetch_financial(secucode):
    r = requests.get(
        "https://datacenter.eastmoney.com/securities/api/data/get",
        params={
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": 1, "ps": 6, "st": "NOTICE_DATE", "sr": -1,
        },
        headers=EMONEY_HEADERS,
        timeout=15,
    )
    return r.json().get("result", {}).get("data", [])


def fmt_report(rows, name):
    if not rows:
        return f"（{name} 暂无数据）"
    lines = [f"{name} 财务数据报告", "=" * 40]
    for row in rows[:4]:
        date = row.get("REPORT_DATE_NAME", "?")
        revenue = row.get("TOTALOPERATEREVE")
        revenue_tz = row.get("TOTALOPERATEREVETZ", "")
        profit = row.get("PARENTNETPROFIT")
        profit_tz = row.get("PARENTNETPROFITTZ", "")

        def f(v):
            if v is None:
                return "N/A"
            try:
                return f"{float(v)/1e8:.1f}亿"
            except (ValueError, TypeError):
                return str(v)

        def fp(v):
            if v is None:
                return "N/A"
            try:
                return f"{float(v):.2f}%"
            except (ValueError, TypeError):
                return str(v)

        def fy(v):
            if v is None or v == "":
                return ""
            try:
                return f"(同比{float(v):.1f}%)"
            except (ValueError, TypeError):
                return str(v)

        lines.append(f"\n── {date} ──")
        lines.append(f"营业收入: {f(revenue)} {fy(revenue_tz)}")
        lines.append(f"净利润: {f(profit)} {fy(profit_tz)}")
        lines.append(f"扣非净利润: {f(row.get('KCFJCXSYJLR', ''))}")
        lines.append(f"毛利率: {fp(row.get('XSMLL', ''))}")
        lines.append(f"净利率: {fp(row.get('XSJLL', ''))}")
        lines.append(f"每股收益: {row.get('EPSXS') or 'N/A'}")
        lines.append(f"ROE: {fp(row.get('ROEJQ', ''))}")
        lines.append(f"总资产: {f(row.get('TOTAL_ASSETS_PK', ''))}")
        lines.append(f"净资产: {f(row.get('TOTAL_EQUITY_PK', ''))}")
        lines.append(f"资产负债率: {fp(row.get('ZCFZL', ''))}")
    lines.append(f"\n(数据来源: 东方财富数据中心, {time.strftime('%Y-%m-%d %H:%M')})")
    return "\n".join(lines)


def search_realtime(query):
    """根据查询返回财务数据报告。"""
    results = []
    if "宁德时代" in query and ("营收" in query or "财务" in query or "财报" in query):
        results.append(fmt_report(fetch_financial("300750.SZ"), "宁德时代(300750)"))
    if "比亚迪" in query and ("营收" in query or "财务" in query or "财报" in query):
        results.append(fmt_report(fetch_financial("002594.SZ"), "比亚迪(002594)"))
    if "对比" in query or "比较" in query:
        catl = fetch_financial("300750.SZ")
        byd = fetch_financial("002594.SZ")
        if catl and byd:
            results.append(fmt_report(catl, "宁德时代(300750)"))
            results.append(fmt_report(byd, "比亚迪(002594)"))
            cr, br = catl[0], byd[0]
            items = [
                "\n\n── 核心指标对比 ──",
                f"{'指标':<20} {'宁德时代':<20} {'比亚迪':<20}",
            ]
            for k, cn, mode in [
                ("TOTALOPERATEREVE", "营收(亿)", "f"),
                ("PARENTNETPROFIT", "净利润(亿)", "f"),
                ("XSMLL", "毛利率(%)", "p"),
                ("XSJLL", "净利率(%)", "p"),
                ("ROEJQ", "ROE(%)", "p"),
                ("ZCFZL", "负债率(%)", "p"),
            ]:
                cv = safe_float(cr.get(k)) / 1e8 if mode == "f" else safe_float(cr.get(k))
                bv = safe_float(br.get(k)) / 1e8 if mode == "f" else safe_float(br.get(k))
                items.append(f"{cn:<20} {cv:<20.2f} {bv:<20.2f}")
            results.append("\n".join(items))
    if not results:
        results.append(fmt_report(fetch_financial("300750.SZ"), "宁德时代(300750)"))
    return "\n\n".join(results)
