"""
kg_query.py — Neo4j 知识图谱查询接口

个股→关键词 / 关键词→个股 双向查询
"""

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASS


def _get_driver():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    return driver


def get_keywords(stock_code: str) -> list[dict]:
    """输入股票代码 → [{keyword, categories}, ...]"""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword) "
            "RETURN k.keyword AS keyword, k.categories AS categories "
            "ORDER BY keyword",
            code=stock_code,
        )
        rows = [{"keyword": r["keyword"], "categories": r["categories"]}
                for r in result]
    driver.close()
    return rows


def get_stocks_by_keyword(keyword: str) -> list[dict]:
    """输入关键词 → [{code, name}, ...]"""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (s:Stock)-[:HAS_KEY]->(k:Keyword {keyword: $keyword}) "
            "RETURN s.code AS code, s.name AS name "
            "ORDER BY s.code",
            keyword=keyword,
        )
        rows = [{"code": r["code"], "name": r["name"]} for r in result]
    driver.close()
    return rows


def get_stock_count() -> int:
    """返回图谱中的个股总数"""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run("MATCH (s:Stock) RETURN count(s) AS cnt")
        cnt = result.single()["cnt"]
    driver.close()
    return cnt


def get_keyword_count() -> int:
    """返回图谱中的关键词总数"""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run("MATCH (k:Keyword) RETURN count(k) AS cnt")
        cnt = result.single()["cnt"]
    driver.close()
    return cnt


def search_stock(name_or_code: str) -> list[dict]:
    """模糊搜索个股（按名称或代码）"""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (s:Stock) "
            "WHERE s.code CONTAINS $q OR s.name CONTAINS $q "
            "RETURN s.code AS code, s.name AS name "
            "LIMIT 20",
            q=name_or_code,
        )
        rows = [{"code": r["code"], "name": r["name"]} for r in result]
    driver.close()
    return rows
