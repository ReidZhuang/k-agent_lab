"""time_parser — 相对时间条件 → 具体日期范围

解析 agent_guide 输出的 condition 中的时间表达：
    "今天"          → 20260715 ~ 20260715
    "昨天"          → 20260714 ~ 20260714
    "最近5天"       → 20260711 ~ 20260715
    "最近一个月"    → 20260616 ~ 20260715
    "最近一个季度"  → 20260416 ~ 20260715
    "最新" / "上一期" → time_start="", time_end=""
    "上周收盘"      → 20260711 ~ 20260711
    "今天中午收盘"  → 20260715 ~ 20260715
"""
import re, datetime
from typing import Tuple


def _today_str() -> str:
    """返回今天日期 YYYYMMDD"""
    return datetime.date.today().strftime("%Y%m%d")


def _today_date() -> datetime.date:
    return datetime.date.today()


# ── 中文数字 → 阿拉伯数字 ──
_CN_NUMS = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _cn_digit(text: str) -> int | None:
    """尝试提取中文数字，如 '一个季度' → 1, '三十天' → 30"""
    # 单一数字
    if text in _CN_NUMS:
        return _CN_NUMS[text]
    # 十几
    m = re.match(r'^十([一二三四五六七八九])?$', text)
    if m:
        return 10 + _CN_NUMS.get(m.group(1), 0)
    # 几十
    m = re.match(r'^([二三四五六七八九])十([一二三四五六七八九])?$', text)
    if m:
        base = _CN_NUMS.get(m.group(1), 0) * 10
        return base + _CN_NUMS.get(m.group(2), 0) if m.group(2) else base
    return None


def _extract_number(text: str) -> int | None:
    """从文本开头提取数字（支持阿拉伯数字和中文数字）"""
    # 阿拉伯数字
    m = re.match(r'(\d+)', text)
    if m:
        return int(m.group(1))
    # 中文数字
    m = re.match(r'[一二两三四五六七八九十]+', text)
    if m:
        return _cn_digit(m.group(0))
    return None


def parse_condition(conditions: list[str]) -> tuple[str, str]:
    """解析 condition 列表 → (time_start, time_end)

    Returns:
        (start_date YYYYMMDD, end_date YYYYMMDD)
        空字符串表示不限制
    """
    cond_text = " ".join(conditions)
    today = _today_date()

    # ── 按优先级匹配 ──

    # 空条件 → 默认今天
    if not cond_text.strip():
        return _today_str(), _today_str()

    cond_text = cond_text.strip()

    # 1. "最新" / "上一期" / "最近一期" → 无时间限制
    if cond_text in ("最新", "上一期", "最近一期"):
        return "", ""

    # 2. "今天" / "今日" / "盘中"
    if cond_text in ("今天", "今日", "盘中", "今天收盘", "今天中午收盘", "上午收盘"):
        return _today_str(), _today_str()

    # 3. "昨天" / "昨日"
    if cond_text in ("昨天", "昨日", "上周收盘"):
        d = today - datetime.timedelta(days=1)
        return d.strftime("%Y%m%d"), d.strftime("%Y%m%d")

    # 4. "最近N天" / "近N日"
    m = re.search(r'(?:最近|近|过去)\s*([\d一二两三四五六七八九十]+)\s*(?:天|日|个交易日)', cond_text)
    if m:
        days = _extract_number(m.group(1))
        if days and days > 0:
            end = today
            start = end - datetime.timedelta(days=days)
            return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # 5. "最近N个月" / "近N月"
    m = re.search(r'(?:最近|近|过去)\s*([\d一二两三四五六七八九十]+)\s*(?:个月|月)', cond_text)
    if m:
        months = _extract_number(m.group(1))
        if months and months > 0:
            end = today
            m_total = end.year * 12 + end.month - months
            y = m_total // 12
            m_remain = m_total % 12
            if m_remain == 0:
                y -= 1
                m_remain = 12
            try:
                start = end.replace(year=y, month=m_remain, day=end.day)
            except ValueError:
                start = end.replace(year=y, month=m_remain, day=1)
            return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # 6a. "最近一周" / "近一周"
    if cond_text in ("最近一周", "近一周", "过去一周"):
        end = today
        start = end - datetime.timedelta(days=7)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # 6b. "最近一个季度" / "最近一季度"
    if cond_text in ("最近一个季度", "最近一季度", "上季度"):
        end = today
        # 当前季度起始月
        q_start_month = ((end.month - 1) // 3) * 3 + 1
        try:
            start = end.replace(month=q_start_month, day=1)
        except ValueError:
            start = end
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # 7. "最近N年" / "近N年"
    m = re.search(r'(?:最近|近|过去)\s*([\d一二两三四五六七八九十]+)\s*(?:年)', cond_text)
    if m:
        years = _extract_number(m.group(1))
        if years and years > 0:
            end = today
            start = end.replace(year=end.year - years)
            return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # 8. 具体日期 YYYYMMDD 或 YYYY-MM-DD
    m = re.search(r'(\d{4})-?(\d{2})-?(\d{2})', cond_text)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}", _today_str()

    # 默认为无时间约束
    return "", ""


def parse_conditions_list(conditions: list[str]) -> tuple[str, str]:
    """直接从 condition 列表解析时间范围"""
    return parse_condition(conditions)


def contains_time_condition(conditions: list[str]) -> bool:
    """检查 condition 中是否包含时间条件"""
    time_keywords = ["今天", "昨天", "最近", "近", "过去", "最新", "上一期"]
    for c in conditions:
        for kw in time_keywords:
            if kw in c:
                return True
    return False
