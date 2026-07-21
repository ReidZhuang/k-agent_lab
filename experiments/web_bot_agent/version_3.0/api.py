"""
bot_search API v3.0 — 引擎分发 + mode=list + 单篇正文按需提取

新增功能:
  1. engine 参数: "ddg"(默认) | "sinafin" | "baidu"
  2. mode=list: 返回文章列表即止，后台逐篇提取正文（截断8000字）
  3. /article/{session_id}/{article_id} 按需取单篇正文
  4. start_date / end_date 日期过滤（透传给 sinafin）

用法:
    uvicorn api:app --host 0.0.0.0 --port 8300 --reload
"""
import asyncio, time, threading, re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from core import run_search_pipeline
from core import _call_llm, build_point_locate_prompt, parse_point_locate_output
from core import phase1_fetch_and_extract, truncate_body
from session_manager import manager as session_manager

_PROMPT_BATCH_LOCATE_PATH = __import__('os').path.join(
    __import__('os').path.dirname(__file__), "prompts", "point_locate_batch.txt"
)
with open(_PROMPT_BATCH_LOCATE_PATH, encoding='utf-8') as f:
    _prompt_batch_locate_template = f.read()

app = FastAPI(title="bot_search API v3.0", version="3.0.0")


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
    engine: str = "ddg"                   # "ddg" | "sinafin" | "baidufin"
    start_date: str | None = None
    end_date: str | None = None


class PollResponse(BaseModel):
    session_id: str
    status: str            # processing | preview | list_ready | done | error
    mode: str | None = None
    llm_mode: str | None = None
    engine: str | None = None
    empty: bool | None = None      # true: 无结果正常空；false: 有结果；null: 出错或未完成
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
    article_id: str


class ArticleResponse(BaseModel):
    session_id: str
    article_id: str
    status: str            # "ready" | "processing" | "error"
    title: str = ""
    url: str = ""
    date: str = ""
    body_text: str = ""
    truncated: bool = False
    fetch_error: str = ""


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
            result = await run_search_pipeline(
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
            )
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


def _run_baidufin_phase1_in_thread(session_id: str, raw_results: list[dict]):
    """后台线程: baidufin 模式自动提取全部文章正文（httpx→trafilatura，失败则 Playwright 兜底）"""
    from core import truncate_body, _fetch_single, _extract_body_from_html, _extract_with_playwright
    import asyncio, time

    start = time.time()

    async def _fetch_all():
        """Phase 1: 用 httpx 并行提取"""
        from core import phase1_fetch_and_extract
        return await phase1_fetch_and_extract(
            raw_results, max_parallel=10, include_snippet=True, truncate=True,
        )

    # ── 第1步: httpx + trafilatura 并行提取 ──
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        phase1_results = loop.run_until_complete(_fetch_all())
    finally:
        loop.close()

    # ── 第2步: 找出失败的需要 Playwright 兜底 ──
    failed = [a for a in phase1_results
              if not a.get("body_text") or sum(1 for c in a["body_text"] if not c.isspace()) < 20]

    if failed:
        urls = [a["url"] for a in failed]
        print(f"[baidufin] {len(failed)} 篇需要 Playwright 兜底提取", flush=True)
        pw_bodies = _extract_with_playwright(urls)
        for art in failed:
            pw_body = pw_bodies.get(art["url"], "")
            if pw_body and sum(1 for c in pw_body if not c.isspace()) >= 20:
                body, truncated = truncate_body(pw_body)
                art["body_text"] = body
                art["truncated"] = truncated

    # ── 第3步: 存入 session（失败的文章也存入，body_text 为空 + fetch_error）──
    for art in phase1_results:
        body = art.get("body_text", "") or ""
        fetch_err = art.get("fetch_error", "")
        # Playwright 兜底也失败了 → body 还是空的
        if not body.strip() and not fetch_err:
            fetch_err = "httpx + Playwright 均无法提取正文"
        truncated_body, was_truncated = truncate_body(body) if body.strip() else ("", False)
        session_manager.set_article_body(
            session_id, art["id"],
            body_text=truncated_body,
            truncated=was_truncated,
            fetch_error=fetch_err,
        )

    elapsed = time.time() - start
    session_manager.set_list_done(session_id, elapsed)
    print(f"[baidufin] {len(phase1_results)} 篇正文提取完成, {len(failed)} 篇 Playwright 兜底, 耗时 {elapsed:.1f}s", flush=True)


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
            result = await run_search_pipeline(
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
            )
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

            # DDG 模式：正文已在 Phase 1 提取完毕，直接存入 article_bodies
            if req.engine == "ddg":
                for art in raw_for_phase1:
                    body = art.get("body_text", "")
                    truncated_body, was_truncated = truncate_body(body)
                    session_manager.set_article_body(
                        session_id, art["id"],
                        body_text=truncated_body,
                        truncated=was_truncated,
                        fetch_error=art.get("fetch_error", ""),
                    )
                session_manager.set_list_done(session_id, elapsed)

            # Baidufin 模式：后台自动提取全部文章正文（httpx → Playwright 兜底）
            if req.engine == "baidufin":
                t = threading.Thread(
                    target=_run_baidufin_phase1_in_thread,
                    args=(session_id, raw_for_phase1),
                    daemon=True,
                )
                t.start()

            # list 模式不做 LLM，强制 none
            status = "done" if req.engine == "ddg" else "list_ready"

            return PollResponse(
                session_id=session_id,
                status=status,
                mode="list",
                llm_mode="none",
                engine=req.engine,
                preview=preview_data,
                elapsed=round(elapsed, 1),
                created_at=session_manager.get(session_id).to_dict().get("created_at"),
            )

        except Exception as e:
            session_manager.set_error(session_id, str(e))
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
            result = await run_search_pipeline(
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
            )
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

    响应:
        如果正文已提取: status="ready", body_text="..."
        如果正在提取:   status="processing"
        如果出错:       status="error", fetch_error="..."
    """
    sess = session_manager.get(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if sess.mode != "list":
        raise HTTPException(status_code=400,
                            detail="get_article 仅适用于 list 模式")

    # 从 preview 中找文章基本信息
    article_info = None
    preview = sess.preview or {}
    for art in preview.get("articles", []):
        if art.get("id") == req.article_id:
            article_info = art
            break

    title = (article_info or {}).get("title", "")
    url = (article_info or {}).get("url", "")
    date = (article_info or {}).get("date", "")

    # 检查正文是否已提取
    body = session_manager.get_article_body(req.session_id, req.article_id)
    if body is None:
        return ArticleResponse(
            session_id=req.session_id,
            article_id=req.article_id,
            status="processing",
            title=title,
            url=url,
            date=date,
        )

    if body.get("fetch_error"):
        return ArticleResponse(
            session_id=req.session_id,
            article_id=req.article_id,
            status="error",
            title=title,
            url=url,
            date=date,
            fetch_error=body["fetch_error"],
        )

    return ArticleResponse(
        session_id=req.session_id,
        article_id=req.article_id,
        status="ready",
        title=title,
        url=url,
        date=date,
        body_text=body.get("body_text", ""),
        truncated=body.get("truncated", False),
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
        "engines": ["ddg", "sinafin", "baidufin"],
        "new_features": [
            "引擎分发 (engine: ddg | sinafin | baidu)",
            "list 模式: 返回文章列表 + 按需取单篇正文",
            "正文截断8000字（list 模式）",
            "sinafin 精确日期（跳过日期提取）",
            "日期范围过滤 (start_date / end_date)",
        ],
    }
