"""Fix concept IDs: remove backticks, then create BELONGS_TO_CONCEPT relationships"""
import csv
from neo4j import GraphDatabase

DRIVER = GraphDatabase.driver(
    "bolt://localhost:7687", auth=("neo4j", "kg_route_2026")
)


def main():
    with DRIVER.session() as session:
        # Step 1: Fix backticks in concept IDs
        print("Step 1: 清理反引号...")
        ids = session.run("MATCH (c:IntentConcept) RETURN c.id as id")
        for rec in ids:
            old_id = rec["id"]
            if old_id.startswith("`"):
                new_id = old_id.strip("`")
                session.run(
                    "MATCH (c:IntentConcept {id: $old}) SET c.id = $new",
                    old=old_id, new=new_id,
                )
                print(f"  {old_id} -> {new_id}")

        # Verify
        r = session.run("MATCH (c:IntentConcept) RETURN count(c) as c").single()
        print(f"IntentConcept 节点数: {r['c']}")
        r = session.run("MATCH (c:IntentConcept) RETURN c.id as id LIMIT 3")
        for rec in r:
            print(f"  ID: {repr(rec['id'])}")

        # Step 2: Create BELONGS_TO_CONCEPT relationships
        print("\nStep 2: 写入 BELONGS_TO_CONCEPT...")
        with open("../data/datafield_new_alias_520_deepseek.txt") as f:
            rows = list(csv.DictReader(f))

        created = 0
        for i, row in enumerate(rows):
            result = session.run(
                (
                    "MATCH (f:DataField {id: $fid}) "
                    "MATCH (c:IntentConcept {id: $cid}) "
                    "MERGE (f)-[:BELONGS_TO_CONCEPT {"
                    "relevance_score: 0.8, is_approved: true, "
                    "is_auto_suggested: false}]->(c) "
                    "RETURN count(f) as matched"
                ),
                fid=row["field_id"],
                cid=row["concept_id"],
            ).single()
            if result and result["matched"] > 0:
                created += 1
            if (i + 1) % 100 == 0:
                print(f"  进度: {i+1}/{len(rows)}")

        # Verify
        r = session.run(
            "MATCH ()-[r:BELONGS_TO_CONCEPT]->() RETURN count(r) as c"
        ).single()
        print(f"\nBELONGS_TO_CONCEPT 关系数: {r['c']}")

    DRIVER.close()
    print("完成!")


if __name__ == "__main__":
    main()
