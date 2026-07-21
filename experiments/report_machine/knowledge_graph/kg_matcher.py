"""
kg_matcher.py — 关键词→文章匹配算法

匹配规则：
  - 只使用行业 + 地区关键词（纯概念不参与）
  - 跨类别关键词（概念+行业，标记 boosted）匹配到计 2
  - 普通行业关键词匹配到计 1
  - 地区关键词匹配到计 1/3
  - effective_m = Σ(权重), score = min(1.0, effective_m / 4)
"""

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASS


def _get_matching_keywords(stock_code: str) -> list[dict]:
    """获取个股用于匹配的关键词（仅行业 + 地区，含 boosted 标记）

    Returns:
        [{keyword, assigned_weight}, ...]
        assigned_weight: 2(boosted跨类别) / 1(普通行业) / 0.33(地区)
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        result = session.run(
            """MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword)
               WHERE '行业' IN k.categories OR '地区' IN k.categories
               RETURN k.keyword AS keyword,
                      k.categories AS categories,
                      k.boosted AS boosted""",
            code=stock_code,
        )
        keywords = []
        for r in result:
            cats = r["categories"]
            boosted = r.get("boosted", False)

            if boosted:
                # 跨类别（概念+行业）→ 权重 2
                weight = 2.0
            elif "地区" in cats:
                # 纯地区 → 权重 1/3
                weight = 1.0 / 3.0
            else:
                # 普通行业 → 权重 1
                weight = 1.0

            keywords.append({
                "keyword": r["keyword"],
                "weight": weight,
            })

    driver.close()
    return keywords


def match_stock_to_article(
    stock_code: str,
    article: str,
) -> float:
    """计算单只股票与文章的匹配度

    Args:
        stock_code: 股票代码（如 "600519.SH"）
        article: 资讯文章全文

    Returns:
        float: 匹配度 0.0 ~ 1.0
    """
    keywords = _get_matching_keywords(stock_code)
    if not keywords:
        return 0.0

    effective_m = 0.0
    for kw in keywords:
        if kw["keyword"] in article:
            effective_m += kw["weight"]

    if effective_m <= 0:
        return 0.0

    return min(1.0, effective_m / 4.0)


def match_stocks_to_article(
    stock_codes: list[str],
    article: str,
    top_n: int | None = None,
) -> list[dict]:
    """批量匹配：多只股票对同一篇文章

    Args:
        stock_codes: 股票代码列表
        article: 资讯文章全文
        top_n: 只返回前 N 条，None 返回全部

    Returns:
        [{stock_code, score}, ...] 按分数降序
    """
    results = []
    for code in stock_codes:
        score = match_stock_to_article(code, article)
        if score > 0:
            results.append({"stock_code": code, "score": round(score, 4)})

    results.sort(key=lambda x: x["score"], reverse=True)
    if top_n:
        results = results[:top_n]
    return results


# ---- 快速 Demo ----

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        stock_code = sys.argv[1]
        article_text = sys.argv[2]
        score = match_stock_to_article(stock_code, article_text)
        print(f"stock={stock_code}, score={score:.4f}")
    else:
        print("用法: python kg_matcher.py <stock_code> '<article_text>'")
        print("示例: python kg_matcher.py 600519.SH '白酒行业今日表现强劲'")
