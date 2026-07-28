"""
Fetcher — 取数编排

协调调用 fetch_midday_data.fetch_all 和 fetch_midday_message.fetch_all，
合并结果和警告，返回统一格式的数据给 writer。

设计决策（已确认）：
- 不作为独立 API，而是 writer 直接调用的函数
- 直接 import 调用，不通过 subprocess
- 两个脚本独立 try/except，互不影响
"""
import os
import sys
import traceback

# ── 确保能导入取数脚本 ──
_MIDDAY_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data_fetch", "midday")
)
_SNOWBALL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "snowball_token")
)
for _p in [_MIDDAY_DIR, _SNOWBALL_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fetch_midday_data import fetch_all as _fetch_data
from fetch_midday_message import fetch_all as _fetch_message

from database import log_office_error


def fetch_all(stock_names: list[str]) -> tuple[dict, dict]:
    """统一取数入口

    调用两个 fetch 脚本，合并结果。

    Args:
        stock_names: 股票名称列表，如 ['宁德时代', '比亚迪']

    Returns:
        (data_by_stock, warnings_by_tscode)
        data_by_stock = {name: {"data": str, "message": str}}
        warnings_by_tscode = {ts_code: {"critical": [...], "non_critical": [...]}}
        两个 dict 均为空表示全部失败
    """
    data_by_stock = {}
    warnings_by_tscode = {}

    # ── 1. 数据取数（关键数据） ──
    try:
        data_result = _fetch_data(stock_names)
        # 提取 warning
        data_warnings = data_result.pop("warning", {})
        # 剩余 key 为股票名称 → 文本
        for name in stock_names:
            text = data_result.get(name, "")
            if text:
                data_by_stock.setdefault(name, {})["data"] = text
        # 合并 data warning
        for ts_code, warn in data_warnings.items():
            warnings_by_tscode.setdefault(ts_code, {"critical": [], "non_critical": []})
            if isinstance(warn, dict):
                for k in ("critical", "non_critical"):
                    if k in warn:
                        warnings_by_tscode[ts_code][k].extend(warn[k])
    except Exception as e:
        log_office_error(
            module="office.fetcher",
            function="fetch_all.fetch_data",
            level="ERROR",
            error_msg=f"fetch_midday_data 执行失败: {e}",
            error_code="FETCH_SCRIPT_FAILED",
        )

    # ── 2. 消息取数（非关键数据） ──
    try:
        msg_result = _fetch_message(stock_names)
        msg_warnings = msg_result.pop("warning", {})
        for name in stock_names:
            text = msg_result.get(name, "")
            if text:
                data_by_stock.setdefault(name, {})["message"] = text
        # 合并 msg warning
        for ts_code, warn in msg_warnings.items():
            warnings_by_tscode.setdefault(ts_code, {"critical": [], "non_critical": []})
            if warn == "no data":
                warnings_by_tscode[ts_code]["non_critical"].append("message_all_empty")
            elif isinstance(warn, dict):
                for k in ("critical", "non_critical"):
                    if k in warn:
                        warnings_by_tscode[ts_code][k].extend(warn[k])
    except Exception as e:
        log_office_error(
            module="office.fetcher",
            function="fetch_all.fetch_message",
            level="WARNING",
            error_msg=f"fetch_midday_message 执行失败: {e}",
            error_code="FETCH_SCRIPT_FAILED",
        )

    # ── 3. 完整性检查 ──
    missing = []
    for name in stock_names:
        if name not in data_by_stock:
            missing.append(name)

    if missing and not data_by_stock:
        log_office_error(
            module="office.fetcher",
            function="fetch_all",
            level="ERROR",
            error_msg=f"所有股票取数失败: {missing}",
            error_code="FETCH_ALL_FAILED",
        )
    elif missing:
        for name in missing:
            log_office_error(
                module="office.fetcher",
                function="fetch_all",
                level="WARNING",
                stock_name=name,
                error_msg=f"股票取数部分失败",
                error_code="FETCH_PARTIAL_DATA",
            )

    return data_by_stock, warnings_by_tscode
