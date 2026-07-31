"""启动入口 — 强制 spawn 避免 fork 锁问题。"""
import multiprocessing, os
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

import uvicorn
workers = int(os.environ.get("WORKERS", "12"))
uvicorn.run("api:app", host="0.0.0.0", port=8300, workers=workers, backlog=2048)
