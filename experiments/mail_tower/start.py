"""
mail_tower 启动入口 — 解决 uvicorn fork 后 threading.Lock 幽灵死锁问题。

问题:
  uvicorn 默认用 fork 创建 worker。父进程中 asyncio.Semaphore / threading.Lock
  在 fork 后子进程继承半初始化状态，属于「废弃状态」— 调用 acquire() 永久阻塞。

解决:
  强制 multiprocessing 用 spawn 方式（重新导入模块，不继承锁状态）。
"""
import multiprocessing
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # 已设置

import uvicorn
import os

if __name__ == "__main__":
    workers = int(os.environ.get("WORKERS", "12"))
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8300,
        workers=workers,
        backlog=2048,
    )
