"""
ETL: 筹码分布(stg_cyq_perf + stg_cyq_chips, 接口 cyq_perf / cyq_chips)

更新: 每天 18~19 点之间更新当日数据(19:10 跑增量)
⚠️ 探测回退: 当天数据未出(返回空) → 记告警并回退 T-1, 报告侧标注数据日期
限量: 单次 6000 条; cyq_perf 标称 ts_code 必选(待实测是否支持 trade_date 全市场)
      若全市场不支持: 增量退化为关注股循环(每只 1 次调用)

用法:
  python etl_cyq.py                       # 增量: 当天(探测) → 回退 T-1
  python etl_cyq.py --date 20260805       # 指定日期全市场 perf + 关注股 chips
  python etl_cyq.py --backfill 20260720 20260805 --stocks ...
                                          # 回填: 关注股近 N 日(perf+chips 合并)
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
logger = setup_logger("etl_cyq", "etl_cyq.log")

TABLE_PERF = "stg_cyq_perf"
TABLE_CHIPS = "stg_cyq_chips"
COL_PERF = ["ts_code", "trade_date", "his_low", "his_high", "cost_5pct",
            "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct",
            "weight_avg", "winner_rate"]
COL_CHIPS = ["ts_code", "trade_date", "price", "percent"]

FOCUS_STOCKS = ["002821.SZ", "688166.SH", "002419.SZ", "300750.SZ", "000001.SZ",
                "300436.SZ", "002594.SZ", "600985.SH", "688017.SH", "000636.SZ"]

# cyq_perf 全市场单次上限 6000; 全市场 5000+ 只 → 需分页 offset(若接口支持)
PERF_PAGE = 3000


def fetch_perf_trade_date(trade_date: str, stocks=None) -> int:
    """cyq_perf 单日拉取: 优先全市场分页, 失败(须带ts_code)则退化为关注股循环"""
    total = 0
    if stocks is None:
        # 尝试全市场(不带 ts_code, 若接口拒绝则异常由 safe_api_call 转 None)
        offset = 0
        while True:
            df = safe_api_call(PRO.cyq_perf, logger=logger,
                               trade_date=trade_date, offset=offset, limit=PERF_PAGE)
            if df is None or df.empty:
                if offset == 0:
                    # 全市场不支持 → 退化为关注股
                    logger.warning("  全市场拉取失败/空, 退化为关注股循环")
                    return fetch_perf_trade_date(trade_date, stocks=FOCUS_STOCKS)
                break
            rows = [(
                r["ts_code"], r["trade_date"], r.get("his_low"), r.get("his_high"),
                r.get("cost_5pct"), r.get("cost_15pct"), r.get("cost_50pct"),
                r.get("cost_85pct"), r.get("cost_95pct"), r.get("weight_avg"),
                r.get("winner_rate"),
            ) for _, r in df.iterrows()]
            total += db.insert_batch(TABLE_PERF, COL_PERF, rows, ignore=True)
            logger.info(f"  [{trade_date}/perf] 页{offset//PERF_PAGE}: {len(rows)} 行")
            if len(rows) < PERF_PAGE:
                break
            offset += PERF_PAGE
    else:
        for code in stocks:
            df = safe_api_call(PRO.cyq_perf, logger=logger,
                               ts_code=code, trade_date=trade_date)
            if df is None or df.empty:
                continue
            rows = [(
                r["ts_code"], r["trade_date"], r.get("his_low"), r.get("his_high"),
                r.get("cost_5pct"), r.get("cost_15pct"), r.get("cost_50pct"),
                r.get("cost_85pct"), r.get("cost_95pct"), r.get("weight_avg"),
                r.get("winner_rate"),
            ) for _, r in df.iterrows()]
            total += db.insert_batch(TABLE_PERF, COL_PERF, rows, ignore=True)
    logger.info(f"  [{trade_date}/perf] 共入库 {total} 行")
    return total


def fetch_chips_stocks(trade_date: str, stocks=None) -> int:
    """cyq_chips 单日: 仅关注股(接口 ts_code 必选, 逐股循环)"""
    stocks = stocks or FOCUS_STOCKS
    total = 0
    for code in stocks:
        df = safe_api_call(PRO.cyq_chips, logger=logger,
                           ts_code=code, trade_date=trade_date)
        if df is None or df.empty:
            logger.info(f"  {code} [{trade_date}/chips] 空")
            continue
        rows = [(r["ts_code"], r["trade_date"], r.get("price"), r.get("percent"))
                for _, r in df.iterrows()]
        total += db.insert_batch(TABLE_CHIPS, COL_CHIPS, rows, ignore=True)
    logger.info(f"  [{trade_date}/chips] {len(stocks)} 只, 共入库 {total} 行")
    return total


def etl_increment():
    """增量: 当天探测, 空则回退 T-1(告警; 报告侧靠数据日期标注兜底)"""
    today = datetime.now().strftime("%Y%m%d")
    s = datetime.now().isoformat()
    try:
        n = fetch_perf_trade_date(today) + fetch_chips_stocks(today)
        if n == 0:
            logger.warning(f"  ⚠️  [{today}] 当天筹码数据未出(18~19点更新), 回退 T-1")
            t1 = prev_trading_day(today)
            n = fetch_perf_trade_date(t1) + fetch_chips_stocks(t1)
            db.log_update(batch_id(), "cyq_perf/chips", TABLE_PERF, t1, s,
                          datetime.now().isoformat(), "PARTIAL", n, n,
                          "当天数据未出, 回退T-1")
            return n
        db.log_update(batch_id(), "cyq_perf/chips", TABLE_PERF, today, s,
                      datetime.now().isoformat(), "SUCCESS", n, n)
        return n
    except Exception as e:
        db.log_update(batch_id(), "cyq_perf/chips", TABLE_PERF, today, s,
                      datetime.now().isoformat(), "FAILED", 0, 0, str(e))
        logger.error(f"  增量失败: {e}")
        return 0


def etl_backfill(start: str, end: str, stocks=None):
    """回填: 关注股区间(perf+chips, 每只 1+1 次调用)"""
    stocks = stocks or FOCUS_STOCKS
    s = datetime.now().isoformat()
    total = 0
    for code in stocks:
        df = safe_api_call(PRO.cyq_perf, logger=logger,
                           ts_code=code, start_date=start, end_date=end)
        if df is not None and not df.empty:
            rows = [(
                r["ts_code"], r["trade_date"], r.get("his_low"), r.get("his_high"),
                r.get("cost_5pct"), r.get("cost_15pct"), r.get("cost_50pct"),
                r.get("cost_85pct"), r.get("cost_95pct"), r.get("weight_avg"),
                r.get("winner_rate"),
            ) for _, r in df.iterrows()]
            total += db.insert_batch(TABLE_PERF, COL_PERF, rows, ignore=True)
        df2 = safe_api_call(PRO.cyq_chips, logger=logger,
                            ts_code=code, start_date=start, end_date=end)
        if df2 is not None and not df2.empty:
            rows2 = [(r["ts_code"], r["trade_date"], r.get("price"), r.get("percent"))
                     for _, r in df2.iterrows()]
            total += db.insert_batch(TABLE_CHIPS, COL_CHIPS, rows2, ignore=True)
        logger.info(f"  {code}: perf+chips 共 {len(rows) if 'rows' in dir() else 0}+"
                    f"{len(rows2) if 'rows2' in dir() else 0} 行")
    db.log_update(batch_id(), "cyq_perf/chips", TABLE_PERF, end, s,
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
        fetch_perf_trade_date(_d)
        fetch_chips_stocks(_d)
    else:
        etl_increment()
