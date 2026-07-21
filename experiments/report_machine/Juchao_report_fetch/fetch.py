"""
巨潮盘后公告提取 API

从巨潮资讯网获取指定股票在指定日期范围内的盘后公告，
下载 PDF 并提取文字内容。

用法:
    from fetch import fetch_announcements

    # 单只股票
    result = fetch_announcements("300395", start_date="20260720", end_date="20260721")

    # 多只股票
    result = fetch_announcements(["300395", "300750"], start_date="20260720", end_date="20260721")

    # 返回格式: {stock_code: [公告文本1, 公告文本2, ...]}
    # 无公告时: {stock_code: None}
"""

import re
import time
import logging
from typing import Optional
from io import BytesIO

import akshare as ak
import requests
from pypdf import PdfReader

logger = logging.getLogger("juchao_fetch")

# ===== 巨潮 API 配置 =====

CNINFO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "http://www.cninfo.com.cn/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    ),
    "Referer": "http://www.cninfo.com.cn/",
}

# 请求间隔（秒），避免对巨潮接口造成压力
REQUEST_INTERVAL = 0.3

# PDF 正文截断阈值（中文字数）
MAX_CHINESE_CHARS = 3000
TRUNCATION_NOTICE = f"[截断，只保留{MAX_CHINESE_CHARS}字]"


# ===== 核心函数 =====

def fetch_announcements(
    symbols: str | list[str],
    start_date: str,
    end_date: str,
    include_pdf_text: bool = True,
) -> dict:
    """获取指定股票在指定日期范围内的盘后公告

    Args:
        symbols: 股票代码或股票代码列表（如 "300395" 或 ["300395", "300750"]）
        start_date: 开始日期，格式 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        include_pdf_text: 是否提取 PDF 正文文字（默认 True）

    Returns:
        {stock_code: [公告文本1, 公告文本2, ...]}
        无公告时: {stock_code: None}
    """
    if isinstance(symbols, str):
        symbols = [symbols]

    # 统一日期格式为 YYYYMMDD（akshare 此接口需要）
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)

    result = {}
    for sym in symbols:
        logger.info(f"正在获取 {sym} 的公告 ({start} ~ {end})")
        texts = _fetch_single(sym, start, end, include_pdf_text)
        result[sym] = texts if texts else None
        time.sleep(REQUEST_INTERVAL)

    return result


# ===== 内部实现 =====

def _normalize_date(date_str: str) -> str:
    """统一为 YYYYMMDD 格式"""
    cleaned = re.sub(r"\D", "", date_str)
    if len(cleaned) == 8:
        return cleaned
    raise ValueError(f"无法解析日期: {date_str}")


def _fetch_single(
    symbol: str,
    start_date: str,
    end_date: str,
    include_pdf_text: bool,
) -> list[str] | None:
    """获取单只股票的公告文本列表"""
    try:
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        err_msg = str(e)
        # akshare 在无公告时会抛 KeyError（列选择失败）或 JSON 解析错误
        # 这些都是"无公告"的正常信号，不是真的异常
        if "None of [Index" in err_msg or "Expecting value" in err_msg:
            logger.info(f"  {symbol}: 无公告（akshare 返回空集）")
            return None
        logger.warning(f"{symbol} 调用 akshare 失败: {e}")
        return None

    if df is None or df.empty:
        logger.info(f"  {symbol}: 无公告")
        return None

    logger.info(f"  {symbol}: 找到 {len(df)} 条公告")

    texts = []
    for i, row in df.iterrows():
        title = str(row.get("公告标题", ""))
        link = str(row.get("公告链接", ""))
        date = str(row.get("公告时间", ""))

        text = _build_announcement_text(
            symbol=symbol,
            title=title,
            date=date,
            link=link,
            extract_pdf=include_pdf_text,
        )
        if text:
            texts.append(text)

        # 公告间间隔
        time.sleep(REQUEST_INTERVAL)

    return texts if texts else None


def _build_announcement_text(
    symbol: str,
    title: str,
    date: str,
    link: str,
    extract_pdf: bool,
) -> str | None:
    """构建单条公告的文本"""
    lines = [f"公告: {title}", f"日期: {date}"]

    # 从链接提取 announcementId 和 announceTime
    ann_id = _extract_param(link, "announcementId")
    ann_time = _extract_param(link, "announcementTime")

    if ann_id and ann_time:
        pdf_text = _fetch_pdf_text(ann_id, date)
        if pdf_text:
            lines.append("--- PDF 正文 ---")
            lines.append(pdf_text)
    else:
        logger.debug(f"  无法解析公告链接参数: {link}")

    return "\n".join(lines)


def _extract_param(url: str, key: str) -> str | None:
    """从 URL 查询参数中取值"""
    m = re.search(rf"{key}=([^&]+)", url)
    return m.group(1) if m else None


