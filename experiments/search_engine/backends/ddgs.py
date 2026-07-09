"""ddgs 搜索后端"""
import os
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

        # 设置代理
        old_http = os.environ.get("http_proxy")
        old_https = os.environ.get("https_proxy")
        os.environ["http_proxy"] = PROXY
        os.environ["https_proxy"] = PROXY

        try:
            with DDGS() as ddgs:
                kwargs = {"max_results": max_results}
                if timelimit:
                    kwargs["timelimit"] = timelimit
                raw = list(ddgs.text(query, **kwargs))
        finally:
            # 还原代理环境变量
            if old_http:
                os.environ["http_proxy"] = old_http
            else:
                os.environ.pop("http_proxy", None)
            if old_https:
                os.environ["https_proxy"] = old_https
            else:
                os.environ.pop("https_proxy", None)

        # 统一字段映射
        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            })
        return results
