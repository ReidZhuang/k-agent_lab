"""
Writer — Office 系统入口 API

接收股票列表 → 调用 fetcher 取数 → 启动 sub writer 池 → 发送 reporter

一个端点：
  POST /api/v1/report — 主入口
"""
import os
import sys
import json
import time
import uuid
import asyncio
import random
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── sys.path ──
_OFFICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _OFFICE_DIR not in sys.path:
    sys.path.insert(0, _OFFICE_DIR)
_MIDDAY_DIR = os.path.normpath(
    os.path.join(_OFFICE_DIR, "..", "data_fetch", "midday")
)
if _MIDDAY_DIR not in sys.path:
    sys.path.insert(0, _MIDDAY_DIR)

from dlog.debug_logger import get_logger
import fetcher
from models import (
    ReportRequest, ReportResponse, SubWorkerResult, ReportContext,
)
from cfg import load_config
from database import log_office_error
from name_to_code import batch_name_info

# ── 配置加载 ──
_cfg = load_config()
_writer_cfg = _cfg.get("writer", {})
_reporter_cfg = _cfg.get("reporter", {})
_middleman_cfg = _cfg.get("middleman", {})
_MAX_WORKERS = _writer_cfg.get("sub_worker_max_workers", 64)
_MIDDLEMAN_URL = f"http://{_middleman_cfg.get('host', 'localhost')}:{_middleman_cfg.get('port', 8311)}"
_REPORTER_URL = f"http://{_reporter_cfg.get('host', 'localhost')}:{_reporter_cfg.get('port', 8312)}"

# ── Writer 线程池（非阻塞，fork-safe） ──
_WRITER_POOL = None
_POOL_LOCK = threading.Lock()

def _get_writer_pool():
    global _WRITER_POOL
    if _WRITER_POOL is None:
        with _POOL_LOCK:
            if _WRITER_POOL is None:
                _WRITER_POOL = ThreadPoolExecutor(max_workers=4)
    return _WRITER_POOL

# ── 共享 HTTP 连接池（大连接池防耗尽） ──
_HTTP_SESSION = requests.Session()
_HTTP_ADAPTER = requests.adapters.HTTPAdapter(
    pool_connections=200, pool_maxsize=200, max_retries=0
)
_HTTP_SESSION.mount("http://", _HTTP_ADAPTER)
_HTTP_SESSION.mount("https://", _HTTP_ADAPTER)

_FALLBACK_DIR = os.path.normpath(os.path.join(_OFFICE_DIR, "fallback"))
os.makedirs(_FALLBACK_DIR, exist_ok=True)
_OUTPUT_DIR = os.path.normpath(os.path.join(_OFFICE_DIR, "output"))
_CONTEXT_SAMPLE_DIR = os.path.normpath(os.path.join(_OFFICE_DIR, "context_samples"))
os.makedirs(_CONTEXT_SAMPLE_DIR, exist_ok=True)

