"""
v3.0 错误报送模块 — 标准化错误代码 + 自动写入数据库 error_log。

用法:
    from reporting.error_reporter import report_error, ERROR_CODES

    report_error(
        error_code="ENGINE_TIMEOUT",
        engine="sinafin",
        session_id="s_xxx",
        error_msg="search timed out after 90s",
    )

    # 捕获当前异常
    try:
        risky_operation()
    except Exception:
        report_exception(error_code="BODY_EXTRACT_FAIL", engine="thsfin")
"""

import os
import sys
import json
import uuid
import traceback
import sqlite3
import threading
from datetime import datetime

# ── 模块标识 ──
SERVICE_NAME = "v3.0_api"
_WORKER_ID = str(os.getpid())

# ── 数据库路径 ──
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", "..", "..",
    "database", "report_market.db",
)
_DB_PATH = os.path.normpath(_DB_PATH)

# ── 数据库连接（lazy 初始化，线程安全） ──
_conn = None
_conn_lock = threading.Lock()


def _get_conn():
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is not None:
            return _conn
        try:
            _conn = sqlite3.connect(_DB_PATH)
        except Exception:
            _conn = None
    return _conn


# ============================================================
# 错误代码字典
# ============================================================

ERROR_CODES = {
    # ── 搜索阶段 ──
    "ENGINE_TIMEOUT": {
        "code": "ENGINE_TIMEOUT", "level": "ERROR",
        "message": "搜索引擎执行超时",
        "description": "run_search_pipeline() 超过 90s 超时限制",
    },
    "ENGINE_ERROR": {
        "code": "ENGINE_ERROR", "level": "ERROR",
        "message": "搜索引擎返回错误",
        "description": "后端引擎抛出异常或返回 HTTP 500",
    },
    "ENGINE_EMPTY": {
        "code": "ENGINE_EMPTY", "level": "WARNING",
        "message": "搜索返回空结果",
        "description": "引擎正常执行但返回 0 条文章",
    },
    "ENGINE_ANTI_CRAWL": {
        "code": "ENGINE_ANTI_CRAWL", "level": "WARNING",
        "message": "搜索触发反爬",
        "description": "页面返回验证码/身份核实（如 dcfin 东方财富）",
    },
    "ENGINE_NAME_RESOLVE": {
        "code": "ENGINE_NAME_RESOLVE", "level": "WARNING",
        "message": "股票名称解析失败",
        "description": "无法将股票名称映射到 6 位数字代码",
    },

    # ── 正文提取 ──
    "BODY_EXTRACT_FAIL": {
        "code": "BODY_EXTRACT_FAIL", "level": "WARNING",
        "message": "文章正文提取失败",
        "description": "httpx/Playwright 无法获取文章正文",
    },
    "BODY_EXTRACT_EMPTY": {
        "code": "BODY_EXTRACT_EMPTY", "level": "WARNING",
        "message": "正文提取为空",
        "description": "页面无文字内容（SPA 页面或 JS 渲染）",
    },
    "PDF_DOWNLOAD_FAIL": {
        "code": "PDF_DOWNLOAD_FAIL", "level": "ERROR",
        "message": "PDF 下载失败",
        "description": "巨潮公告 PDF 无法下载",
    },
    "PDF_EXTRACT_FAIL": {
        "code": "PDF_EXTRACT_FAIL", "level": "WARNING",
        "message": "PDF 文字提取失败",
        "description": "扫描件或加密 PDF",
    },

    # ── Session ──
    "SESSION_NOT_FOUND": {
        "code": "SESSION_NOT_FOUND", "level": "WARNING",
        "message": "Session 不存在或已过期",
        "description": "session_id 无效或已被清理（45 分钟 TTL）",
    },
    "SESSION_CLOSED": {
        "code": "SESSION_CLOSED", "level": "INFO",
        "message": "Session 已关闭",
        "description": "Session 正常关闭",
    },

    # ── 系统 ──
    "RATE_LIMIT": {
        "code": "RATE_LIMIT", "level": "WARNING",
        "message": "引擎速率限制",
        "description": "引擎内部速率限制触发",
    },
    "INTERNAL_ERROR": {
        "code": "INTERNAL_ERROR", "level": "CRITICAL",
        "message": "服务内部错误",
        "description": "未预期的内部异常（需人工介入）",
    },
    "WORKER_BUSY": {
        "code": "WORKER_BUSY", "level": "WARNING",
        "message": "服务繁忙",
        "description": "所有 worker 槽位满，请求排队超时",
    },
}


