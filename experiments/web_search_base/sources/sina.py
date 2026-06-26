"""新浪财经实时行情

接口: http://hq.sinajs.cn/list={code}
免费，无密钥，数据有 15 分钟延迟

返回字段:
  0: 股票名称
  1: 今日开盘价
  2: 昨日收盘价
  3: 当前价格
  4: 今日最高价
  5: 今日最低价
  6: 竞买价（买一）
  7: 竞卖价（卖一）
  8: 成交股数
  9: 成交金额（元）
  10-29: 买五/卖五 档位
  30: 日期
  31: 时间

速度: ~0.1s 每次
"""

import requests
import time

_URL = "http://hq.sinajs.cn/list"
_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}

# 代码映射: stock code -> sina prefix
_PREFIX = {
    "sh": ["600", "601", "603", "605", "688"],
    "sz": ["000", "001", "002", "003", "300", "301"],
}


def _sina_code(code: str) -> str:
    """将 6 位股票代码转为新浪格式（如 sz300750）。"""
    for prefix, codes in _PREFIX.items():
        if any(code.startswith(c) for c in codes):
            return f"{prefix}{code}"
    return f"sz{code}"


def fetch_quotes(codes: list[str]) -> dict[str, dict]:
    """获取多只股票的实时行情。

    Args:
        codes: 股票代码列表，如 ["300750", "002594"]

    Returns:
        {code: {field: value}, ...}
    """
    sina_codes = ",".join(_sina_code(c) for c in codes)
    url = f"{_URL}={sina_codes}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.encoding = "gbk"
    except Exception as e:
        return {c: {"error": str(e)} for c in codes}

    result = {}
    for line in r.text.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        # 解析 var hq_str_sz300750="..."
        raw_data = line.split('"')[1] if '"' in line else ""
        fields = raw_data.split(",")

        # 从变量名中提取原始代码
        var_part = line.split("=")[0].split("_")[-1]
        # 去掉前缀得到 6 位代码
        actual_code = var_part[2:] if len(var_part) > 2 else var_part

        if len(fields) >= 32:
            result[actual_code] = {
                "name": fields[0],
                "open": fields[1],
                "prev_close": fields[2],
                "price": fields[3],
                "high": fields[4],
                "low": fields[5],
                "bid": fields[6],
                "ask": fields[7],
                "volume": fields[8],
                "amount": fields[9],
                "date": fields[30],
                "time": fields[31],
            }
        else:
            result[actual_code] = {"error": "insufficient data"}
    return result


def format_quote(code: str, name: str) -> str:
    """格式化为可读的行情文本。"""
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

    lines = [
        f"{name}({code}) 实时行情",
        f"  当前价: {q.get('price', 'N/A')}",
        f"  涨跌幅: {change:+.2f} ({change_pct:+.2f}%)",
        f"  最高/最低: {q.get('high', 'N/A')} / {q.get('low', 'N/A')}",
        f"  开盘/昨收: {q.get('open', 'N/A')} / {q.get('prev_close', 'N/A')}",
        f"  成交额: {q.get('amount', 'N/A')}",
        f"  时间: {q.get('date', '')} {q.get('time', '')}",
        f"\n(来源: 新浪财经, 数据延迟约 15 分钟)",
    ]
    return "\n".join(lines)
