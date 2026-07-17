"""
分层日期提取器 — 从 HTML / URL / 正文文本中提取文章发布日期。

置信度体系 (HIGH → MEDIUM → LOW)：

  HIGH (找到即停，无需交叉验证):
    1. JSON-LD script → datePublished / dateModified
    2. <meta property="article:published_time" content="...">
    3. <meta name="pubdate" content="...">
    4. <meta name="publishdate" content="...">
    5. <meta name="dc.date" content="...">  / <meta name="DC.date" ...>
    6. <meta itemprop="datePublished" content="...">
    7. <time datetime="..." itemprop="datePublished">
    8. URL 路径含 YYYY/MM/DD（常见于新浪/东财等中文新闻 URL）

  MEDIUM (需位置上下文锚定避免误抓):
    9. URL 含 YYYYMMDD 连续数字 (可能是文章 ID 而非日期, 标识 medium)
   10. 正文前 300 字匹配 "发布时[间间]：YYYY-MM-DD" 等模式
   11. 正文前 200 字匹配 "来源：xxx YYYY-MM-DD"
   12. DDG snippet 中的日期（英文格式 Jul 17, 2026）
   13. trafilatura metadata date（已有，保留）

  LOW (兜底):
   14. 正文前 200 字首次出现的任意日期模式（无关键词上下文锚定）

使用方式：
    extractor = DateExtractor()
    result = extractor.extract(html_text, url, snippet="...")
    # → {"date": "2026-07-17", "source": "article:published_time", "confidence": "high"}
"""
import re
import json


# ── 统一日期解析：多种格式 → "YYYY-MM-DD" ──