# ============================================================
# 内部写入函数
# ============================================================

def _write_db(
    module="", function="", level="ERROR",
    api_name="", error_msg="", detail="", data_snapshot="",
    service_name="", error_code="", engine_name="",
    session_id="", worker_id="",
):
    """直接写入 error_log 表"""
    conn = _get_conn()
    if not conn:
        return
    try:
        batch_id = uuid.uuid4().hex[:12]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        err_type = error_msg.split(":")[0][:64] if ":" in error_msg else error_msg[:64]

        conn.execute(
            """INSERT INTO error_log
               (batch_id, timestamp, module, function, level,
                api_name, error_type, error_msg, detail, data_snapshot,
                service_name, error_code, engine_name, session_id, worker_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batch_id, now,
                str(module)[:64], str(function)[:64], str(level)[:16],
                str(api_name)[:64] if api_name else None,
                str(err_type)[:64],
                str(error_msg)[:1024],
                str(detail)[:2048] if detail else "",
                str(data_snapshot)[:2048] if data_snapshot else "",
                str(service_name)[:64] if service_name else None,
                str(error_code)[:64] if error_code else None,
                str(engine_name)[:32] if engine_name else None,
                str(session_id)[:64] if session_id else None,
                str(worker_id)[:32] if worker_id else None,
            ),
        )
        conn.commit()
    except Exception:
        pass  # 错误报送自身失败不打断主流程


# ============================================================
# 公开 API
# ============================================================

def report_error(
    error_code: str = "INTERNAL_ERROR",
    engine: str = "",
    session_id: str = "",
    error_msg: str = "",
    detail: str = "",
    data: dict | None = None,
    function: str = "",
):
    """将 v3.0 错误记录写入数据库 error_log。

    Args:
        error_code: 错误代码（来自 ERROR_CODES 字典）
        engine: 引擎名称（如 'sinafin', 'juchao'）
        session_id: 会话 ID
        error_msg: 错误描述
        detail: 详细错误信息（堆栈等）
        data: 上下文数据，会序列化为 JSON 存入 data_snapshot
        function: 函数名
    """
    code_info = ERROR_CODES.get(error_code, ERROR_CODES["INTERNAL_ERROR"])

    data_str = json.dumps(data, ensure_ascii=False) if data else ""
    if len(data_str) > 2048:
        data_str = data_str[:2048]

    try:
        _write_db(
            module=f"{SERVICE_NAME}.{engine}" if engine else SERVICE_NAME,
            function=function or "",
            level=code_info["level"],
            api_name=engine or "",
            error_msg=error_msg or code_info["message"],
            detail=str(detail)[:2048] if detail else "",
            data_snapshot=data_str,
            service_name=SERVICE_NAME,
            error_code=error_code,
            engine_name=engine or "",
            session_id=session_id or "",
            worker_id=_WORKER_ID,
        )
    except Exception:
        pass  # 不打断主流程


def report_exception(
    error_code: str = "INTERNAL_ERROR",
    engine: str = "",
    session_id: str = "",
    function: str = "",
    data: dict | None = None,
):
    """捕获当前异常并报送（自动提取 traceback）"""
    exc = sys.exc_info()[1]
    report_error(
        error_code=error_code,
        engine=engine,
        session_id=session_id,
        error_msg=str(exc) if exc else "Unknown error",
        detail=traceback.format_exc(),
        data=data,
        function=function,
    )
