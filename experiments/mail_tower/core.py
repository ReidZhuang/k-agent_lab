"""
mail_tower 核心引擎 — 引擎分发 + mode=list + 截断8000

新增:
  - engine 参数: "ddg" | "sinafin" | "baidufin" | "thsfin" | "dcfin" | "juchao"
  - mode="list": Phase 0 返回列表即止，Phase 1 后台提取正文（截断8000）
  - juchao: 巨潮盘后公告，列表仅标题/日期（精确到天），后台异步下载PDF提取正文
  - _known_date: 跳过日期提取，直接使用 sinafin/thsfin/dcfin 精确日期
  - 正文截断：超过 max_body_chars 字截断，尾部加截断标记
"""
import json, os, sys, time, re, asyncio, threading
from dataclasses import dataclass, field
from collections import defaultdict

import httpx

# ── 配置 ──
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

_SEARCH_PARENT = os.path.join(os.path.dirname(__file__), "..")
if _SEARCH_PARENT not in sys.path:
    sys.path.insert(0, _SEARCH_PARENT)
from search_engine import search as search_web

from date_extractor import extract_date_fast, upgrade_date_with_body
from filter import ArticleFilter

# ── 提前导入（避免并发 import 竞态） ──
import trafilatura  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from readability import Document  # noqa: E402
import html2text  # noqa: E402
try:
    from playwright.sync_api import sync_playwright
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False

OLLAMA_URL = f"{cfg['ollama']['endpoint']}/api/generate"
MODEL = cfg["ollama"]["models"]["default"]
MAX_PARALLEL = cfg["ollama"]["max_parallel"]
OLLAMA_TIMEOUT = cfg["ollama"]["timeout"]
OLLAMA_TEMP = cfg["ollama"]["temperature"]
OLLAMA_NUM_PREDICT = cfg["ollama"]["num_predict"]
SPLIT_MAX_TOKENS = cfg["split"]["max_tokens"]
MAX_BODY_CHARS = cfg["extraction"].get("max_body_chars", 8000)


# ============================================================
# ChunkUnit (保持与 v1.0/v2.0 兼容)
# ============================================================
@dataclass
class ChunkUnit:
    article_id: str
    title: str
    url: str
    date: str
    snippet: str
    source: str
    chunk_index: int
    total_chunks: int
    paragraphs: list
    para_offset: int

    @property
    def is_splitted(self) -> bool:
        return self.total_chunks > 1

    @property
    def position(self) -> str:
        if self.total_chunks <= 1:
            return ""
        if self.chunk_index == 0:
            return "开头"
        if self.chunk_index == self.total_chunks - 1:
            return "结尾"
        return "中间"


# ============================================================
# 正文截断
# ============================================================

_TRUNCATE_MARKER = "\n\n[截断 全文长于8000字]\n"

# 空白字符占比阈值 — 超过此比例认为"大量空白"，触发清理
WHITESPACE_RATIO_THRESHOLD = 0.5


def has_excessive_whitespace(text: str) -> bool:
    """检测正文是否包含大量空白字符。

    计算逻辑：空白字符数 / 总字符数 > threshold 即判定为过量。
    """
    if not text:
        return False
    total = len(text)
    ws = sum(1 for c in text if c.isspace())
    ratio = ws / total
    return ratio > WHITESPACE_RATIO_THRESHOLD


def clean_excessive_whitespace(text: str) -> str:
    """清理正文中的大量空白字符。

    - 连续的空白行（3个以上换行）压缩为2个
    - 行首行尾空白去除
    - 全空白行删除
    - 多余的水平空白压缩
    """
    if not text:
        return text

    # 1. 按行处理
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # 去除行首行尾空白
        line = line.strip()
        # 跳过全空行
        if not line:
            continue
        # 压缩行内连续空格（保留单个空格）
        import re as _re
        line = _re.sub(r'[ \t]+', ' ', line)
        cleaned.append(line)

    # 2. 段落间保留一个空行
    result = '\n\n'.join(cleaned)

    # 3. 如果清理后太短（<10% 原长），说明原内容本身就少，保留原文前500字示意
    if len(result) < len(text) * 0.05 and len(text) > 1000:
        # 截取原文可见字符的前500
        visible = ''.join(c for c in text if not c.isspace())[:500]
        result = visible + "\n\n[正文包含大量格式空白，已压缩显示]"

    return result


def truncate_body(body_text: str, max_chars: int = MAX_BODY_CHARS) -> tuple[str, bool]:
    """如果正文超过 max_chars，截断并添加标记。

    Returns:
        (处理后的正文, 是否被截断)
    """
    if not body_text or len(body_text) <= max_chars:
        return body_text, False
    truncated = body_text[:max_chars] + _TRUNCATE_MARKER
    return truncated, True


# ============================================================
# PDF 提取（公告页面 Fallback）
# ============================================================

