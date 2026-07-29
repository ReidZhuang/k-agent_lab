"""
sinafin 并发控制器 — 最多 N 个并发请求（从 config.json search.sinafin.max_concurrent 读取）。

取代旧版 1.8s 固定间隔文件锁（串行化），新设计：
  - Semaphore(N)：最多 N 个线程同时访问 sinafin
  - 请求之间无强制间隔，真正并行
  - N 由配置文件控制

用法:
    from sinafin_rate_limiter import acquire_slot, release_slot
    acquire_slot()
    # ... fetch sinafin ...
    release_slot()

    或使用上下文管理器:
    with slot():
        # ... fetch sinafin ...
"""
import threading
import contextlib
import json
import os

# 从 config.json 读取 max_concurrent，默认 40
_config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
try:
    with open(_config_path) as f:
        _cfg = json.load(f)
    _MAX_CONCURRENT = _cfg.get("search", {}).get("sinafin", {}).get("max_concurrent", 40)
except Exception:
    _MAX_CONCURRENT = 40

_SEM = threading.Semaphore(_MAX_CONCURRENT)


def acquire_slot():
    """获取一个 sinafin 请求槽位（阻塞直到有空位）"""
    _SEM.acquire()


def release_slot():
    """释放一个槽位"""
    _SEM.release()


@contextlib.contextmanager
def slot():
    """上下文管理器用法"""
    try:
        acquire_slot()
        yield
    finally:
        release_slot()
