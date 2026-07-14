"""IRKG v3 路由主逻辑"""
from .types import RouteResult, RouteCondition, FieldInfo
from .matcher import AliasMatcher
from .embedding import EmbeddingRetriever
from .graph import GraphQuerier
from .config import config


class Router:
    def __init__(self):
        self.matcher = AliasMatcher()
        self.embedding = EmbeddingRetriever()
        self.graph = GraphQuerier()

    def build(self, alias_csv_path: str = None, fields_csv: list[dict] = None):
        if alias_csv_path:
            self.matcher.build_from_csv(alias_csv_path)
        elif fields_csv:
            self.matcher.build(fields_csv)

    def route(
        self,
        keywords: list[str],
        intent_type: str = "fact",
        conditions: RouteCondition = None,
        strict: bool = False,
    ) -> RouteResult:
        result = RouteResult(intent_type=intent_type)
        if conditions:
            result.conditions = conditions

        if not keywords or not any(k.strip() for k in keywords):
            return result

        # Step 1: alias 多级匹配
        matches = self.matcher.match_multi(keywords)

        if matches:
            for fid, match_type in matches:
                info = self.matcher.get_info(fid)
                if info:
                    result.fields.append(FieldInfo(
                        id=fid, standard_name=info["standard_name"],
                        description=info.get("description", ""),
                        match_type=match_type,
                    ))
        elif not strict:
            # Step 2: Faiss 向量检索兜底
            query_text = " ".join(keywords)
            query_vec = self.embedding.embed_query(query_text)
            candidates = self.embedding.search_fields(query_vec)
            for cand in candidates:
                info = self.graph.get_field_by_id(cand["id"])
                if info:
                    info.similarity = cand["score"]
                    info.match_type = "fuzzy"
                    result.fields.append(info)

        # 从图数据库补充字段属性
        for f in result.fields:
            node = self.graph.get_field_by_id(f.id)
            if node:
                if node.api_column:
                    f.api_column = node.api_column
                f.has_backup = node.has_backup
                if node.granularity:
                    f.granularity = node.granularity
                if node.refresh_time:
                    f.refresh_time = node.refresh_time
                if node.unit:
                    f.unit = node.unit
                if node.data_type:
                    f.data_type = node.data_type

        if not result.fields:
            return result

        primary_field = result.fields[0]

        # Step 3: 查 BELONGS_TO_CONCEPT
        concept_ids = self.graph.get_concept(primary_field.id)
        if concept_ids:
            result.concept_id = concept_ids[0]
            info = self.graph.get_concept_info(concept_ids[0])
            if info:
                result.concept_name = info["name"]

        # Step 4: 近邻扩散
        levels = config.SIMILAR_LEVELS.get(intent_type, ["high"])
        if levels:
            similar = self.graph.get_similar_fields(primary_field.id, levels)
            existing_ids = {f.id for f in result.fields}
            for s in similar:
                if s.id not in existing_ids:
                    result.expanded_fields.append(s)

        # Step 5: 数据源反查
        ds = self.graph.get_datasource(primary_field.id)
        if ds:
            result.datasource = ds

        # Step 6: 站内搜索（当数据源为 web_search 时携带 site 信息）
        if result.datasource and result.datasource.protocol == "web_search" and result.concept_id:
            sites = self.graph.get_site_search_urls(result.concept_id)
            result.web_search_sites = sites

        return result
