"""
bot_search API - FastAPI 应用

用法:
    uvicorn api:app --host 0.0.0.0 --port 8300 --reload
"""

import asyncio, time, threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import run_search_pipeline
from session_manager import manager as session_manager

app = FastAPI(title="bot_search API", version="1.0.0")


# ============================================================
# 请求/响应模型
# ============================================================

class SearchRequest(BaseModel):
    query: str
    keyword: str = ""
    max_results: int = 5
    session: str = "new"  # "new" 或 session_id（仅当组装层想复用已有 session 时）


class PollResponse(BaseModel):
    session_id: str
    status: str
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


class StatusResponse(BaseModel):
    session_id: str
    status: str
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

def _run_pipeline_in_thread(session_id: str, query: str, keyword: str, max_results: int):
    """在新线程中执行 pipeline，完成后更新 session 状态"""

    async def _run():
        try:
            result = await run_search_pipeline(query, keyword, max_results)
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
    session_id = session_manager.create(req.query, req.keyword, req.max_results)

    # 启动后台线程执行 pipeline
    t = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(session_id, req.query, req.keyword, req.max_results),
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
        return PollResponse(session_id=session_id, status="processing")

    data = sess.to_dict()
    return PollResponse(
        session_id=session_id,
        status=data["status"],
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


@app.get("/")
async def root():
    return {"service": "bot_search API", "version": "1.0.0"}
