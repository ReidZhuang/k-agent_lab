"""
交易日历工具 — 基于 Tushare trade_cal 接口

缓存策略:
  - 缓存覆盖年份范围: [当前年-1, 当前年]（Tushare 只提供已发生的年份）
  - 每次启动检查: 当前年 和 去年 是否在缓存覆盖范围内
  - 缺哪年补哪年（增量拉取，不重拉已有年份）
  - 2027-01-01 首次运行 → 检测到 2027 不在缓存 → 只拉 2027（去年 2026 已有）
  - 次年 API 还不存在时 → 只覆盖已有年份，不报错

使用 pretrade_date 字段精确获取上一个交易日（跳过周末和法定节假日）。

用法:
  from trade_calendar import TradeCalendar
  cal = TradeCalendar()
  cal.last_trading_day()              # → "20260717"
  cal.prev_trading_day("20260717")    # → "20260716"
"""

import os
import sys
import json
import datetime
import pandas as pd
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_FILE = CACHE_DIR / "trade_calendar.pkl"
META_FILE = CACHE_DIR / "trade_calendar_meta.json"

_log = lambda msg: print(f"[trade_calendar] {msg}", file=sys.stderr)


class TradeCalendar:
    """交易日历，基于 Tushare trade_cal + pretrade_date"""

    def __init__(self, refresh: bool = False):
        self._df = None
        self._years_cached = set()
        self._load(refresh=refresh)

    # ── 数据加载 ──────────────────────────────────────────

    def _load(self, refresh: bool = False):
        """加载交易日历：从缓存读，若覆盖不足则补拉"""
        if refresh:
            self._df = self._fetch_missing_years(set(), force_all=True)
            self._save_cache()
            return

        # 1) 尝试读缓存
        cached = self._load_cache()
        if cached is not None:
            self._df, self._years_cached = cached

        # 2) 判断需要补充哪些年份
        needed = self._required_years()
        missing = needed - self._years_cached

        if missing:
            _log(f"缓存缺少年份: {sorted(missing)}，正在补充...")
            new_df = self._fetch_missing_years(missing)
            if self._df is None:
                self._df = new_df
            elif new_df is not None:
                self._df = pd.concat(
                    [self._df, new_df], ignore_index=True
                ).drop_duplicates(subset=["cal_date"])
            self._years_cached |= missing
            self._save_cache()

        if self._df is None:
            # 兜底: 完全没有缓存，全量拉取
            self._df = self._fetch_missing_years(
                self._required_years(), force_all=True
            )
            self._years_cached = self._required_years()
            self._save_cache()

        # 确保索引
        if "cal_date" in self._df.columns:
            self._df = self._df.set_index("cal_date")

    @staticmethod
    def _required_years() -> set[int]:
        """当前需要的年份范围: [去年, 今年]（Tushare 不提供未来年份）"""
        y = datetime.date.today().year
        return {y - 1, y}

    def _load_cache(self):
        """尝试从本地缓存读取"""
        if not CACHE_FILE.exists() or not META_FILE.exists():
            return None
        try:
            with open(META_FILE, "r") as f:
                meta = json.load(f)
            years = set(meta.get("years", []))
            df = pd.read_pickle(CACHE_FILE)
            if "cal_date" in df.columns:
                df = df.set_index("cal_date")
            return df, years
        except Exception as e:
            _log(f"缓存读取失败 ({e})，将重新拉取")
            return None

    def _save_cache(self):
        """保存缓存到本地"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # 保存时把索引重置，避免跨版本兼容问题
        save_df = self._df.reset_index() if "cal_date" in self._df.index.names else self._df
        save_df.to_pickle(CACHE_FILE)
        with open(META_FILE, "w") as f:
            json.dump({"years": sorted(self._years_cached)}, f)
        _log(f"缓存已保存: {sorted(self._years_cached)}, {len(self._df)} 天")

    def _fetch_missing_years(self, years: set[int], force_all: bool = False) -> pd.DataFrame | None:
        """从 Tushare 拉取指定年份的交易日历"""
        import tushare as ts

        if not years and not force_all:
            return None

        pro = ts.pro_api()
        dfs = []
        fetch_years = years if not force_all else self._required_years()

        for y in sorted(fetch_years):
            start = f"{y}0101"
            end = f"{y}1231"
            _log(f"拉取 {y} 年交易日历...")
            df = pro.trade_cal(exchange="SSE", start_date=start, end_date=end)
            dfs.append(df)

        result = pd.concat(dfs, ignore_index=True)
        return result

    # ── 查询方法 ──────────────────────────────────────────

    def is_trading_day(self, date_str: str) -> bool:
        if date_str not in self._df.index:
            return False
        val = self._df.loc[date_str, "is_open"]
        return str(val) == "1"

    def pretrade_date(self, date_str: str) -> str | None:
        """获取指定日期的上一个交易日（使用 API 的 pretrade_date 字段）"""
        if date_str in self._df.index:
            val = self._df.loc[date_str, "pretrade_date"]
            if val and not (isinstance(val, float) and pd.isna(val)):
                return str(val)
        # fallback: 往前遍历最多 15 天
        dt = datetime.datetime.strptime(date_str, "%Y%m%d")
        for i in range(1, 15):
            d = dt - datetime.timedelta(days=i)
            ds = d.strftime("%Y%m%d")
            if ds in self._df.index and str(self._df.loc[ds, "is_open"]) == "1":
                return ds
        return None

    def prev_trading_day(self, date_str: str, n: int = 1) -> str | None:
        """从 date_str 往前推 n 个交易日"""
        current = date_str
        for _ in range(n):
            next_date = self.pretrade_date(current)
            if next_date is None:
                return None
            current = next_date
        return current

    def last_trading_day(self) -> str:
        """最近一个已收盘、可获取盘后数据的交易日

        规则:
          - 如果是交易日且当前时间 >= 15:00，返回今天（盘后数据已出）
          - 否则返回 pretrade_date(今天)
        """
        today = datetime.date.today().strftime("%Y%m%d")
        now = datetime.datetime.now()

        if self.is_trading_day(today) and now.hour >= 15:
            return today

        return self.pretrade_date(today)

    def last_two_trading_days(self) -> tuple[str, str]:
        t1 = self.last_trading_day()
        t2 = self.prev_trading_day(t1, n=1)
        return t1, t2


# ===== 全局单例 =====
_DEFAULT_CALENDAR: TradeCalendar | None = None


def get_calendar(refresh: bool = False) -> TradeCalendar:
    global _DEFAULT_CALENDAR
    if _DEFAULT_CALENDAR is None or refresh:
        _DEFAULT_CALENDAR = TradeCalendar(refresh=refresh)
    return _DEFAULT_CALENDAR


def last_trading_day(refresh: bool = False) -> str:
    return get_calendar(refresh=refresh).last_trading_day()


def prev_trading_day(date_str: str, n: int = 1) -> str | None:
    return get_calendar().prev_trading_day(date_str, n=n)


def is_trading_day(date_str: str) -> bool:
    return get_calendar().is_trading_day(date_str)


# ===== CLI =====
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "last"
    cal = get_calendar(refresh="--refresh" in sys.argv)

    if action == "last":
        t1, t2 = cal.last_two_trading_days()
        today = datetime.date.today().strftime("%Y%m%d")
        print(f"今天:        {today}  {'交易日' if cal.is_trading_day(today) else '非交易日'}")
        print(f"T-1 (昨日): {t1}")
        print(f"T-2 (前日): {t2}")
    elif action == "check":
        date = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().strftime("%Y%m%d")
        print(f"{date}: {'交易日' if cal.is_trading_day(date) else '非交易日'} | pretrade={cal.pretrade_date(date)}")
    elif action == "prev":
        date = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().strftime("%Y%m%d")
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        print(f"{date} 往前 {n} 个交易日: {cal.prev_trading_day(date, n=n)}")
    else:
        print("用法: python trade_calendar.py [last|check <date>|prev <date> <n>]")
