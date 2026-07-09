"""搜索后端抽象基类"""
from abc import ABC, abstractmethod


class SearchBackend(ABC):
    """搜索后端接口。所有后端实现需继承此类并实现 search() 方法。"""

    @abstractmethod
    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None) -> list[dict]:
        """
        执行搜索，返回统一格式的结果列表。

        返回格式: [{title, url, snippet}, ...]
        """
