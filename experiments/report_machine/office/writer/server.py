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
for _d in ("midday", "endday"):
    _p = os.path.normpath(os.path.join(_OFFICE_DIR, "..", "data_fetch", _d))
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
                _WRITER_POOL = ThreadPoolExecutor(
                    max_workers=_writer_cfg.get("main_pool_workers", 4))
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
# 端到端测试: 可用环境变量 E2E_SUBWRITER_DIR 覆盖 context 样本目录(默认不变)
_CONTEXT_SAMPLE_DIR = os.path.normpath(
    os.environ.get("E2E_SUBWRITER_DIR", os.path.join(_OFFICE_DIR, "context_samples"))
)
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
                     fetch_message_text: str, report_id: str, query: str = "",
                     report_type: str = "noon") -> SubWorkerResult:
    """单个股票的 sub writer

    流程：
      1. 并行解析 fetch data + 调 middleman Type A
      2. checklist 齐全后组装 context
      3. POST reporter（总闸 25 分钟: error 无限重试同一 context, 到点直接失败）
      4. 失败 → 记录异常
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
        query=query,
        report_type=report_type,
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

    # ── POST reporter（总闸设计, 2026-08-04） ──
    # 从第一次请求开始计时(总闸 sub_writer_total_timeout=1500s):
    #   - reporter 返回非 ok(error / HTTP 非 200 / 请求超时) → 用同一 context 无限重试
    #   - 总闸到点 → 直接返回失败给 commander, 终结可能的重试死循环
    #   - 单次请求 timeout = 总闸剩余时间(reporter 非流式, 处理期间无数据, read 空闲≈总等待)
    # reporter 内部所有超时(LLM read 180s×3 次尝试 / 正文)都会返回明确 error, 重试安全(无双份生成)
    _SUB_WRITER_TOTAL_TIMEOUT = _writer_cfg.get("sub_writer_total_timeout", 1500)
    t_deadline = time.time() + _SUB_WRITER_TOTAL_TIMEOUT
    attempt = 0
    log("post_reporter_start", stock_name=stock_name, context_size=len(json.dumps(context.model_dump())))
    while True:
        remaining = t_deadline - time.time()
        attempt += 1
        if remaining <= 0:
            err_msg = f"sub writer 总超时({_SUB_WRITER_TOTAL_TIMEOUT}s, {attempt-1} 次尝试后放弃)"
            log_office_error(
                module="office.writer",
                function="_run_sub_writer",
                level="ERROR",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=err_msg,
                error_code="WRITER_SUB_TOTAL_TIMEOUT",
            )
            return SubWorkerResult(stock_name=stock_name, success=False, error=err_msg)
        log("post_reporter_attempt", stock_name=stock_name, attempt=attempt,
            remaining=round(remaining))
        try:
            resp = _HTTP_SESSION.post(
                f"{_REPORTER_URL}/api/v1/generate",
                json=context.model_dump(),
                timeout=remaining,
            )
            if resp.ok:
                result_data = resp.json()
                if result_data.get("status") == "ok":
                    log("post_reporter_success", stock_name=stock_name,
                        output=result_data.get("output_path", ""),
                        _elapsed=time.time()-t_sub)
                    return SubWorkerResult(stock_name=stock_name, success=True)
                # reporter 明确报错(200 + status=error) → 记录后重试(总闸内)
                err_msg = f"reporter 返回 {result_data.get('status')}: {result_data.get('error', '')[:300]}"
                log_office_error(
                    module="office.writer",
                    function="_run_sub_writer",
                    level="WARNING",
                    stock_name=stock_name, ts_code=ts_code,
                    error_msg=err_msg,
                    error_code="REPORTER_RETURNED_ERROR",
                )
                continue
            # HTTP 非 200 → 记录后重试(瞬时故障, 总闸内)
            err_msg = f"reporter 返回 HTTP {resp.status_code}"
            log_office_error(
                module="office.writer",
                function="_run_sub_writer",
                level="WARNING",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=err_msg,
                error_code="REPORTER_HTTP_ERROR",
            )
            continue
        except (requests.Timeout, requests.ConnectionError) as e:
            log_office_error(
                module="office.writer",
                function="_run_sub_writer",
                level="WARNING",
                stock_name=stock_name, ts_code=ts_code,
                error_msg=f"POST reporter 超时(剩余 {remaining:.0f}s): {e}",
                error_code="WRITER_REPORTER_TIMEOUT",
            )
            continue


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
    query = req.query
    report_type = req.report_type
    log = get_logger("writer_api")
    t_start = time.time()
    log("report_start", report_id=report_id, stocks=stock_names, report_type=report_type)

    if not stock_names:
        raise HTTPException(status_code=400, detail="股票列表不能为空")

    # ── 1. 股票名称 → 代码 ──
    infos = batch_name_info(stock_names)
    if not infos:
        raise HTTPException(status_code=400, detail="所有股票名称均无法识别")

    # ── 2. Fetcher 取数（按 report_type 选择脚本） ──
    data_by_stock, warnings_by_tscode = fetcher.fetch_all(stock_names, report_type)
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
                _run_sub_writer, name, info, data_text, msg_text, report_id, query, report_type
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
    workers = _writer_cfg.get("workers", 4)
    uvicorn.run("server:app", host=host, port=port, workers=workers)
