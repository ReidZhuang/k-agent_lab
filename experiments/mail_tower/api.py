"""
bot_search API v3.0 — 引擎分发 + mode=list + 单篇正文按需提取

新增功能:
  1. engine 参数: "ddg"(默认) | "sinafin" | "baidufin" | "thsfin" | "dcfin" | "juchao" | "qnainfo"
  2. mode=list: 返回文章列表即止，后台逐篇提取正文（截断8000字）
  3. /article/{session_id}/{article_id} 按需取单篇正文
  4. start_date / end_date 日期过滤（透传给 sinafin）

用法:
    uvicorn api:app --host 0.0.0.0 --port 8300 --reload
"""
import asyncio, time, threading, re, traceback
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from reporting.error_reporter import report_error, report_exception, ERROR_CODES
from reporting.service_log import log_svc

from core import run_search_pipeline
from core import _call_llm, build_point_locate_prompt, parse_point_locate_output
from core import phase1_fetch_and_extract, truncate_body, extract_pdf_from_article
from session_manager import manager as session_manager

_PROMPT_BATCH_LOCATE_PATH = __import__('os').path.join(
    __import__('os').path.dirname(__file__), "prompts", "point_locate_batch.txt"
)
with open(_PROMPT_BATCH_LOCATE_PATH, encoding='utf-8') as f:
    _prompt_batch_locate_template = f.read()

app = FastAPI(title="bot_search API v3.0", version="3.0.0")

# ── 全局并发控制 ──
# 限制同时处理的 /search 请求数，超过的排队等待。
# 默认 = 物理线程数（超出部分在 OS socket 层排队，不会丢失）。
SEARCH_SEM = asyncio.Semaphore(16)

# ── 搜索超时 + 排队超时（从 config.json 加载） ──
import json as _json
_SEARCH_CONFIG_PATH = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "config", "config.json"
)
with open(_SEARCH_CONFIG_PATH) as _f:
    _cfg = _json.load(_f)
SEARCH_TIMEOUT = _cfg.get("search", {}).get("timeout_seconds", 90)
MAX_SEARCH_WAIT = _cfg.get("search", {}).get("max_wait_seconds", 300)  # 排队超时，超时返回 503


# ============================================================
# 请求/响应模型
# ============================================================

class SearchRequest(BaseModel):
    query: str
    keyword: str = ""
    max_results: int = 5
    mode: str = "full"                     # "preview" | "full" | "list"
    session: str = "new"
    site: str | None = None
    timelimit: str | None = None
    filter_days: int | None = None
    filter_title: str | None = None
    include_snippet: bool = False
    llm_mode: str = "segments"            # "segments" | "summary" | "none"
    # v3.0 新增
    engine: str = "ddg"                   # "ddg" | "sinafin" | "baidufin" | "thsfin" | "dcfin" | "juchao" | "qnainfo"
    start_date: str | None = None   # "YYYY-MM-DD" 或 baidufin 支持 "YYYY-MM-DD HH:MM"
    end_date: str | None = None     # "YYYY-MM-DD" 或 baidufin 支持 "YYYY-MM-DD HH:MM"


class PollResponse(BaseModel):
    session_id: str
    status: str            # processing | preview | list_ready | done | error
    mode: str | None = None
    llm_mode: str | None = None
    engine: str | None = None
    empty: bool | None = None      # true: 无结果正常空；false: 有结果；null: 出错或未完成
    session_closed: bool = False   # true: session 已关闭，不可再调 /article
    preview: dict | None = None
    articles: dict | None = None
    segments: dict | None = None
    error: str | None = None
    elapsed: float | None = None
    created_at: str | None = None

    @model_validator(mode='after')
    def _auto_empty(self):
        """根据 status/preview/error 自动推算 empty 值。"""
        total = (self.preview or {}).get("total", 0)
        if self.status == "error":
            self.empty = None
        elif total > 0:
            self.empty = False
        elif self.status not in ("processing",):
            # done / list_ready / preview 但 total=0 → 正常空结果
            self.empty = True
        else:
            # processing → 未知
            self.empty = None
        return self


class SegmentRequest(BaseModel):
    session_id: str
    article_id: str
    segment_id: str


class SegmentResponse(BaseModel):
    session_id: str
    article_id: str
    segment_id: str
    text: str


class PointTextRequest(BaseModel):
    session_id: str
    article_id: str
    point_indices: list[int]


class PointTextItem(BaseModel):
    point_index: int
    key_point: str
    found: bool
    text: str = ""


class PointTextResponse(BaseModel):
    session_id: str
    article_id: str
    results: list[PointTextItem]


class StatusResponse(BaseModel):
    session_id: str
    status: str
    mode: str | None = None
    llm_mode: str | None = None
    engine: str | None = None
    query: str | None = None
    keyword: str | None = None
    created_at: str | None = None
    elapsed: float | None = None
    article_count: int | None = None
    error: str | None = None
    phase: str | None = None


class CloseResponse(BaseModel):
    session_id: str
    status: str


class ArticleRequest(BaseModel):
    session_id: str
    article_id: str | None = None
    article_ids: list[str] | None = None
    close: bool = False         # True = 本次返回正文后关闭 session

    @model_validator(mode='after')
    def check_ids(self):
        if not self.article_id and not self.article_ids:
            raise ValueError("必须提供 article_id 或 article_ids")
        return self


class ArticleItem(BaseModel):
    article_id: str
    status: str            # "ready" | "processing" | "error"
    title: str = ""
    url: str = ""
    date: str = ""
    body_text: str = ""
    truncated: bool = False
    fetch_error: str = ""


class ArticleResponse(BaseModel):
    session_id: str
    status: str = "processing"   # "processing" | "ready" | "error"
    articles: list[ArticleItem]
    session_closed: bool = False  # True = 本次返回后 session 已关闭


class ExtractRequest(BaseModel):
    session_id: str
    article_ids: list[str]        # 需要提取正文的文章 ID 列表，如 ["a_01", "a_03", "a_05"]


class ExtractResponse(BaseModel):
    session_id: str
    status: str                   # "processing" | "error"
    requested: int
    ignored: int = 0              # 因 ID 无效而被忽略的个数
    message: str = ""


# ============================================================
# 后台处理函数
# ============================================================

def _run_full_pipeline_in_thread(session_id: str, query: str, keyword: str,
                                  max_results: int, mode: str, site: str | None,
                                  timelimit: str | None, llm_mode: str,
                                  filter_days: int | None, filter_title: str | None,
                                  include_snippet: bool,
                                  engine: str, start_date: str | None,
                                  end_date: str | None):
    """后台线程: 运行完整 pipeline (Phase 1 + Phase 2) — full / preview 模式的 Phase 2"""

    async def _run():
        try:
            result = await asyncio.wait_for(run_search_pipeline(
                query, keyword, max_results,
                mode="full",
                site=site, timelimit=timelimit,
                filter_days=filter_days,
                filter_title=filter_title,
                include_snippet=include_snippet,
                llm_mode=llm_mode,
                engine=engine,
                start_date=start_date,
                end_date=end_date,
            ), timeout=SEARCH_TIMEOUT)
            elapsed = time.time() - start
            session_manager.set_done(
                session_id,
                articles=result.get("articles", {}),
                segments=result.get("segments", {}),
                texts=result.get("_texts", {}),
                elapsed=elapsed,
            )
        except Exception as e:
            session_manager.set_error(session_id, str(e))

    start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run())
    loop.close()