def _find_pdf_urls_in_html(html: str) -> list[str]:
    """从 HTML 中提取所有 PDF 下载链接。

    覆盖以下场景:
      - <a href="...pdf">
      - <iframe src="...pdf">
      - <embed src="...pdf">
      - JavaScript: pdfsource = '...', otherSource = '...'
      - 任何含 .pdf 的 URL
    """
    urls = []
    seen = set()

    # 1. HTML 标签中的 PDF 链接
    for pat in [
        r'<a[^>]*href\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
        r'<iframe[^>]*src\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
        r'<embed[^>]*src\s*=\s*["\']([^"\']*\.pdf[^"\']*)["\']',
    ]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            u = m.group(1).strip()
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    # 2. JavaScript 中常见的 PDF url 变量
    for pat in [
        r'''pdfsource\s*=\s*['"]([^'"]+\.pdf[^'"]*)['"]''',
        r'''otherSource\s*=\s*['"]([^'"]+\.pdf[^'"]*)['"]''',
        r'''pdfUrl\s*[:=]\s*['"]([^'"]+\.pdf[^'"]*)['"]''',
        r'''fileUrl\s*[:=]\s*['"]([^'"]+\.pdf[^'"]*)['"]''',
    ]:
        for m in re.finditer(pat, html, re.IGNORECASE):
            u = m.group(1).strip()
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    # 3. 确保 URL 有 scheme（部分页面省略协议前缀）
    resolved = []
    for u in urls:
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = "https:" + u   # 对于公告类页面通常同站 https
        if u.startswith("http"):
            resolved.append(u)

    return resolved


def _extract_pdf_from_url(pdf_url: str, timeout: int = 30) -> str:
    """下载 PDF 并用 pypdf 提取文字。

    Returns:
        提取的文本，失败返回空字符串。
    """
    try:
        import requests
        from io import BytesIO
        from pypdf import PdfReader
        from urllib.parse import quote, urlparse, urlunparse

        # URL 编码 — 处理 URL 路径中的中文字符（requests 的 latin-1 header 限制）
        parsed = urlparse(pdf_url)
        encoded_path = "".join(
            quote(ch, safe="/:@!$&'()*+,;=-._~?#") if ord(ch) > 127 else ch
            for ch in parsed.path
        )
        safe_url = urlunparse((
            parsed.scheme, parsed.netloc, encoded_path,
            parsed.params, parsed.query, parsed.fragment
        ))

        resp = requests.get(
            safe_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "http://www.cninfo.com.cn/",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # 内容类型检查
        ct = resp.headers.get("Content-Type", "")
        if "application/pdf" not in ct and "octet-stream" not in ct:
            # 有时 PDF 的 Content-Type 缺失但仍可解析
            if not resp.content[:8].startswith(b"%PDF-"):
                return ""

        reader = PdfReader(BytesIO(resp.content))
        pages = []
        for page in reader.pages:
            pt = page.extract_text()
            if pt:
                pages.append(pt.strip())

        if not pages:
            return ""

        full = "\n".join(pages)

        # 空白治理（与正文提取一致）
        if has_excessive_whitespace(full):
            full = clean_excessive_whitespace(full)

        return full

    except Exception:
        return ""


_BOILERPLATE_MARKERS = [
    "无法在线阅读",
    "下载原文",
    "pdfsource",
    "当前公告无法在线",
    "请下载原文",
    "该公告暂不支持在线浏览",
]


def _is_pdf_announcement_page(body_text: str) -> bool:
    """检测正文是否仅为 PDF 公告占位提示。"""
    if not body_text or len(body_text.strip()) < 200:
        return True
    text_lower = body_text.lower()
    for marker in _BOILERPLATE_MARKERS:
        if marker.lower() in text_lower:
            return True
    return False


def _try_extract_pdf_from_html(html: str, timeout: int = 30) -> str:
    """从 HTML 中找出 PDF 链接并尝试提取正文。

    Args:
        timeout: 每个 PDF URL 的下载+解析超时（秒）

    Returns:
        提取的 PDF 正文（最长的那个 PDF 的内容），失败返回空字符串。
    """
    pdf_urls = _find_pdf_urls_in_html(html)
    if not pdf_urls:
        return ""

    best_text = ""
    for url in pdf_urls:
        text = _extract_pdf_from_url(url, timeout=timeout)
        if len(text) > len(best_text):
            best_text = text

    return best_text


def extract_pdf_from_article(article: dict, timeout: int = 15) -> str:
    """从文章 dict 中提取 PDF 正文（用于后台异步提取）。

    Args:
        article: phase1_fetch_and_extract 返回的文章 dict（需含 html 字段）
        timeout: 每个 PDF URL 的下载+解析超时（秒）

    Returns:
        提取的正文（失败返回空字符串）
    """
    html = article.get("html", "")
    if not html:
        return ""
    return _try_extract_pdf_from_html(html, timeout=timeout)


async def _fetch_single(url: str) -> tuple[str, str]:
    """下载单个 URL, 返回 (html_text, error_or_blank).

    自动检测编码（支持 GBK/GB2312/GB18030 等中文编码）。
    """
    _t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            raw = resp.content
            text = _decode_html_bytes(raw, resp.encoding)
            _elapsed = int((time.time() - _t0) * 1000)
            from reporting.debug_log import DLog
            DLog.log("fetch_single_done", url=url[:100], status=resp.status_code,
                     html_len=len(text), elapsed_ms=_elapsed)
            return text, ""
    except Exception as e:
        _elapsed = int((time.time() - _t0) * 1000)
        from reporting.debug_log import DLog
        DLog.log("fetch_single_error", url=url[:100], error=str(e)[:80],
                 elapsed_ms=_elapsed)
        return "", str(e)


def _decode_html_bytes(raw: bytes, declared_encoding: str | None = None) -> str:
    """解码 HTML 字节数据，自动检测编码（GBK/GB2312/GB18030/UTF-8）。"""
    # 优先使用响应头声明的编码
    if declared_encoding:
        try:
            return raw.decode(declared_encoding)
        except (UnicodeDecodeError, LookupError):
            pass

    # 常见中文编码依次尝试
    for enc in ["gb18030", "gbk", "gb2312", "utf-8", "latin-1"]:
        try:
            text = raw.decode(enc)
            # 如果解码后包含大量替换字符/乱码特征，继续尝试下一个编码
            if _looks_corrupted(text, enc):
                continue
            return text
        except UnicodeDecodeError:
            continue

    # 兜底
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return raw.decode("latin-1")


def _looks_corrupted(text: str, encoding: str) -> bool:
    """粗略检测解码是否乱码：统计替换字符和不可见字符的占比。"""
    if not text:
        return True
    bad = sum(1 for c in text if c in ("�", "￾", "￿") or
              (ord(c) >= 0x80 and not c.isprintable() and not c.isspace()))
    # 如果坏字符占比高，认为是乱码
    if bad > max(10, len(text) * 0.05):
        return True
    # 如果声明是中文编码但解码后中文字符极少，也可能是乱码
    chinese = sum(1 for c in text if '一' <= c <= '鿿')
    if encoding in ("gb18030", "gbk", "gb2312") and chinese < max(5, len(text) * 0.01):
        return True
    return False


def _extract_body_from_html(html: str) -> tuple[str, str, list]:
    """
    用 trafilatura 从 HTML 提取正文。返回 (body_text, date_from_meta, paragraphs).

    提取链：trafilatura → readability → PDF 下载兜底。
    """
    meta_json = trafilatura.extract(html, output_format='json', include_images=False, with_metadata=True)
    date_from_meta = ""
    if meta_json:
        try:
            meta = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
            date_from_meta = meta.get("date", "") or ""
        except Exception:
            pass

    body = trafilatura.extract(html, output_format='markdown', include_images=False)
    if not body or len(body.strip()) < 200:
        try:
            from readability import Document
            import html2text
            doc = Document(html)
            h = html2text.HTML2Text()
            h.body_width = 0
            h.ignore_links = False
            h.ignore_images = True
            body = h.handle(doc.summary()).strip()
        except Exception:
            pass

    # PDF 下载兜底：trafilatura + readability 都失败时，尝试提取页面中的 PDF 链接
    if not body or len(body.strip()) < 200:
        try:
            pdf_text = _try_extract_pdf_from_html(html, timeout=15)
            if pdf_text:
                body = pdf_text
        except Exception:
            pass

    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()] if body else []
    return body or "", date_from_meta, paragraphs


