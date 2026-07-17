"""route_tool — 路由工具（双检索版）

关键字匹配 + Embedding 向量检索 双路合并，返回候选 DataField 列表。
"""
import json, os, sys

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KG_DIR = os.path.dirname(_QA_DIR)
sys.path.insert(0, _KG_DIR)

from irkg.router import Router
from irkg.types import RouteCondition
from irkg.embedding import EmbeddingRetriever
from irkg.graph import GraphQuerier


class RouteTool:
    """路由工具"""

    def __init__(self):
        self.router = Router()
        alias_path = os.path.join(_KG_DIR, "data", "datafield_new_alias_all.txt")
        if os.path.exists(alias_path):
            self.router.build(alias_csv_path=alias_path)
        self.embedding = EmbeddingRetriever()
        self.graph = GraphQuerier()

    def hybrid_query(self, keywords: list[str], top_k_embed: int = 3,
                     max_candidates: int = 8) -> list[dict]:
        """双检索：关键字匹配 + Embedding 向量检索，合并去重后返回候选列表

        Args:
            keywords: 指标关键词，如 ["涨跌幅"]
            top_k_embed: Embedding 检索返回的 top-K
            max_candidates: 最终返回的最大候选数

        Returns:
            [{"id": "FIELD_XXX", "name": "个股涨跌幅", "match": "qualified",
              "time_gran": "实时", "scope": "个股级别",
              "ds_name": "...", "protocol": "tushare"}, ...]
        """
        # 1. 关键字匹配
        alias_result = self.router.route(keywords, conditions=RouteCondition(), strict=False)

        # 2. Embedding 检索
        query_text = " ".join(keywords)
        try:
            query_vec = self.embedding.embed_query(query_text)
            emb_results = self.embedding.search_fields(query_vec, top_k=top_k_embed)
        except Exception:
            emb_results = []

        # 3. 合并（alias 结果优先，embedding 补充不在 alias 中的）
        seen = set()
        merged = []
        for f in alias_result.fields:
            if f.id not in seen:
                seen.add(f.id)
                merged.append(f)
        for r in emb_results:
            if r["id"] not in seen:
                seen.add(r["id"])
                info = self.graph.get_field_by_id(r["id"])
                if info:
                    info.match_type = "embedding"
                    info.similarity = r["score"]
                    merged.append(info)

        # 4. 格式化为精简候选列表
        candidates = []
        for f in merged[:max_candidates]:
            gran = (f.granularity or "").split(",")
            time_gran = gran[0].strip() if len(gran) > 0 else ""
            scope = gran[1].strip() if len(gran) > 1 else ""
            ds = self.graph.get_datasource(f.id)
            # 获取权威评级
            auth = getattr(f, 'authority_level', '') or ''
            candidates.append({
                "id": f.id,
                "name": f.standard_name,
                "match": f.match_type,
                "time_gran": time_gran,
                "scope": scope,
                "ds_name": ds.name if ds else "",
                "protocol": ds.protocol if ds else "",
                "prompt_dir": ds.prompt_dir if ds else "",
                "authority": auth,
            })

        return candidates


# 单例
_tool: RouteTool | None = None


def get_route_tool() -> RouteTool:
    global _tool
    if _tool is None:
        _tool = RouteTool()
    return _tool
