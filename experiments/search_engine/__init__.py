"""search_engine — 统一搜索接口

用法:
    from search_engine import search

    # DDG 基本搜索
    results = search("中国芯片")

    # DDG 站内搜索
    results = search("中国芯片", site="zhihu.com")

    # Sinafin 个股新闻
    results = search("宁德时代", engine="sinafin", max_results=3)
    results = search("300750", engine="sinafin", start_date="2026-07-18")

    # Baidufin 百度股市通资讯
    results = search("300436", engine="baidufin")
    results = search("600519", engine="baidufin", start_date="2026-07-20")

返回格式: [{title, url, snippet}, ...]
    engine=sinafin 时额外返回 _known_date 字段（精确发布日期）。
    engine=baidufin 时额外返回 _baidu_sentiment / _baidu_provider / _baidu_abstract。
"""
from .backends.ddgs import DDGSSearchBackend
from .backends.sinafin import SinaFinBackend
from .backends.baidufin import BaidufinBackend


def search(query: str, max_results: int = 10,
           site: str | None = None, timelimit: str | None = None,
           engine: str = "ddg",
           start_date: str | None = None,
           end_date: str | None = None) -> list[dict]:
    """
    统一搜索接口。支持多后端分发。

    Args:
        query: 搜索关键词（DDG）或股票代码/名称（sinafin）
        max_results: 返回条数（DDG）或翻页页数（sinafin）
        site: 站内限制（仅 DDG）
        timelimit: 时间限制（仅 DDG）
        engine: 搜索后端，可选 "ddg"（默认）| "sinafin" | "baidufin"
        start_date: 起始日期过滤 YYYY-MM-DD（sinafin/baidufin）
        end_date: 截止日期过滤 YYYY-MM-DD（sinafin/baidufin）

    Returns:
        [{title, url, snippet}, ...]
        engine=sinafin 时额外含 _known_date 字段。
    """
    if engine == "sinafin":
        backend = SinaFinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    elif engine == "baidufin":
        backend = BaidufinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    else:
        backend = DDGSSearchBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit)