# ============================================================
# Phase 1.5: Playwright 兜底提取（当 trafilatura 提取失败时）
# ============================================================

def _extract_with_playwright(urls: list[str]) -> dict[str, str]:
    """
    用 Playwright 渲染页面后提取正文。作为 trafilatura 提取失败的兜底。

    用 ThreadPoolExecutor + 60s 总超时防止卡死。
    原版含 `pass` 死代码导致 Playwright 从未执行，此版本已修复。

    Args:
        urls: 需要提取的 URL 列表

    Returns:
        {url: body_text, ...}  提取失败则 body_text 为空字符串
    """
    import concurrent.futures

    def _pw_worker(url_list):
        result = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            for url in url_list:
                body_text = ""
                try:
                    page = ctx.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(2000)

                    body_text = trafilatura.extract(page.content(), output_format='markdown', include_images=False) or ""

                    if not body_text or len(body_text.strip()) < 20:
                        page_text = page.inner_text("body").strip()[:200]
                        if "身份核实" in page_text or "拖动滑块" in page_text:
                            print(f"  [pw] captcha 拦截，等待重试: {url[:60]}", flush=True)
                            page.wait_for_timeout(2000)

                    if not body_text or len(body_text.strip()) < 20:
                        for sel in ["div.newstext", "div#zw_body", "div.article-body",
                                    "article", "div[class*='content']", "div[class*='article']",
                                    "div[class*='detail']", "div[class*='main-text']", "#content"]:
                            el = page.query_selector(sel)
                            if el:
                                t = el.inner_text().strip()
                                if len(t) > 50:
                                    body_text = t
                                    break

                    if not body_text or len(body_text.strip()) < 20:
                        body_text = page.inner_text("body").strip()

                    if body_text and has_excessive_whitespace(body_text):
                        body_text = clean_excessive_whitespace(body_text)

                    if _is_pdf_announcement_page(body_text):
                        try:
                            import requests as _requests
                            r = _requests.get(url, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                            }, timeout=10)
                            r.encoding = "utf-8"
                            pdf_text = _try_extract_pdf_from_html(r.text)
                            if pdf_text:
                                body_text = pdf_text
                        except Exception:
                            pass

                    page.close()
                except Exception:
                    body_text = ""
                result[url] = body_text
            browser.close()
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_pw_worker, urls)
        try:
            return fut.result(timeout=60)
        except concurrent.futures.TimeoutError:
            print(f"  [pw] Playwright 兜底超时（60s）", flush=True)
            return {}


