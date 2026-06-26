"""东方财富数据中心 API

接口地址: https://datacenter.eastmoney.com/securities/api/data/get
数据表: RPT_F10_FINANCE_MAINFINADATA（主要财务数据）
字段数: 165 个

覆盖数据:
  - 利润表: 营收、营业利润、净利润、扣非净利润、毛利率、净利率
  - 资产负债表: 总资产、净资产、资产负债率
  - 每股指标: 每股收益、每股净资产、每股现金流
  - 增长率: 营收同比、净利润同比
  - ROE 等回报率指标

速度: ~0.3-0.5s 每次
"""

import time
import requests

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_BASE_URL = "https://datacenter.eastmoney.com/securities/api/data/get"
_SECUCODES = {
    "300750": "300750.SZ",
    "002594": "002594.SZ",
}


def _fetch_secucode(secucode: str) -> list[dict]:
    """从东方财富数据中心获取指定股票的财务数据。

    Args:
        secucode: 证券代码，如 "300750.SZ"

    Returns:
        list[dict]: 按报告期倒序的财务数据行
    """
    r = requests.get(
        _BASE_URL,
        params={
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": 1, "ps": 6, "st": "NOTICE_DATE", "sr": -1,
        },
        headers=_HEADERS,
        timeout=15,
    )
    return r.json().get("result", {}).get("data", [])


def format_financial_report(code: str, name: str) -> str:
    """获取并格式化财务数据报告。

    Args:
        code: 股票代码，如 "300750"
        name: 公司显示名称，如 "宁德时代"

    Returns:
        格式化后的报告文本
    """
    secucode = _SECUCODES.get(code, f"{code}.SZ")
    rows = _fetch_secucode(secucode)
    if not rows:
        return f"（{name} 暂无数据）"

    lines = [f"{name}({code}) 财务数据报告", "=" * 40]
    for row in rows[:4]:
        date = row.get("REPORT_DATE_NAME", "?")
        lines.append(f"\n── {date} ──")

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

        lines.append(f"营业收入: {f(row.get('TOTALOPERATEREVE', ''))} {fy(row.get('TOTALOPERATEREVETZ', ''))}")
        lines.append(f"营业利润: {f(row.get('OPERATEPROFIT', ''))}")
        lines.append(f"净利润: {f(row.get('PARENTNETPROFIT', ''))} {fy(row.get('PARENTNETPROFITTZ', ''))}")
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


def format_comparison(code_a: str, name_a: str, code_b: str, name_b: str) -> str:
    """获取两家公司的对比报告。

    Returns:
        格式化后的对比文本（含合并对比表）
    """
    rows_a = _fetch_secucode(_SECUCODES.get(code_a, f"{code_a}.SZ"))
    rows_b = _fetch_secucode(_SECUCODES.get(code_b, f"{code_b}.SZ"))
    if not rows_a or not rows_b:
        return "（对比数据不足）"

    report_a = format_financial_report(code_a, name_a)
    report_b = format_financial_report(code_b, name_b)

    ra, rb = rows_a[0], rows_b[0]

    def sf(v, mode="f"):
        val = 0
        if v is None:
            val = 0
        else:
            try:
                val = float(v)
            except (ValueError, TypeError):
                val = 0
        if mode == "f":
            return val / 1e8
        return val

    items = ["\n\n── 核心指标对比（最新报告期）──",
             f"{'指标':<24} {name_a:<22} {name_b:<22}",
             f"{'─'*24} {'─'*22} {'─'*22}"]
    for k, cn, mode in [
        ("TOTALOPERATEREVE", "营收(亿)", "f"),
        ("PARENTNETPROFIT", "净利润(亿)", "f"),
        ("XSMLL", "毛利率(%)", "p"),
        ("XSJLL", "净利率(%)", "p"),
        ("ROEJQ", "ROE(%)", "p"),
        ("ZCFZL", "负债率(%)", "p"),
    ]:
        cv = sf(ra.get(k), mode)
        bv = sf(rb.get(k), mode)
        items.append(f"{cn:<24} {cv:<22.2f} {bv:<22.2f}")

    return f"{report_a}\n\n{report_b}\n\n" + "\n".join(items)


def get_stock_list_from_query(query: str) -> list[tuple[str, str]]:
    """从查询文本中提取股票代码和公司名称。

    Args:
        query: 自然语言查询

    Returns:
        [(code, name), ...] 如 [("300750", "宁德时代")]
    """
    stocks = []
    if "宁德时代" in query or "CATL" in query.upper() or "300750" in query:
        stocks.append(("300750", "宁德时代(300750)"))
    if "比亚迪" in query or "002594" in query:
        stocks.append(("002594", "比亚迪(002594)"))
    return stocks
