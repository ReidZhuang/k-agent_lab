# 知识图谱审计清单

## 审计范围

审计覆盖 `audit_full.py` 中的所有检查项，以及人工复查流程。

---

## 一、自动化审计（audit_full.py）

### 1. 节点完整性
- IntentConcept 数量 = 41
- DataSource 数量 ≥ 71
- DataField 数量 ≥ 520
- 所有 Field 有 embedding、granularity、api_column、data_type、unit

### 2. 关系完整性
- HAS_DATASOURCE 关系数 ≥ DataField 数
- BELONGS_TO_CONCEPT 关系数 ≥ DataField 数
- SEMANTIC_SIMILAR_TO 关系数 ≥ 3700
- 新增字段的 Concept 分配正确（如 Sina Finance → CONCEPT_FINANCIAL_STATEMENTS）

### 3. DataSource 质量
- 所有 DS 有 table_name
- 无孤岛 DataSource（没有被任何 Field 引用的 DS）

### 4. 路由功能
- 关键 alias 能正确路由（毛利率、指数涨跌幅、PE_TTM 等）
- 新字段能路由（同花顺概念、高管姓名、回购金额等）
- 路由能匹配到正确 Concept

### 5. 协议覆盖
- 所有已注册协议都存在：tushare, akshare, levistock, sina, tencent, xueqiu, web_search, llm_gen, local_calc, html_scrape

### 5b. 同数据源内重复字段
- 同 standard_name + 同数据源的字段
- 已配主备关系的视为合理，未配的报出

### 5c. 疑似重复字段（api_column + 数据源）
- 同 api_column + 同数据源的字段分组
- 检出后写入文档供人工判断
- 人工判断流程见下文"二"

### 6. Faiss
- Faiss 索引数量与 ID 文件一致

### 6b. api_column 一致性
- 非 html_scrape/akshare 协议不应有中文 api_column
- 不应有 `col_N` 格式的自动编号 api_column

### 7. ds_prompts
- 至少 12 个数据源有 ds_prompts 文档

### 8. SQL 提示 / 9. 场景验证
- 关键场景的路由能返回字段

---

## 二、疑似重复字段的人工判断流程

当审计 5c 报出"同 api_column + 同数据源"的字段组时，按以下流程判断：

### 步骤 1：查数据源文档

确认该数据源的实际表结构：

- **Tushare**：查 `web_search_base/knowledge/tushare/description.md` 中的 API 文档，或直接调用 `pro.xxx(limit=1)` 获取列名
- **Akshare**：查 `web_search_base/knowledge/akshare/` 下的文档，或调用 `ak.xxx()` 获取列名
- **Sina Finance**：查 `web_search_base/knowledge/sina_finance/` 下的文档
- **其他数据源**：查对应知识文档或调用接口

### 步骤 2：对比实际列名

```python
# Tushare 示例：获取真实 API 列名
df = pro.daily_basic(ts_code='000001.SZ', trade_date='20260715', limit=1)
print(list(df.columns))
# → ['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', ...]
```

对比 Neo4j 中的 `api_column` 是否与实际列名一致。

### 步骤 3：判断类别

| 发现 | 结论 | 处理 |
|------|------|------|
| 多个字段指向同一 API 列且语义相同 | **真重复** | 删一个，保留 usable 的那个 |
| 多个字段指向同一 API 列但语义不同（如 roe_dt=摊薄ROE vs 扣非ROE） | **至少一个是录入错误** | 修正 api_column 或删除不存在字段 |
| 字段指向的 API 列在真实接口中不存在 | **该字段不存在** | 删除 |
| 字段指向的 api_column 值错误 | **录入错误** | 修正为正确的 api_column |
| 同一宽表中不同字段巧合共享列名（如可转债 pct_chg） | **不是重复** | 不处理，字段本身语义不同 |

### 步骤 4：执行修正

```cypher
// 删除字段（自动清理所有关系）
MATCH (f:DataField {id: 'FIELD_XXX'}) DETACH DELETE f

// 修正 api_column
MATCH (f:DataField {id: 'FIELD_XXX'})
SET f.api_column = '正确的列名'
```

### 步骤 5：重生成 Embedding

删除/修正后，必须重跑 embedding：
```bash
python3 scripts/generate_embeddings.py
```

### 步骤 6：验证

```bash
python3 scripts/audit_full.py          # 审计通过
python3 query_agent_api/test_agent_router.py  # 路由测试通过
```

---

---

> **指标匹配排查流程** 已拆分为独立文档：[field_mismatch_troubleshooting.md](field_mismatch_troubleshooting.md)
