# 知识图谱质量审计流程

## 审计维度

| 维度 | 检查内容 |
|:---|:---|
| 1. 节点唯一性 | ID 唯一、standard_name 无歧义 |
| 2. 节点完整性 | 必需属性已填写、embedding 存在 |
| 3. Alias 质量 | 4 级无冲突、synonyms>=3 |
| 4. 关系完整性 | HAS_DATASOURCE/BELONGS_TO_CONCEPT 存在 |
| 5. Concept 归属 | 每个 Field 有 Concept |
| 6. DataSource 质量 | protocol/table_name/prompt_dir 完整 |
| 7. 数据粒度 | description 包含粒度说明 |
| 8. 语义关系 | SEMANTIC_SIMILAR_TO 合理 |
| 9. 功能审计 | 路由测试全部通过 |

## 审计步骤

### Step 1: 节点唯一性
```
MATCH (f:DataField) WITH f.id AS id, count(*) AS cnt WHERE cnt > 1 RETURN id
MATCH (ds:DataSource) WITH ds.id AS id, count(*) AS cnt WHERE cnt > 1 RETURN id
```

### Step 2: 节点完整性
```
MATCH (f:DataField) WHERE f.api_column IS NULL RETURN f.id
MATCH (ds:DataSource) WHERE ds.table_name IS NULL RETURN ds.id
MATCH (f:DataField) WHERE f.embedding IS NULL RETURN f.id
```

### Step 3: Alias 质量
解析 datafield_new_alias_all.txt：
- qualified 必须全局唯一，否则加限定前缀
- synonyms 每行 >= 3 个去重后
- synonyms 不含 simple 自身
- 与现有 alias 无冲突

### Step 4: 关系完整性
```
MATCH (f:DataField) WHERE NOT (f)-[:HAS_DATASOURCE]->() RETURN f.id
MATCH (f:DataField) WHERE NOT (f)-[:BELONGS_TO_CONCEPT]->() RETURN f.id
```

### Step 5: Concept 归属
- 每个 Concept 下至少有一个 Field
- 新增 Field 是否需要新建 Concept？
  - 全新分析维度 + 无法归入现有 41 个 Concept 时才新建

### Step 6: DataSource 质量
- 每个 DS 有 table_name（对应真实 API 函数名）
- protocol 在合法列表中
- ds_prompts 目录下有文件
- 无孤岛 DataSource

### Step 7: 数据粒度
description 应包含：
- 时间粒度：年/季/月/日/分钟/实时
- 范围粒度：全市场/板块/个股/概念

### Step 8: 语义关系
- SEMANTIC_SIMILAR_TO 无孤立节点
- high/medium/low 分布合理

### Step 9: 功能审计
运行 python3 scripts/audit_full.py

---

## Step 10: API 字段名一致性审计（新增）

### 背景
之前发生过多次 api_column 凭记忆填写导致与真实 API 返回列名不匹配的问题。

### 检查项
- [ ] 每个 DataField 的 api_column 是否在对应 DataSource 的 API 真实返回中存在？
- [ ] 新增 API 字段时必须通过 `print(df.columns.tolist())` 验证

### 方法
```python
# 1. 调用 API 获取实际列名
df = pro.fina_indicator(ts_code='300750.SZ', ...)
actual_cols = set(df.columns)

# 2. 获取该 DS 下所有字段的 api_column
# 3. 检查每个 api_column 是否在 actual_cols 中
```

### 已知问题记录
| 字段 | 原 api_column | 实际值 | 原因 |
|:---|:---|:---|:---|
| FIELD_LIMIT_FIRST_TIME | first_zt_time | first_time | 按 levistock 记忆填写 |
| FIELD_LIMIT_LAST_TIME | last_zt_time | last_time | 同上 |
| FIELD_LIMIT_CONTINUOUS | continuous | limit_times | 同上 |

### 预防规则
1. **禁止**凭记忆填写 api_column
2. **必须**调用 API 获取 `df.columns.tolist()` 后逐条映射
3. **增量接入时**必须在该 DS 的 API 调用结果中验证每个新字段的 api_column

## Step 11: 主备关系审计（新增）

### 检查项
- [ ] 每个 DataField 是否有必要的主备关系？
- [ ] 备用 DataSource 的 api_column 是否与主源一致（或已正确标注）？
- [ ] 主备之间的 unit 是否需要转换？
- [ ] 是否存在遗漏的主备关系（即同一业务含义的字段来自不同源）

### 判断标准
```
主备关系建立条件:
  1. 两个 DataSource 提供同业务含义字段
  2. 主源和备源在同一 Concept 维度上
  3. 已在 config/backup_weights.json 中配置权重

不建立条件:
  1. 虽然字段名相同，但属于不同 Concept（不可互换）
  2. 备源字段覆盖不足 70%
```

### 方法
```cypher
// 查所有没有备份关系的 Field
MATCH (f:DataField)-[:HAS_DATASOURCE]->(ds:DataSource)
WHERE NOT (f)-[:HAS_BACKUP_DATASOURCE]->()
RETURN f.id, ds.id

// 查可能的遗漏: 同一 Concept 下存在多个同语义 DataSource
MATCH (c:IntentConcept)<-[:BELONGS_TO_CONCEPT]-(f:DataField)-[:HAS_DATASOURCE]->(ds:DataSource)
WITH c, f, ds
// 按 Concept 分组看是否有同语义的多源覆盖
```

## Step 12: 主备策略审计

### 检查项
- [ ] backup_weights.json 中的权重配置是否合理
- [ ] 备用源的可靠性/权威性/时效性评分是否最新
- [ ] 执行器降级日志是否正常
