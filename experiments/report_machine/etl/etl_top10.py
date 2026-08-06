"""
ETL: 十大流通股东(stg_top10_floatholder, 接口 top10_floatholders)

披露: 季度报告期(4/30、8/31、10/31 后全市场陆续披露)
限量: 未标明, 全市场单期数据量大(5000股×10) → offset 分页循环

用法:
  python etl_top10.py --periods 20260331 20251231 20250930
                       # 按报告期全市场分页拉取(每期多次调用)
  python etl_top10.py                          # 默认: 最近已披露 4 期
"""
import sys
from datetime import datetime
from pathlib import Path

import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager
from utils import setup_logger, batch_id, safe_api_call

PRO = ts.pro_api()
db = DatabaseManager()
logger = setup_logger("etl_top10", "etl_top10.log")

TABLE = "stg_top10_floatholder"
COLUMNS = ["ts_code", "ann_date", "end_date", "holder_name", "hold_amount",
           "hold_ratio", "hold_float_ratio", "hold_change", "holder_type"]

PAGE_SIZE = 1000  # 分页步长

# 近 4 期(按当前日期 2026-08 推算, 调用方可按需覆盖)
DEFAULT_PERIODS = ["20260331", "20251231", "20250930", "20250630"]


def fetch_period(period: str) -> int:
    """按报告期全市场分页拉取, 直到返回行数 < 页大小"""
    total = 0
    offset = 0
    while True:
        df = safe_api_call(PRO.top10_floatholders, logger=logger,
                           period=period, offset=offset, limit=PAGE_SIZE)
        if df is None or df.empty:
            break
        rows = [(
            r["ts_code"], r.get("ann_date", ""), r["end_date"],
            r["holder_name"], r.get("hold_amount"), r.get("hold_ratio"),
            r.get("hold_float_ratio"), r.get("hold_change"), r.get("holder_type", ""),
        ) for _, r in df.iterrows()]
        n = db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
        total += n
        logger.info(f"  [{period}] 页{offset//PAGE_SIZE}: 拉取 {len(rows)}, 入库 {n}")
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset > 100000:  # 兜底防死循环
            logger.error(f"  [{period}] offset 超过 100000, 强制停止")
            break
    logger.info(f"  [{period}] 完成, 共入库 {total} 行")
    return total


def latest_quarter_end() -> str:
    """最近一个已结束的季度末(如 2026-08-06 → 20260630; 2026-05-01 → 20260331)"""
    today = datetime.now()
    q = (today.month - 1) // 3  # 当前季度序号 0-3
    if q == 0:
        return f"{today.year - 1}1231"
    return f"{today.year}{q * 3:02d}31"


def etl_periods(periods=None):
    periods = periods or DEFAULT_PERIODS
    s = datetime.now().isoformat()
    total = 0
    for p in periods:
        try:
            total += fetch_period(p)
        except Exception as e:
            logger.error(f"  [{p}] 失败: {e}")
    db.log_update(batch_id(), "top10_floatholders", TABLE, periods[0], s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  完成: {periods}, 共 {total} 行")
    return total


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auto" in args:
        etl_periods([latest_quarter_end()])  # 季度 cron 用: 最新已结束报告期全市场
    elif "--periods" in args:
        _periods = args[args.index("--periods") + 1:]
        _periods = [p for p in _periods if p.isdigit() and len(p) == 8]
        etl_periods(_periods)
    else:
        etl_periods()