async def phase1_fetch_and_extract(
    raw_results: list[dict],
    max_parallel: int = 4,
    include_snippet: bool = False,
    truncate: bool = False,       # mail_tower: 是否截断正文
    skip_pdf: bool = False,       # mail_tower: 跳过 PDF 提取（后台异步处理）
) -> list[dict]:
    """
    Phase 1: 并行下载 HTML → trafilatura 正文提取 → 日期提取。

    mail_tower 新增:
      - 输入项含 _known_date 时跳过日期提取，直接使用
      - truncate=True 时截断正文至 max_body_chars

    返回:
        [{
            "id", "title", "url",
            "date", "date_source", "date_confidence",
            "snippet", "source",
            "html", "body_text", "paragraphs",
            "fetch_error",
            "truncated": True/False,   # (仅 truncate=True)
        }, ...]
    """
    sem = asyncio.Semaphore(max_parallel)

    async def _process_one(item: dict, idx: int) -> dict:
        async with sem:
            aid = item.get("_original_id") or f"a_{idx + 1:02d}"
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            title = item.get("title", url)

            # 1. Fetch HTML
            html, error = await _fetch_single(url)
            source = re.sub(r'https?://(www\.)?', '', url).split('/')[0] if url else ""

            if not html or error:
                return {
                    "id": aid, "title": title, "url": url,
                    "date": "", "date_source": "", "date_confidence": "",
                    "snippet": snippet if include_snippet else "",
                    "source": source,
                    "html": "", "body_text": "", "paragraphs": [],
                    "fetch_error": error or "empty response",
                }

            # 2. 日期提取：有 _known_date 则直接使用，否则走标准提取
            known_date = item.get("_known_date", "")
            if known_date:
                date_info = {"date": known_date, "source": "sinafin", "confidence": "high"}
            else:
                date_info = extract_date_fast(html, url, snippet)

            # 3. trafilatura 正文提取
            body_text, meta_date, paragraphs = _extract_body_from_html(html)

            # mail_tower: 清理过量空白字符（如同花顺 7x24 直播页等模板页）
            if body_text and has_excessive_whitespace(body_text):
                body_text = clean_excessive_whitespace(body_text)

            # mail_tower: PDF 公告 fallback — 正文为空或为"无法在线阅读"等占位时
            is_pdf = False
            if _is_pdf_announcement_page(body_text):
                if skip_pdf:
                    is_pdf = True  # 标记为 PDF 页，后台异步提取
                else:
                    pdf_text = _try_extract_pdf_from_html(html)
                    if pdf_text:
                        body_text = pdf_text
                        paragraphs = [p.strip() for p in body_text.split('\n\n') if p.strip()]

            # mail_tower: 截断正文
            truncated = False
            if truncate and body_text:
                body_text, truncated = truncate_body(body_text)

            # 4. 用正文升级日期（仅当非 _known_date）
            if not known_date and body_text:
                date_info = upgrade_date_with_body(date_info, body_text)

            # 5. 如果 trafilatura meta 提供了日期且尚未获取到，用它
            if meta_date and not date_info["date"]:
                date_info = {"date": meta_date, "source": "trafilatura_meta", "confidence": "medium"}

            result = {
                "id": aid,
                "title": title,
                "url": url,
                "date": date_info["date"],
                "date_source": date_info["source"],
                "date_confidence": date_info["confidence"],
                "snippet": snippet if include_snippet else "",
                "source": source,
                "html": html,
                "body_text": body_text,
                "paragraphs": paragraphs,
                "fetch_error": error,
            }
            if item.get("_original_id"):
                result["_original_id"] = item["_original_id"]
            if truncate:
                result["truncated"] = truncated
            if is_pdf:
                result["_is_pdf"] = True
            return result

    tasks = [_process_one(item, i) for i, item in enumerate(raw_results)]
    return await asyncio.gather(*tasks)


def build_preview(articles: list[dict]) -> list[dict]:
    """从 Phase 1 结果构建预览列表（不含 html/body 字段）。"""
    return [
        {
            "id": a["id"],
            "title": a["title"],
            "url": a["url"],
            "date": a["date"],
            "date_source": a["date_source"],
            "date_confidence": a["date_confidence"],
            "snippet": a["snippet"],
            "source": a["source"],
            "fetch_error": a["fetch_error"],
        }
        for a in articles
    ]


# ============================================================
# Phase 2: LLM 处理（分组/摘要）
# ============================================================

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
with open(os.path.join(PROMPTS_DIR, "summary.txt"), encoding='utf-8') as f:
    _prompt_summary_template = f.read()
with open(os.path.join(PROMPTS_DIR, "summary_merge.txt"), encoding='utf-8') as f:
    _prompt_merge_template = f.read()
with open(os.path.join(PROMPTS_DIR, "point_locate.txt"), encoding='utf-8') as f:
    _prompt_locate_template = f.read()
with open(os.path.join(PROMPTS_DIR, "point_locate_simple.txt"), encoding='utf-8') as f:
    _prompt_locate_simple_template = f.read()
with open(os.path.join(PROMPTS_DIR, "grouping.txt"), encoding='utf-8') as f:
    _prompt_grouping_template = f.read()


def estimate_tokens(text: str) -> int:
    chinese = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    ascii_chars = sum(1 for c in text if c.isascii() and c.isprintable())
    other = max(0, len(text) - chinese - ascii_chars)
    return int(chinese / 1.8 + ascii_chars / 3.5 + other / 2) + 1


def split_paragraphs(paragraphs: list) -> list:
    total_tokens = estimate_tokens('\n'.join(paragraphs))
    if total_tokens <= SPLIT_MAX_TOKENS:
        return [paragraphs]
    parts = []
    current = []
    current_tokens = 0
    for p in paragraphs:
        p_tokens = estimate_tokens(p)
        if current_tokens + p_tokens > SPLIT_MAX_TOKENS and current:
            parts.append(current)
            current = []
            current_tokens = 0
        current.append(p)
        current_tokens += p_tokens
    if current:
        parts.append(current)
    return parts


async def _call_llm(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": OLLAMA_NUM_PREDICT, "temperature": OLLAMA_TEMP},
    }
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        return f"[Ollama 错误] {e}"


def build_grouping_prompt(paragraphs: list, max_groups: int = 5) -> str:
    n = len(paragraphs)
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
    return _prompt_grouping_template.replace('{n}', str(n)).replace('{numbered}', numbered)


def build_summary_prompt(paragraphs: list, query: str = "", keyword: str = "") -> str:
    body = '\n\n'.join(paragraphs)
    return _prompt_summary_template.format(query=query, keyword=keyword, body=body)


