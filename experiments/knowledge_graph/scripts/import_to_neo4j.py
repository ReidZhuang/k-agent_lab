#!/usr/bin/env python3
"""将 CSV 数据导入 Neo4j"""
import csv, json
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"

DATA_DIR = "../data"

def read_csv(filename):
    with open(f"{DATA_DIR}/{filename}", newline="") as f:
        return list(csv.DictReader(f))

def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print("Neo4j 连接成功")

    concepts = read_csv("concepts.csv")
    sources = read_csv("sources.csv")
    fields = read_csv("fields.csv")

    with driver.session() as session:
        # 清空数据库（开发阶段，后续会去掉）
        session.run("MATCH (n) DETACH DELETE n")
        print("数据库已清空")

        # --- IntentConcept ---
        print(f"\n写入 {len(concepts)} 个 IntentConcept...")
        result = session.run("""
            UNWIND $rows AS row
            CREATE (c:IntentConcept {
                id: row.id,
                name: row.name,
                description: row.description,
                seed_keywords: split(row.seed_keywords, '、'),
                requires_entity:
                    CASE WHEN row.requires_entity = '[]' THEN []
                    ELSE [x IN split(replace(replace(replace(row.requires_entity, '[', ''), ']', ''), '\"', ''), ',') | trim(x)]
                    END,
                default_seed_fields: split(row.default_seed_fields, ', '),
                site_search_urls: row.site_search_urls
            })
            RETURN count(c) as count
        """, rows=concepts)
        print(f"  写入 {result.single()['count']} 个节点")
        # 创建唯一索引
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:IntentConcept) REQUIRE c.id IS UNIQUE")

        # --- DataSource ---
        print(f"\n写入 {len(sources)} 个 DataSource...")
        result = session.run("""
            UNWIND $rows AS row
            CREATE (ds:DataSource {
                id: row.id,
                name: row.name,
                protocol: row.protocol,
                execution_meta: row.execution_meta,
                refresh_time: row.refresh_time,
                authority_level: row.authority_level,
                reliability_score:
                    CASE WHEN row.reliability_score = '' THEN 0.0
                    ELSE toFloat(row.reliability_score) END,
                latency_ms:
                    CASE WHEN row.latency_ms = '' THEN 0
                    ELSE toInteger(row.latency_ms) END,
                code_format: row.code_format,
                prompt_dir: row.prompt_dir
            })
            RETURN count(ds) as count
        """, rows=sources)
        print(f"  写入 {result.single()['count']} 个节点")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DataSource) REQUIRE ds.id IS UNIQUE")

        # --- DataField ---
        print(f"\n写入 {len(fields)} 个 DataField...")
        result = session.run("""
            UNWIND $rows AS row
            CREATE (f:DataField {
                id: row.id,
                standard_name: row.standard_name,
                alias: row.alias,
                description: row.description,
                data_type: row.data_type,
                unit: row.unit,
                authority_level: row.authority_level,
                refresh_time: row.refresh_time,
                default_datasource_id: row.default_datasource_id
            })
            RETURN count(f) as count
        """, rows=fields)
        print(f"  写入 {result.single()['count']} 个节点")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:DataField) REQUIRE f.id IS UNIQUE")

        # --- 从属关系: DataField -> DataSource ---
        print("\n建立 DataField -> DataSource 关系...")
        result = session.run("""
            MATCH (f:DataField), (ds:DataSource {id: f.default_datasource_id})
            CREATE (f)-[:HAS_DATASOURCE]->(ds)
            RETURN count(*) as count
        """)
        print(f"  建立 {result.single()['count']} 条关系")

        # --- 统计验证 ---
        print("\n=== 节点统计 ===")
        for label in ["IntentConcept", "DataSource", "DataField"]:
            count = session.run(f"MATCH (n:{label}) RETURN count(n) as c").single()["c"]
            print(f"  {label}: {count}")

    driver.close()
    print("\nPhase 1 数据导入完成!")

if __name__ == "__main__":
    main()
