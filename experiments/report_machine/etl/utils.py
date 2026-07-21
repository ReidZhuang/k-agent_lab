"""
ETL 工具函数
"""
import time
import logging
import threading
from datetime import datetime, date, timedelta
from pathlib import Path

from config import LOG_DIR


def setup_logger(name, log_file=None, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        path = Path(LOG_DIR) / log_file
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


class TokenBucket:
    """线程安全的令牌桶限流器（所有线程共享同一个实例）

    确保总 API 调用速率不超过 rate 次/秒，避免触达 Tushare 频率限制。
    三个线程(THS/DC/TDX)共用此桶，谁快谁用，总量可控。
    """
    def __init__(self, rate=8, burst=20):
        self.rate = rate          # 每秒补充 rate 个令牌
        self.burst = burst        # 最大令牌积攒上限
        self._tokens = burst      # 当前令牌数
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self):
        """获取一个令牌（阻塞直到有令牌可用）"""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            # 无令牌可用，短暂等待后重试
            time.sleep(0.01)

    def wait(self):
        """同 acquire()，与旧 RateLimiter 接口兼容"""
        self.acquire()


class RateLimiter(TokenBucket):
    """向后兼容别名 — 旧代码使用 RateLimiter"""
    pass


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def batch_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def trade_date_str():
    return date.today().strftime("%Y%m%d")
