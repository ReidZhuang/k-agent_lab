"""
ETL: 北向持股(stg_hk_hold, 接口 hk_hold)

⚠️ 港交所 2024-08-20 起停止日度披露, 改为季度 — 增量按季度最后交易日拉全市场
限量: 单次 3800 条(北向全市场约 2000 只, 一次覆盖)

用法:
  python etl_hk_hold.py --date 20260630       # 按交易日全市场(季度最后交易日)
  python etl_hk_hold.py --backfill 20240901 20260805 --stocks 002821.SZ ...
                                               # 回填: 按股票循环(每只1次调用, 取区间内全部季度节点)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager
from utils import setup_logger, batch_id, safe_api_call

PRO = ts.pro_api()
db = DatabaseManager()
logger = setup_logger("etl_hk_hold", "etl_hk_hold.log")

TABLE = "stg_hk_hold"
COLUMNS = ["code", "trade_date", "ts_code", "name", "vol", "ratio", "exchange"]

FOCUS_STOCKS = ["002821.SZ", "688166.SH", "002419.SZ", "300750.SZ", "000001.SZ",
                "300436.SZ", "002594.SZ", "600985.SH", "688017.SH", "000636.SZ"]


def fetch_trade_date(trade_date: str) -> int:
    """全市场单日拉取(单次 3800 上限, 北向约 2000 只; 需 SH/SZ 两交易所)"""
    total = 0
    for exch in ["SH", "SZ"]:
        df = safe_api_call(PRO.hk_hold, logger=logger,
                           trade_date=trade_date, exchange=exch)
        if df is None or df.empty:
            logger.info(f"  [{trade_date}/{exch}] 返回空")
            continue
        rows = [(
            r.get("code", ""), r["trade_date"], r["ts_code"], r.get("name", ""),
            r.get("vol"), r.get("ratio"), r.get("exchange", exch),
        ) for _, r in df.iterrows()]
        total += db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
        logger.info(f"  [{trade_date}/{exch}] 拉取 {len(rows)}, 入库 {len(rows)}")
        if len(rows) >= 3800:
            logger.warning(f"  ⚠️  [{trade_date}/{exch}] 达到3800上限疑似截断")
    return total


def etl_backfill(start: str, end: str, stocks=None):
    """回填: 按股票循环, 每只 1 次调用取区间内全部季度披露日"""
    stocks = stocks or FOCUS_STOCKS
    s = datetime.now().isoformat()
    total = 0
    for code in stocks:
        df = safe_api_call(PRO.hk_hold, logger=logger,
                           ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            continue
        rows = [(
            r.get("code", ""), r["trade_date"], r["ts_code"], r.get("name", ""),
            r.get("vol"), r.get("ratio"), r.get("exchange", ""),
        ) for _, r in df.iterrows()]
        total += db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
        logger.info(f"  {code}: {len(rows)} 行(区间内披露节点)")
    db.log_update(batch_id(), "hk_hold", TABLE, end, s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  回填完成: {len(stocks)} 只, {start}~{end}, 共 {total} 行")
    return total


def auto_latest_trade_date() -> str:
    """最近已结束季度的最后交易日(季度 cron 用)"""
    from trade_calendar import get_calendar
    today = datetime.now()
    q = (today.month - 1) // 3
    qe = f"{today.year - 1}1231" if q == 0 else f"{today.year}{q * 3:02d}31"
    cal = get_calendar()
    d = datetime.strptime(qe, "%Y%m%d")
    for _ in range(10):  # 最多回退 10 天(长假后)
        s = d.strftime("%Y%m%d")
        if cal.is_trading_day(s):
            return s
        d -= timedelta(days=1)
    return qe  # 兜底


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auto" in args:
        fetch_trade_date(auto_latest_trade_date())  # 季度 cron 用
    elif "--backfill" in args:
        i = args.index("--backfill")
        _start = args[i + 1]
        _end = args[i + 2]
        _stocks = args[args.index("--stocks") + 1:] if "--stocks" in args else FOCUS_STOCKS
        etl_backfill(_start, _end, _stocks)
    elif "--date" in args:
        fetch_trade_date(args[args.index("--date") + 1])
    else:
        print("用法: --auto | --date YYYYMMDD | --backfill START END [--stocks ...]")
