"""
kg_incremental.py — 知识图谱增量更新

对比 Neo4j 已有股票和 member 表最新股票，
补齐新出现的个股→关键词关系。
"""

import sqlite3
from collections import defaultdict
from neo4j import GraphDatabase
from config import DB_PATH, NEO4J_URI, NEO4J_USER, NEO4J_PASS


def _get_existing_stocks(driver) -> set[str]:
    """Neo4j 中已存在的股票代码集合"""
    with driver.session() as session:
        result = session.run("MATCH (s:Stock) RETURN s.code AS code")
        return {r["code"] for r in result}


def _get_all_member_stocks(conn) -> set[str]:
    """member 表中所有股票代码集合"""
    cur = conn.cursor()
    all_codes = set()
    for tbl in ["stg_dc_member", "stg_ths_member", "stg_tdx_member"]:
        try:
            cur.execute(f"SELECT DISTINCT con_code FROM {tbl}")
            all_codes.update(r[0] for r in cur.fetchall())
        except Exception:
            continue
    return all_codes


def _get_sector_keywords(conn) -> dict[str, list[tuple[str, str]]]:
    """加载板块→关键词"""
    cur = conn.cursor()
    cur.execute("SELECT ts_code, keywords, category FROM meta_sector_keywords")
    result = {}
    for ts_code, kw_str, cat in cur.fetchall():
        keywords = [k.strip() for k in kw_str.split(";") if k.strip()]
        result[ts_code] = [(kw, cat) for kw in keywords]
    return result


def _get_new_stock_members(conn, new_stocks: set[str]) -> list[tuple[str, str, str]]:
    """查询新股票的板块归属

    Returns:
        [(stock_code, stock_name, sector_code), ...]
    """
    if not new_stocks:
        return []

    cur = conn.cursor()
    rows = []
    for tbl in ["stg_dc_member", "stg_ths_member", "stg_tdx_member"]:
        try:
            placeholders = ",".join("?" for _ in new_stocks)
            cur.execute(
                f"SELECT DISTINCT con_code, con_name, ts_code FROM {tbl} "
                f"WHERE con_code IN ({placeholders})",
                list(new_stocks),
            )
            rows.extend(cur.fetchall())
        except Exception:
            continue
    return rows


def _write_new_stock(driver, stock_code, stock_name, keywords: dict):
    """写入单个新股票及其关键词关系"""
    keyword_list = [
        {"keyword": kw, "categories": sorted(cats)}
        for kw, cats in keywords.items()
    ]

    with driver.session() as session:
        session.run("""
            MERGE (s:Stock {code: $code})
            SET s.name = $name
            WITH s
            UNWIND $keywords AS kw_data
            MERGE (k:Keyword {keyword: kw_data.keyword})
            SET k.categories = kw_data.categories
            SET k.boosted = '概念' IN kw_data.categories AND '行业' IN kw_data.categories
            MERGE (s)-[:HAS_KEY]->(k)
        """, code=stock_code, name=stock_name, keywords=keyword_list)


def incremental_update():
    """增量更新入口"""
    print("[incremental] 增量更新开始")

    conn = sqlite3.connect(str(DB_PATH))
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()

    # 1. 对比差异
    existing = _get_existing_stocks(driver)
    all_stocks = _get_all_member_stocks(conn)
    new_stocks = all_stocks - existing
    print(f"  存量: {len(existing)}, 全量: {len(all_stocks)}, 新增: {len(new_stocks)}")

    if not new_stocks:
        print("[incremental] 无新增股票")
        driver.close()
        conn.close()
        return

    # 2. 加载板块→关键词
    sector_keywords = _get_sector_keywords(conn)
    print(f"  板块→关键词: {len(sector_keywords)} 个板块")

    # 3. 查新股票的板块归属
    members = _get_new_stock_members(conn, new_stocks)
    print(f"  新股票板块归属: {len(members)} 条")

    # 4. 构建个股→关键词
    from collections import defaultdict
    stock_data = defaultdict(lambda: {"name": "", "keywords": defaultdict(set)})
    for code, name, sector_code in members:
        if sector_code not in sector_keywords:
            continue
        stock_data[code]["name"] = name
        for kw, cat in sector_keywords[sector_code]:
            stock_data[code]["keywords"][kw].add(cat)

    # 5. 写入 Neo4j
    for code, data in stock_data.items():
        _write_new_stock(driver, code, data["name"], data["keywords"])

    print(f"  ✅ 新增 {len(stock_data)} 个股")
    driver.close()
    conn.close()
    print("[incremental] ✅ 增量更新完成")


if __name__ == "__main__":
    incremental_update()