def _run_preview_phase2_in_thread(session_id: str, phase2_input: list,
                                    query: str, keyword: str, llm_mode: str):
    """后台线程: 预览模式下的 Phase 2（仅 LLM 分析，正文已在 Phase 1 提取完毕）"""

    async def _run():
        try:
            from core import phase2_llm_analysis
            llm_result = await phase2_llm_analysis(
                phase2_input, query=query, keyword=keyword,
                mode=llm_mode,
            )
            elapsed = time.time() - start
            session_manager.set_done(
                session_id,
                articles=llm_result.get("articles", {}),
                segments=llm_result.get("segments", {}),
                texts=llm_result.get("_texts", {}),
                elapsed=elapsed,
            )
        except Exception as e:
            session_manager.set_error(session_id, str(e))

    start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run())
    loop.close()


def _run_list_phase1_in_thread(session_id: str, raw_results: list[dict],
                                article_ids: list[str] | None = None,
                                llm_mode: str = "none",
                                query: str = "", keyword: str = ""):
    """后台线程: list 模式按需提取正文

    Args:
        article_ids: 要提取的 article_id 列表。为 None 时提取全部（兼容旧调用）。
    """
    # 按 article_ids 过滤：article_ids 为空时什么都不做
    if article_ids is not None and not article_ids:
        session_manager.set_list_done(session_id, 0)
        return

    async def _run(max_parallel: int = 20):
        try:
            # 从 raw_results 中筛选出要提取的文章
            if article_ids is not None:
                # article_ids → 提取对应索引的 raw item
                target_indices = set()
                for aid in article_ids:
                    try:
                        idx = int(aid.split("_")[1]) - 1  # "a_03" → 2
                        target_indices.add(idx)
                    except (IndexError, ValueError):
                        pass
                to_fetch = [r for i, r in enumerate(raw_results) if i in target_indices]
            else:
                to_fetch = raw_results

            if not to_fetch:
                session_manager.set_list_done(session_id, 0)
                return

            # 在每项中嵌入原始 article_id，让 phase1 使用而非重新编号
            if article_ids is not None:
                for i, aid in enumerate(article_ids):
                    if i < len(to_fetch):
                        to_fetch[i]["_original_id"] = aid

            # Phase 1: 提取全文（不截断，保留 paragraphs 给 LLM）
            results = await phase1_fetch_and_extract(
                to_fetch, truncate=False, max_parallel=max_parallel,
            )
            # 逐篇存储截断正文（用原始 article_id）
            phase2_input = []
            for art in results:
                orig_aid = art.get("_original_id") or art["id"]
                body = art.get("body_text", "")
                truncated_body, was_truncated = truncate_body(body)
                session_manager.set_article_body(
                    session_id, art["id"],
                    body_text=truncated_body,
                    truncated=was_truncated,
                    fetch_error=art.get("fetch_error", ""),
                )
                if llm_mode != "none":
                    phase2_input.append(art)

            # Phase 2: LLM 分析（非 none 模式）
            if llm_mode != "none" and phase2_input:
                from core import phase2_llm_analysis
                llm_result = await phase2_llm_analysis(
                    phase2_input, query=query, keyword=keyword,
                    mode=llm_mode,
                )
                elapsed = time.time() - start
                session_manager.set_done(
                    session_id,
                    articles=llm_result.get("articles", {}),
                    segments=llm_result.get("segments", {}),
                    texts=llm_result.get("_texts", {}),
                    elapsed=elapsed,
                )
            else:
                elapsed = time.time() - start
                session_manager.set_list_done(session_id, elapsed)
        except Exception as e:
            session_manager.set_error(session_id, str(e))

    start = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run(max_parallel=20))
    loop.close()


def _run_thsfin_phase1_in_thread(session_id: str, raw_results: list[dict]):
    """后台线程: thsfin 模式提取有 URL 的文章正文（httpx→trafilatura，失败则 Playwright 兜底 + 1次重试）"""
    from core import truncate_body, _fetch_single, _extract_body_from_html, _extract_with_playwright, extract_pdf_from_article
    import asyncio, time, random

    start = time.time()

    # 只提取有 URL 的文章
    has_url = [a for a in raw_results if a.get("url", "").strip().startswith("http")]
    if not has_url:
        print("[thsfin] 没有需要提取正文的文章（全部无 URL）", flush=True)
        session_manager.set_list_done(session_id, 0)
        return

    async def _fetch_one(item: dict) -> dict:
        """单篇提取（httpx → HTML → trafilatura）"""
        from core import _fetch_single, _extract_body_from_html, truncate_body, _is_pdf_announcement_page, _try_extract_pdf_from_html
        url = item.get("url", "")
        try:
            html_text, fetch_err = await _fetch_single(url)
            if html_text:
                body_text, meta_date, paragraphs = _extract_body_from_html(html_text)
                # PDF 回退
                if not body_text or len(body_text.strip()) < 50:
                    if _is_pdf_announcement_page(body_text or html_text):
                        pdf_text = _try_extract_pdf_from_html(html_text, timeout=15)
                        if pdf_text:
                            body_text = pdf_text
                item["body_text"] = body_text or ""
            else:
                item["body_text"] = ""
                item["fetch_error"] = "HTTP fetch returned empty"
        except Exception as e:
            item["body_text"] = ""
            item["fetch_error"] = str(e)
        return item

    async def _fetch_all(items=None):
        target = items if items is not None else has_url
        tasks = [_fetch_one(a) for a in target]
        return await asyncio.gather(*tasks)

    def _run_pw_fallback(results):
        failed = [a for a in results
                  if not a.get("body_text") or sum(1 for c in a["body_text"] if not c.isspace()) < 20]
        if not failed:
            return failed
        urls = [a["url"] for a in failed]
        print(f"[thsfin] {len(failed)} 篇需要 Playwright 兜底提取", flush=True)
        pw_bodies = _extract_with_playwright(urls)
        for art in failed:
            pw_body = pw_bodies.get(art["url"], "")
            if pw_body and sum(1 for c in pw_body if not c.isspace()) >= 20:
                body, truncated = truncate_body(pw_body)
                art["body_text"] = body
                art["truncated"] = truncated
        return failed

    def _get_failed(results):
        return [a for a in results
                if not a.get("body_text") or sum(1 for c in a["body_text"] if not c.isspace()) < 20]

    # 第1步: httpx 并行提取
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        phase1_results = loop.run_until_complete(_fetch_all())
    finally:
        loop.close()

    # 第2步: Playwright 兜底
    _run_pw_fallback(phase1_results)

    # 第3步: 重试（1次）：Playwright 仍失败 → 1~3s 后从头重试
    still_failed = _get_failed(phase1_results)
    if still_failed:
        wait = 1 + random.random() * 2
        print(f"[thsfin] {len(still_failed)} 篇 Playwright 仍失败，{wait:.1f}s 后重试 httpx", flush=True)
        time.sleep(wait)
        retry_items = [a for a in has_url if a["id"] in {f["id"] for f in still_failed}]
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        try:
            retry_results = loop2.run_until_complete(_fetch_all(items=retry_items))
        finally:
            loop2.close()
        for art in retry_results:
            for i, orig in enumerate(phase1_results):
                if orig.get("id") == art.get("id"):
                    phase1_results[i] = art
                    break
        # 重试后 Playwright 兜底
        _run_pw_fallback(phase1_results)

    # 第4步: 存入 session（基于 has_url 保持原始顺序）
    for art in has_url:
        # 找到 phase1 中对应项
        matched = next((a for a in phase1_results if a.get("id") == art["id"]), None)
        body = (matched or {}).get("body_text", "") or ""
        fetch_err = (matched or {}).get("fetch_error", "")
        if not body.strip() and not fetch_err:
            fetch_err = "httpx + Playwright 均无法提取正文（已重试1次）"
        truncated_body, was_truncated = truncate_body(body) if body.strip() else ("", False)
        session_manager.set_article_body(
            session_id, art["id"],
            body_text=truncated_body,
            truncated=was_truncated,
            fetch_error=fetch_err,
        )

    # 无 URL 的文章：标记无正文
    no_url = [a for a in raw_results if not a.get("url", "").strip().startswith("http")]
    for art in no_url:
        session_manager.set_article_body(
            session_id, art["id"],
            body_text="",
            truncated=False,
            fetch_error="该事件无外部文章链接",
        )

    elapsed = time.time() - start
    session_manager.set_list_done(session_id, elapsed)
    print(f"[thsfin] {len(has_url)} 篇提取完成, 耗时 {elapsed:.1f}s", flush=True)


