"""
bot_search API - FastAPI 应用

用法:
    uvicorn api:app --host 0.0.0.0 --port 8300 --reload
"""

import asyncio, time, threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import run_search_pipeline
from core import _call_llm, build_point_locate_prompt, parse_point_locate_output
import os, re
_PROMPT_BATCH_LOCATE_PATH = os.path.join(os.path.dirname(__file__), "prompts", "point_locate_batch.txt")
with open(_PROMPT_BATCH_LOCATE_PATH, encoding='utf-8') as f:
    _prompt_batch_locate_template = f.read()
from session_manager import manager as session_manager

app = FastAPI(title="bot_search API", version="1.0.0")


# ============================================================
# 请求/响应模型
# ============================================================

class SearchRequest(BaseModel):
    query: str
    keyword: str = ""
    max_results: int = 5
    session: str = "new"
    mode: str = "segments"
    site: str | None = None
    timelimit: str | None = None


class PollResponse(BaseModel):
    session_id: str
    status: str
    mode: str | None = None
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
    point_indices: list[int]  # 要点序号列表（从1开始），如 [1,4,9]


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
    query: str | None = None
    keyword: str | None = None
    created_at: str | None = None
    elapsed: float | None = None
    article_count: int | None = None
    error: str | None = None


class CloseResponse(BaseModel):
    session_id: str
    status: str


# ============================================================
# 后台处理线程
# ============================================================

def _run_pipeline_in_thread(session_id: str, query: str, keyword: str, max_results: int,
                             mode: str = "segments", site: str | None = None, timelimit: str | None = None):
    """在新线程中执行 pipeline，完成后更新 session 状态"""

    async def _run():
        try:
            result = await run_search_pipeline(query, keyword, max_results, mode, site=site, timelimit=timelimit)
            elapsed = time.time() - start
            session_manager.set_done(
                session_id,
                articles=result["articles"],
                segments=result["segments"],
                texts=result["_texts"],
                elapsed=elapsed
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
    """发起新搜索"""
    session_id = session_manager.create(req.query, req.keyword, req.max_results, req.mode, req.site, req.timelimit)

    # 启动后台线程执行 pipeline
    t = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(session_id, req.query, req.keyword, req.max_results, req.mode, req.site, req.timelimit),
        daemon=True
    )
    t.start()

    return PollResponse(
        session_id=session_id,
        status="processing",
        created_at=session_manager.get(session_id).to_dict().get("created_at")
    )


@app.get("/poll/{session_id}", response_model=PollResponse)
async def poll(session_id: str):
    """轮询搜索结果是否就绪"""
    sess = session_manager.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found or closed")

    if sess.status == "processing":
        return PollResponse(session_id=session_id, status="processing", mode=sess.mode)

    data = sess.to_dict()
    return PollResponse(
        session_id=session_id,
        status=data["status"],
        mode=data.get("mode"),
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
        text=text
    )


@app.get("/status/{session_id}", response_model=StatusResponse)
async def status(session_id: str):
    """查询会话状态详情"""
    data = session_manager.get_status(session_id)
    if data["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Session not found or closed")
    return StatusResponse(
        session_id=session_id,
        status=data.get("status", "unknown"),
        mode=data.get("mode"),
        query=data.get("query"),
        keyword=data.get("keyword"),
        created_at=data.get("created_at"),
        elapsed=data.get("elapsed"),
        article_count=len(data.get("articles", {})) if data.get("articles") else None,
        error=data.get("error"),
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
    """根据要点序号查找对应的原文段落"""
    sess = session_manager.get(req.session_id)
    if not sess or sess.status != "done":
        raise HTTPException(status_code=404, detail="Session not found or not ready")
    if sess.mode != "summary":
        raise HTTPException(status_code=400, detail="point-text only available in summary mode")

    article = sess.articles.get(req.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    key_points = article.get("key_points", [])

    # 按块分组，同块要点合并一次 LLM 调用
    from collections import defaultdict
    chunk_groups = defaultdict(list)
    for idx in indices:
        ci = kp_chunk_map[idx] if idx < len(kp_chunk_map) else 0
        chunk_groups[ci].append((idx, key_points[idx]))

    # (已在模块顶部导入)
    results = []

    async def _process_chunk(chunk_idx: int, items: list) -> list:
        chunk = chunks[chunk_idx]
        chunk_kps = [kp for _, kp in items]
        out = []
        if len(items) == 1:
            orig_idx, kp = items[0]
            prompt = build_point_locate_prompt(chunk, kp, all_key_points=chunk_kps, target_index=1)
            raw = await _call_llm(prompt)
            paras = parse_point_locate_output(raw)
            valid = [p for p in paras if 1 <= p <= len(chunk)]
            out.append(PointTextItem(point_index=orig_idx+1, key_point=kp,
                                     found=bool(valid),
                                     text='\n\n'.join(chunk[p-1] for p in valid) if valid else ""))
        else:
            point_lines = [f"{orig_idx+1}. {kp}" for orig_idx, kp in items]
            numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(chunk)])
            prompt = _prompt_batch_locate_template.format(point_list='\n'.join(point_lines), numbered_body=numbered)
            raw = await _call_llm(prompt)
            for orig_idx, kp in items:
                tag = f"【{orig_idx+1}】"
                m = re.search(re.escape(tag) + r'\s*段落[：:]\s*(.+)', raw)
                if m:
                    res_str = m.group(1).strip()
                    if res_str in ('无', '「无」'):
                        out.append(PointTextItem(point_index=orig_idx+1, key_point=kp, found=False, text=""))
                    else:
                        paras = parse_point_locate_output(f"【段落】{res_str}")
                        valid = [p for p in paras if 1 <= p <= len(chunk)]
                        out.append(PointTextItem(point_index=orig_idx+1, key_point=kp, found=bool(valid),
                                                  text='\n\n'.join(chunk[p-1] for p in valid) if valid else ""))
                else:
                    out.append(PointTextItem(point_index=orig_idx+1, key_point=kp, found=False, text=""))
        return out

    chunk_tasks = [_process_chunk(ci, items) for ci, items in chunk_groups.items()]
    chunk_results_lists = await asyncio.gather(*chunk_tasks)
    results = [item for sublist in chunk_results_lists for item in sublist]
    results.sort(key=lambda r: r.point_index)
    return PointTextResponse(session_id=req.session_id, article_id=req.article_id, results=results)


@app.get("/")
async def root():
    return {"service": "bot_search API", "version": "1.0.0"}
