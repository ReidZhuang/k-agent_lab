"""
realtime_fetcher — 实时快照类数据源的硬编码取数

替代 LLM 代码生成，用于 tencent/sina 等纯 HTTP GET 实时行情接口。
字段索引通过实际 API 响应 + 交叉运算验证得到。
"""
import requests

# ── 腾讯财经实时行情 ──
# API: https://web.sqt.gtimg.cn/q={code}
# 返回 ~ 分隔的 88 个字段，字段[0] 是前缀
# 验证方法：数学交叉运算（change=pct_chg*pre_close/100, amplitude=(high-low)/pre_close*100 等）
TENCENT_INDEX_MAP = {
    "name":         1,   # 股票名称
    "股票名称":       1,   # （中文别名）
    "code":         2,   # 股票代码
    "股票代码":       2,   # （中文别名）
    "price":        3,   # 当前价
    "当前价":         3,   # （中文别名）
    "pre_close":    4,   # 昨收价
    "pre_close":    4,   # 昨收价
    "open":         5,   # 开盘价
    "vol":          6,   # 成交量(手)
    "change":      31,   # 涨跌额 = price - pre_close ✅
    "pct_chg":     32,   # 涨跌幅% = change / pre_close * 100 ✅
    "high":        33,   # 最高价 ✅ ≥ price
    "low":         34,   # 最低价 ✅ ≤ price
    "turnover_rate": 38, # 换手率%
    "amplitude":   43,   # 振幅 = (high-low)/pre_close*100 ✅
    "振幅":          43,   # （中文别名）
    "float_mv":    44,   # 流通市值(亿元)
    "total_mv":    45,   # 总市值(亿元)
    "pb":          46,   # 市净率
    "pe":          52,   # 动态市盈率
    "amount":      57,   # 成交额(万元) ✅ 与 vol×均价 交叉验证
    "high_52w":    67,   # 52周最高
    "low_52w":     68,   # 52周最低
}
_TENCENT_URL = "https://web.sqt.gtimg.cn/q={code}"
_TENCENT_HEADERS = {"User-Agent": "Mozilla/5.0"}

# ── 新浪财经实时行情 ──
# API: http://hq.sinajs.cn/list={prefix}{code}
# 返回 GBK 编码，逗号分隔的 34 个字段
# 注意：新浪字段索引待完整验证
SINA_INDEX_MAP = {
    "name":         0,   # 股票名称
    "open":         1,   # 开盘价
    "pre_close":    2,   # 昨收价
    "price":        3,   # 当前价
    "high":         4,   # 最高价
    "low":          5,   # 最低价
    "buy1":         6,   # 买一价
    "sell1":        7,   # 卖一价
    "volume":       8,   # 成交量(股)
    "amount":       9,   # 成交额(元)
    "b1_v":        10,   # 买一量
    "buy1_dup":    11,   # 买一价(重复)
    "b2_v":        12,   # 买二量
    "buy2":        13,   # 买二价
    "b3_v":        14,   # 买三量
    "buy3":        15,   # 买三价
    "b4_v":        16,   # 买四量
    "buy4":        17,   # 买四价
    "b5_v":        18,   # 买五量
    "buy5":        19,   # 买五价
    "s1_v":        20,   # 卖一量
    "sell1_dup":   21,   # 卖一价(重复)
    "s2_v":        22,   # 卖二量
    "sell2":       23,   # 卖二价
    "s3_v":        24,   # 卖三量
    "sell3":       25,   # 卖三价
    "s4_v":        26,   # 卖四量
    "sell4":       27,   # 卖四价
    "s5_v":        28,   # 卖五量
    "sell5":       29,   # 卖五价
    "date":        30,   # 日期
    "time":        31,   # 时间
    "status":      32,   # 状态
}
_SINA_URL = "http://hq.sinajs.cn/list={prefix}{code}"
_SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0",
}


def _fmt_code(code_val: str) -> str:
    """300750.SZ → sz300750"""
    if "." in code_val:
        parts = code_val.split(".")
        sym, ex = parts[0], parts[1]
        ex_map = {"SH": "sh", "SZ": "sz"}
        return f"{ex_map.get(ex, ex.lower())}{sym}"
    return code_val


def fetch_tencent(code: str, field_names: list[str]) -> str:
    """腾讯实时行情 — 硬编码取数"""
    fmt_code = _fmt_code(code)
    url = _TENCENT_URL.format(code=fmt_code)
    try:
        resp = requests.get(url, headers=_TENCENT_HEADERS, timeout=10, allow_redirects=True)
        parts = resp.text.split("~")
    except Exception as e:
        return f"请求失败: {e}"

    result_parts = []
    for fn in field_names:
        idx = TENCENT_INDEX_MAP.get(fn)
        if idx is None:
            result_parts.append(f"  {fn}: 字段索引未验证")
            continue
        try:
            val = parts[idx].strip()
            result_parts.append(f"  {fn}: {val}")
        except (IndexError, ValueError):
            result_parts.append(f"  {fn}: 提取失败")
    return "\n".join(result_parts)


def fetch_sina(code: str, field_names: list[str]) -> str:
    """新浪实时行情 — 硬编码取数（数据延迟约 15 分钟）"""
    fmt_code = _fmt_code(code)
    url = _SINA_URL.format(prefix=fmt_code[:2], code=fmt_code[2:])
    try:
        resp = requests.get(url, headers=_SINA_HEADERS, timeout=10)
        resp.encoding = "gbk"
        text = resp.text.strip()
        data_part = text.split('=\"')
        if len(data_part) > 1:
            fields = data_part[1].rstrip('\";').split(",")
        else:
            return "解析失败: 响应格式异常"
    except Exception as e:
        return f"请求失败: {e}"

    result_parts = []
    for fn in field_names:
        idx = SINA_INDEX_MAP.get(fn)
        if idx is None:
            result_parts.append(f"  {fn}: 字段索引未验证")
            continue
        try:
            result_parts.append(f"  {fn}: {fields[idx]}")
        except IndexError:
            result_parts.append(f"  {fn}: 提取失败")
    return "\n".join(result_parts)


# ── 统一入口 ──

_PROTOCOL_FETCHERS = {
    "tencent": fetch_tencent,
    "sina": fetch_sina,
}


def is_realtime_protocol(protocol: str) -> bool:
    return protocol in _PROTOCOL_FETCHERS


def fetch(protocol: str, code: str, field_names: list[str]) -> str | None:
    """硬编码取数，不支持返回 None"""
    fetcher = _PROTOCOL_FETCHERS.get(protocol)
    if fetcher is None:
        return None
    return fetcher(code, field_names)
