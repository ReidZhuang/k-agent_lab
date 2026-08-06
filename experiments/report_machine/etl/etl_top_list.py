"""
ETL: 龙虎榜(stg_top_list, 接口 top_list)

更新: 当日 17:30 后数据已出(19:10 跑增量)
限量: 单次 10000 条(全市场单日仅 200-400 行, 一次覆盖)

用法:
  python etl_top_list.py                     # 增量: 当天全市场
  python etl_top_list.py --date 20260805     # 指定日期全市场
  python etl_top_list.py --backfill 20260701 20260730
                                             # 回填: 按日循环(每天1次调用)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager
from utils import setup_logger, batch_id, safe_api_call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_fetch" / "midday"))
from trade_calendar import prev_trading_day  # noqa: E402

PRO = ts.pro_api()
db = DatabaseManager()
logger = setup_logger("etl_top_list", "etl_top_list.log")

TABLE = "stg_top_list"
COLUMNS = ["trade_date", "ts_code", "name", "close", "pct_change", "turnover_rate",
           "amount", "l_sell", "l_buy", "l_amount", "net_amount", "net_rate",
           "amount_rate", "float_values", "reason"]


def fetch_trade_date(trade_date: str) -> int:
    """全市场单日拉取(单股同日可多行=不同上榜理由, 唯一键含 reason)"""
    df = safe_api_call(PRO.top_list, logger=logger, trade_date=trade_date)
    if df is None or df.empty:
        logger.info(f"  [{trade_date}] 返回空")
        return 0
    rows = [(
        r["trade_date"], r["ts_code"], r.get("name", ""), r.get("close"),
        r.get("pct_change"), r.get("turnover_rate"), r.get("amount"),
        r.get("l_sell"), r.get("l_buy"), r.get("l_amount"), r.get("net_amount"),
        r.get("net_rate"), r.get("amount_rate"), r.get("float_values"),
        r.get("reason", ""),
    ) for _, r in df.iterrows()]
    n = db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
    logger.info(f"  [{trade_date}] 拉取 {len(rows)} 行, 入库 {n}")
    return n


def etl_increment():
    """增量: 当天(若今天非交易日则跳过)"""
    today = datetime.now().strftime("%Y%m%d")
    # 直接拉今天: 非交易日返回空, 无副作用
    s = datetime.now().isoformat()
    try:
        n = fetch_trade_date(today)
        db.log_update(batch_id(), "top_list", TABLE, today, s,
                      datetime.now().isoformat(), "SUCCESS", n, n)
        return n
    except Exception as e:
        db.log_update(batch_id(), "top_list", TABLE, today, s,
                      datetime.now().isoformat(), "FAILED", 0, 0, str(e))
        logger.error(f"  增量失败: {e}")
        return 0


def etl_backfill(start: str, end: str):
    """回填: 按交易日循环(近30日 ≈ 22个交易日调用)"""
    s = datetime.now().isoformat()
    total = 0
    d = datetime.strptime(start, "%Y%m%d")
    d_end = datetime.strptime(end, "%Y%m%d")
    while d <= d_end:
        total += fetch_trade_date(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    db.log_update(batch_id(), "top_list", TABLE, end, s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  回填完成: {start}~{end}, 共 {total} 行")
    return total


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--backfill" in args:
        i = args.index("--backfill")
        _start = args[i + 1]
        _end = args[i + 2] if len(args) > i + 2 else datetime.now().strftime("%Y%m%d")
        etl_backfill(_start, _end)
    elif "--date" in args:
        fetch_trade_date(args[args.index("--date") + 1])
    else:
        etl_increment()
