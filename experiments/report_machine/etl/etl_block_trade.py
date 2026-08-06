"""
ETL: 大宗交易(stg_block_trade, 接口 block_trade)

⚠️ 单次上限 1000 条(实测 90 天全市场正好 1000 截断) → 增量按日全市场(单日几十条), 回填按股

用法:
  python etl_block_trade.py                    # 增量: 当天全市场(1次调用)
  python etl_block_trade.py --date 20260805    # 指定日期全市场
  python etl_block_trade.py --backfill 20260501 20260805 --stocks 002821.SZ ...
                                               # 回填: 按股票循环(每只1次调用)
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
logger = setup_logger("etl_block_trade", "etl_block_trade.log")

TABLE = "stg_block_trade"
COLUMNS = ["ts_code", "trade_date", "price", "vol", "amount", "buyer", "seller"]

FOCUS_STOCKS = ["002821.SZ", "688166.SH", "002419.SZ", "300750.SZ", "000001.SZ",
                "300436.SZ", "002594.SZ", "600985.SH", "688017.SH", "000636.SZ"]


def fetch_trade_date(trade_date: str) -> int:
    """全市场单日拉取(单日几十条 << 1000)"""
    df = safe_api_call(PRO.block_trade, logger=logger, trade_date=trade_date)
    if df is None or df.empty:
        logger.info(f"  [{trade_date}] 返回空")
        return 0
    rows = [(
        r["ts_code"], r["trade_date"], r.get("price"), r.get("vol"),
        r.get("amount"), r.get("buyer", ""), r.get("seller", ""),
    ) for _, r in df.iterrows()]
    n = db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
    logger.info(f"  [{trade_date}] 拉取 {len(rows)} 行, 入库 {n}")
    if len(rows) >= 1000:
        logger.warning(f"  ⚠️  [{trade_date}] 达到1000上限疑似截断")
    return n


def etl_increment():
    """增量: 当天全市场"""
    today = datetime.now().strftime("%Y%m%d")
    s = datetime.now().isoformat()
    try:
        n = fetch_trade_date(today)
        db.log_update(batch_id(), "block_trade", TABLE, today, s,
                      datetime.now().isoformat(), "SUCCESS", n, n)
        return n
    except Exception as e:
        db.log_update(batch_id(), "block_trade", TABLE, today, s,
                      datetime.now().isoformat(), "FAILED", 0, 0, str(e))
        logger.error(f"  增量失败: {e}")
        return 0


def etl_backfill(start: str, end: str, stocks=None):
    """回填: 按股票循环(每只1次调用, 90天区间内行数远小于1000)"""
    stocks = stocks or FOCUS_STOCKS
    s = datetime.now().isoformat()
    total = 0
    for code in stocks:
        df = safe_api_call(PRO.block_trade, logger=logger,
                           ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            continue
        rows = [(
            r["ts_code"], r["trade_date"], r.get("price"), r.get("vol"),
            r.get("amount"), r.get("buyer", ""), r.get("seller", ""),
        ) for _, r in df.iterrows()]
        total += db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
        logger.info(f"  {code}: {len(rows)} 行")
        if len(rows) >= 1000:
            logger.warning(f"  ⚠️  {code} 区间内达到1000上限疑似截断, 需缩小区间")
    db.log_update(batch_id(), "block_trade", TABLE, end, s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  回填完成: {len(stocks)} 只, {start}~{end}, 共 {total} 行")
    return total


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--backfill" in args:
        i = args.index("--backfill")
        _start = args[i + 1]
        _end = args[i + 2]
        _stocks = args[args.index("--stocks") + 1:] if "--stocks" in args else FOCUS_STOCKS
        etl_backfill(_start, _end, _stocks)
    elif "--date" in args:
        fetch_trade_date(args[args.index("--date") + 1])
    else:
        etl_increment()
