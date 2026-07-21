"""
kg_builder.py — SQLite → Neo4j 知识图谱构建

从 stg_{dc/ths/tdx}_member 读取个股归属板块，
从 meta_sector_keywords 读取板块关键词，
构建 (Stock)-[:HAS_KEY]->(Keyword) 图谱。
"""

import sqlite3
from collections import defaultdict
from neo4j import GraphDatabase
from config import DB_PATH, NEO4J_URI, NEO4J_USER, NEO4J_PASS


# ===== Step 1: 从 SQLite 读取数据 =====

def _load_sector_keywords(conn) -> dict[str, list[tuple[str, str]]]:
    """加载 meta_sector_keywords → {ts_code: [(keyword, category), ...]}"""
    cur = conn.cursor()
    cur.execute("SELECT ts_code, keywords, category FROM meta_sector_keywords")
    result = {}
    for ts_code, kw_str, cat in cur.fetchall():
        keywords = [k.strip() for k in kw_str.split(";") if k.strip()]
        result[ts_code] = [(kw, cat) for kw in keywords]
    return result


def _load_member_stocks(conn) -> list[tuple[str, str, str]]:
    """从三张 member 表加载个股板块归属

    Returns:
        [(stock_code, stock_name, sector_code), ...]
    """
    cur = conn.cursor()
    all_rows = []

    for tbl in ["stg_dc_member", "stg_ths_member", "stg_tdx_member"]:
        try:
            cur.execute(f"SELECT DISTINCT con_code, con_name, ts_code FROM {tbl}")
            all_rows.extend(cur.fetchall())
        except Exception:
            continue

    return all_rows


def _build_stock_keywords(members, sector_keywords) -> dict:
    """构建个股→关键词映射（去重合并）

    Args:
        members: [(stock_code, stock_name, sector_code), ...]
        sector_keywords: {ts_code: [(keyword, category), ...]}

    Returns:
        {stock_code: {"name": str, "keywords": {keyword: set[categories]}}}
    """
    stock_data = {}

    for stock_code, stock_name, sector_code in members:
        if sector_code not in sector_keywords:
            continue

        if stock_code not in stock_data:
            stock_data[stock_code] = {
                "name": stock_name,
                "keywords": defaultdict(set),
            }

        for kw, cat in sector_keywords[sector_code]:
            stock_data[stock_code]["keywords"][kw].add(cat)

    return stock_data


# ===== Step 2: 写入 Neo4j =====

def _create_constraints(driver):
    """创建唯一约束"""
    with driver.session() as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Stock) REQUIRE s.code IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (k:Keyword) REQUIRE k.keyword IS UNIQUE")


def _clear_graph(driver):
    """清空图谱（用于全量重建）"""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("[builder] 图谱已清空")


def _write_stock_keywords(driver, stock_data, batch_size=500):
    """批量写入 Neo4j"""
    items = list(stock_data.items())

    with driver.session() as session:
        total = 0
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # 构建 Cypher 参数
            rows = []
            for code, data in batch:
                keyword_list = []
                for kw, cats in data["keywords"].items():
                    keyword_list.append({
                        "keyword": kw,
                        "categories": sorted(cats),
                    })
                rows.append({
                    "code": code,
                    "name": data["name"],
                    "keywords": keyword_list,
                })

            session.run("""
                UNWIND $rows AS row
                MERGE (s:Stock {code: row.code})
                SET s.name = row.name

                WITH s, row
                UNWIND row.keywords AS kw_data
                MERGE (k:Keyword {keyword: kw_data.keyword})
                SET k.categories = kw_data.categories
                SET k.boosted = '概念' IN kw_data.categories AND '行业' IN kw_data.categories
                MERGE (s)-[:HAS_KEY]->(k)
            """, rows=rows)

            total += len(batch)
            print(f"  progress: {total}/{len(items)} stocks")

        print(f"  ✅ 写入 {total} 个股, 共 {sum(len(d['keywords']) for d in stock_data.values())} 条关系")


# ===== 全量构建 =====

def build_all():
    print("=" * 50)
    print("[builder] 知识图谱全量构建")
    print("=" * 50)

    # 1. 从 SQLite 读取
    print("\n[Step 1] 读取 SQLite ...")
    conn = sqlite3.connect(str(DB_PATH))

    sector_keywords = _load_sector_keywords(conn)
    print(f"  板块→关键词: {len(sector_keywords)} 个板块")

    members = _load_member_stocks(conn)
    print(f"  个股→板块归属: {len(members)} 条")

    # 2. 构建个股→关键词映射
    print("\n[Step 2] 构建个股→关键词映射（去重合并）...")
    stock_data = _build_stock_keywords(members, sector_keywords)
    print(f"  个股数: {len(stock_data)}")

    # 统计
    total_edges = sum(len(d["keywords"]) for d in stock_data.values())
    total_keywords = len(set(
        kw for d in stock_data.values() for kw in d["keywords"]
    ))
    print(f"  关键词节点数（去重后）: {total_keywords}")
    print(f"  个股→关键词关系数: {total_edges}")

    conn.close()

    # 3. 写入 Neo4j
    print("\n[Step 3] 写入 Neo4j ...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print("  Neo4j 连接成功")

    _clear_graph(driver)
    _create_constraints(driver)
    _write_stock_keywords(driver, stock_data)

    driver.close()
    print("\n[builder] ✅ 全量构建完成")


if __name__ == "__main__":
    build_all()
