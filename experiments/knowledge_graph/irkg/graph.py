"""Neo4j 图查询模块"""
from neo4j import GraphDatabase
from .config import config
from .types import FieldInfo, DataSourceInfo


class GraphQuerier:
    """知识图谱查询封装"""

    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASS)
            )
            self._driver.verify_connectivity()
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def get_field_by_id(self, field_id: str) -> FieldInfo | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (f:DataField {id: $id}) RETURN f", id=field_id
            ).single()
            if not result:
                return None
            f = result["f"]
            return FieldInfo(
                id=f["id"],
                standard_name=f.get("standard_name", ""),
                description=f.get("description", ""),
                data_type=f.get("data_type", ""),
                unit=f.get("unit", ""),
                api_column=f.get("api_column", ""),
                has_backup=f.get("has_backup", False),
                granularity=f.get("granularity", ""),
                refresh_time=f.get("refresh_time", ""),
                authority_level=f.get("authority_level", ""),
            )

    def get_concept(self, field_id: str) -> list[str]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:DataField {id: $id})-[:BELONGS_TO_CONCEPT]->(c:IntentConcept)
                RETURN c.id as cid
            """, id=field_id)
            return [r["cid"] for r in result]

    def get_similar_fields(self, field_id: str, levels: list[str]) -> list[FieldInfo]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:DataField {id: $id})-[r:SEMANTIC_SIMILAR_TO]->(n:DataField)
                WHERE r.level IN $levels
                RETURN n.id as id, n.standard_name as name,
                       n.description as desc, n.data_type as type,
                       n.unit as unit, r.cosine_similarity as sim
                ORDER BY sim DESC
            """, id=field_id, levels=levels)
            return [
                FieldInfo(
                    id=r["id"], standard_name=r["name"] or "",
                    description=r["desc"] or "", data_type=r["type"] or "",
                    unit=r["unit"] or "", similarity=r["sim"],
                    match_type="similar",
                )
                for r in result
            ]

    def get_datasource(self, field_id: str) -> DataSourceInfo | None:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (f:DataField {id: $id})-[:HAS_DATASOURCE]->(ds:DataSource)
                RETURN ds.id as id, ds.name as name, ds.protocol as protocol,
                       ds.prompt_dir as prompt_dir
            """, id=field_id).single()
            if not result:
                return None
            return DataSourceInfo(
                id=result["id"],
                name=result["name"] or "",
                protocol=result["protocol"] or "",
                prompt_dir=result.get("prompt_dir", "") or "",
            )

    def get_concept_info(self, concept_id: str) -> dict | None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:IntentConcept {id: $id}) RETURN c", id=concept_id
            ).single()
            if not result:
                return None
            c = result["c"]
            return {
                "id": c["id"],
                "name": c.get("name", ""),
                "description": c.get("description", ""),
            }

    def get_site_search_urls(self, concept_id: str) -> list[str]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:IntentConcept {id: $id}) RETURN c.site_search_urls as urls",
                id=concept_id,
            ).single()
            if not result or not result.get("urls"):
                return []
            urls = result["urls"]
            if isinstance(urls, str):
                return [u.strip() for u in urls.split("；") if u.strip()]
            return urls
