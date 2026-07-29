# Sinafin 并行取正文 — 设计记录

## 背景

mail_tower 的 sinafin 引擎原本使用 **1.8s 固定间隔文件锁**（`wait_slot()`）序列化所有正文提取请求。每个请求必须等前一个完成满 1.8s 后才能开始，多篇文章串行提取，效率低。

## 新设计：滑动并发控制

### 核心思路

用 **`threading.Semaphore(10)`** 替代 1.8s 文件锁。最多 10 个线程同时发 HTTP 请求到 sinafin，请求之间无强制等待间隔，真正并行。

### 实现文件

**`mail_tower/sinafin_rate_limiter.py`**

```python
_SEM = threading.Semaphore(10)

def acquire_slot():
    \"""获取一个 sinafin 请求槽位（阻塞直到有空位）\"""
    _SEM.acquire()

def release_slot():
    \"""释放一个槽位\"""
    _SEM.release()

@contextlib.contextmanager
def slot():
    \"""上下文管理器用法\"""
    try:
        acquire_slot()
        yield
    finally:
        release_slot()
```

### 使用方式

在 `/article` handler 的 sinafin 按需加载路径中：

```python
from sinafin_rate_limiter import acquire_slot, release_slot

if body not cached:
    await asyncio.to_thread(acquire_slot)
    try:
        # fetch + extract article body (真正并行)
    finally:
        await asyncio.to_thread(release_slot)
```

### 效果对比

| 指标 | 旧版（1.8s 锁） | 新版（Semaphore 10） |
|:-----|:--------------:|:-------------------:|
| 提取 5 篇文章 | ~109s（串行 1.8s×5+20s×5）| **~20s**（10 并发）|
| 并发上限 | 1 请求/1.8s（全局串行）| 10 请求同时跑 |
| 反爬风险 | 低 | 低（已验证 80 只无触发）|
| 实现复杂度 | 文件锁 + 跨进程同步 | 单进程 Semaphore |

### 注意事项

- `Semaphore` 是 `threading` 级别，**每进程独立**。8 个 uvicorn worker = 理论上 80 总并发，但在实践中 8×10=80 对 sinafin 仍安全（已测试验证）
- 如果将来需要跨进程共享，可改为文件锁+滑动窗口（已在 `acquire_slot` 的旧版实现中实验过，过于复杂）
- 当前 10 的并发量对 sinafin 服务器友好，初次调用时已验证无反爬触发
