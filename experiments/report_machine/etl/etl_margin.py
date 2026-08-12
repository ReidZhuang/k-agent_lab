"""
ETL: 融资融券明细(stg_margin, 接口 margin_detail)

更新: 交易所每天 8:30 左右更新上一交易日数据
频控: 2000积分接口, 每分钟限次(普通频控), 无每天总量限制

用法:
  python etl_margin.py                    # 增量: T-1 全市场(1次调用)
  python etl_margin.py --date 20260805    # 指定日期全市场
  python etl_margin.py --backfill 20250701 20260805 --stocks 002821.SZ 688166.SH ...
                                          # 回填: 按股票循环(每只1次调用, 限频注意)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager
from utils import setup_logger, batch_id, safe_api_call

# 交易日历
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_fetch" / "midday"))
from trade_calendar import prev_trading_day  # noqa: E402

PRO = ts.pro_api()
db = DatabaseManager()
logger = setup_logger("etl_margin", "etl_margin.log")

TABLE = "stg_margin"
COLUMNS = ["trade_date", "ts_code", "name", "rzye", "rqye", "rzmre",
           "rqyl", "rzche", "rqchl", "rqmcl", "rzrqye"]

# 关注股(回填/核对用)
FOCUS_STOCKS = ["002821.SZ", "688166.SH", "002419.SZ", "300750.SZ", "000001.SZ",
                "300436.SZ", "002594.SZ", "600985.SH", "688017.SH", "000636.SZ"]


def fetch_trade_date(trade_date: str) -> int:
    """全市场单日拉取(6000条上限, 全市场融资标的约3000只, 一次可覆盖)"""
    df = safe_api_call(PRO.margin_detail, logger=logger, trade_date=trade_date)
    if df is None or df.empty:
        logger.info(f"  [{trade_date}] 返回空")
        return 0
    rows = [(
        r["trade_date"], r["ts_code"], r.get("name", ""),
        r.get("rzye"), r.get("rqye"), r.get("rzmre"), r.get("rqyl"),
        r.get("rzche"), r.get("rqchl"), r.get("rqmcl"), r.get("rzrqye"),
    ) for _, r in df.iterrows()]
    n = db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
    logger.info(f"  [{trade_date}] 拉取 {len(rows)} 行, 入库 {n}")
    if len(rows) >= 6000:
        logger.warning(f"  ⚠️  [{trade_date}] 达到6000上限疑似截断")
    return n


def etl_increment():
    """增量: T-1 全市场"""
    td = prev_trading_day(datetime.now().strftime("%Y%m%d"))
    s = datetime.now().isoformat()
    try:
        n = fetch_trade_date(td)
        db.log_update(batch_id(), "margin_detail", TABLE, td, s,
                      datetime.now().isoformat(), "SUCCESS", n, n)
        return n
    except Exception as e:
        db.log_update(batch_id(), "margin_detail", TABLE, td, s,
                      datetime.now().isoformat(), "FAILED", 0, 0, str(e))
        logger.error(f"  增量失败: {e}")
        return 0


def etl_backfill(start: str, end: str, stocks=None):
    """回填: 按股票循环, 每只一次调用拉 [start, end]"""
    stocks = stocks or FOCUS_STOCKS
    s = datetime.now().isoformat()
    total = 0
    for code in stocks:
        df = safe_api_call(PRO.margin_detail, logger=logger,
                           ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            continue
        rows = [(
            r["trade_date"], r["ts_code"], r.get("name", ""),
            r.get("rzye"), r.get("rqye"), r.get("rzmre"), r.get("rqyl"),
            r.get("rzche"), r.get("rqchl"), r.get("rqmcl"), r.get("rzrqye"),
        ) for _, r in df.iterrows()]
        total += db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
        logger.info(f"  {code}: {len(rows)} 行")
    db.log_update(batch_id(), "margin_detail", TABLE, end, s,
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
        _d = args[args.index("--date") + 1]
        etl_increment() if _d == "auto" else fetch_trade_date(_d)
    else:
        etl_increment()