# ── FastAPI ──
app = FastAPI(title="Office Writer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================================
# Sub Writer
# ======================================================================

def _run_sub_writer(stock_name: str, stock_info: dict, fetch_data_text: str,
                     fetch_message_text: str, report_id: str) -> SubWorkerResult:
    """单个股票的 sub writer

    流程：
      1. 并行解析 fetch data + 调 middleman Type A
      2. checklist 齐全后组装 context
      3. POST reporter（30s 超时，3 次重试）
      4. 失败兜底 → 保存 context + 记录异常
    """
    t_start = time.time()
    ts_code = stock_info.get("ts_code", "")
    symbol = stock_info.get("symbol", "")

    def _call_type_a():
        """调用 middleman Type A"""
        try:
            resp = _HTTP_SESSION.post(
                f"{_MIDDLEMAN_URL}/api/v1/search",
                json={"writer_id": report_id, "stock_code": symbol},
                timeout=180,
            )
            if resp.ok:
                return resp.json().get("results", {})
            log_office_error(
                module="office.writer",
                function="_run_sub_writer._call_type_a",
                level="WARNING",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=f"middleman Type A 返回 {resp.status_code}",
            )
            return {}
        except Exception as e:
            log_office_error(
                module="office.writer",
                function="_run_sub_writer._call_type_a",
                level="WARNING",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=f"middleman Type A 异常: {e}",
            )
            return {}

    # ── 并行执行：解析 fetch data + 调 middleman ──
    log = get_logger("writer_sub")
    t_sub = time.time()
    articles = {}
    middleman_warnings = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_articles = pool.submit(_call_type_a)
        # fetch 文本直接使用（已由 fetcher 格式化好）

        articles = fut_articles.result()
    t_type_a = time.time()
    log("type_a_done", stock_name=stock_name, engines=len(articles),
        _elapsed=t_type_a - t_sub)

    # 收集 middleman 异常
    for engine, result in articles.items():
        if result.get("error"):
            middleman_warnings.append(f"{engine}: {result['error']}")

    # ── 组装 context ──
    context = ReportContext(
        stock_name=stock_name,
        ts_code=ts_code,
        fetch_data=fetch_data_text,
        fetch_message=fetch_message_text,
        fetch_warnings={},
        articles=articles,
        middleman_warnings=middleman_warnings,
    )

    # ── 保存 context 样本（用于研究 prompt，POST reporter 前保存） ──
    try:
        sample_path = os.path.join(
            _CONTEXT_SAMPLE_DIR,
            f"{stock_name}_{report_id}_context.json"
        )
        with open(sample_path, "w", encoding="utf-8") as f:
            json.dump(context.model_dump(), f, ensure_ascii=False, indent=2)
        print(f"  📄 context 已保存: {sample_path}")
    except Exception as e:
        print(f"  ⚠️  context 保存失败: {e}")

    # ── POST reporter（超时 180s/90s/60s，3 次重试） ──
    retry_timeouts = [180, 90, 60]
    log("post_reporter_start", stock_name=stock_name, context_size=len(json.dumps(context.model_dump())))
    for attempt, (delay, to) in enumerate(zip([2, 5, 10], retry_timeouts)):
        try:
            resp = _HTTP_SESSION.post(
                f"{_REPORTER_URL}/api/v1/generate",
                json=context.model_dump(),
                timeout=to,
            )
            if resp.ok:
                result_data = resp.json()
                if result_data.get("status") in ("ok",):
                    log("post_reporter_success", stock_name=stock_name,
                        output=result_data.get("output_path",""),
                        _elapsed=time.time()-t_sub)
                    return SubWorkerResult(stock_name=stock_name, success=True)
                # reporter 返回了 200 但 status=error/partial
                if attempt < 2:
                    time.sleep(delay + random.random())
                    continue
            # 服务端错误 → 重试
            if attempt < 2:
                time.sleep(delay + random.random())
                continue
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < 2:
                time.sleep(delay + random.random())
                continue
            log_office_error(
                module="office.writer",
                function="_run_sub_writer",
                level="ERROR",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=f"POST reporter 超时（3 次）: {e}",
                error_code="WRITER_REPORTER_TIMEOUT",
            )

    # ── 响应丢失检查：reporter 实际已成功但响应没回来？ ──
    today = time.strftime("%Y%m%d")
    expected_path = os.path.join(
        _OUTPUT_DIR, stock_name, f"{today}_{stock_name}_midday.md"
    )
    if os.path.exists(expected_path):
        log("post_reporter_recovered", stock_name=stock_name,
            output=expected_path, _elapsed=time.time()-t_sub)
        return SubWorkerResult(stock_name=stock_name, success=True)

    # ── 兜底：保存 context ──
    fallback_path = os.path.join(
        _FALLBACK_DIR, f"{stock_name}_{report_id}_{int(time.time())}.json"
    )
    try:
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump(context.model_dump(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    log_office_error(
        module="office.writer",
        function="_run_sub_writer",
        level="ERROR",
        stock_name=stock_name, ts_code=ts_code,
        error_msg=f"sub writer 失败，context 已保存到 {fallback_path}",
        error_code="WRITER_SUB_WORKER_FAILED",
    )

    return SubWorkerResult(
        stock_name=stock_name, success=False,
        error=f"reporter 无响应，context 已保存",
    )


# ======================================================================
# API 端点
# ======================================================================

@app.post("/api/v1/report")
async def create_report(req: ReportRequest):
    """生成报告入口（非阻塞版）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _get_writer_pool(), _sync_create_report, req
    )


def _sync_create_report(req: ReportRequest) -> ReportResponse:
    """同步执行函数（在 _WRITER_POOL 线程中运行）"""
    report_id = uuid.uuid4().hex[:12]
    stock_names = req.stock_names
    log = get_logger("writer_api")
    t_start = time.time()
    log("report_start", report_id=report_id, stocks=stock_names)

    if not stock_names:
        raise HTTPException(status_code=400, detail="股票列表不能为空")

    # ── 1. 股票名称 → 代码 ──
    infos = batch_name_info(stock_names)
    if not infos:
        raise HTTPException(status_code=400, detail="所有股票名称均无法识别")

    # ── 2. Fetcher 取数 ──
    data_by_stock, warnings_by_tscode = fetcher.fetch_all(stock_names)
    if not data_by_stock:
        return ReportResponse(
            report_id=report_id, total=0, success=0,
            failed=stock_names, results=[],
        )

    # ── 3. 启动 sub writer ──
    results = []
    with ThreadPoolExecutor(max_workers=min(len(infos), _MAX_WORKERS)) as pool:
        fut_map = {}
        for info in infos:
            name = info["name"]
            data_text = data_by_stock.get(name, {}).get("data", "")
            msg_text = data_by_stock.get(name, {}).get("message", "")
            fut = pool.submit(
                _run_sub_writer, name, info, data_text, msg_text, report_id
            )
            fut_map[fut] = name

        for fut in as_completed(fut_map):
            try:
                result = fut.result()
                results.append(result)
            except Exception as e:
                name = fut_map[fut]
                results.append(SubWorkerResult(stock_name=name, success=False, error=str(e)))

    success = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    log("report_done", report_id=report_id, total=len(results),
        success=len(success), failed=[r.stock_name for r in failed],
        _elapsed=time.time()-t_start)

    return ReportResponse(
        report_id=report_id,
        total=len(results),
        success=len(success),
        failed=[r.stock_name for r in failed],
        results=results,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "office-writer"}


# ======================================================================
# 启动入口
# ======================================================================

if __name__ == "__main__":
    import uvicorn
    host = _writer_cfg.get("host", "0.0.0.0")
    port = _writer_cfg.get("port", 8310)
    uvicorn.run("server:app", host=host, port=port, workers=4)
