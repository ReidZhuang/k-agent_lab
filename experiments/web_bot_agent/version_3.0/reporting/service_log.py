"""
v3.0 服务日志 — 记录每个 worker 的请求步骤，用于问题排查。

与 error_log 的关系:
  error_log 记录"发生了什么错误"
  service_log 记录"请求经历了哪些步骤"

排查流程:
  1. error_log 发现错误 → 拿到 session_id + timestamp
  2. service_log 查同一 session_id 的完整步骤链 → 定位问题环节
  3. 结合步骤耗时（elapsed_ms）判断是慢查询还是崩溃

用法:
    from reporting.service_log import log_svc

    # 记录步骤
    log_svc(session_id="s_xxx", engine="sinafin", step="search_start")
    log_svc(session_id="s_xxx", step="search_complete", elapsed_ms=1234)
    log_svc(session_id="s_xxx", step="body_extract_fail",
            error_code="PDF_DOWNLOAD_FAIL", message="PDF 下载失败")
"""
import os
import json
import sqlite3
import threading
from datetime import datetime

_SERVICE_NAME = "v3.0_api"
_WORKER_ID = str(os.getpid())

_DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", "..", "..",
    "database", "report_market.db",
))

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


def log_svc(
    session_id: str = "",
    engine: str = "",
    step: str = "",
    message: str = "",
    elapsed_ms: int = 0,
    error_code: str = "",
    level: str = "INFO",
    extra: dict | None = None,
):
    """写入一条服务日志。

    Args:
        session_id: 会话 ID
        engine: 引擎名称
        step: 步骤标识（见下方步骤表）
        message: 描述信息
        elapsed_ms: 该步骤耗时（毫秒）
        error_code: 关联的错误代码（如有）
        level: INFO / WARNING / ERROR
        extra: 额外上下文（dict，不含敏感数据）
    """
    conn = _get_conn()
    if not conn:
        return
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else ""

        conn.execute(
            """INSERT INTO service_log_v3
               (timestamp, worker_id, session_id, engine, level,
                step, message, elapsed_ms, error_code, extra)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                _WORKER_ID,
                str(session_id)[:64] if session_id else None,
                str(engine)[:32] if engine else None,
                str(level)[:16],
                str(step)[:64],
                str(message)[:256] if message else "",
                int(elapsed_ms) if elapsed_ms > 0 else None,
                str(error_code)[:64] if error_code else None,
                extra_json[:2048] if extra_json else "",
            ),
        )
        conn.commit()
    except Exception:
        pass  # 日志自身失败不打断主流程


# ============================================================
# 步骤标识速查
# ============================================================
#
# 搜索阶段:
#   search_start       — POST /search 收到请求
#   search_queue_wait  — 等待并发槽位（可能返回 503）
#   search_complete    — 搜索完成，列表返回
#   search_error       — 搜索报错（关联 error_code）
#   search_timeout     — 搜索超时 90s
#
# 后台正文提取:
#   body_extract_start   — 后台线程开始提取
#   body_extract_done    — 全部文章提取完成
#   body_extract_fail    — 单篇提取失败（关联 error_code）
#
# 取正文:
#   article_fetch      — POST /article 请求
#   article_ready      — 返回 ready 正文
#   article_error      — 返回 error（关联 error_code）
#
# Session:
#   session_close      — session 关闭（正常或报错）
#   session_expire     — session 过期清理
