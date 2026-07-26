"""
调试日志 — 记录每个请求/提取步骤的详细时间线和结果。
写入独立文件，不依赖 stdout（避免被服务日志淹没）。

用法:
    from reporting.debug_log import DLog
    DLog.log("search_start", session_id="s_xxx", engine="sinafin",
             query="600519", extra={"filter_days": 90})
"""
import os, json, threading, time
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_LOCK = threading.Lock()
_LOG_FILE = None
_SESSION = None  # 当前日志文件名（按天滚动）


def _get_log_file():
    global _LOG_FILE
    today = datetime.now().strftime("%Y%m%d")
    if _LOG_FILE is None or today not in _LOG_FILE:
        _LOG_FILE = os.path.join(_LOG_DIR, f"debug_{today}.log")
    return _LOG_FILE


class DLog:
    """调试日志写入器（线程安全）。"""

    @staticmethod
    def log(step: str, **kwargs):
        """写一条调试日志。

        Args:
            step: 步骤标识，如 "fetch_start", "fetch_done", "extract_start"
            **kwargs: 任意 key=value 上下文（session_id, engine, url, status, elapsed_ms, error...）
        """
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "ts_unix": time.time(),
            "pid": os.getpid(),
            "thread": threading.current_thread().name[:20],
            "step": step,
        }
        entry.update(kwargs)

        # 截断长字符串
        for k, v in entry.items():
            if isinstance(v, str) and len(v) > 300:
                entry[k] = v[:300] + "..."

        line = json.dumps(entry, ensure_ascii=False)

        with _LOCK:
            try:
                with open(_get_log_file(), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass  # 日志失败不打断主流程

    @staticmethod
    def log_extract(session_id: str, engine: str, article_id: str, url: str,
                    step: str, status: str = "", elapsed_ms: int = 0,
                    body_len: int = 0, error: str = "", extra: dict | None = None):
        """提取流程专用日志（标准化字段）。"""
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "pid": os.getpid(),
            "thread": threading.current_thread().name[:20],
            "session_id": session_id[:32] if session_id else "",
            "engine": engine[:16],
            "article_id": article_id[:8],
            "step": step,
            "status": status[:16],
            "url": url[:150] if url else "",
            "elapsed_ms": int(elapsed_ms),
            "body_len": body_len,
            "error": (str(error)[:100] if error else ""),
        }
        if extra:
            entry["extra"] = extra

        line = json.dumps(entry, ensure_ascii=False)
        with _LOCK:
            try:
                with open(_get_log_file(), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
