"""腾讯财经实时行情

接口: https://web.sqt.gtimg.cn/q={code}
免费，数据格式简单，速度较快

返回字段（共 88 项，经 ~ 分隔）:
  1: 股票名称
  2: 股票代码
  3: 当前价格
  4: 昨收
  5: 开盘价
  6: 成交量
  30: 时间戳 YYYYMMDDHHMMSS
  31: 涨跌额
  32: 涨跌幅%
  33: 最高价
  34: 最低价
  37: 成交额（万）★
  38: 换手率%
  39: 市盈率（动态）★
  41: 最高价
  42: 最低价
  43: 振幅%
  44: 总市值（亿）★
  45: 流通市值（亿）★
  46: 市净率★
  47: 涨停价
  48: 跌停价
  49: 量比

速度: ~0.1-0.3s 每次
"""

import requests

_URL = "https://web.sqt.gtimg.cn/q="
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _tencent_code(code: str) -> str:
    """将 6 位股票代码转为腾讯格式。"""
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    """获取多只股票的实时行情。

    Returns:
        {code: {field: value}, ...}
    """
    tcodes = ",".join(_tencent_code(c) for c in codes)
    try:
        r = requests.get(f"{_URL}{tcodes}", headers=_HEADERS, timeout=10)
    except Exception as e:
        return {c: {"error": str(e)} for c in codes}

    result = {}
    for line in r.text.strip().split(";"):
        line = line.strip()
        if not line or "~" not in line:
            continue
        fields = line.split("~")
        if len(fields) < 45:
            continue
        code = fields[2] if len(fields) > 2 else "?"
        try:
            result[code] = {
                "name": fields[1],
                "price": fields[3],
                "prev_close": fields[4],
                "open": fields[5],
                "volume": fields[6],
                "amount_wan": fields[37],       # 成交额（万）
                "high": fields[41],
                "low": fields[42],
                "turnover_rate": fields[38],    # 换手率 %
                "pe_dynamic": fields[39],       # 市盈率（动态）
                "amplitude": fields[43],        # 振幅 %
                "market_cap_total": fields[44], # 总市值（亿）
                "market_cap_flow": fields[45],  # 流通市值（亿）
                "pb": fields[46],               # 市净率
            }
        except (IndexError, ValueError):
            result[code] = {"error": "parse failed"}
    return result


def format_quote(code: str, name: str) -> str:
    """格式化为可读的行情+估值文本。"""
    quotes = fetch_quotes([code])
    q = quotes.get(code, {})
    if "error" in q:
        return f"（{name} 行情获取失败: {q['error']}）"

    try:
        price = float(q.get("price", 0))
        prev = float(q.get("prev_close", 0))
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
    except (ValueError, TypeError):
        change = 0
        change_pct = 0

    mc_total = q.get("market_cap_total", "N/A")
    if mc_total != "N/A":
        try:
            mc_total = f"{float(mc_total):.0f} 亿"
        except (ValueError, TypeError):
            pass

    mc_flow = q.get("market_cap_flow", "N/A")
    if mc_flow != "N/A":
        try:
            mc_flow = f"{float(mc_flow):.0f} 亿"
        except (ValueError, TypeError):
            pass

    amount = q.get("amount_wan", "N/A")
    if amount != "N/A":
        try:
            amount = f"{float(amount) / 10000:.1f} 亿"
        except (ValueError, TypeError):
            amount = f"{amount} 万"

    lines = [
        f"{name}({code}) 实时行情与估值",
        f"  当前价: {q.get('price', 'N/A')}",
        f"  涨跌幅: {change:+.2f} ({change_pct:+.2f}%)",
        f"  最高/最低: {q.get('high', 'N/A')} / {q.get('low', 'N/A')}",
        f"  总市值/流通市值: {mc_total} / {mc_flow}",
        f"  市盈率(动): {q.get('pe_dynamic', 'N/A')}",
        f"  市净率: {q.get('pb', 'N/A')}",
        f"  换手率: {q.get('turnover_rate', 'N/A')}%",
        f"  成交额: {amount}",
        f"\n(来源: 腾讯财经)",
    ]
    return "\n".join(lines)
