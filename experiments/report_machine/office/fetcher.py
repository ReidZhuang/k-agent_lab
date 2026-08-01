"""
Fetcher — 取数编排

协调调用数据脚本(fetch_all)和消息脚本(fetch_all)，
合并结果和警告，返回统一格式的数据给 writer。

报告类型可配置(report_type):
  - "noon":   data=fetch_midday_data_v2, message=fetch_message
  - "endday": data=fetch_endday_data,    message=fetch_message

设计决策（已确认）：
- 不作为独立 API，而是 writer 直接调用的函数
- 直接 import 调用，不通过 subprocess
- 数据/消息两路独立 try/except，互不影响
- 静态注册表（模块名写死），不做任意模块动态加载
"""
import os
import sys
import importlib
import traceback

# ── 确保能导入取数脚本（midday + endday） ──
_DATA_DIRS = [
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data_fetch", "midday")),
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data_fetch", "endday")),
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "snowball_token")),
]
for _p in _DATA_DIRS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database import log_office_error

# ── 报告类型注册表（静态，可审查） ──
_FETCH_REGISTRY = {
    "noon":   {"data": "fetch_midday_data_v2", "message": "fetch_message"},
    "endday": {"data": "fetch_endday_data",    "message": "fetch_message"},
}
_DEFAULT_TYPE = "noon"


def _load_module(module_name: str):
    """加载取数模块（sys.path 已注入）"""
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        log_office_error(
            module="office.fetcher",
            function="_load_module",
            level="ERROR",
            error_msg=f"取数模块 {module_name} 导入失败: {e}",
            error_code="FETCH_MODULE_IMPORT_FAILED",
        )
        raise


def fetch_all(stock_names: list[str], report_type: str = _DEFAULT_TYPE) -> tuple[dict, dict]:
    """统一取数入口

    按 report_type 从注册表选择数据/消息脚本，合并结果。

    Args:
        stock_names: 股票名称列表，如 ['宁德时代', '比亚迪']
        report_type: "noon" | "endday"（默认 "noon"，与旧行为一致）

    Returns:
        (data_by_stock, warnings_by_tscode)
        data_by_stock = {name: {"data": str, "message": str}}
        warnings_by_tscode = {ts_code: {"critical": [...], "non_critical": [...]}}
        两个 dict 均为空表示全部失败
    """
    registry = _FETCH_REGISTRY.get(report_type, _FETCH_REGISTRY[_DEFAULT_TYPE])

    data_by_stock = {}
    warnings_by_tscode = {}

    # ── 1. 数据取数（关键数据） ──
    try:
        data_mod = _load_module(registry["data"])
        data_result = data_mod.fetch_all(stock_names)
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
            error_msg=f"数据脚本({registry['data']})执行失败: {e}",
            error_code="FETCH_SCRIPT_FAILED",
        )

    # ── 2. 消息取数（非关键数据，午间/日终共用） ──
    if registry.get("message"):
        try:
            msg_mod = _load_module(registry["message"])
            msg_result = msg_mod.fetch_all(stock_names)
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
                error_msg=f"消息脚本({registry['message']})执行失败: {e}",
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
