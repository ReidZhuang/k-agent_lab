"""启动入口 — 强制 spawn 避免 fork 锁问题。"""
import multiprocessing, os, json
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

# 从 config.json 读取 workers，支持环境变量覆盖
_config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
try:
    with open(_config_path) as f:
        _cfg = json.load(f)
    _cfg_workers = _cfg.get("server", {}).get("workers", 12)
except Exception:
    _cfg_workers = 12
workers = int(os.environ.get("WORKERS", str(_cfg_workers)))

import uvicorn
uvicorn.run("api:app", host="0.0.0.0", port=8300, workers=workers, backlog=2048)