def _fetch_pdf_text(announce_id: str, announce_time: str) -> str | None:
    """下载 PDF 并提取文字"""
    # Step 1: 调用 bulletin_detail 获取 PDF URL
    pdf_url = _get_pdf_url(announce_id, announce_time)
    if not pdf_url:
        return None

    # Step 2: 下载 PDF
    try:
        resp = requests.get(
            pdf_url, headers=PDF_HEADERS, timeout=30, allow_redirects=True
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "application/pdf" not in content_type and "octet-stream" not in content_type:
            logger.debug(f"  非 PDF 内容: {content_type}")
            return None
    except Exception as e:
        logger.debug(f"  PDF 下载失败: {e}")
        return None

    # Step 3: 用 pypdf 提取文字
    try:
        reader = PdfReader(BytesIO(resp.content))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text.strip())
        full_text = "\n".join(pages)
        return _clean_text(full_text) if full_text.strip() else None
    except Exception as e:
        logger.debug(f"  PDF 文字提取失败: {e}")
        return None


def _get_pdf_url(announce_id: str, announce_time: str) -> str | None:
    """通过巨潮 bulletin_detail 接口获取 PDF 直链"""
    url = "http://www.cninfo.com.cn/new/announcement/bulletin_detail"
    data = {
        "announceId": announce_id,
        "flag": "true",
        "announceTime": announce_time,
    }
    try:
        resp = requests.post(
            url, data=data, headers=CNINFO_HEADERS, timeout=15
        )
        resp.raise_for_status()
        payload = resp.json()
        # 优先用 fileUrl（完整直链），其次用 adjunctUrl 拼接
        file_url = payload.get("fileUrl") or ""
        adjunct_url = (
            payload.get("announcement", {}).get("adjunctUrl") or ""
        )
        if file_url:
            return file_url
        if adjunct_url:
            return f"http://static.cninfo.com.cn/{adjunct_url}"
        return None
    except Exception as e:
        logger.debug(f"  获取 PDF URL 失败: {e}")
        return None


def _clean_text(text: str) -> str:
    """清理提取的文字，并截断超出 MAX_CHINESE_CHARS 的部分"""
    # 去除多余空白行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # 截断：统计中文字数，超过 MAX_CHINESE_CHARS 则截断
    text = _truncate_by_chinese_count(text)

    return text


def _truncate_by_chinese_count(text: str) -> str:
    """按中文字数截断，超过 MAX_CHINESE_CHARS 时在末尾追加截断提示

    Args:
        text: 原始文本

    Returns:
        截断后的文本（超过阈值时末尾追加 [截断，只保留3000字]）
    """
    if not text:
        return text

    chinese_chars = re.findall(r"[一-鿿]", text)
    if len(chinese_chars) <= MAX_CHINESE_CHARS:
        return text

    # 需要截断：找到第 MAX_CHINESE_CHARS 个中文字所在位置
    count = 0
    cut_pos = 0
    for i, ch in enumerate(text):
        if "一" <= ch <= "鿿":
            count += 1
            if count == MAX_CHINESE_CHARS:
                cut_pos = i + 1
                break

    truncated = text[:cut_pos].strip()
    truncated += "\n\n" + TRUNCATION_NOTICE
    return truncated


# ===== 快捷函数 =====

def fetch_single(symbol: str, start_date: str, end_date: str) -> str | None:
    """获取单只股票的公告文本（多条合并）

    Returns:
        合并后的公告文本，无公告则返回 None
    """
    result = fetch_announcements(symbol, start_date, end_date)
    texts = result.get(symbol)
    if not texts:
        return None
    return "\n\n==========\n\n".join(texts)


# ===== 自测 =====

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("测试 1: 菲利华 — 有公告")
    print("=" * 60)
    r1 = fetch_announcements("300395", start_date="20260720", end_date="20260721")
    for code, texts in r1.items():
        if texts:
            print(f"\n{code}: {len(texts)} 条公告")
            for t in texts:
                print(f"\n{t[:500]}...")
                print("---")
        else:
            print(f"\n{code}: 无公告")

    print("\n" + "=" * 60)
    print("测试 2: 广生堂 — 假设无公告范围（回测2025年）")
    print("=" * 60)
    r2 = fetch_announcements("300436", start_date="20250101", end_date="20250105")
    for code, texts in r2.items():
        if texts:
            print(f"\n{code}: {len(texts)} 条公告")
        else:
            print(f"\n{code}: None（无公告）")

    print("\n" + "=" * 60)
    print("测试 3: 多只股票混合")
    print("=" * 60)
    r3 = fetch_announcements(
        ["300395", "300436"],
        start_date="20260720",
        end_date="20260721",
    )
    for code, texts in r3.items():
        if texts:
            print(f"\n{code}: {len(texts)} 条公告")
        else:
            print(f"\n{code}: None（无公告）")
