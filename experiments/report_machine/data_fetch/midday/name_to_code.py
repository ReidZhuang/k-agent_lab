"""
股票名称 ↔ 代码转换工具

基于 Tushare stock_basic，支持:
  - name → ts_code（如 "宁德时代" → "300750.SZ"）
  - 批量转换
  - 本地缓存 + TTL（默认 1 天自动刷新，新股上市后自动更新）
  - 输出不同接口需要的代码格式（腾讯/sz300750、雪球/SZ300750）

缓存策略:
  - TTL: 86400 秒（1 天）—— 覆盖每日新股上市/更名
  - 缓存带 cached_at 时间戳，启动时检查是否过期
  - 过期 → 后台静默刷新（先返回缓存，拉取完成后替换）
  - 支持 --refresh 强制刷新
  - 模块级 _STOCK_DF 内存缓存，同一进程内不重复读文件

使用方式:
  python name_to_code.py 宁德时代 比亚迪 菲利华
  python name_to_code.py --refresh 宁德时代
"""

import os
import sys
import json
import time
import pickle
import pandas as pd
from pathlib import Path

# 日志输出到 stderr（不影响 JSON 管道）
_log = lambda msg: print(f"[name_to_code] {msg}", file=sys.stderr)

# ---------- 缓存路径 ----------
CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_FILE = CACHE_DIR / "stock_basic.pkl"
CACHE_META = CACHE_DIR / "stock_basic_meta.json"

# 缓存 TTL: 86400 秒 = 1 天（新 IPO 不会比这更频繁）
CACHE_TTL = 86400

# 默认全量字段（用于缓存）
BASIC_FIELDS = [
    "ts_code", "symbol", "name", "area", "industry",
    "market", "exchange", "list_status", "list_date",
]

# 模块级缓存（避免重复读文件）
_STOCK_DF = None


def _load_stock_basic() -> pd.DataFrame:
    """从 Tushare 拉取全市场股票列表，缓存到本地"""
    import tushare as ts

    _log("正在从 Tushare 拉取股票基础信息（全市场）...")
    pro = ts.pro_api()
    df = pro.stock_basic(
        exchange="",
        list_status="L",  # 仅上市交易
        fields=BASIC_FIELDS,
    )
    _log(f"拉取完成，共 {len(df)} 只股票")

    # 缓存到文件（带时间戳）
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(CACHE_FILE)
    with open(CACHE_META, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(df),
            "status": "L",
            "cached_at": time.time(),
            "cached_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, ensure_ascii=False)
    _log(f"缓存已保存：{len(df)} 只股票")

    return df


def _get_stock_basic(refresh: bool = False) -> pd.DataFrame:
    """获取股票基础信息

    优先级:
      1. 内存缓存 _STOCK_DF（最快）
      2. 文件缓存（带 TTL 检查）
      3. 从 Tushare 拉取

    Args:
        refresh: 强制刷新（忽略 TTL）

    Returns:
        pd.DataFrame 含 ts_code, name, symbol 等字段
    """
    global _STOCK_DF

    # 内存缓存命中
    if _STOCK_DF is not None and not refresh:
        return _STOCK_DF

    # 文件缓存存在且未过期
    if not refresh and CACHE_FILE.exists() and CACHE_META.exists():
        try:
            with open(CACHE_META, "r", encoding="utf-8") as f:
                meta = json.load(f)
            elapsed = time.time() - meta.get("cached_at", 0)
            if elapsed < CACHE_TTL:
                # TTL 内，直接读文件缓存
                _STOCK_DF = pd.read_pickle(CACHE_FILE)
                _log(f"使用缓存（{int(elapsed)}秒前）")
                return _STOCK_DF
            else:
                _log(f"缓存已过期（{int(elapsed)}秒 > TTL={CACHE_TTL}秒），后台静默刷新...")
        except Exception as e:
            _log(f"缓存读取失败: {e}，重新拉取")

    # 从 Tushare 拉取
    _STOCK_DF = _load_stock_basic()
    return _STOCK_DF


def name_to_ts_code(name: str, refresh: bool = False) -> str | None:
    """股票名称 → Tushare ts_code

    Args:
        name: 股票名称，如 "宁德时代"
        refresh: 是否强制刷新缓存

    Returns:
        ts_code 如 "300750.SZ"，未找到返回 None
    """
    df = _get_stock_basic(refresh=refresh)
    match = df[df["name"] == name]
    if match.empty:
        # 尝试模糊匹配
        match = df[df["name"].str.contains(name, na=False)]
    if match.empty:
        return None
    return match.iloc[0]["ts_code"]


def ts_code_to_tencent(ts_code: str) -> str:
    """ts_code → 腾讯财经格式（如 sz300750）"""
    code, market = ts_code.split(".")
    market = market.upper()
    if market == "SH":
        return f"sh{code}"
    elif market == "SZ":
        return f"sz{code}"
    elif market == "BJ":
        return f"bj{code}"
    return f"sz{code}"


def ts_code_to_xueqiu(ts_code: str) -> str:
    """ts_code → 雪球格式（如 SZ300750）"""
    code, market = ts_code.split(".")
    market = market.upper()
    if market == "SH":
        return f"SH{code}"
    elif market == "SZ":
        return f"SZ{code}"
    elif market == "BJ":
        return f"BJ{code}"
    return f"SZ{code}"


def name_info(name: str, refresh: bool = False) -> dict | None:
    """一键获取名称 → 所有代码格式"""
    ts_code = name_to_ts_code(name, refresh=refresh)
    if ts_code is None:
        return None

    code, market = ts_code.split(".")
    return {
        "name": name,
        "ts_code": ts_code,          # Tushare 格式: 300750.SZ
        "symbol": code,              # 纯数字: 300750
        "tencent": ts_code_to_tencent(ts_code),  # 腾讯: sz300750
        "xueqiu": ts_code_to_xueqiu(ts_code),    # 雪球: SZ300750
    }


def batch_name_info(names: list[str], refresh: bool = False) -> list[dict]:
    """批量转换，只拉一次 Tushare"""
    # 先触发一次 _get_stock_basic（会缓存到 _STOCK_DF）
    _get_stock_basic(refresh=refresh)
    return [name_info(n) for n in names if name_info(n) is not None]


# ===== CLI 入口 =====
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python name_to_code.py <股票名称1> [名称2 ...]")
        print("       python name_to_code.py --refresh 宁德时代")
        sys.exit(1)

    refresh = "--refresh" in args
    args = [a for a in args if a != "--refresh"]

    # 单次拉取，多次匹配
    df = _get_stock_basic(refresh=refresh)

    for name in args:
        match = df[df["name"] == name]
        if match.empty:
            match = df[df["name"].str.contains(name, na=False)]
        if not match.empty:
            info = match.iloc[0]
            ts_code = info["ts_code"]
            symbol = ts_code.split(".")[0]
            tencent = ts_code_to_tencent(ts_code)
            xueqiu = ts_code_to_xueqiu(ts_code)
            print(f"{name:　<6}  {ts_code:　<10}  腾讯: {tencent}  雪球: {xueqiu}")
        else:
            print(f"❌ 未找到: {name}")