def _run_baidufin_phase1_in_thread(session_id: str, raw_results: list[dict]):
    """后台线程: baidufin 模式自动提取全部文章正文（httpx→trafilatura，失败则 Playwright 兜底 + 1次重试）"""
    from core import truncate_body, _fetch_single, _extract_body_from_html, _extract_with_playwright
    import asyncio, time, random

    start = time.time()

    async def _fetch_all(items=None, label="初次"):
        """用 httpx 并行提取"""
        from core import phase1_fetch_and_extract
        target = items if items is not None else raw_results
        if not target:
            return []
        return await phase1_fetch_and_extract(
            target, max_parallel=10, include_snippet=True, truncate=True,
        )

    def _run_pw_fallback(results, failed):
        """Playwright 兜底"""
        if not failed:
            return
        urls = [a["url"] for a in failed]
        print(f"[baidufin] {len(failed)} 篇需要 Playwright 兜底提取", flush=True)
        pw_bodies = _extract_with_playwright(urls)
        for art in failed:
            pw_body = pw_bodies.get(art["url"], "")
            if pw_body and sum(1 for c in pw_body if not c.isspace()) >= 20:
                body, truncated = truncate_body(pw_body)
                art["body_text"] = body
                art["truncated"] = truncated

    def _get_failed(results):
        return [a for a in results
                if not a.get("body_text") or sum(1 for c in a["body_text"] if not c.isspace()) < 20]

    # ── 第1步: httpx + trafilatura 并行提取 ──
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        phase1_results = loop.run_until_complete(_fetch_all())
    finally:
        loop.close()

    # ── 第2步: Playwright 兜底 ──
    failed = _get_failed(phase1_results)
    _run_pw_fallback(phase1_results, failed)

    # ── 第3步: 重试（1次）：Playwright 仍失败 → 1~3s 后从头重试 ──
    still_failed = _get_failed(phase1_results)
    if still_failed:
        wait = 1 + random.random() * 2
        print(f"[baidufin] {len(still_failed)} 篇 Playwright 仍失败，{wait:.1f}s 后重试 httpx", flush=True)
        time.sleep(wait)
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        try:
            retry_results = loop2.run_until_complete(_fetch_all(items=still_failed, label="重试"))
        finally:
            loop2.close()
        # 重试结果覆盖到 phase1_results 中
        for art in retry_results:
            for i, orig in enumerate(phase1_results):
                if orig.get("url") == art.get("url") or orig.get("id") == art.get("id"):
                    phase1_results[i] = art
                    break
        # 重试后还要 Playwright 兜底
        retry_failed = _get_failed(phase1_results)
        _run_pw_fallback(phase1_results, retry_failed)

    # ── 第4步: 存入 session ──
    for art in phase1_results:
        body = art.get("body_text", "") or ""
        fetch_err = art.get("fetch_error", "")
        if not body.strip() and not fetch_err:
            fetch_err = "httpx + Playwright 均无法提取正文（已重试1次）"
        truncated_body, was_truncated = truncate_body(body) if body.strip() else ("", False)
        session_manager.set_article_body(
            session_id, art["id"],
            body_text=truncated_body,
            truncated=was_truncated,
            fetch_error=fetch_err,
        )

    elapsed = time.time() - start
    session_manager.set_list_done(session_id, elapsed)
    print(f"[baidufin] {len(phase1_results)} 篇正文提取完成, 耗时 {elapsed:.1f}s", flush=True)


