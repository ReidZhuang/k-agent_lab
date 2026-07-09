"""search_engine — 统一搜索接口

用法:
    from search_engine import search

    # 基本搜索
    results = search("中国芯片")

    # 站内搜索
    results = search("中国芯片", site="zhihu.com")

    # 站内 + 时间过滤
    results = search("中国芯片", site="stcn.com", timelimit="y")
"""
from .backends.ddgs import DDGSSearchBackend


def search(query: str, max_results: int = 10,
           site: str | None = None, timelimit: str | None = None) -> list[dict]:
    """
    统一搜索接口。默认使用 ddgs 后端。

    返回 [{title, url, snippet}, ...]
    """
    backend = DDGSSearchBackend()
    return backend.search(query, max_results=max_results,
                          site=site, timelimit=timelimit)
