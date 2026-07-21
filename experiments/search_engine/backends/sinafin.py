"""sinafin 搜索后端 — 通过 sinafin_artical_tool API 获取个股新闻

用法:
    from search_engine import search
    results = search("300750", max_results=3, engine="sinafin")
    results = search("宁德时代", engine="sinafin", start_date="2026-07-18")

返回格式: [{title, url, snippet, _known_date}, ...]
    _known_date 是 sinafin 返回的精确发布日期，Phase 1 应直接使用，无需重新提取。
"""
import re
import httpx
from .base import SearchBackend
from ..config import SNAFIN_ENDPOINT


class SinaFinBackend(SearchBackend):
    """通过 sinafin_artical_tool API 获取个股新闻列表"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or SNAFIN_ENDPOINT).rstrip("/")

    def search(self, query: str, max_results: int = 3,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行个股新闻搜索。

        Args:
            query: 股票代码（如 "300750"）或名称（如 "宁德时代"）
            max_results: 翻页页数（映射为 sinafin 的 pages 参数）
            start_date: 起始日期过滤 YYYY-MM-DD
            end_date: 截止日期过滤 YYYY-MM-DD

        Returns:
            [{title, url, snippet, _known_date}, ...]
        """
        # 判断 query 是代码还是名称
        if re.match(r'^[a-zA-Z]{0,2}\d{6}(\.\w+)?$', query.strip()):
            params = {"code": query.strip()}
        else:
            params = {"name": query.strip()}

        params["pages"] = max(1, min(max_results, 50))
        params["format"] = "json"

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        try:
            resp = httpx.get(
                f"{self.base_url}/news",
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"无法连接 sinafin_artical_tool ({self.base_url})，请确认服务已启动"
            )
        except Exception as e:
            raise RuntimeError(f"sinafin API 调用失败: {e}")

        results = []
        for item in data.get("news", []):
            date_str = item.get("date", "")
            time_str = item.get("time", "")
            snippet = f"{date_str} {time_str}".strip()
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": snippet,
                "_known_date": date_str,  # 精确日期，Phase 1 直接使用
            })

        return results