def _extract_body_with_bs4(html: str, url: str) -> str:
    """用 BS4 从特定网站提取正文（作为 trafilatura 的补充）。

    针对已知网站的正文容器做精确提取：
      - guba.eastmoney.com → div#zw_body（在 div.newstext 内）
      - caifuhao.eastmoney.com → div.article-body

    Returns:
        提取的正文，提取失败返回空字符串。
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, 'lxml')

    # 东方财富股吧文章
    if 'guba.eastmoney.com' in url:
        newstext = soup.find('div', class_='newstext')
        if newstext:
            zw_body = newstext.find(id='zw_body')
            if zw_body:
                paras = zw_body.find_all('p')
                text = '\n'.join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))
                if len(text) >= 20:
                    return text
        # 兜底：取整个 newstext
        body = newstext.get_text(strip=True) if newstext else ""
        if len(body) >= 20:
            return body

    # 东方财富财富号文章
    if 'caifuhao.eastmoney.com' in url:
        article_body = soup.find(class_='article-body')
        if article_body:
            text = article_body.get_text(strip=True)
            if len(text) >= 20:
                return text

    return ""


def _run_dcfin_phase1_in_thread(session_id: str, raw_results: list[dict]):
    """后台线程: dcfin 正文提取 — Playwright 全程驱动 + 人类行为模拟。

    流程：
      1. 访问 guba 首页建立 Cookie 会话
      2. 逐篇访问文章页，停留 5~8 秒后提取正文
      3. 请求间隔 1.5~3 秒随机
      4. 使用 guba 专属选择器 (div.newstext / div#zw_body) 提取正文
    """
    from core import truncate_body, has_excessive_whitespace, clean_excessive_whitespace
    import time, random, trafilatura

    start = time.time()

    # 筛选有 URL 的文章
    has_url = [a for a in raw_results if a.get("url", "").strip().startswith("http")]
    if not has_url:
        print("[dcfin] 没有需要提取正文的文章", flush=True)
        session_manager.set_list_done(session_id, 0)
        return

    print(f"[dcfin] {len(has_url)} 篇正文 Playwright 提取", flush=True)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )

            # ── 首页建立 Cookie 会话（绕过反爬的关键） ──
            seed = ctx.new_page()
            try:
                seed.goto("https://guba.eastmoney.com/", wait_until="load", timeout=15000)
                seed.wait_for_timeout(random.uniform(2000, 4000))
            except Exception:
                pass
            seed.close()

            # ── 逐篇提取 ──
            for idx, art in enumerate(has_url):
                url = art["url"]
                aid = f"a_{idx + 1:02d}"
                body_text = ""
                fetch_error = ""

                # 请求间隔 1.5~3 秒随机
                if idx > 0:
                    time.sleep(random.uniform(1.5, 3.0))

                try:
                    page = ctx.new_page()
                    page.goto(url, wait_until="load", timeout=30000)
                    # 文章页停留 5~8 秒模拟阅读
                    page.wait_for_timeout(random.uniform(5000, 8000))

                    # 优先用 guba 专用选择器
                    for sel in ["div.newstext", "div#zw_body", "div.article-body"]:
                        el = page.query_selector(sel)
                        if el:
                            t = el.inner_text().strip()
                            if len(t) > 50 and "身份核实" not in t:
                                body_text = t
                                break

                    # trafilatura 兜底
                    if not body_text or len(body_text.strip()) < 20:
                        body_text = trafilatura.extract(
                            page.content(), output_format='markdown', include_images=False
                        ) or ""

                    # 空白治理
                    if body_text and has_excessive_whitespace(body_text):
                        body_text = clean_excessive_whitespace(body_text)

                    page.close()
                except Exception as e:
                    fetch_error = str(e)

                truncated_body, was_truncated = truncate_body(body_text) if body_text else ("", False)
                session_manager.set_article_body(
                    session_id, aid,
                    body_text=truncated_body,
                    truncated=was_truncated,
                    fetch_error=fetch_error,
                )

            browser.close()
    except Exception as e:
        print(f"[dcfin] Playwright 提取失败: {e}", flush=True)

    elapsed = time.time() - start
    session_manager.set_list_done(session_id, elapsed)


def _run_ddg_pdf_extraction_in_thread(session_id: str, pdf_articles: list[dict]):
    """后台线程：DDG list 模式下异步提取 PDF 正文（15 秒超时）"""
    for art in pdf_articles:
        aid = art["id"]
        try:
            pdf_text = extract_pdf_from_article(art, timeout=15)
            if pdf_text:
                truncated_body, was_truncated = truncate_body(pdf_text)
                session_manager.set_article_body(
                    session_id, aid,
                    body_text=truncated_body,
                    truncated=was_truncated,
                )
                print(f"[ddg_pdf] {aid} PDF 提取完成 ({len(truncated_body)} 字)", flush=True)
            else:
                # PDF 提取超时或失败，保留原始 trafilatura 占位正文
                original_body = art.get("body_text", "")
                truncated_body, was_truncated = truncate_body(original_body)
                session_manager.set_article_body(
                    session_id, aid,
                    body_text=truncated_body,
                    truncated=was_truncated,
                    fetch_error="PDF extraction timeout or failed",
                )
                print(f"[ddg_pdf] {aid} PDF 提取失败，保留原始正文 ({len(truncated_body)} 字)", flush=True)
        except Exception as e:
            session_manager.set_article_body(
                session_id, aid,
                body_text="",
                truncated=False,
                fetch_error=str(e),
            )
            print(f"[ddg_pdf] {aid} PDF 提取异常: {e}", flush=True)


# ============================================================
# juchao 后台 PDF 下载线程
# ============================================================

def _run_juchao_phase1_in_thread(session_id: str, raw_results: list[dict]):
    """后台线程：juchao list 模式下异步下载公告 PDF 并提取正文。"""
    import sys as _sys, os as _os
    _juchao_dir = _os.path.join(_os.path.dirname(__file__), "..")
    if _juchao_dir not in _sys.path:
        _sys.path.insert(0, _juchao_dir)
    from search_engine.backends.juchao import juchao_fetch_pdf_text

    for idx, art in enumerate(raw_results):
        aid = f"a_{idx + 1:02d}"
        ann_id = art.get("_announce_id", "")
        ann_time = art.get("_announce_time", "")
        if not ann_id or not ann_time:
            continue

        pdf_text = juchao_fetch_pdf_text(ann_id, ann_time)
        if pdf_text:
            truncated_body, was_truncated = truncate_body(pdf_text)
            session_manager.set_article_body(
                session_id, aid,
                body_text=truncated_body,
                truncated=was_truncated,
                fetch_error="",
            )
        else:
            log_svc(session_id=session_id, engine="juchao", step="body_extract_fail",
                    error_code="PDF_DOWNLOAD_FAIL", message=f"PDF 下载失败: {aid}")
            report_error(
                error_code="PDF_DOWNLOAD_FAIL",
                engine="juchao",
                session_id=session_id,
                error_msg=f"PDF 下载失败或内容为空: {aid}",
                data={"article_id": aid, "announce_id": ann_id},
                function="_run_juchao_phase1_in_thread",
            )
            session_manager.set_article_body(
                session_id, aid,
                body_text="",
                truncated=False,
                fetch_error="PDF 下载失败或内容为空",
            )

    log_svc(session_id=session_id, engine="juchao", step="body_extract_done")
    # 标记全部就绪
    session_manager.set_list_done(session_id, time.time())


# ============================================================
# API 端点
# ============================================================

@app.post("/search", response_model=PollResponse)
async def search(req: SearchRequest):
    """
    发起搜索。

    mode=preview (同步):
        - 返回过滤后的预览文章列表（正文已提取）
        - 后台启动 Phase 2（LLM 分析）
    mode=full (异步，默认):
        - 返回 session_id，通过 /poll 轮询结果
        - 完整 pipeline（搜索 → 日期提取 → 过滤 → 正文 → LLM）
    mode=list (同步):
        - engine=sinafin: 返回文章列表（标题/ID/日期/URL），无正文，等 /extract
        - engine=ddg:     自动提取正文+日期+过滤，返回带字数预览，正文立即可取
        - engine=baidufin: 百度股市通资讯（含情绪/来源/摘要），返回即后台自动提取正文
        - engine=thsfin:   同花顺 F10 公司大事（含日期/类型/详情/URL），返回即后台自动提取有URL的文章正文
        - engine=dcfin:   东方财富股吧（热门/资讯/公告），含分类标签+精确到分钟的日期，返回即后台自动提取正文
        - engine=juchao:  巨潮盘后公告，仅返回列表（标题/日期），后台异步下载 PDF 提取正文
        - engine=qnainfo: 巨潮互动易问答，已回答条目含完整问答内容，列表返回时 body 即就绪
        - 通过 /article 端点按需取单篇正文
    """
    if req.mode == "list":
        # ── List 模式: 同步 Phase 0，后台 Phase 1 ──
        session_id = session_manager.create(
            req.query, req.keyword, req.max_results,
            mode="list", site=req.site, timelimit=req.timelimit,
            filter_days=req.filter_days, filter_title=req.filter_title,
            include_snippet=req.include_snippet, llm_mode=req.llm_mode,
            engine=req.engine,
            start_date=req.start_date, end_date=req.end_date,
        )

        try:
            start = time.time()
            log_svc(session_id=session_id, engine=req.engine, step="search_start", message=f"{req.query} filter_days={req.filter_days}")

            # 全局并发控制：等待槽位（最多等 MAX_SEARCH_WAIT 秒）
            try:
                await asyncio.wait_for(SEARCH_SEM.acquire(), timeout=MAX_SEARCH_WAIT)
            except asyncio.TimeoutError:
                report_error(
                    error_code="WORKER_BUSY",
                    function="search",
                    error_msg="所有搜索槽位已满，请求排队超时",
                )
                raise HTTPException(
                    status_code=503,
                    detail="服务繁忙，请稍后重试（所有搜索槽位已满）"
                )
            try:
                result = await asyncio.wait_for(run_search_pipeline(
                    req.query, req.keyword, req.max_results,
                    mode="list",
                    site=req.site, timelimit=req.timelimit,
                    filter_days=req.filter_days,
                    filter_title=req.filter_title,
                    include_snippet=req.include_snippet,
                    llm_mode=req.llm_mode,
                    engine=req.engine,
                    start_date=req.start_date,
                    end_date=req.end_date,
                ), timeout=SEARCH_TIMEOUT)
            finally:
                SEARCH_SEM.release()
            elapsed = time.time() - start

            # 提取 Phase 1 输入
            raw_for_phase1 = result.pop("_phase2_input", [])

            preview_data = {
                "articles": result.get("articles", []),
                "total": result.get("total", 0),
                "total_raw": result.get("total_raw", 0),
                "filter_stats": result.get("filter_stats", {}),
            }

            # 存入 session
            session_manager.set_preview(session_id, preview_data, raw_for_phase1, elapsed)

            # 空结果：无需后台线程，session 无存在意义，直接关闭
            if preview_data["total"] == 0:
                session_manager.close(session_id)
                log_svc(session_id=session_id, engine=req.engine, step="search_complete", elapsed_ms=int((time.time()-start)*1000), extra={"total": 0, "total_raw": preview_data["total_raw"]})
                return PollResponse(
                    session_id=session_id,
                    status="list_ready",
                    mode="list",
                    llm_mode="none",
                    engine=req.engine,
                    empty=True,
                    session_closed=True,
                    preview=preview_data,
                    elapsed=round(elapsed, 1),
                    created_at=session_manager.get(session_id).to_dict().get("created_at") if session_manager.get(session_id) else None,
                )

            # DDG 模式：正文已在 Phase 1 提取完毕，直接存入 article_bodies
            # 但 PDF 公告页跳过（后台异步提取），/article 返回 processing
            if req.engine == "ddg":
                pdf_articles = []
                for art in raw_for_phase1:
                    if art.get("_is_pdf", False):
                        pdf_articles.append(art)
                        continue  # 不存 body → /article 返回 processing
                    body = art.get("body_text", "")
                    truncated_body, was_truncated = truncate_body(body)
                    session_manager.set_article_body(
                        session_id, art["id"],
                        body_text=truncated_body,
                        truncated=was_truncated,
                        fetch_error=art.get("fetch_error", ""),
                    )
                # PDF 文章：后台异步提取（15 秒超时）
                if pdf_articles:
                    t = threading.Thread(
                        target=_run_ddg_pdf_extraction_in_thread,
                        args=(session_id, pdf_articles),
                        daemon=True,
                    )
                    t.start()
                session_manager.set_list_done(session_id, elapsed)

            log_svc(session_id=session_id, engine=req.engine, step="body_extract_start", message="启动后台提取线程")

            # Juchao 巨潮公告模式：后台异步下载 PDF 并提取正文
            if req.engine == "juchao":
                t = threading.Thread(
                    target=_run_juchao_phase1_in_thread,
                    args=(session_id, raw_for_phase1),
                    daemon=True,
                )
                t.start()

            # Sinafin 模式：不启动后台线程 — 正文改为按需加载。
            # _phase1_raw 已在 set_preview 中存好，/article 调用时从池子
            # 取出 URL，经全局节流阀后提取正文。

            # Baidufin 模式：后台自动提取全部文章正文（httpx → Playwright 兜底）
            if req.engine == "baidufin":
                t = threading.Thread(
                    target=_run_baidufin_phase1_in_thread,
                    args=(session_id, raw_for_phase1),
                    daemon=True,
                )
                t.start()

            # Thsfin 模式：后台自动提取有 URL 的文章正文（httpx → Playwright 兜底）
            if req.engine == "thsfin":
                t = threading.Thread(
                    target=_run_thsfin_phase1_in_thread,
                    args=(session_id, raw_for_phase1),
                    daemon=True,
                )
                t.start()

            # Dcfin 模式：后台自动提取全部文章正文（httpx → trafilatura+BS4 → Playwright 兜底）
            if req.engine == "dcfin":
                t = threading.Thread(
                    target=_run_dcfin_phase1_in_thread,
                    args=(session_id, raw_for_phase1),
                    daemon=True,
                )
                t.start()

            # QnAinfo 互动易问答：首次调用即返回完整问答内容（含 body_text）
            # 无列表/正文分离，直接存入 body，无需后台线程
            if req.engine == "qnainfo":
                for idx, art in enumerate(raw_for_phase1):
                    body = art.get("body_text", "") or art.get("_answer", "")
                    if body:
                        truncated_body, was_truncated = truncate_body(body)
                        session_manager.set_article_body(
                            session_id, f"a_{idx + 1:02d}",
                            body_text=truncated_body,
                            truncated=was_truncated,
                        )
                session_manager.set_list_done(session_id, elapsed)
                # qnainfo 一次性返回全部内容，无需保留 session
                session_manager.close(session_id)

            log_svc(session_id=session_id, engine=req.engine, step="search_complete", elapsed_ms=int((time.time()-start)*1000), extra={"total": result.get("total",0), "total_raw": result.get("total_raw",0)})

            # list 模式不做 LLM，强制 none
            status = "done" if req.engine in ("ddg", "qnainfo") else "list_ready"

            # created_at 在 set_preview 时已固定，get() 在 qnainfo close 后可能返回 None
            sess = session_manager.get(session_id)
            created_at = sess.to_dict().get("created_at") if sess else None

            return PollResponse(
                session_id=session_id,
                status=status,
                mode="list",
                llm_mode="none",
                engine=req.engine,
                preview=preview_data,
                elapsed=round(elapsed, 1),
                created_at=created_at,
            )

        except asyncio.TimeoutError:
            report_error(
                error_code="ENGINE_TIMEOUT",
                engine=req.engine,
                session_id=session_id,
                error_msg=f"搜索超时 ({SEARCH_TIMEOUT}s)",
                function="search",
                data={"query": req.query, "filter_days": req.filter_days},
            )
            session_manager.set_error(session_id, f"搜索超时 ({SEARCH_TIMEOUT}s)")
            session_manager.close(session_id)
            log_svc(session_id=session_id, engine=req.engine, step="search_timeout", error_code="ENGINE_TIMEOUT", elapsed_ms=SEARCH_TIMEOUT*1000)
            raise HTTPException(status_code=504, detail=f"搜索超时 ({SEARCH_TIMEOUT}s)")
        except Exception as e:
            report_error(
                error_code="ENGINE_ERROR",
                engine=req.engine,
                session_id=session_id,
                error_msg=str(e)[:1024],
                detail=traceback.format_exc() if hasattr(traceback, 'format_exc') else "",
                function="search",
                data={"query": req.query, "engine": req.engine},
            )
            session_manager.set_error(session_id, str(e))
            session_manager.close(session_id)
            log_svc(session_id=session_id, engine=req.engine, step="search_error", error_code="ENGINE_ERROR", message=str(e)[:200])
            raise HTTPException(status_code=500, detail=f"搜索失败: {e}")

    elif req.mode == "preview":
        # ── 预览模式: 同步 Phase 1 ──
        session_id = session_manager.create(
            req.query, req.keyword, req.max_results,
            mode="preview", site=req.site, timelimit=req.timelimit,
            filter_days=req.filter_days, filter_title=req.filter_title,
            include_snippet=req.include_snippet, llm_mode=req.llm_mode,
            engine=req.engine,
            start_date=req.start_date, end_date=req.end_date,
        )

        try:
            start = time.time()
            log_svc(session_id=session_id, engine=req.engine, step="search_start", message=f"{req.query} filter_days={req.filter_days}")

            # 全局并发控制：等待槽位
            try:
                await asyncio.wait_for(SEARCH_SEM.acquire(), timeout=MAX_SEARCH_WAIT)
            except asyncio.TimeoutError:
                report_error(
                    error_code="WORKER_BUSY",
                    function="search",
                    error_msg="所有搜索槽位已满，请求排队超时",
                )
                raise HTTPException(
                    status_code=503,
                    detail="服务繁忙，请稍后重试（所有搜索槽位已满）"
                )
            try:
                result = await asyncio.wait_for(run_search_pipeline(
                    req.query, req.keyword, req.max_results,
                    mode="preview",
                site=req.site, timelimit=req.timelimit,
                filter_days=req.filter_days,
                filter_title=req.filter_title,
                include_snippet=req.include_snippet,
                llm_mode=req.llm_mode,
                engine=req.engine,
                start_date=req.start_date,
                end_date=req.end_date,
            ), timeout=SEARCH_TIMEOUT)
            finally:
                SEARCH_SEM.release()
            elapsed = time.time() - start

            phase2_input = result.pop("_phase2_input", [])

            preview_data = {
                "articles": result.get("articles", []),
                "total": result.get("total", 0),
                "total_raw": result.get("total_raw", 0),
                "date_stats": result.get("date_stats", {}),
                "filter_stats": result.get("filter_stats", {}),
            }

            session_manager.set_preview(session_id, preview_data, phase2_input, elapsed)

            # 启动 Phase 2 后台线程
            t = threading.Thread(
                target=_run_preview_phase2_in_thread,
                args=(session_id, phase2_input, req.query, req.keyword, req.llm_mode),
                daemon=True,
            )
            t.start()

            return PollResponse(
                session_id=session_id,
                status="preview",
                mode="preview",
                llm_mode=req.llm_mode,
                engine=req.engine,
                preview=preview_data,
                elapsed=round(elapsed, 1),
                created_at=session_manager.get(session_id).to_dict().get("created_at"),
            )

        except Exception as e:
            session_manager.set_error(session_id, str(e))
            raise HTTPException(status_code=500, detail=f"搜索失败: {e}")

    else:
        # ── 完整模式: 异步（与 v1.0/v2.0 兼容） ──
        session_id = session_manager.create(
            req.query, req.keyword, req.max_results,
            mode="full", site=req.site, timelimit=req.timelimit,
            filter_days=req.filter_days, filter_title=req.filter_title,
            include_snippet=req.include_snippet, llm_mode=req.llm_mode,
            engine=req.engine,
            start_date=req.start_date, end_date=req.end_date,
        )

        t = threading.Thread(
            target=_run_full_pipeline_in_thread,
            args=(session_id, req.query, req.keyword, req.max_results,
                  "full", req.site, req.timelimit, req.llm_mode,
                  req.filter_days, req.filter_title, req.include_snippet,
                  req.engine, req.start_date, req.end_date),
            daemon=True,
        )
        t.start()

        sess = session_manager.get(session_id)
        return PollResponse(
            session_id=session_id,
            status="processing",
            mode="full",
            llm_mode=req.llm_mode,
            engine=req.engine,
            created_at=sess.to_dict().get("created_at") if sess else None,
        )


@app.post("/article", response_model=ArticleResponse)
async def get_article(req: ArticleRequest):
    """
    获取单篇文章正文（仅 list 模式）。

    请求 body:
        {"session_id": "s_...", "article_id": "a_01"}
        请求 body:
            {"session_id": "s_...", "article_id": "a_01"}
            {"session_id": "s_...", "article_ids": ["a_01", "a_03", "a_05"]}
            {"session_id": "s_...", "article_ids": ["a_01", "a_02"], "close": true}

        响应:
            articles: 每篇的状态和正文
            session_closed: True 表示本次返回后 session 已自动关闭

        说明：
            - 每调用一次 /article 计为 1 次正文请求，无论请求多少篇文章
            - 上限 2 次正文请求，第 2 次请求返回后自动关闭 session
            - processing/error 不消耗正文请求次数
    """
    sess = session_manager.get(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if sess.mode != "list":
        raise HTTPException(status_code=400,
                            detail="get_article 仅适用于 list 模式")

    # 解析请求的文章 ID 列表
    if req.article_ids:
        target_ids = req.article_ids
    elif req.article_id:
        target_ids = [req.article_id]
    else:
        raise HTTPException(status_code=400, detail="必须提供 article_id 或 article_ids")

    # 从 preview 构建 article_id → 基本信息 的映射
    preview_articles = (sess.preview or {}).get("articles", [])
    info_map = {a.get("id", ""): a for a in preview_articles}

    log_svc(session_id=req.session_id, step="article_fetch", extra={"article_ids": req.article_ids or [req.article_id] if req.article_id else []})

    # ── Sinafin 按需取正文（懒加载 + 全局节流） ──
    if sess.engine == "sinafin":
        for aid in target_ids:
            body = session_manager.get_article_body(req.session_id, aid)
            if body is not None:
                continue
            info = session_manager.get_article_info(req.session_id, aid)
            if not info or not info.get("url"):
                session_manager.set_article_body(
                    req.session_id, aid, body_text="", fetch_error="无可用 URL",
                )
                continue
            from sinafin_rate_limiter import wait_slot
            await asyncio.to_thread(wait_slot)
            body = session_manager.get_article_body(req.session_id, aid)
            if body is not None:
                continue
            from core import _fetch_single, _extract_body_from_html, truncate_body
            import random
            last_error = ""
            for attempt in range(3):
                try:
                    html_text, fetch_err = await _fetch_single(info["url"])
                    if html_text:
                        bt, _, _ = _extract_body_from_html(html_text)
                        if bt and bt.strip():
                            truncated_body, was_truncated = truncate_body(bt)
                            session_manager.set_article_body(
                                req.session_id, aid,
                                body_text=truncated_body or "",
                                truncated=was_truncated,
                            )
                            break  # 成功，跳出重试循环
                    last_error = fetch_err or "提取正文失败"
                except Exception as e:
                    last_error = str(e)[:200]
                # 最后一次失败后不再等待
                if attempt < 2:
                    wait = 1 + random.random() * 2
                    print(f"[sinafin] 第{attempt+1}次提取失败 ({last_error})，{wait:.1f}s 后重试", flush=True)
                    await asyncio.sleep(wait)
            else:
                # 3 次全部失败
                session_manager.set_article_body(
                    req.session_id, aid,
                    body_text="", fetch_error=last_error,
                )
                continue
            # 成功时已 break，这里继续下一篇文章
            continue

    # ── 先检查是否所有文章都已就绪或失败 ──
    all_statuses = set()
    for aid in target_ids:
        body = session_manager.get_article_body(req.session_id, aid)
        if body is None:
            all_statuses.add("processing")
        elif body.get("fetch_error"):
            all_statuses.add("error")
        else:
            all_statuses.add("ready")

    # 有任意一篇还是 processing → 整体返回 processing，articles 留空
    if "processing" in all_statuses:
        return ArticleResponse(
            session_id=req.session_id,
            status="processing",
            articles=[],
            session_closed=False,
        )

    # ── 全部就绪或失败 → 正常返回 ──
    results = []
    has_ready_body = False
    for aid in target_ids:
        info = info_map.get(aid, {})
        body = session_manager.get_article_body(req.session_id, aid)

        if body and body.get("fetch_error"):
            results.append(ArticleItem(
                article_id=aid, status="error",
                title=info.get("title", ""),
                url=info.get("url", ""),
                date=info.get("date", ""),
                fetch_error=body["fetch_error"],
            ))
        elif body:
            has_ready_body = True
            results.append(ArticleItem(
                article_id=aid, status="ready",
                title=info.get("title", ""),
                url=info.get("url", ""),
                date=info.get("date", ""),
                body_text=body.get("body_text", ""),
                truncated=body.get("truncated", False),
            ))
        else:
            results.append(ArticleItem(
                article_id=aid, status="processing",
                title=info.get("title", ""),
            ))

    # 本次请求有成功返回正文 → 消耗 1 次正文请求次数
    if has_ready_body:
        session_manager.increment_body_return(req.session_id)

    # 判断是否关闭
    closed = session_manager.close_after_article(req.session_id, req.close)

    # 顶层 status: 任一 ready → "ready", 全 error → "error"
    overall = "ready" if has_ready_body else "error"

    return ArticleResponse(
        session_id=req.session_id,
        status=overall,
        articles=results,
        session_closed=closed,
    )


@app.post("/extract", response_model=ExtractResponse)
async def extract(req: ExtractRequest):
    """
    提交需要提取正文的文章 ID 列表（仅 list 模式）。

    请求 body:
        {"session_id": "s_...", "article_ids": ["a_01", "a_03", "a_05"]}

    响应:
        {"session_id": "...", "status": "processing", "requested": 3}
    之后通过 /article 端点轮询各篇正文是否就绪。
    """
    sess = session_manager.get(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.mode != "list":
        raise HTTPException(status_code=400, detail="/extract 仅适用于 list 模式")

    # 从 session 中取出原始搜索结果
    raw_results = sess._phase1_raw
    if not raw_results:
        raise HTTPException(status_code=400, detail="Session data not available")

    # 检查 article_ids 是否有效 — 忽略不在预览列表中的 ID
    preview_articles = (sess.preview or {}).get("articles", [])
    existing_ids = {a["id"] for a in preview_articles}
    valid_ids = [aid for aid in req.article_ids if aid in existing_ids]

    if not valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"没有有效的 article_id。有效 ID: {sorted(existing_ids)}"
        )

    ignored = len(req.article_ids) - len(valid_ids)

    # 启动后台线程提取正文（20篇并行）
    t = threading.Thread(
        target=_run_list_phase1_in_thread,
        args=(req.session_id, raw_results, valid_ids, sess.llm_mode, sess.query, sess.keyword),
        daemon=True,
    )
    t.start()

    return ExtractResponse(
        session_id=req.session_id,
        status="processing",
        requested=len(valid_ids),
        ignored=ignored,
        message=f"已提交 {len(valid_ids)} 篇正文提取任务{'，忽略 ' + str(ignored) + ' 个无效 ID' if ignored else ''}",
    )


@app.get("/poll/{session_id}", response_model=PollResponse)
async def poll(session_id: str):
    """轮询搜索进度状态"""
    sess = session_manager.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or closed")

    data = sess.to_dict()

    if sess.status == "processing":
        return PollResponse(
            session_id=session_id, status="processing",
            mode=sess.mode, llm_mode=sess.llm_mode, engine=sess.engine,
        )

    if sess.status == "list_ready":
        return PollResponse(
            session_id=session_id, status="list_ready",
            mode="list", llm_mode=sess.llm_mode, engine=sess.engine,
            preview=data.get("preview"),
            elapsed=data.get("elapsed"),
            created_at=data.get("created_at"),
        )

    if sess.status == "preview":
        return PollResponse(
            session_id=session_id, status="preview",
            mode=sess.mode, llm_mode=sess.llm_mode, engine=sess.engine,
            preview=data.get("preview"),
            elapsed=data.get("elapsed"),
            created_at=data.get("created_at"),
        )

    # list + none done: articles 在 preview 中，不在 dict articles 字段
    if sess.mode == "list" and sess.status == "done" and not sess.articles:
        # 构建带 body_status 的预览传给 preview 字段
        arts = list(sess.preview.get("articles", [])) if sess.preview else []
        for a in arts:
            body = sess.article_bodies.get(a.get("id", ""))
            a["body_status"] = "ready" if body else "error"
        done_preview = {"articles": arts, "total": len(arts)}
        return PollResponse(
            session_id=session_id, status="done",
            mode="list", llm_mode="none", engine=sess.engine,
            preview=done_preview,
            elapsed=data.get("elapsed"),
            created_at=data.get("created_at"),
        )

    return PollResponse(
        session_id=session_id,
        status=data["status"],
        mode=data.get("mode"),
        llm_mode=data.get("llm_mode"),
        engine=data.get("engine"),
        preview=data.get("preview"),
        articles=data.get("articles"),
        segments=data.get("segments"),
        error=data.get("error"),
        elapsed=data.get("elapsed"),
        created_at=data.get("created_at"),
    )


@app.post("/segment", response_model=SegmentResponse)
async def get_segment(req: SegmentRequest):
    """获取指定段落的原文"""
    text = session_manager.get_segment_text(req.session_id, req.article_id, req.segment_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Segment not found or session not ready")
    return SegmentResponse(
        session_id=req.session_id,
        article_id=req.article_id,
        segment_id=req.segment_id,
        text=text,
    )


@app.get("/status/{session_id}", response_model=StatusResponse)
async def status(session_id: str):
    """查询会话状态"""
    data = session_manager.get_status(session_id)
    if data["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Session not found or closed")

    phase = None
    if data.get("mode") == "list":
        phase = "list_phase0" if data["status"] in ("list_ready", "processing") else "completed"
    elif data.get("mode") == "preview":
        phase = "preview" if data["status"] == "preview" else "full_analysis"
    else:
        phase = "pipeline_running" if data["status"] == "processing" else "completed"

    article_count = None
    articles = data.get("articles", data.get("preview", {}).get("articles"))
    if isinstance(articles, dict):
        article_count = len(articles)
    elif isinstance(articles, list):
        article_count = len(articles)

    return StatusResponse(
        session_id=session_id,
        status=data.get("status", "unknown"),
        mode=data.get("mode"),
        llm_mode=data.get("llm_mode"),
        engine=data.get("engine"),
        query=data.get("query"),
        keyword=data.get("keyword"),
        created_at=data.get("created_at"),
        elapsed=data.get("elapsed"),
        article_count=article_count,
        error=data.get("error"),
        phase=phase,
    )


@app.post("/close/{session_id}", response_model=CloseResponse)
async def close(session_id: str):
    """主动关闭会话"""
    ok = session_manager.close(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found or already closed")
    return CloseResponse(session_id=session_id, status="closed")


@app.post("/point-text", response_model=PointTextResponse)
async def point_text(req: PointTextRequest):
    """根据要点序号查找对应的原文段落（仅 summary 模式）"""
    sess = session_manager.get(req.session_id)
    if not sess or sess.status != "done":
        raise HTTPException(status_code=404, detail="Session not found or not ready")
    if sess.llm_mode != "summary":
        raise HTTPException(status_code=400, detail="point-text only available in summary mode")

    article = sess.articles.get(req.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    key_points = article.get("key_points", [])
    texts_data = sess._texts.get(req.article_id, {})
    chunks = texts_data.get("_chunks", [])
    kp_chunk_map = texts_data.get("_kp_chunk_map", [])

    from collections import defaultdict
    chunk_groups = defaultdict(list)
    for idx in req.point_indices:
        ci = kp_chunk_map[idx] if idx < len(kp_chunk_map) else 0
        chunk_groups[ci].append((idx, key_points[idx]))

    results = []

    async def _process_chunk(chunk_idx: int, items: list) -> list:
        chunk = chunks[chunk_idx] if chunk_idx < len(chunks) else []
        if not chunk:
            return [PointTextItem(point_index=orig_idx+1, key_point=kp, found=False, text="")
                    for orig_idx, kp in items]
        out = []
        if len(items) == 1:
            orig_idx, kp = items[0]
            prompt = build_point_locate_prompt(chunk, kp, all_key_points=[kp], target_index=1)
            raw = await _call_llm(prompt)
            paras = parse_point_locate_output(raw)
            valid = [p for p in paras if 1 <= p <= len(chunk)]
            out.append(PointTextItem(
                point_index=orig_idx+1, key_point=kp,
                found=bool(valid),
                text='\n\n'.join(chunk[p-1] for p in valid) if valid else "",
            ))
        else:
            point_lines = [f"{orig_idx+1}. {kp}" for orig_idx, kp in items]
            numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(chunk)])
            prompt = _prompt_batch_locate_template.format(
                point_list='\n'.join(point_lines), numbered_body=numbered,
            )
            raw = await _call_llm(prompt)
            for orig_idx, kp in items:
                tag = f"【{orig_idx+1}】"
                m = re.search(re.escape(tag) + r'\s*段落[：:]\s*(.+)', raw)
                if m:
                    res_str = m.group(1).strip()
                    if res_str in ('无', '「无」'):
                        out.append(PointTextItem(
                            point_index=orig_idx+1, key_point=kp, found=False, text="",
                        ))
                    else:
                        paras = parse_point_locate_output(f"【段落】{res_str}")
                        valid = [p for p in paras if 1 <= p <= len(chunk)]
                        out.append(PointTextItem(
                            point_index=orig_idx+1, key_point=kp,
                            found=bool(valid),
                            text='\n\n'.join(chunk[p-1] for p in valid) if valid else "",
                        ))
                else:
                    out.append(PointTextItem(
                        point_index=orig_idx+1, key_point=kp, found=False, text="",
                    ))
        return out

    chunk_tasks = [_process_chunk(ci, items) for ci, items in chunk_groups.items()]
    chunk_results_lists = await asyncio.gather(*chunk_tasks)
    results = [item for sublist in chunk_results_lists for item in sublist]
    results.sort(key=lambda r: r.point_index)

    return PointTextResponse(
        session_id=req.session_id,
        article_id=req.article_id,
        results=results,
    )


@app.get("/")
async def root():
    return {
        "service": "bot_search API",
        "version": "3.0.0",
        "modes": ["preview", "full", "list"],
        "engines": ["ddg", "sinafin", "baidufin", "thsfin", "dcfin", "juchao"],
        "new_features": [
            "引擎分发 (engine: ddg | sinafin | baidufin | thsfin | dcfin | juchao)",
            "list 模式: 返回文章列表 + 按需取单篇正文",
            "正文截断8000字（list 模式）",
            "sinafin/thsfin 精确日期（跳过日期提取）",
            "日期范围过滤 (start_date / end_date)",
            "juchao: 巨潮盘后公告，列表秒回 + 后台异步 PDF 提取正文",
        ],
    }
