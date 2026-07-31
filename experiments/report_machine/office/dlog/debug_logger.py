"""
压力测试日志系统 — JSONL 格式，可开关

每个组件通过 log_step() 记录各环节耗时和数据。
通过 config.yaml 中 logging.debug_logger: true/false 控制。
"""
import os
import json
import time
import threading
from datetime import datetime

_OFFICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_LOG_DIR = os.path.join(_OFFICE_DIR, "test_drive", "results", "debug_logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_LOCK = threading.Lock()
_ENABLED = True  # 运行时动态开关


class DebugLogger:
    """按组件分文件的结构化日志器"""

    def __init__(self, component: str):
        self.component = component
        date = datetime.now().strftime("%Y%m%d")
        self.path = os.path.join(_LOG_DIR, f"{component}_{date}.jsonl")

    def log(self, step: str, data: dict, elapsed_ms: float | None = None):
        """写一行 JSONL 日志"""
        if not _ENABLED:
            return
        entry = {
            "t": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "ts": time.time(),
            "component": self.component,
            "step": step,
            "elapsed_ms": round(elapsed_ms, 1) if elapsed_ms is not None else None,
        }
        entry.update(data)
        with _LOCK:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def __call__(self, step: str, **data):
        """快速调用方式: logger('step_name', key=value, ...)"""
        elapsed_s = data.pop("_elapsed", None)
        self.log(step, data, elapsed_ms=elapsed_s * 1000 if elapsed_s is not None else None)


# ── 快捷创建 ──
_loggers = {}


def get_logger(component: str) -> DebugLogger:
    if component not in _loggers:
        _loggers[component] = DebugLogger(component)
    return _loggers[component]


def set_enabled(enabled: bool):
    global _ENABLED
    _ENABLED = enabled
