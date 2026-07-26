"""ddgs 搜索后端

注意：DuckDuckGo 被墙，必须走代理。但代理只传给 DDGS 实例本身，
不设置环境变量，避免影响同一进程中其他引擎（sinafin/thsfin 等）
的 HTTP 请求。它们直连国内金融站点，走代理反而会被 RST。
"""
from ddgs import DDGS
from .base import SearchBackend
from ..config import PROXY


class DDGSSearchBackend(SearchBackend):
    """基于 ddgs 的 DuckDuckGo 搜索实现"""

    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None) -> list[dict]:
        # 拼接 site: 到 query
        if site:
            query = f"{query} site:{site}"

        # 直接传 proxy 给 DDGS，不设环境变量
        with DDGS(proxy=PROXY) as ddgs:
            kwargs = {"max_results": max_results}
            if timelimit:
                kwargs["timelimit"] = timelimit
            raw = list(ddgs.text(query, **kwargs))

        # 统一字段映射
        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            })
        return results
