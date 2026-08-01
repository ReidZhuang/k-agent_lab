"""
数据库工具 — 复用 fetch_midday_data 的 log_error

所有 office 组件的异常统一通过此函数写入 error_log 表。
使用延迟加载（fork-safe），避免 spawn 子进程中的 import 路径问题。
"""
import os
import sys
import traceback

_LOG_ERROR_CACHE = None


def _get_log_error():
    """延迟加载 log_error（带缓存，fork-safe）"""
    global _LOG_ERROR_CACHE
    if _LOG_ERROR_CACHE is not None:
        return _LOG_ERROR_CACHE
    _MIDDAY_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data_fetch", "midday")
    )
    if _MIDDAY_DIR not in sys.path:
        sys.path.insert(0, _MIDDAY_DIR)
    from fetch_midday_data import log_error
    _LOG_ERROR_CACHE = log_error
    return _LOG_ERROR_CACHE


def log_office_error(
    module: str = "office",
    function: str = "",
    level: str = "ERROR",
    stock_name: str = "",
    ts_code: str = "",
    error_msg: str = "",
    detail: str = "",
    error_code: str = "",
    data_snapshot: str = "",
    engine_name: str = "",
):
    """Office 系统专用错误记录包装

    自动填充 service_name="office"。
    所有 office 组件（fetcher/writer/middleman/reporter）统一调用此函数。
    """
    _log_error = _get_log_error()
    _log_error(
        module=module,
        function=function,
        level=level,
        stock_name=stock_name,
        ts_code=ts_code,
        error_msg=error_msg,
        detail=detail or traceback.format_exc(),
        data_snapshot=data_snapshot,
        service_name="office",
        error_code=error_code,
        engine_name=engine_name,
    )
