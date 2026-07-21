"""查询 Neo4j 中板块/换手率相关的 DataField — 分两类展示"""
import json, os, sys
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

# ── 搜索关键词 —— 分两组 ──
SECTOR_KW = ["板块", "sector", "board"]
TURNOVER_KW = ["换手率", "turnover"]


def build_condition(keywords):
    return " OR ".join(
        f"n.name CONTAINS '{kw}' OR n.description CONTAINS '{kw}' OR n.id CONTAINS '{kw}'"
        for kw in keywords
    )


def fetch_rows(conditions):
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
        return [record.data() for record in result]


def extract_alias_short(alias_raw):
    if isinstance(alias_raw, str):
        try:
            alias_raw = json.loads(alias_raw)
        except:
            alias_raw = {}
    simple = (alias_raw or {}).get("simple", [])[:3]
    return ", ".join(simple) if simple else ""


def make_table(rows):
    lines = [
        "| ID | 名称 | 说明 | 别名(简) | 粒度 | 单位 | 数据类型 | 数据源 | 协议 |",
        "|:--|:----|:-----|:---------|:----:|:----:|:--------|:------|:----:|",
    ]
    for r in rows:
        alias_short = extract_alias_short(r.get("alias"))
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
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# ── 分两组查询 ──
sector_rows = fetch_rows(build_condition(SECTOR_KW))
turnover_rows = fetch_rows(build_condition(TURNOVER_KW))

driver.close()

# ── 去重：同一条 field 可能同时匹配两类 —— 按 id 去重 ──
def dedup_by_id(rows):
    seen = set()
    out = []
    for r in rows:
        rid = r.get("id")
        if rid not in seen:
            seen.add(rid)
            out.append(r)
    return out

sector_rows = dedup_by_id(sector_rows)
turnover_rows = dedup_by_id(turnover_rows)

# ── 生成 Markdown ──
md = "# DataField 查询结果\n\n"

# --- 板块相关 ---
md += f"## 📊 板块相关\n\n"
md += f"关键词: `{'`, `'.join(SECTOR_KW)}`  →  共 {len(sector_rows)} 个\n\n"
if sector_rows:
    md += make_table(sector_rows)
else:
    md += "*未匹配到结果*\n"
md += "\n\n"

# --- 换手率相关 ---
md += f"## 🔄 换手率相关\n\n"
md += f"关键词: `{'`, `'.join(TURNOVER_KW)}`  →  共 {len(turnover_rows)} 个\n\n"
if turnover_rows:
    md += make_table(turnover_rows)
else:
    md += "*未匹配到结果*\n"
md += "\n\n"

# --- 全部（去重汇总）---
all_rows = {r.get("id"): r for r in sector_rows}
for r in turnover_rows:
    all_rows.setdefault(r.get("id"), r)
all_rows = list(all_rows.values())

md += f"---\n"
md += f"## 📋 汇总（去重）\n\n"
md += f"板块 {len(sector_rows)} 个 + 换手率 {len(turnover_rows)} 个 = **{len(all_rows)}** 个唯一 DataField\n\n"
md += make_table(all_rows)
md += "\n\n"

# --- 交集 ---
sector_ids = {r.get("id") for r in sector_rows}
turnover_ids = {r.get("id") for r in turnover_rows}
intersection = sector_ids & turnover_ids
if intersection:
    md += f"### 🔗 同时匹配两类关键词（交集）\n\n"
    for rid in intersection:
        r = next(rr for rr in all_rows if rr.get("id") == rid)
        md += f"- `{r.get('id')}` — {r.get('name')}\n"
    md += "\n\n"

md += f"*查询时间: 2026-07-17*"

out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "datafield_sector_turnover.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(md)

print(md)
print(f"\n✅ 已保存: {out_path}")
