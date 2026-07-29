"""
sinafin 并发控制器 — 最多 10 个并发请求。

取代旧版 1.8s 固定间隔文件锁（串行化），新设计：
  - Semaphore(10)：最多 10 个线程同时访问 sinafin
  - 请求之间无强制间隔，真正并行
  - 10 的上限防止反爬

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

# 全局并发上限 10（跨所有 worker 进程）
# 每个 worker 独立计数，8 workers → 最多 80 并发
# 但实际受 1.8s 旧锁串行化，不受此限
# 新设计：每个 worker 最多 2 个并发，8 workers ≈ 16 总并发
_SEM = threading.Semaphore(10)


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
