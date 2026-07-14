#!/usr/bin/env python3
"""Phase 4: 写入 BELONGS_TO_CONCEPT 关系到 Neo4j"""
import csv
from neo4j import GraphDatabase

DRIVER = GraphDatabase.driver(
    "bolt://localhost:7687", auth=("neo4j", "kg_route_2026")
)

CSV_PATH = "../data/datafield_new_alias_520_deepseek.txt"

def main():
    with open(CSV_PATH) as f:
        rows = list(csv.DictReader(f))

    print(f"读取 {len(rows)} 条 field -> concept 映射")

    with DRIVER.session() as session:
        # 删除旧关系
        session.run("MATCH ()-[r:BELONGS_TO_CONCEPT]->() DELETE r")

        # 逐条写入
        count = 0
        for row in rows:
            session.run(
                (
                    "MATCH (f:DataField {id: $fid}) "
                    "MATCH (c:IntentConcept {id: $cid}) "
                    "MERGE (f)-[r:BELONGS_TO_CONCEPT {"
                    "relevance_score: $rel, "
                    "is_approved: true, "
                    "is_auto_suggested: false"
                    "}]->(c)"
                ),
                fid=row["field_id"],
                cid=row["concept_id"],
                rel=0.8,
            )
            count += 1
            if count % 100 == 0:
                print(f"  进度: {count}/{len(rows)}")

        # 验证
        result = session.run(
            "MATCH ()-[r:BELONGS_TO_CONCEPT]->() RETURN count(r) as c"
        ).single()
        print(f"\nBELONGS_TO_CONCEPT 关系数: {result['c']}")

        # 展示分布
        result = session.run(
            "MATCH (f:DataField)-[:BELONGS_TO_CONCEPT]->(c:IntentConcept) "
            "RETURN c.id as concept, count(f) as fields "
            "ORDER BY fields DESC LIMIT 10"
        )
        print("Top 10 Concept 分布:")
        for r in result:
            print(f"  {r['concept']}: {r['fields']} 个字段")

    DRIVER.close()
    print("Phase 4 完成!")

if __name__ == "__main__":
    main()
