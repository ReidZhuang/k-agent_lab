# 数据源接入标准作业流程

## 概述

本文档定义了将新数据源接入知识图谱的全流程标准步骤。每次增量接入必须按此流程执行，确保一致性和可追溯性。

---

## Step 1: 需求评估

**输入**: 新数据源名称、API 文档

**检查清单**:
- [ ] 该数据源的字段是否已存在于现有 KG 中？
- [ ] 如果已存在，粒度是否相同？记录在 `description` 中
- [ ] 如果粒度不同，不可替代，必须新增
- [ ] 如果完全相同，标记为备选源，`reliability_score` 设较低值

**输出**: 接入决策（新增/备选/跳过）+ 理由

---

## Step 2: 连通性验证

**检查清单**:
- [ ] SDK/API 是否可安装/调用？
- [ ] 是否需要 Token/密钥？如何获取？
- [ ] 调用是否会超时或报错？
- [ ] 响应时间是否在可接受范围内？

**注意**: 必须重复验证 3 次以上，排除临时故障

**输出**: 连通性报告

---

## Step 3: 字段映射

**检查清单**:
- [ ] 调用 API 获取返回的**实际列名**（`print(df.columns.tolist())`）
- [ ] 不要凭文档或记忆写列名，也不要猜
- [ ] {标准名称(中文)} → {API 列名} 逐条映射
- [ ] 逐列与现有 DataField 对比，确认无重复

**输出**: 字段映射表

---

## Step 4: 写入 Neo4j DataSource 节点

```cypher
CREATE (ds:DataSource {
  id: $id,
  name: $name,
  protocol: $protocol,         // tushare/akshare/levistock/sina/tencent/xueqiu/web_search
  authority_level: $al,         // S/A/B/C
  refresh_time: $rt,            // realtime/intraday/daily_17:00/quarterly
  reliability_score: $rs,       // 0.0~1.0
  prompt_dir: $pd               // ds_prompts/DS_XXX/
})
```

**检查清单**:
- [ ] id 命名规范: `DS_{数据源缩写}_{功能}` (全大写，下划线分隔)
- [ ] protocol 必须在已支持的列表中
- [ ] prompt_dir 指向后续要创建的 ds_prompts 目录

---

## Step 5: 创建 ds_prompts 文件

每个 DataSource 必须创建 3 个文件：

```
ds_prompts/DS_XXX/
  field.md      # 可用字段表
  table.md      # 表/接口结构说明
  api.md        # API 调用规则 + 代码示例
```

**`field.md`**: 字段名必须是 API 返回的**实际列名**，不是中文名
**`table.md`**: 写清楚函数签名、参数、限制
**`api.md`**: 必须包含可运行的 Python 示例，Token 通过 `os.getenv()` 读取

**检查清单**:
- [ ] field.md 的字段名与 Step 3 的实际列名一致
- [ ] api.md 中的示例代码可以原样执行
- [ ] Token 不要硬编码

---

## Step 6: 创建 DataField 节点

在 Neo4j 中为每个字段创建 DataField 节点：

```python
CREATE (f:DataField {
  id: $id,                    // FIELD_{功能}_{字段名} (全大写)
  standard_name: $sn,         // 中文标准名
  alias: $alias,              // JSON 数组
  data_type: $dt,             // float/int/string/date/boolean
  unit: $unit,
  api_column: $col,           // Step 3 验证的实际 API 列名
  default_datasource_id: $ds,
  description: $desc          // 含数据粒度说明，如"全市场/板块/按日/按季"
})
```

**检查清单**:
- [ ] **api_column 必须从 API 实际调用获得**，禁止凭记忆填写
- [ ] description 中记录数据粒度（全市场/板块/个股、按年/按季/按月/按日）
- [ ] 创建 HAS_DATASOURCE 关系到对应的 DataSource
- [ ] 创建 BELONGS_TO_CONCEPT 关系到对应的 IntentConcept

---

## Step 7: 写入 alias CSV

追加到 `datafield_new_alias_all.txt`：

| field_id | standard_name | concept_id | simple | qualified | business_tag | synonyms |
|----------|---------------|------------|--------|-----------|--------------|----------|

**alias 编写规则**:
- `simple`: 最简中文名，日常口语
- `qualified`: 带限定词的全称（**必须唯一，防止冲突**）
- `business_tag`: 业务意义标签，助 LLM 理解
- `synonyms`: 近义词，至少 3 个，**不要包含 simple**

**检查清单**:
- [ ] simple 不与现有 alias 冲突
- [ ] qualified 不与现有 alias 冲突
- [ ] synonyms 不含 simple 自身
- [ ] 如有冲突，加限定前缀（如"新浪买1价" vs 现有"买1价"）

---

## Step 8: 生成 Embedding

```python
model = Llama(model_path=MODEL, n_gpu_layers=-1, embedding=True)
for each new field:
    emb = model.embed(standard_name + " " + aliases + " " + description)
    save to Neo4j f.embedding = emb
```

**检查清单**:
- [ ] 所有新字段的 embedding 已写入 Neo4j
- [ ] Faiss 索引已重建（包含新字段）

---

## Step 9: 全量审计

运行 `scripts/audit_full.py`，确认：
- [ ] 节点数正确
- [ ] 关系数正确
- [ ] 路由功能正常
- [ ] alias 无冲突
- [ ] Faiss 索引包含新字段

---

## Step 10: 更新开发日志

在 `dev_log.md` 中记录：
- 新增内容（DataSource/DataField 数量）
- 变更内容（alias 修改等）
- 遇到的问题和解决方案

---

## 已知踩坑记录（避免重犯）

| # | 坑 | 后果 | 正确做法 |
|---|-----|------|---------|
| 1 | 凭记忆写 api_column | 列名写错，LLM 代码执行失败 | 必须真实调用 API 获取列名 |
| 2 | 批量映射时不验证每个字段 | 543 个字段中有 3 个错误 | 逐一验证，最好写脚本自动检查 |
| 3 | alias 用 1:1 映射 | 冲突字段被后者覆盖 | 用多值映射 (list[str]) |
| 4 | 不检查新 qualified 是否与现有冲突 | 消歧失效 | 添加前 grep 现有 alias |
| 5 | synonyms 包含 simple 自身 | 去重后不足 3 个 | 写入前过滤 |
| 6 | 一次修改太多不测试 | 出错后难以定位 | 每步改完立刻测试 |
| 7 | description 不写粒度 | 无法区分同字段不同粒度 | 写明"全市场/板块/个股"、"按季/按月/按日" |