def build_merge_prompt(chunk_summaries: list, query: str = "", keyword: str = "",
                       title: str = "") -> str:
    text = '\n\n'.join(f'{i+1}. {s}' for i, s in enumerate(chunk_summaries))
    return _prompt_merge_template.format(
        query=query, keyword=keyword, title=title, chunk_summaries=text
    )


def build_point_locate_prompt(paragraphs: list, key_point: str,
                               all_key_points: list = None, target_index: int = None) -> str:
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
    if all_key_points and target_index is not None:
        kp_text = '\n'.join(f"{i+1}. {kp}" for i, kp in enumerate(all_key_points))
        return _prompt_locate_template.format(
            key_point=key_point, numbered_body=numbered,
            all_key_points_text=kp_text, target_index=target_index
        )
    return _prompt_locate_simple_template.format(key_point=key_point, numbered_body=numbered)


def parse_summary_output(raw: str) -> dict:
    result = {"summary": "", "summary_objective": "", "summary_relevant": "", "key_points": []}
    obj_match = re.search(r'【客观概括】[ \t]*\n?(.*?)(?=\n\s*【相关摘要】|\Z)', raw, re.DOTALL)
    if obj_match:
        result["summary_objective"] = obj_match.group(1).strip()
    rel_match = re.search(r'【相关摘要】[ \t]*\n?(.*?)(?=\n\s*【核心要点】|\Z)', raw, re.DOTALL)
    if rel_match:
        result["summary_relevant"] = rel_match.group(1).strip()
    parts = [p for p in [result["summary_objective"], result["summary_relevant"]] if p]
    result["summary"] = '\n\n'.join(parts)
    kp_match = re.search(r'【核心要点】[ \t]*\n?(.*?)$', raw, re.DOTALL)
    if kp_match:
        kp_text = kp_match.group(1).strip()
        for line in kp_text.split('\n'):
            line = line.strip()
            m = re.match(r'^\d+[.、．]\s*(.*)', line)
            if m:
                point = m.group(1).strip()
                if point:
                    result["key_points"].append(point)
    return result


def parse_merge_output(raw: str) -> str:
    m = re.search(r'【统一概括】[ \t]*\n?(.*?)(?=\n\s*【各分块概括】|\Z)', raw, re.DOTALL)
    return m.group(1).strip() if m else raw


def parse_point_locate_output(raw: str) -> list[int]:
    m = re.search(r'【段落】\s*(.+)', raw)
    if not m:
        return []
    result_str = m.group(1).strip()
    if result_str == '无':
        return []
    if not re.match(r'^[Pp]', result_str):
        result_str = 'P' + result_str
    return parse_paragraphs(result_str)


def parse_paragraphs(para_str: str) -> list[int]:
    paragraphs = []
    parts = [p.strip() for p in para_str.split(',')]
    for part in parts:
        range_match = re.match(r'P(\d+)\s*[-–]\s*P(\d+)', part, re.IGNORECASE)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            paragraphs.extend(range(start, end + 1))
        else:
            single_match = re.match(r'P(\d+)', part, re.IGNORECASE)
            if single_match:
                paragraphs.append(int(single_match.group(1)))
    return sorted(set(paragraphs))


