"""
Reporter — 接收 context，启动 agent loop，输出分析报告

端点：
  POST /api/v1/generate — 生成单只股票的午间报告
"""
import os
import sys
import time
import uuid
import asyncio
import threading
import concurrent.futures

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── sys.path ──
_OFFICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _OFFICE_DIR not in sys.path:
    sys.path.insert(0, _OFFICE_DIR)

from models import ReportContext, ReporterResponse
from cfg import load_config
from database import log_office_error
from reporter import agent
from dlog.debug_logger import get_logger

_cfg = load_config()
_reporter_cfg = _cfg.get("reporter", {})

# ── 延迟创建线程池（fork-safe） ──
_THREAD_POOL = None
_POOL_LOCK = threading.Lock()

def _get_pool():
    global _THREAD_POOL
    if _THREAD_POOL is None:
        with _POOL_LOCK:
            if _THREAD_POOL is None:
                _THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
                    max_workers=_reporter_cfg.get("thread_pool_size", 64))
    return _THREAD_POOL

app = FastAPI(title="Office Reporter", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/generate")
async def generate_report(ctx: ReportContext):
    """生成单只股票的午间分析报告

    接收 sub writer 传来的 context，启动 agent loop。
    """
    report_id = uuid.uuid4().hex[:12]
    _log = get_logger("reporter")
    _log("handler_enter", report_id=report_id, stock_name=ctx.stock_name,
         ts_code=ctx.ts_code)

    t0 = time.time()
    try:
        _log("before_get_pool", report_id=report_id, stock_name=ctx.stock_name)
        pool = _get_pool()
        _log("after_get_pool", report_id=report_id, stock_name=ctx.stock_name)

        loop = asyncio.get_running_loop()
        _log("before_run_in_executor", report_id=report_id, stock_name=ctx.stock_name)
        output_path, rounds_used = await loop.run_in_executor(
            pool, agent.run, ctx
        )
        _log("after_run_in_executor", report_id=report_id, stock_name=ctx.stock_name,
             rounds=rounds_used, output=output_path or "", _elapsed=time.time()-t0)
    except agent.EmptyLLMResponseError as e:
        # LLM 返回空内容 → 明确失败(2026-08-04): writer 收到 error 后在总闸内重试
        log_office_error(
            module="office.reporter",
            function="generate_report",
            level="ERROR",
            stock_name=ctx.stock_name, ts_code=ctx.ts_code,
            error_msg=str(e),
            error_code="REPORTER_EMPTY_RESPONSE",
        )
        return ReporterResponse(
            report_id=report_id,
            status="error",
            error=str(e),
        )
    except Exception as e:
        log_office_error(
            module="office.reporter",
            function="generate_report",
            level="ERROR",
            stock_name=ctx.stock_name, ts_code=ctx.ts_code,
            error_msg=f"agent.run 异常: {e}",
            error_code="REPORTER_AGENT_ERROR",
        )
        return ReporterResponse(
            report_id=report_id,
            status="error",
            error=f"报告生成异常: {e}",
        )

    if not output_path:
        # 无任何内容可交付(如达到最大轮次未生成)→ 统一 error(2026-08-04 删除 partial 状态)
        return ReporterResponse(
            report_id=report_id,
            status="error",
            error="未生成完整报告",
            rounds=rounds_used,
        )

    return ReporterResponse(
        report_id=report_id,
        status="ok",
        output_path=output_path,
        rounds=rounds_used,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "office-reporter"}


if __name__ == "__main__":
    import uvicorn
    host = _reporter_cfg.get("host", "0.0.0.0")
    port = _reporter_cfg.get("port", 8312)
    workers = _reporter_cfg.get("workers", 4)
    uvicorn.run("server:app", host=host, port=port, workers=workers)
