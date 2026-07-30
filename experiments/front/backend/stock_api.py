"""
Tushare 股票数据接口
"""
import sys
from datetime import datetime
from pathlib import Path

import tushare as ts
import pandas as pd

from database import db
from config import OFFICE_DIR
from models import DailyDataItem

# 延迟初始化 Tushare（避免模块导入时阻塞）
_PRO = None
def _get_pro():
    global _PRO
    if _PRO is None:
        _PRO = ts.pro_api()
    return _PRO

# 交易日历
_MIDDAY_DIR = OFFICE_DIR.parent / "data_fetch" / "midday"
if str(_MIDDAY_DIR) not in sys.path:
    sys.path.insert(0, str(_MIDDAY_DIR))
from trade_calendar import prev_trading_day


def ensure_stock_basic_refreshed():
    """确保 stg_stock_basic 表今天已更新"""
    today = datetime.now().strftime("%Y%m%d")
    r = db.execute_one(
        "SELECT update_date FROM stg_stock_basic LIMIT 1"
    )
    if r and r.get("update_date") == today:
        return  # 今天已更新

    print("  📡 从 Tushare 拉取股票基础信息...")
    df = _get_pro().stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    if df is None or df.empty:
        print("  ⚠️  Tushare stock_basic 返回空")
        return

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r.get("ts_code", ""),
            r.get("symbol", ""),
            r.get("name", ""),
            r.get("area", ""),
            r.get("industry", ""),
            r.get("market", ""),
            r.get("list_date", ""),
            today,
        ))
    db.refresh_stock_basic(rows)
    print(f"  ✅ 股票基础信息已更新: {len(rows)} 只")


def search_stock(keyword: str) -> list[dict]:
    """搜索股票"""
    ensure_stock_basic_refreshed()
    return db.search_stock(keyword)


def get_stocks_by_names(names: list[str]) -> list[dict]:
    """按名称批量查询"""
    ensure_stock_basic_refreshed()
    return db.get_stock_by_names(names)


def fetch_yesterday_daily(ts_codes: list[str]) -> dict[str, DailyDataItem]:
    """从 Tushare 获取昨日日线行情 + 每日指标

    Returns:
        {ts_code: DailyDataItem}
    """
    td = prev_trading_day(datetime.now().strftime("%Y%m%d"))
    result: dict[str, DailyDataItem] = {}

    # 将 ts_codes 分批（Tushare 支持逗号分隔）
    for i in range(0, len(ts_codes), 200):
        batch = ts_codes[i:i + 200]
        codes_str = ",".join(batch)
        try:
            df = _get_pro().daily(ts_code=codes_str, trade_date=td)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    code = r["ts_code"]
                    result[code] = DailyDataItem(
                        ts_code=code,
                        trade_date=str(r.get("trade_date", td)),
                        open=float(r["open"]) if r.get("open") is not None else None,
                        high=float(r["high"]) if r.get("high") is not None else None,
                        low=float(r["low"]) if r.get("low") is not None else None,
                        close=float(r["close"]) if r.get("close") is not None else None,
                        pre_close=float(r["pre_close"]) if r.get("pre_close") is not None else None,
                        change=float(r["change"]) if r.get("change") is not None else None,
                        pct_chg=float(r["pct_chg"]) if r.get("pct_chg") is not None else None,
                        vol=float(r["vol"]) if r.get("vol") is not None else None,
                        amount=float(r["amount"]) if r.get("amount") is not None else None,
                    )

            # 补充换手率（从 daily_basic，1 次全量拉取）
            if i == 0:  # 只在第一批查询时拉一次全量
                try:
                    df2 = _get_pro().daily_basic(trade_date=td)
                    if df2 is not None and not df2.empty:
                        for _, r in df2.iterrows():
                            code = r["ts_code"]
                            if code in result:
                                result[code].turnover_rate = (
                                    float(r["turnover_rate"]) if r.get("turnover_rate") is not None else None
                                )
                except Exception as e:
                    print(f"  ⚠️  daily_basic 拉取失败: {e}")
            # 补充个股名称
            for item in result.values():
                name_r = db.execute_one(
                    "SELECT name FROM stg_stock_basic WHERE ts_code=?", (item.ts_code,)
                )
                if name_r:
                    item.name = name_r["name"]

        except Exception as e:
            print(f"  ⚠️  Tushare daily 拉取失败: {e}")

    return result
