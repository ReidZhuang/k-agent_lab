#!/usr/bin/env python3
"""
一次性迁移：将 datafield_new_alias_all.txt 的 4 级别名写入 Neo4j

alias 存储为结构化 JSON 字符串：
  {"simple":["涨跌幅"],"qualified":["个股涨跌幅","实时涨跌幅"],"business_tag":[...],"synonyms":[...]}

仅更新 Neo4j 中 DataField 节点的 alias 属性，不影响其他。
"""
import json, csv
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"
ALIAS_FILE = "../data/datafield_new_alias_all.txt"


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print("Neo4j 连接成功")

    # 1. 读取 alias 文件
    print(f"\n[1/3] 读取 alias 文件...")
    with open(ALIAS_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"    共 {len(rows)} 条")

    # 2. 构建批量更新数据
    print(f"\n[2/3] 构建结构化 JSON...")
    batch = []
    for row in rows:
        structured = {
            "simple": [s.strip() for s in row.get("simple","").split("|") if s.strip()],
            "qualified": [s.strip() for s in row.get("qualified","").split("|") if s.strip()],
            "business_tag": [s.strip() for s in row.get("business_tag","").split("|") if s.strip()],
            "synonyms": [s.strip() for s in row.get("synonyms","").split("|") if s.strip()],
        }
        batch.append({"id": row["field_id"], "alias": json.dumps(structured, ensure_ascii=False)})

    # 3. 写入 Neo4j
    print(f"\n[3/3] 写入 Neo4j...")
    with driver.session() as session:
        BATCH = 100
        total = 0
        for i in range(0, len(batch), BATCH):
            chunk = batch[i:i + BATCH]
            result = session.run("""
                UNWIND $rows AS row
                MATCH (f:DataField {id: row.id})
                SET f.alias = row.alias
                RETURN count(f) as c
            """, rows=chunk)
            total += result.single()["c"]
            print(f"    进度: {total}/{len(batch)}", end="\r")
        print(f"\n    完成! 更新 {total} 个节点")

    # 4. 检查空 alias 节点
    print(f"\n{'='*60}")
    print("检查 alias 仍为空的 DataField")
    print(f"{'='*60}")
    with driver.session() as session:
        # 统计
        total = session.run("MATCH (f:DataField) RETURN count(f) as c").single()["c"]
        null_or_empty = session.run("""
            MATCH (f:DataField)
            WHERE f.alias IS NULL
               OR f.alias = '[]'
               OR f.alias = ''
            RETURN count(f) as c
        """).single()["c"]

        if null_or_empty == 0:
            print(f"\n✅ 全部 {total} 个 DataField 都有 alias 数据，无遗漏")
        else:
            print(f"\n⚠️  共 {null_or_empty}/{total} 个节点 alias 仍为空：")
            result = session.run("""
                MATCH (f:DataField)
                WHERE f.alias IS NULL
                   OR f.alias = '[]'
                   OR f.alias = ''
                RETURN f.id as id, f.standard_name as name,
                       f.description as desc
                ORDER BY f.id
            """)
            for r in result:
                print(f"  ❌ {r['id']:40s} | {r['name']:<12s} | {r['desc'][:40] or 'N/A'}")

        # 也看看 alias 非空的样例
        print(f"\n  抽样验证（alias 非空的前 3 条）：")
        result = session.run("""
            MATCH (f:DataField)
            WHERE f.alias IS NOT NULL AND f.alias <> '[]' AND f.alias <> ''
            RETURN f.id as id, f.alias as alias
            LIMIT 3
        """)
        for r in result:
            try:
                data = json.loads(r["alias"])
                levels = {k: len(v) for k, v in data.items()}
                print(f"  ✅ {r['id']:40s} 别名数: {levels}")
            except:
                print(f"  ✅ {r['id']:40s} alias={str(r['alias'])[:60]}")

    driver.close()
    print(f"\n迁移完成")


if __name__ == "__main__":
    main()