# 所有能匹配的日期格式（按优先级）
_DATE_PATTERNS = [
    # ISO datetime: 2026-07-17T20:46:00+08:00 / 2026-07-17 20:46:00
    (r"(\d{4})-(\d{1,2})-(\d{1,2})T\d{2}:\d{2}", 0),
    (r"(\d{4})-(\d{1,2})-(\d{1,2}) \d{2}:\d{2}", 0),
    # YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", 0),
    (r"(\d{4})/(\d{1,2})/(\d{1,2})", 0),
    (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", 0),
    # YYYY年M月D日 / YYYY年MM月DD日
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日", 0),
    # English format: Jul 17, 2026 / 17 Jul 2026
    (r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", 1),
    (r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", 2),
    # YYYYMMDD (8 digits, must be valid date)
    (r"(\d{4})(\d{2})(\d{2})", 0),
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _normalize_date(year: int, month: int, day: int) -> str | None:
    """Validate and normalize to YYYY-MM-DD. Returns None if invalid."""
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    # Basic day-in-month check
    days_in_month = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
                     7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    if day > days_in_month.get(month, 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_date_str(text: str, fmt_mode: int = 0) -> str | None:
    """Try to find and normalize a date in text. Returns YYYY-MM-DD or None."""
    if not text:
        return None
    for pattern, mode in _DATE_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        if mode == 0:
            # YYYY-MM-DD style
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif mode == 1:
            # "Jul 17, 2026"
            mo_name = m.group(1).lower()[:3]
            mo = _MONTH_MAP.get(mo_name, 0)
            d = int(m.group(2))
            y = int(m.group(3))
        elif mode == 2:
            # "17 Jul 2026"
            d = int(m.group(1))
            mo_name = m.group(2).lower()[:3]
            mo = _MONTH_MAP.get(mo_name, 0)
            y = int(m.group(3))
        else:
            continue
        result = _normalize_date(y, mo, d)
        if result:
            return result
    return None


def _parse_date_from_text(text: str) -> str | None:
    """Parse the first valid date from arbitrary text. Calls _parse_date_str."""
    return _parse_date_str(text)


# ── High-confidence extractors ──

def _extract_jsonld(html: str) -> str | None:
    """Extract date from JSON-LD script blocks."""
    # Find all <script type="application/ld+json">...</script>
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # Handle both single object and list/Graph
        items = data if isinstance(data, list) else [data]
        for item in items:
            for key in ("datePublished", "dateModified", "dateCreated",
                        "pubDate", "publish_date"):
                val = item.get(key)
                if val:
                    result = _parse_date_str(str(val))
                    if result:
                        return result
            # Also check @graph
            graph = item.get("@graph", [])
            for g_item in graph:
                for key in ("datePublished", "dateModified", "dateCreated"):
                    val = g_item.get(key)
                    if val:
                        result = _parse_date_str(str(val))
                        if result:
                            return result
    return None


def _extract_meta_tags(html: str) -> str | None:
    """Extract date from standard HTML meta tags."""
    # Patterns ordered by reliability
    meta_patterns = [
        # Open Graph / Facebook
        r'<meta\s+[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']',
        # itemprop datePublished (schema.org microdata)
        r'<meta\s+[^>]*itemprop=["\']datePublished["\'][^>]*content=["\']([^"\']+)["\']',
        # itemprop dateModified (fallback)
        r'<meta\s+[^>]*itemprop=["\']dateModified["\'][^>]*content=["\']([^"\']+)["\']',
        # name=pubdate / publishdate
        r'<meta\s+[^>]*name=["\'](?:pubdate|publishdate)["\'][^>]*content=["\']([^"\']+)["\']',
        # DC.date / dc.date
        r'<meta\s+[^>]*name=["\'](?:dc\.date|DC\.date)["\'][^>]*content=["\']([^"\']+)["\']',
        # weibo article create_at
        r'<meta\s+[^>]*name=["\']weibo:article:create_at["\'][^>]*content=["\']([^"\']+)["\']',
    ]
    for pattern in meta_patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            result = _parse_date_str(m.group(1).strip())
            if result:
                return result

    # Also try reversed attribute order (content before name/property)
    meta_patterns_reversed = [
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time["\']',
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*itemprop=["\']datePublished["\']',
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*itemprop=["\']dateModified["\']',
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*name=["\'](?:pubdate|publishdate)["\']',
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*name=["\'](?:dc\.date|DC\.date)["\']',
    ]
    for pattern in meta_patterns_reversed:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            result = _parse_date_str(m.group(1).strip())
            if result:
                return result

    return None


def _extract_time_tag(html: str) -> str | None:
    """Extract date from HTML5 <time datetime='...'> element."""
    # <time datetime="2026-07-17" ...>
    m = re.search(
        r'<time\s+[^>]*datetime=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if m:
        return _parse_date_str(m.group(1).strip())
    return None


def _extract_url_date(url: str) -> str | None:
    """Extract date from URL path patterns. HIGH confidence if YYYY/MM/DD in path."""
    if not url:
        return None
    # Priority: YYYY/MM/DD in URL path
    path = url.split("://", 1)[-1] if "://" in url else url

    # Pattern 1: /YYYY/MM/DD/  — common in Chinese news URLs
    m = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', path)
    if m:
        return _normalize_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Pattern 2: /YYYY-MM-DD/  or _YYYY-MM-DD
    m = re.search(r'[/_](\d{4})-(\d{1,2})-(\d{1,2})[/_]', path)
    if m:
        return _normalize_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Pattern 3: /YYYYMMDD  (8 consecutive digits in URL path)
    # Conservatively check only after the domain (in the path)
    path_part = path.split("/", 1)[1] if "/" in path else ""
    m = re.search(r'/(\d{4})(\d{2})(\d{2})', path_part)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Must start with valid year prefix (20xx or 19xx)
        if 1900 <= y <= 2100:
            return _normalize_date(y, mo, d)

    return None


# ── Medium-confidence extractors ──

def _extract_in_body_prefix(body_text: str, max_chars: int = 300) -> tuple[str | None, str]:
    """
    Scan body text first N chars for date-prefix keywords like "发布时间".
    Returns (date, source_detail) or (None, "").
    """
    if not body_text:
        return None, ""

    prefix = body_text[:max_chars].strip()

    # Pattern 1: "发布时间：YYYY-MM-DD HH:MM"  or "发布日期：YYYY-MM-DD"
    # Common across most Chinese news portals
    markers = [
        r'发布时间[：:]?\s*',
        r'发布日期[：:]?\s*',
        r'发表时间[：:]?\s*',
        r'更新时间[：:]?\s*',
        r'时间[：:]?\s*',           # generic time, less specific
    ]

    # Try each marker with an immediately following date
    for marker in markers:
        # Standard date: YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
        m = re.search(marker + r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', prefix)
        if m:
            result = _parse_date_str(m.group(1).strip())
            if result:
                return result, f"body_prefix_{m.group(0)[:4]}"
        # Chinese date: YYYY年M月D日 / YYYY年MM月DD日
        m = re.search(marker + r'(\d{4})年(\d{1,2})月(\d{1,2})日', prefix)
        if m:
            result = _normalize_date(
                int(m.group(1)), int(m.group(2)), int(m.group(3))
            )
            if result:
                return result, f"body_prefix_cn_{m.group(0)[:4]}"

    # Pattern 2: "来源：xxx YYYY-MM-DD"  or "出处：xxx YYYY-MM-DD"
    m = re.search(r'[来|出][源|自|处][：:]?\s*[^\d\n]*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', prefix)
    if m:
        result = _parse_date_str(m.group(1).strip())
        if result:
            return result, "body_source_ref"

    return None, ""


def _extract_url_date_medium(url: str) -> str | None:
    """
    URL dates from query params or ambiguous patterns.
    Only called if HIGH confidence URL extractors didn't match.
    """
    if not url:
        return None
    path = url.split("://", 1)[-1] if "://" in url else url

    # Query parameter: ?date=YYYY-MM-DD  or ?t=YYYYMMDD
    m = re.search(r'[?&](?:date|time|t|p)=(\d{4}[-]?\d{2}[-]?\d{2})', path)
    if m:
        raw = m.group(1)
        # Clean up separators
        raw_clean = raw.replace("-", "").replace("/", "").replace(".", "")
        if len(raw_clean) == 8:
            y, mo, d = int(raw_clean[:4]), int(raw_clean[4:6]), int(raw_clean[6:8])
            return _normalize_date(y, mo, d)

    return None


def _extract_ddg_snippet(snippet: str) -> str | None:
    """Extract date from DDG snippet (e.g. 'Jul 17, 2026 — content...')."""
    if not snippet:
        return None
    # Try English format at the start of snippet: "Jul 17, 2026 — ..."
    m = re.match(r'^([A-Z][a-z]+ \d{1,2}, \d{4})\s*[–—-]', snippet)
    if m:
        return _parse_date_str(m.group(1))
    return None


# ── Low-confidence extractors ──

def _extract_body_fallback(body_text: str, max_chars: int = 200) -> str | None:
    """
    Last resort: find any date pattern in the first N chars of body text.
    No keyword anchoring — high risk of false positive.
    """
    if not body_text:
        return None
    prefix = body_text[:max_chars].strip()
    return _parse_date_str(prefix)


# ── Main extraction API ──

def extract_date(html: str, url: str = "", snippet: str = "",
                 body_text: str | None = None) -> dict:
    """
    Main entry point: layered date extraction.

    Args:
        html: Full HTML text of the article page
        url: Article URL (for URL-based date extraction)
        snippet: DDG search snippet (for snippet-based date extraction)
        body_text: Extracted body text (for body-prefix extraction).
                   Optional for Phase 1, available in Phase 2.

    Returns:
        {"date": "2026-07-17" or "", "source": "...", "confidence": "high"|"medium"|"low"|""}
        If no date found, confidence="", date=""
    """
    # ── Layer 1: HIGH confidence ──
    # (1) JSON-LD
    d = _extract_jsonld(html)
    if d:
        return {"date": d, "source": "json-ld", "confidence": "high"}

    # (2) Meta tags
    d = _extract_meta_tags(html)
    if d:
        return {"date": d, "source": "meta_tag", "confidence": "high"}

    # (3) <time datetime>
    d = _extract_time_tag(html)
    if d:
        return {"date": d, "source": "time_tag", "confidence": "high"}

    # (4) URL path date (YYYY/MM/DD or YYYY-MM-DD in path)
    d = _extract_url_date(url)
    if d:
        return {"date": d, "source": "url_path", "confidence": "high"}

    # ── Layer 2: MEDIUM confidence ──
    # (5) Body prefix with keyword context
    if body_text:
        d, src_detail = _extract_in_body_prefix(body_text)
        if d:
            return {"date": d, "source": src_detail, "confidence": "medium"}

    # (6) URL query param date
    d = _extract_url_date_medium(url)
    if d:
        return {"date": d, "source": "url_param", "confidence": "medium"}

    # (7) DDG snippet
    d = _extract_ddg_snippet(snippet)
    if d:
        return {"date": d, "source": "snippet", "confidence": "medium"}

    # ── Layer 3: LOW confidence ──
    # (8) Body fallback (first 200 chars, any date pattern)
    if body_text:
        d = _extract_body_fallback(body_text)
        if d:
            return {"date": d, "source": "body_fallback", "confidence": "low"}

    return {"date": "", "source": "", "confidence": ""}


def extract_date_fast(html: str, url: str = "", snippet: str = "") -> dict:
    """
    Fast variant: HIGH confidence sources only (no body_text needed).
    Suitable for Phase 1 (preview) before trafilatura runs.
    """
    d = _extract_jsonld(html)
    if d:
        return {"date": d, "source": "json-ld", "confidence": "high"}

    d = _extract_meta_tags(html)
    if d:
        return {"date": d, "source": "meta_tag", "confidence": "high"}

    d = _extract_time_tag(html)
    if d:
        return {"date": d, "source": "time_tag", "confidence": "high"}

    d = _extract_url_date(url)
    if d:
        return {"date": d, "source": "url_path", "confidence": "high"}

    # Still try medium sources that don't need body_text
    d = _extract_url_date_medium(url)
    if d:
        return {"date": d, "source": "url_param", "confidence": "medium"}

    d = _extract_ddg_snippet(snippet)
    if d:
        return {"date": d, "source": "snippet", "confidence": "medium"}

    return {"date": "", "source": "", "confidence": ""}


def upgrade_date_with_body(date_info: dict, body_text: str) -> dict:
    """
    Upgrade a Phase 1 date result with body-text-based extraction.
    Only upgrades if confidence is lower than 'medium'.
    Returns the same dict if already high/medium, or updates if body provides better.
    """
    if date_info.get("confidence") in ("high", "medium"):
        return date_info  # already good enough

    # Try body prefix (medium)
    d, src_detail = _extract_in_body_prefix(body_text)
    if d:
        return {"date": d, "source": src_detail, "confidence": "medium"}

    # Try body fallback (low)
    d = _extract_body_fallback(body_text)
    if d:
        return {"date": d, "source": "body_fallback", "confidence": "low"}

    return date_info  # no improvement
