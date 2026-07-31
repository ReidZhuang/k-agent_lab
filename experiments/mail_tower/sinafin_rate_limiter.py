"""
sinafin 跨进程请求节流器 — 保证全局 1-2 秒间隔。

所有 worker 共享同一个文件锁，确保对 sinafin URL 的访问间隔 >= GAP 秒。

用法:
    from sinafin_rate_limiter import wait_slot
    wait_slot()          # 阻塞直到可以访问
    wait_slot(1.5)       # 自定义间隔
"""

import fcntl, json, os, time

_RATE_DIR = os.path.join(os.path.dirname(__file__), "sessions")
_RATE_FILE = os.path.join(_RATE_DIR, ".sinafin_rate.json")
_DEFAULT_GAP = 1.8  # 秒


def wait_slot(min_gap: float = _DEFAULT_GAP) -> None:
    """等待直到可以访问 sinafin URL（全局跨进程节流）。

    用 fcntl.flock LOCK_EX 做原子化的 读-判-写：
      - 读到上次访问时间 → 不够间隔 → 释放锁，sleep，重试
      - 够间隔 → 写入当前时间 → 返回

    min_gap: 最小间隔秒数，默认 1.8
    """
    os.makedirs(_RATE_DIR, exist_ok=True)

    while True:
        # 打开（或创建）状态文件，拿到 fd
        try:
            fd = os.open(_RATE_FILE, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            time.sleep(0.1)
            continue

        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # 用二进制模式讀寫，避免編碼問題
            with os.fdopen(fd, "rb+") as f:
                content = f.read()
                if content:
                    try:
                        data = json.loads(content.decode("utf-8"))
                        last = data.get("t", 0.0)
                    except (json.JSONDecodeError, ValueError):
                        last = 0.0
                else:
                    last = 0.0

                now = time.time()
                if now - last >= min_gap:
                    # 轮到我们了 — 更新時間戳并返回
                    f.seek(0)
                    f.truncate()
                    f.write(json.dumps({"t": now}).encode("utf-8"))
                    f.flush()
                    os.fsync(fd)  # 确保刷盘
                    return  # ✅ 拿到槽位

                remaining = min_gap - (now - last)
        except Exception:
            # 任何意外异常 → 释放锁，稍后重试
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except Exception:
                pass
            time.sleep(0.2)
            continue

        # 等够了再重试（不持有锁，不阻塞其他 worker）
        time.sleep(min(remaining + 0.15, 0.5))
