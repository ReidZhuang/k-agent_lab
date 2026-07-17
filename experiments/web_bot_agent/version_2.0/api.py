"""
bot_search API v2.0 — 双阶段搜索 API

新增功能:
  1. mode=preview: 搜索 → fetch HTML → 日期提取 → 过滤 → 同步返回预览
  2. 后台 Phase 2: trafilatura 正文提取 + LLM 分析（可通过 /poll 查询进度）
  3. filter_days / filter_title 过滤参数
  4. include_snippet 选项

用法:
    uvicorn api:app --host 0.0.0.0 --port 8300 --reload
"""
import asyncio, time, threading, re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import run_search_pipeline
from core import _call_llm, build_point_locate_prompt, parse_point_locate_output
from session_manager import manager as session_manager

_PROMPT_BATCH_LOCATE_PATH = __import__('os').path.join(
    __import__('os').path.dirname(__file__), "prompts", "point_locate_batch.txt"
)
with open(_PROMPT_BATCH_LOCATE_PATH, encoding='utf-8') as f:
    _prompt_batch_locate_template = f.read()

app = FastAPI(title="bot_search API v2.0", version="2.0.0")


# ============================================================
# 请求/响应模型
# ============================================================

class SearchRequest(BaseModel):
    query: str
    keyword: str = ""
    max_results: int = 5
    mode: str = "full"                     # "preview" | "full"
    session: str = "new"
    site: str | None = None
    timelimit: str | None = None
    # v2.0 新参数
    filter_days: int | None = None         # 时间过滤（天）
    filter_title: str | None = None        # 标题正则/关键词
    include_snippet: bool = False          # 预览结果是否包含 snippet
    llm_mode: str = "segments"            # "segments" | "summary" (仅 mode=full)


class PollResponse(BaseModel):
    session_id: str
    status: str            # processing | preview | done | error
    mode: str | None = None
    llm_mode: str | None = None
    preview: dict | None = None
    articles: dict | None = None
    segments: dict | None = None
    error: str | None = None
    elapsed: float | None = None
    created_at: str | None = None


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


# ============================================================
# 后台处理函数
# ============================================================

def _run_full_pipeline_in_thread(session_id: str, query: str, keyword: str,
                                  max_results: int, mode: str, site: str | None,
                                  timelimit: str | None, llm_mode: str,
                                  filter_days: int | None, filter_title: str | None,
                                  include_snippet: bool):
    """后台线程: 运行完整 pipeline (Phase 1 + Phase 2)"""

    async def _run():
        try:
            result = await run_search_pipeline(
                query, keyword, max_results,
                mode="full",  # full 模式, 内部跑 Phase 1+2
                site=site, timelimit=timelimit,
                filter_days=filter_days,
                filter_title=filter_title,
                include_snippet=include_snippet,
                llm_mode=llm_mode,
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


# ============================================================
# API 端点
# ============================================================

@app.post("/search", response_model=PollResponse)
async def search(req: SearchRequest):
    """
    发起搜索。

    mode=preview (同步):
        - 返回过滤后的预览文章列表
        - 后台启动 Phase 2（正文提取 + LLM）
    mode=full (异步，默认):
        - 返回 session_id，通过 /poll 轮询结果
        - 完整 pipeline（搜索 → 日期提取 → 过滤 → 正文 → LLM）
    """
    if req.mode == "preview":
        # ── 预览模式: 同步 Phase 1 ──
        session_id = session_manager.create(
            req.query, req.keyword, req.max_results,
            mode="preview", site=req.site, timelimit=req.timelimit,
            filter_days=req.filter_days, filter_title=req.filter_title,
            include_snippet=req.include_snippet, llm_mode=req.llm_mode,
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
            )
            elapsed = time.time() - start

            # 提取 Phase 2 输入（含 body_text+paragraphs，正文已提取完毕）
            phase2_input = result.pop("_phase2_input", [])

            preview_data = {
                "articles": result.get("articles", []),
                "total": result.get("total", 0),
                "total_raw": result.get("total_raw", 0),
                "date_stats": result.get("date_stats", {}),
                "filter_stats": result.get("filter_stats", {}),
            }

            # 存入 session（Phase 1 完成）
            session_manager.set_preview(session_id, preview_data, phase2_input, elapsed)

            # 启动 Phase 2 后台线程（仅 LLM，正文已就绪）
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
                preview=preview_data,
                elapsed=round(elapsed, 1),
                created_at=session_manager.get(session_id).to_dict().get("created_at"),
            )

        except Exception as e:
            session_manager.set_error(session_id, str(e))
            raise HTTPException(status_code=500, detail=f"搜索失败: {e}")

    else:
        # ── 完整模式: 异步（与 v1.0 兼容） ──
        session_id = session_manager.create(
            req.query, req.keyword, req.max_results,
            mode="full", site=req.site, timelimit=req.timelimit,
            filter_days=req.filter_days, filter_title=req.filter_title,
            include_snippet=req.include_snippet, llm_mode=req.llm_mode,
        )

        t = threading.Thread(
            target=_run_full_pipeline_in_thread,
            args=(session_id, req.query, req.keyword, req.max_results,
                  "full", req.site, req.timelimit, req.llm_mode,
                  req.filter_days, req.filter_title, req.include_snippet),
            daemon=True,
        )
        t.start()

        sess = session_manager.get(session_id)
        return PollResponse(
            session_id=session_id,
            status="processing",
            mode="full",
            llm_mode=req.llm_mode,
            created_at=sess.to_dict().get("created_at") if sess else None,
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
            mode=sess.mode, llm_mode=sess.llm_mode,
        )

    if sess.status == "preview":
        return PollResponse(
            session_id=session_id, status="preview",
            mode=sess.mode, llm_mode=sess.llm_mode,
            preview=data.get("preview"),
            elapsed=data.get("elapsed"),
            created_at=data.get("created_at"),
        )

    return PollResponse(
        session_id=session_id,
        status=data["status"],
        mode=data.get("mode"),
        llm_mode=data.get("llm_mode"),
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
    if data.get("mode") == "preview":
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
        "version": "2.0.0",
        "modes": ["preview", "full"],
        "new_features": [
            "分层日期提取 (HIGH/MEDIUM/LOW 置信度)",
            "时间范围过滤 (filter_days)",
            "标题正则过滤 (filter_title)",
            "轻量级预览列表 (include_snippet)",
            "双阶段 Pipeline (Phase 1 实时返回, Phase 2 后台)",
        ],
    }
