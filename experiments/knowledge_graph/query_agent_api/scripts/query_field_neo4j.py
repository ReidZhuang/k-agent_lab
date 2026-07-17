"""查询 Neo4j 中板块/换手率相关的 DataField"""
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from neo4j import GraphDatabase
except ImportError:
    print("❌ neo4j driver not installed")
    sys.exit(1)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "kg_route_2026")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# ── 搜索关键词 ──
KEYWORDS = ["板块", "换手率", "sector", "turnover", "board"]

# 构建匹配条件：name 或 description 或 id 包含任一关键词
conditions = " OR ".join(
    f"n.name CONTAINS '{kw}' OR n.description CONTAINS '{kw}' OR n.id CONTAINS '{kw}'"
    for kw in KEYWORDS
)

query = f"""
MATCH (n:DataField)
WHERE {conditions}
OPTIONAL MATCH (n)-[r:HAS_DATASOURCE]->(ds:DataSource)
WITH n, ds, r
ORDER BY n.name
RETURN n.id AS id, n.name AS name, n.description AS description,
       n.alias AS alias, n.granularity AS granularity,
       n.unit AS unit, n.data_type AS data_type,
       n.standard_name AS standard_name,
       n.authority_level AS authority_level,
       n.has_backup AS has_backup,
       n.default_datasource_id AS default_ds,
       n.refresh_time AS refresh_time,
       ds.id AS datasource_id, ds.protocol AS protocol,
       ds.name AS datasource_name
"""

with driver.session() as session:
    result = session.run(query)
    rows = [record.data() for record in result]

driver.close()

# ── 输出 ──
if not rows:
    print("未找到匹配的 DataField")
    sys.exit(0)

print(f"找到 {len(rows)} 个 DataField\n")

COLUMNS = ["id", "name", "description", "alias", "granularity", "unit", "data_type", "datasource_id", "protocol"]

# markdown
md = "# 板块 / 换手率 相关 DataField\n\n"
md += f"**搜索关键词**: {', '.join(KEYWORDS)}\n\n"
md += f"**匹配结果**: {len(rows)} 个\n\n"

md += "| ID | 名称 | 说明 | 别名(简) | 粒度 | 单位 | 数据类型 | 数据源 | 协议 |\n"
md += "|:--|:----|:-----|:---------|:----:|:----:|:--------|:------|:----:|\n"

for r in rows:
    alias_raw = r.get("alias") or {}
    if isinstance(alias_raw, str):
        try:
            import json
            alias_raw = json.loads(alias_raw)
        except:
            alias_raw = {}
    # 提取简单别名前3个
    simple_aliases = alias_raw.get("simple", [])[:3]
    alias_short = ", ".join(simple_aliases) if simple_aliases else ""

    vals = [
        str(r.get("id") or ""),
        str(r.get("name") or ""),
        str(r.get("description") or "")[:80],
        alias_short[:50],
        str(r.get("granularity") or ""),
        str(r.get("unit") or ""),
        str(r.get("data_type") or ""),
        str(r.get("datasource_id") or r.get("default_ds") or ""),
        str(r.get("protocol") or ""),
    ]
    md += "| " + " | ".join(vals) + " |\n"

md += f"\n\n---\n\n*查询时间: 2026-07-17*"

out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "datafield_sector_turnover.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(md)

print(md)
print(f"\n✅ 已保存: {out_path}")
