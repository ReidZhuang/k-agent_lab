# 用户指标匹配不到理想字段的排查流程

> 本文档是知识图谱审计清单的第三部分，独立拆分出来方便查阅。

## 场景

用户输入的 var（如"股价"）经过双检索（关键字+embedding）后，LLM 选出的 field_id 在语义上不理想。

## 排查步骤

### Step 1：确认路由候选

查看 `hybrid_query()` 返回的候选字段列表，看理想字段是否在候选列表中：

```python
from query_agent_api.core.route_tool import get_route_tool
import json
t = get_route_tool()
candidates = t.hybrid_query(["股价"])
for c in candidates:
    print(c["id"], c["name"], c["match"], c["scope"])
```

两种情况：
- **在列表中但 LLM 没选** → prompt 工程问题（在 AGENTS.md 中加强筛选规则）
- **不在列表中** → 进行 Step 2

### Step 2：检查 Embedding 覆盖

单独看 embedding 检索是否能找到理想字段：

```python
from irkg.embedding import EmbeddingRetriever
er = EmbeddingRetriever()
vec = er.embed_query("股价")
results = er.search_fields(vec, top_k=10)
for r in results:
    print(r["id"], r["score"])
```

- **能找到** → 关键字匹配阶段排除的，检查 alias 数据
- **找不到** → 进行 Step 3

### Step 3：检查 Embedding 文本

查 Neo4j 中该字段的 alias，确认拼接文本包含足够语义：

```cypher
MATCH (f:DataField {id: 'FIELD_KLINE_CLOSE'})
RETURN f.id, f.standard_name, f.alias, f.description
```

在 Python 中模拟拼接逻辑：

```python
import json
alias_data = json.loads(node["alias"] or "{}")
all_values = []
for level, values in alias_data.items():
    if isinstance(values, list):
        all_values.extend(values)
text = f"{standard_name} {' '.join(all_values)} {description}"
print(text)  # 看是否包含用户输入的同义关键词
```

**语义词不足** → 在 alias 中添加合适的同义词（Step 4）

### Step 4：添加缺失的别名

```python
from neo4j import GraphDatabase
import json

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kg_route_2026"))
with driver.session() as s:
    # 查当前别名
    r = s.run("MATCH (f:DataField {id: 'FIELD_KLINE_CLOSE'}) RETURN f.alias AS alias").single()
    alias = json.loads(r["alias"]) if isinstance(r["alias"], str) else (r["alias"] or {})
    
    # 添加同义词
    syn = alias.get("synonyms", [])
    if "股价" not in syn:
        syn.append("股价")
    alias["synonyms"] = syn
    
    # 写回
    s.run("MATCH (f:DataField {id: $id}) SET f.alias = $alias",
          id="FIELD_KLINE_CLOSE", alias=json.dumps(alias, ensure_ascii=False))
```

### Step 5：重生成 Embedding + 验证

```bash
# 重跑 embedding（GPU）
python3 scripts/generate_embeddings.py

# 验证
python3 scripts/audit_full.py
python3 query_agent_api/test_agent_router.py
```

---

## 配合使用的命令速查

```bash
# 1. 查路由候选
cd /home/stockagent/project_space/research/experiments/knowledge_graph
python3 -c "from query_agent_api.core.route_tool import get_route_tool; t=get_route_tool(); import json; print(json.dumps(t.hybrid_query(['股价']), ensure_ascii=False, indent=2))"

# 2. 查 embedding 检索
python3 -c "from irkg.embedding import EmbeddingRetriever; er=EmbeddingRetriever(); vec=er.embed_query('股价'); results=er.search_fields(vec, top_k=10); [print(r['id'], r['score']) for r in results]"

# 3. 查字段属性
python3 -c "from neo4j import GraphDatabase; import json; d=GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','kg_route_2026')); r=d.session().run('MATCH (f:DataField {id:\\\"FIELD_KLINE_CLOSE\\\"}) RETURN f').single(); f=r['f']; print(json.dumps(dict(f), ensure_ascii=False, default=str))"

# 4. 重做 embedding
python3 scripts/generate_embeddings.py

# 5. 验证测试
cd /home/stockagent/project_space/research/experiments/knowledge_graph/scripts && python3 audit_full.py
cd /home/stockagent/project_space/research/experiments/knowledge_graph && python3 query_agent_api/test_agent_router.py
```