def parse_grouping(raw: str) -> list:
    groups = []
    blocks = re.split(r'【分组】', raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        para_match = re.search(r'段落[：:]\s*(.*?)(?=\n\s*要点[：:])', block, re.DOTALL)
        if not para_match:
            continue
        para_str = para_match.group(1).strip()
        para_numbers = parse_paragraphs(para_str)
        if not para_numbers:
            continue
        group = {"paragraphs": para_numbers, "start_p": min(para_numbers), "end_p": max(para_numbers)}
        point_match = re.search(r'要点[：:]\s*(.*?)(?=\n\s*概括[：:])', block, re.DOTALL)
        group["point"] = point_match.group(1).strip() if point_match else ""
        summary_match = re.search(r'概括[：:]\s*(.*?)(?=\n\s*关键字[：:])', block, re.DOTALL)
        group["summary"] = summary_match.group(1).strip() if summary_match else ""
        kw_match = re.search(r'关键字[：:]\s*(.*?)(?=\n|$)', block, re.DOTALL)
        group["keywords"] = kw_match.group(1).strip() if kw_match else ""
        groups.append(group)
    for i, g in enumerate(groups, 1):
        g["group_id"] = i
    return groups


def consolidate_ranges(groups: list) -> list:
    for g in groups:
        ps = g.get("paragraphs", [])
        if not ps:
            ps = list(range(g["start_p"], g["end_p"] + 1))
            g["paragraphs"] = ps
        g["start_p"] = min(ps)
        g["end_p"] = max(ps)
    return groups


async def phase2_llm_analysis(
    articles: list[dict],
    query: str,
    keyword: str,
    mode: str = "segments",
    max_parallel: int = 4,
) -> dict:
    """
    Phase 2: 对正文已提取的文章运行 LLM 分析。
    正文（paragraphs）由 Phase 1 提供，此函数不做网络请求。

    返回: {"articles": {...}, "segments": {...}, "_texts": {...}}
    """
    chunk_pool = []
    for art in articles:
        paragraphs = art.get("paragraphs", [])
        if not paragraphs:
            continue
        parts = split_paragraphs(paragraphs)
        para_offset = 0
        for pi, part in enumerate(parts):
            cu = ChunkUnit(
                article_id=art["id"],
                title=art["title"],
                url=art["url"],
                date=art["date"],
                snippet=art.get("snippet", ""),
                source=art.get("source", ""),
                chunk_index=pi,
                total_chunks=len(parts),
                paragraphs=part,
                para_offset=para_offset,
            )
            chunk_pool.append(cu)
            para_offset += len(part)

    if not chunk_pool:
        return {"articles": {}, "segments": {}, "_texts": {}}

    sem_llm = asyncio.Semaphore(max_parallel)

    async def _infer_chunk(cu: ChunkUnit) -> dict:
        if mode == "summary":
            prompt = build_summary_prompt(cu.paragraphs, query=query, keyword=keyword)
            raw = await _call_llm(prompt)
            parsed = parse_summary_output(raw)
            return {"article_id": cu.article_id, "cu": cu, "parsed": parsed}
        else:
            prompt = build_grouping_prompt(cu.paragraphs)
            raw = await _call_llm(prompt)
            groups = parse_grouping(raw)
            for g in groups:
                g["start_p"] += cu.para_offset
                g["end_p"] += cu.para_offset
                if "paragraphs" in g:
                    g["paragraphs"] = [p + cu.para_offset for p in g["paragraphs"]]
            return {"article_id": cu.article_id, "cu": cu, "groups": groups}

    async def _bounded_infer(cu):
        async with sem_llm:
            return await _infer_chunk(cu)

    chunk_results = await asyncio.gather(*[_bounded_infer(cu) for cu in chunk_pool])

    by_article = defaultdict(list)
    for cr in chunk_results:
        by_article[cr["article_id"]].append(cr)

    articles_out = {}
    all_segments = {}
    all_texts = {}

    async def _merge_article(aid: str, cr_list: list):
        cu0 = cr_list[0]["cu"]
        total_charnum = sum(len(p) for c in cr_list for p in c["cu"].paragraphs)
        all_paras = sum([c["cu"].paragraphs for c in cr_list], [])

        if mode == "summary":
            parsed_list = [c["parsed"] for c in cr_list]
            summaries = [p["summary_objective"] for p in parsed_list if p["summary_objective"]]
            if len(summaries) > 1:
                merge_raw = await _call_llm(
                    build_merge_prompt(summaries, query=query, keyword=keyword, title=cu0.title)
                )
                unified_summary = parse_merge_output(merge_raw)
            else:
                unified_summary = summaries[0] if summaries else ""

            all_relevant = []
            for p in parsed_list:
                r = p["summary_relevant"]
                if r and r not in all_relevant:
                    all_relevant.append(r)

            all_key_points = []
            kp_chunk_map = []
            for ci, p in enumerate(parsed_list):
                for kp in p["key_points"]:
                    if kp not in all_key_points:
                        all_key_points.append(kp)
                        kp_chunk_map.append(ci)

            return {
                "title": cu0.title, "url": cu0.url, "date": cu0.date,
                "snippet": cu0.snippet, "source": cu0.source,
                "charnum": total_charnum, "mode": "summary",
                "summary": unified_summary,
                "summary_relevant": all_relevant,
                "key_points": all_key_points,
                "segments": [],
            }, {}, {
                "_chunks": [c["cu"].paragraphs for c in cr_list],
                "_kp_chunk_map": kp_chunk_map,
            }

        else:  # segments mode
            all_groups = []
            for c in cr_list:
                all_groups.extend(c["groups"])
            if not all_groups:
                return None, {}, None

            merged = []
            for g in all_groups:
                if merged and g["start_p"] <= merged[-1]["end_p"]:
                    prev = merged[-1]
                    prev["end_p"] = max(prev["end_p"], g["end_p"])
                    prev["point"] += " + " + g["point"]
                    prev["summary"] += "；" + g["summary"]
                    prev_kw = prev.get("keywords", "").strip()
                    g_kw = g.get("keywords", "").strip()
                    if prev_kw and g_kw and prev_kw != g_kw:
                        prev["keywords"] = prev_kw + "+" + g_kw
                    if "paragraphs" in prev and "paragraphs" in g:
                        prev["paragraphs"] = sorted(set(prev["paragraphs"] + g["paragraphs"]))
                else:
                    if "paragraphs" not in g:
                        g["paragraphs"] = list(range(g["start_p"], g["end_p"] + 1))
                    merged.append(g)

            groups = consolidate_ranges(merged)
            covered = set()
            for g in groups:
                for pn in range(g["start_p"], g["end_p"] + 1):
                    covered.add(pn)
            n_total = sum(len(c["cu"].paragraphs) for c in cr_list)
            missing = sorted(set(range(1, n_total + 1)) - covered)
            if missing:
                start = missing[0]
                end = missing[0]
                for pn in missing[1:]:
                    if pn == end + 1:
                        end = pn
                    else:
                        groups.append({
                            "group_id": 99, "start_p": start, "end_p": end,
                            "paragraphs": list(range(start, end + 1)),
                            "point": "[补充]", "summary": "LLM遗漏的段落", "keywords": "",
                        })
                        start = pn
                        end = pn
                groups.append({
                    "group_id": 99, "start_p": start, "end_p": end,
                    "paragraphs": list(range(start, end + 1)),
                    "point": "[补充]", "summary": "LLM遗漏的段落", "keywords": "",
                })

            segment_texts = {}
            segments_out = []
            article_segments = {}
            for gi, g in enumerate(groups, 1):
                s = max(0, g["start_p"] - 1)
                e = min(n_total, g["end_p"])
                group_text = '\n\n'.join(all_paras[s:e])
                charnum = len(group_text)
                seg_id = f"s{gi}"
                segments_out.append({"id": seg_id, "charnum": charnum})
                segment_texts[seg_id] = group_text
                sid = f"{aid}_{seg_id}"
                seg_item = {"article_id": aid, "point": g["point"],
                            "summary": g["summary"], "charnum": charnum}
                if g.get("keywords"):
                    seg_item["keywords"] = g["keywords"]
                article_segments[sid] = seg_item

            return {
                "title": cu0.title, "url": cu0.url, "date": cu0.date,
                "snippet": cu0.snippet, "source": cu0.source,
                "charnum": total_charnum, "segments": segments_out,
            }, article_segments, segment_texts

    merge_results = await asyncio.gather(*[
        _merge_article(aid, crs) for aid, crs in by_article.items()
    ])

    for aid, (art_entry, extra, texts_data) in zip(by_article.keys(), merge_results):
        if art_entry is None:
            continue
        articles_out[aid] = art_entry
        if isinstance(extra, dict):
            segs = {k: v for k, v in extra.items() if k != "_texts"}
            all_segments.update(segs)
        if isinstance(texts_data, dict):
            all_texts[aid] = texts_data

    return {"articles": articles_out, "segments": all_segments, "_texts": all_texts}


# ============================================================
# ============================================================
# 主入口: run_search_pipeline
# ============================================================

async def run_search_pipeline(
    query: str,
    keyword: str = "",
    max_results: int = 5,
    mode: str = "full",       # "preview" | "full" | "list"
    site: str | None = None,
    timelimit: str | None = None,
    filter_days: int | None = None,
    filter_title: str | None = None,
    include_snippet: bool = False,
    llm_mode: str = "segments",
    engine: str = "ddg",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    主入口：支持引擎分发 + mode=list。

    mode=preview:
        - Phase 0+1: 搜索 → fetch → trafilatura → 全量日期 → 过滤 → 返回预览
        - Phase 2 数据在 _phase2_input 中，供调用方后台运行 LLM

    mode=full:
        - Phase 0+1+2 全链路
        - 返回完整分析结果（与 v1.0/v2.0 兼容）

    mode=list:
        - Phase 0: 搜索 → 返回预览（仅列表，无正文）
        - 不执行 Phase 1/2
    """
    # ── Phase 0: 搜索 ──
    raw_results = search_web(
        query, max_results=max_results, site=site, timelimit=timelimit,
        engine=engine, start_date=start_date, end_date=end_date,
    )
    if not raw_results:
        if mode == "list":
            return {"mode": "list", "articles": [], "total": 0, "total_raw": 0}
        empty = {"mode": mode if mode == "preview" else llm_mode,
                 "articles": [], "total": 0, "total_raw": 0}
        if mode != "preview":
            empty.update({"segments": {}, "_texts": {}})
        return empty

    # ── mode = list: 仅返回文章列表，不做 Phase 1/2 ──
    if mode == "list":
        # ── DDG 模式：自动提取正文+日期，过滤后返回带字数的预览 ──
        if engine == "ddg":
            phase1_results = await phase1_fetch_and_extract(
                raw_results, max_parallel=MAX_PARALLEL, include_snippet=True,
                truncate=True, skip_pdf=True,
            )

            # 日期过滤
            if filter_days is not None or filter_title is not None:
                preview_input = build_preview(phase1_results)
                filtered = ArticleFilter.apply(
                    preview_input, days=filter_days, title_pattern=filter_title
                )
                filtered_ids = {a["id"] for a in filtered}
                phase2_input = [a for a in phase1_results if a["id"] in filtered_ids]
            else:
                filtered = build_preview(phase1_results)
                phase2_input = phase1_results

            # 构建带日期、snippet、字数的预览
            articles_out = []
            for a in phase2_input:
                body_text = a.get("body_text", "")
                # 跳过无正文内容的文章（抓取失败或提取为空）
                if not body_text or not body_text.strip():
                    continue
                articles_out.append({
                    "id": a["id"],
                    "title": a["title"],
                    "body_avail": "有",
                    "date": a.get("date", ""),
                    "date_source": a.get("date_source", ""),
                    "date_confidence": a.get("date_confidence", ""),
                    "snippet": a.get("snippet", ""),
                    "source": a.get("source", ""),
                    "word_count": sum(1 for c in body_text if not c.isspace()),
                })

            filter_stats = {
                "raw_count": len(phase1_results),
                "filtered_count": len(phase2_input),
                "dropped_count": len(phase1_results) - len(phase2_input),
                "filter_days": filter_days,
                "filter_title": filter_title,
            }

            return {
                "mode": "list",
                "articles": articles_out,
                "total": len(articles_out),
                "total_raw": len(phase1_results),
                "date_stats": {"high": 0, "medium": 0, "low": 0, "none": 0},
                "filter_stats": filter_stats,
                "_phase2_input": phase2_input,  # 含 body_text，供 /article 取正文
            }

        # ── Sinafin / Baidufin / Thsfin / Dcfin / Juchao / QnAinfo 模式：仅返回列表，不提取正文 ──
        # 保存原始总数（用于统计）
        _total_raw = len(raw_results)

        # 预过滤（标题过滤）
        if engine in ("sinafin", "baidufin", "thsfin", "dcfin", "juchao", "qnainfo"):
            if filter_title:
                raw_results = ArticleFilter.apply(raw_results,
                                                   title_pattern=filter_title)

        # 构建预览列表
        articles_out = []
        for idx, item in enumerate(raw_results):
            known_date = item.get("_known_date", "")
            url = item.get("url", "")
            has_url = bool(url and url.strip().startswith("http"))
            art = {
                "id": f"a_{idx + 1:02d}",
                "title": item.get("title", ""),
                "body_avail": "有" if (has_url or engine in ("juchao", "qnainfo")) else "无",
                "date": known_date,
                "date": known_date,
                "date_source": engine if known_date else "",
                "date_confidence": "high" if known_date else "",
                "snippet": item.get("snippet", ""),
            }
            # dcfin / sinafin 特有字段：分类标签（资讯/公告）
            if engine in ("dcfin", "sinafin"):
                art["_category"] = item.get("_category", "")
            # juchao 特有字段：分类标签（公告）+ 后台提取元数据
            if engine == "juchao":
                art["_category"] = item.get("_category", "")
                art["_announce_id"] = item.get("_announce_id", "")
                art["_announce_time"] = item.get("_announce_time", "")
            # baidufin 特有字段：情绪分类 + 分类固定为资讯
            if engine == "baidufin":
                art["sentiment"] = item.get("_baidu_sentiment", item.get("sentiment", ""))
                art["_category"] = "资讯"
                art["provider"] = item.get("_baidu_provider", "")
                art["snippet"] = item.get("_baidu_abstract", item.get("snippet", ""))
            # thsfin 特有：标题前半段（冒号前）作为分类
            if engine == "thsfin":
                _t = art.get("title", "")
                if "：" in _t:
                    parts = _t.split("：", 1)
                    art["_category"] = parts[0].strip()
                    art["title"] = parts[1].strip()
            # qnainfo 特有字段：互动易问答完整内容（首次调用即全部返回）
            if engine == "qnainfo":
                art["_category"] = item.get("_category", "")
                art["_question"] = item.get("_question", "")
                art["_answerer"] = item.get("_answerer", "")
                art["_answer"] = item.get("_answer", "")
                art["_ask_time"] = item.get("_ask_time", "")
                art["_update_time"] = item.get("_update_time", "")
            articles_out.append(art)

        # ── 通用引擎额外：按 filter_days 做时间筛选（只精确到天） ──
        if engine in ("sinafin", "thsfin", "dcfin", "baidufin", "juchao", "qnainfo") and filter_days is not None:
            _raw_before = len(raw_results)
            kept_ids = {a["id"] for a in ArticleFilter.apply(
                articles_out, days=filter_days, title_pattern=None
            )}
            articles_out = [a for a in articles_out if a["id"] in kept_ids]
            # 同步过滤 raw_results（用 id 中的序号反查索引）
            raw_indices = set()
            for aid in kept_ids:
                try:
                    raw_indices.add(int(aid.split("_")[1]) - 1)
                except (ValueError, IndexError):
                    pass
            raw_results = [raw_results[i] for i in sorted(raw_indices)]
            # 重排 articles_out + raw_results 的 id 为连续编号（保持一致）
            for new_idx, (art, raw) in enumerate(zip(articles_out, raw_results)):
                new_id = f"a_{new_idx + 1:02d}"
                art["id"] = new_id
                raw["id"] = new_id
            _dropped = _raw_before - len(raw_results)
        else:
            _dropped = 0

        filter_stats = {
            "raw_count": _total_raw,
            "filtered_count": len(articles_out),
            "dropped_count": _total_raw - len(raw_results),
            "filter_days": filter_days,
            "filter_title": filter_title,
        }

        return {
            "mode": "list",
            "articles": articles_out,
            "total": len(articles_out),
            "total_raw": _total_raw,
            "filter_stats": filter_stats,
            "_phase2_input": raw_results,  # 原始结果（含 url），供后台提取正文
        }

    # ── Phase 1: 并行 fetch HTML + 正文提取 + 全量日期提取 ──
    # （preview / full 模式走这里）
    phase1_results = await phase1_fetch_and_extract(
        raw_results, max_parallel=MAX_PARALLEL, include_snippet=include_snippet,
    )

    # 统计日期命中率
    confidence_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for a in phase1_results:
        c = a.get("date_confidence", "")
        if c in confidence_counts:
            confidence_counts[c] += 1
        else:
            confidence_counts["none"] += 1

    # ── 过滤（此时日期已是最准的）──
    has_filters = filter_days is not None or filter_title is not None
    if has_filters:
        preview_input = build_preview(phase1_results)
        filtered = ArticleFilter.apply(preview_input, days=filter_days, title_pattern=filter_title)
        filtered_ids = {a["id"] for a in filtered}
        phase2_input = [a for a in phase1_results if a["id"] in filtered_ids]
    else:
        filtered = build_preview(phase1_results)
        phase2_input = phase1_results

    filter_stats = {
        "raw_count": len(phase1_results),
        "filtered_count": len(filtered),
        "dropped_count": len(phase1_results) - len(filtered),
        "filter_days": filter_days,
        "filter_title": filter_title,
    }

    # ── mode = preview: 同步返回 ──
    if mode == "preview":
        return {
            "mode": "preview",
            "articles": filtered,
            "total": len(filtered),
            "total_raw": len(phase1_results),
            "date_stats": confidence_counts,
            "filter_stats": filter_stats,
            "_phase2_input": phase2_input,
        }

    # ── mode = full: 继续 Phase 2 (LLM) ──
    if not phase2_input:
        return {
            "mode": llm_mode,
            "articles": {},
            "segments": {},
            "_texts": {},
            "filter_stats": filter_stats,
            "date_stats": confidence_counts,
        }

    llm_result = await phase2_llm_analysis(
        phase2_input, query=query, keyword=keyword,
        mode=llm_mode, max_parallel=MAX_PARALLEL,
    )

    llm_result["filter_stats"] = filter_stats
    llm_result["mode"] = llm_mode
    llm_result["date_stats"] = confidence_counts
    llm_result["_phase1_results"] = phase1_results

    return llm_result
