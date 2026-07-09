# IRKG v3 知识图谱设计方案（最终版）


## 一、设计哲学

### 1.1 核心定位

```
用户问题 → LLM（大脑） → 知识图谱（路由） → 数据源 → 数据 → LLM分析 → 回答
```

知识图谱不存储金融知识，只存储 **“从信息需求到数据获取路径”** 的路由表。它是连接 LLM 大脑与数据世界的桥梁。

### 1.2 设计原则

| 原则 | 说明 |
| :--- | :--- |
| **字段优先路由** | 路由起点是具体数据字段，而非业务场景，避免二义性 |
| **向量驱动近邻** | 字段间关系由 Embedding 相似度自动计算，零人工维护 |
| **节点精简极致** | 仅 3 种核心节点：IntentConcept、DataField、DataSource |
| **关系带属性** | 关系承载级别、权重等量化属性，支持动态查询裁剪 |
| **多源可备选** | 同一字段可来自多个 DataSource，按时效性/权威性自动取舍 |


## 二、节点设计（3 种核心类型）

### 2.1 节点总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户问题                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 1: IntentConcept】业务场景分类器                      │
│  作用：当用户问题模糊时，定位默认数据套餐                      │
│  属性：id, name, description, embedding, requires_entity,      │
│        default_seed_fields                                     │
│  示例：盈利能力分析、估值分析、资金流向分析                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 2: DataField】最小数据原子单元 ★核心节点★            │
│  作用：代表一个具体可返回的数据列，是路由的真正终点            │
│  属性：id, standard_name, alias[], description, embedding,     │
│        default_datasource_id, belongs_to_concepts[],           │
│        data_type, unit, authority_level, refresh_time          │
│  示例：净利润、毛利率、ROE、北向资金净流入                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 3: DataSource】物理取数指令                           │
│  作用：封装调用接口/爬虫的全部技术细节                        │
│  属性：id, name, protocol, execution_meta, refresh_time,       │
│        authority_level, reliability_score, latency_ms,         │
│        code_format                                            │
│  示例：akshare.stock_financial_abstract, 巨潮资讯网爬虫      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 IntentConcept（意图概念节点）

**身份定义**：用户问题的高层次分类标签，是图谱的“模糊路由入口”。

**适用场景**：当用户问题中**没有提及任何具体指标名称**时（如“分析一下宁德时代”），由 IntentConcept 决定默认返回哪一组数据。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识，如 `CONCEPT_PROFITABILITY` |
| `name` | string | ✅ | 业务标准名称，如 `盈利能力分析` |
| `description` | text | ✅ | 详细描述，用于生成 Embedding 和向 LLM 解释 |
| `embedding` | float[] | ✅ | 由 name + description 生成的 768 维向量，用于语义匹配 |
| `requires_entity` | string[] | ❌ | 必需的实体参数列表，如 `["stock_code"]` |
| `default_seed_fields` | string[] | ✅ | 该概念默认推荐的 3~5 个核心字段 ID，用于初始化扩散 |

**界定标准**（满足以下 2 条即可）：

| 标准 | 说明 |
| :--- | :--- |
| **独立分析视角** | 该概念代表一种独立的分析维度（如盈利、估值、资金） |
| **关键词可收敛** | 3~5 个核心词即可让 LLM 准确识别 |
| **字段可聚合** | 该概念下能找到 3~10 个核心字段组成默认套餐 |

### 2.3 DataField（数据字段节点）★核心节点★

**身份定义**：最小的、不可再分的数据信息单元。这是图谱中最重要的节点，所有路由最终都收敛到它。

**关键约束**：
- 每个 `DataField` 必须且只能指向一个 **默认 DataSource**（通过 `default_datasource_id`）
- 同一个逻辑字段（如“净利润”）若来自不同数据源，必须创建多个 `DataField` 节点（如 `净利润(财报)` 和 `净利润(快报)`），以便根据时效性/权威度做取舍
- 多个 `DataField` 可通过 `SEMANTIC_SIMILAR_TO` 关系互连

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识，如 `FIELD_NET_PROFIT` |
| `standard_name` | string | ✅ | 规范列名，与 DataSource 返回的列名完全一致 |
| `alias` | string[] | ✅ | 同义词数组，用于精确匹配用户口语，如 `["净利润", "净利", "net profit"]` |
| `description` | text | ✅ | 字段含义描述，用于 Embedding 生成和 LLM 理解 |
| `embedding` | float[] | ✅ | 由 standard_name + alias + description 生成的向量 |
| `default_datasource_id` | string | ✅ | 默认取数来源的 DataSource ID |
| `belongs_to_concepts` | string[] | ❌ | 所属的 IntentConcept ID 列表（多对多） |
| `data_type` | enum | ❌ | 数据类型：float / int / string / date |
| `unit` | string | ❌ | 单位，如 `%`、`亿元`、`倍` |
| **`authority_level`** | enum | ✅ | **该字段的权威等级**：`S`（法定披露）、`A`（权威门户）、`B`（普通门户）、`C`（社区）。通常继承自默认 DataSource，但可单独覆写 |
| **`refresh_time`** | enum | ✅ | **该字段的更新时效**：`realtime` / `intraday` / `daily_17:00` / `daily_20:00` / `weekly` / `quarterly`。通常继承自默认 DataSource，但可单独覆写 |

> **关于 authority_level 和 refresh_time 的继承规则**：
> - 创建 DataField 时，若未显式指定这两个属性，则自动从 `default_datasource_id` 指向的 DataSource 节点继承
> - 若显式指定，则以 DataField 自身的属性为准，覆盖 DataSource 的值
> - **设计意图**：同一数据源的不同字段，理论上具有相同的时效和权威性；但特殊情况下（如某个字段是衍生计算值），允许单独覆写

### 2.4 DataSource（数据源节点）

**身份定义**：封装获取数据的技术执行指令。它是图谱的物理执行末端。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识，如 `DS_AK_FIN_ABS` |
| `name` | string | ✅ | 数据源名称，如 `akshare财务摘要接口` |
| `protocol` | enum | ✅ | 协议类型：`akshare` / `requests` / `sqlalchemy` / `selenium` |
| `execution_meta` | json | ✅ | 执行元数据。akshare 存函数名+参数模板；requests 存 URL+请求方式 |
| `refresh_time` | enum | ✅ | 更新时效：`realtime` / `intraday` / `daily_17:00` / `daily_20:00` / `weekly` / `quarterly` |
| `authority_level` | enum | ✅ | 权威等级：`S`（法定披露）、`A`（权威门户）、`B`（普通门户）、`C`（社区） |
| `reliability_score` | float | ✅ | 综合可靠度 0~1，用于多源排序 |
| `latency_ms` | int | ❌ | 预估响应毫秒数，用于超时控制 |
| `code_format` | string | ❌ | 参数格式化规则，如 `SZ_prefix` / `SH_prefix` / `pure_num` |


## 三、关系设计（2 种核心关系）

### 3.1 SEMANTIC_SIMILAR_TO（语义近邻关系）

**方向**：`DataField` → `DataField`（双向）

**含义**：两个字段在向量空间中语义相似度高（余弦相似度 ≥ 阈值），构成近邻关系。

**这是图谱中最核心的关系**，它替代了传统人工维护的 FieldGroup，实现自动化、动态的字段聚合。

**关系属性**：

| 属性名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `cosine_similarity` | float | 余弦相似度原始值（0~1），用于精确排序 |
| `level` | enum | 相似度档位：`high` / `medium` / `low`，由阈值自动判定 |
| `is_direct` | boolean | 是否为直接计算的关系（非通过中间节点传递） |

**阈值分级标准**：

| 级别 | 阈值范围 | 含义 | 典型示例 |
| :--- | :--- | :--- | :--- |
| **high** | ≥ 0.85 | 高度同义或极强关联，可互换使用 | 净利润 ↔ 归母净利润 |
| **medium** | 0.75 ~ 0.85 | 紧密语义邻居，分析时最常搭配 | 净利润 ↔ 营业收入 ↔ 毛利率 |
| **low** | 0.65 ~ 0.75 | 有一定关联，可作补充参考 | 净利润 ↔ EPS（每股收益） |

**建边策略**：
1. 计算所有 `DataField` 两两之间的余弦相似度
2. 对每个字段，仅保留相似度 ≥ 0.65 的邻居
3. 仅当相似度 ≥ 0.75 时，在图谱中创建 `SEMANTIC_SIMILAR_TO` 关系
4. 相似度在 0.65~0.75 之间的，仅记录原始值但不创建关系（或创建但标记为 `low`）

### 3.2 BELONGS_TO_CONCEPT（从属概念关系）

**方向**：`DataField` → `IntentConcept`（多对多）

**含义**：该字段可被用于某个业务场景的分析。

**关系属性**：

| 属性名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `relevance_score` | float | 该字段对该概念的重要性（0~1），如“净利润”对“盈利能力”为 1.0 |
| `is_default` | boolean | 是否为该概念的默认推荐字段 |

**建边策略**：由领域专家在建库时一次性配置，后续新增字段时由管理员挂载。


## 四、完整数据示例

以下用 JSON 展示一个完整的图谱数据实例。

### 4.1 IntentConcept 节点

```json
{
  "id": "CONCEPT_PROFITABILITY",
  "name": "盈利能力分析",
  "description": "分析公司的盈利状况，包括营收、毛利、净利、利润率、ROE等核心指标",
  "requires_entity": ["stock_code"],
  "default_seed_fields": ["FIELD_REVENUE", "FIELD_GROSS_PROFIT", "FIELD_NET_PROFIT", "FIELD_ROE"]
}
```

### 4.2 DataField 节点

```json
{
  "id": "FIELD_NET_PROFIT",
  "standard_name": "归母净利润",
  "alias": ["净利润", "净利", "利润", "net profit", "归属母公司股东的净利润"],
  "description": "归属于上市公司股东的净利润，反映公司最终盈利水平",
  "default_datasource_id": "DS_AK_FIN_ABS",
  "belongs_to_concepts": ["CONCEPT_PROFITABILITY", "CONCEPT_GROWTH"],
  "data_type": "float",
  "unit": "亿元",
  "authority_level": "A",
  "refresh_time": "quarterly"
}
```

```json
{
  "id": "FIELD_GROSS_PROFIT",
  "standard_name": "毛利率",
  "alias": ["毛利润", "毛利", "gross margin", "毛利率"],
  "description": "营业收入扣除营业成本后的利润占营业收入的比例",
  "default_datasource_id": "DS_AK_FIN_ABS",
  "belongs_to_concepts": ["CONCEPT_PROFITABILITY"],
  "data_type": "float",
  "unit": "%",
  "authority_level": "A",
  "refresh_time": "quarterly"
}
```

### 4.3 DataSource 节点

```json
{
  "id": "DS_AK_FIN_ABS",
  "name": "akshare 财务摘要接口",
  "protocol": "akshare",
  "execution_meta": {
    "function": "stock_financial_abstract",
    "param_template": {"symbol": "{stock_code}"}
  },
  "refresh_time": "quarterly",
  "authority_level": "A",
  "reliability_score": 0.92,
  "latency_ms": 300,
  "code_format": "pure_num"
}
```

### 4.4 SEMANTIC_SIMILAR_TO 关系

```json
{
  "from": "FIELD_NET_PROFIT",
  "to": "FIELD_GROSS_PROFIT",
  "type": "SEMANTIC_SIMILAR_TO",
  "properties": {
    "cosine_similarity": 0.82,
    "level": "medium"
  }
}
```


## 五、工作流程图

### 5.1 整体架构流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             用户输入问题                                     │
│                    "宁德时代2025年净利润表现如何？"                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【LLM 解析层】                                      │
│  1. 提取目标指标词 → "净利润"                                               │
│  2. 提取实体参数 → stock_code: "300750", year: "2025"                     │
│  3. 判断意图类型 → "analysis" (需要上下文) / "fact" (仅需单值)             │
│                                                                             │
│  输出 JSON:                                                                 │
│  {                                                                          │
│    "target_metrics": ["净利润"],                                            │
│    "entities": {"stock_code": "300750"},                                   │
│    "intent_type": "analysis"                                               │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【知识图谱路由层】                                   │
│                                                                             │
│  Step 1: 精准寻的                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  用 "净利润" 匹配 DataField.alias 数组                               │   │
│  │  → 命中 FIELD_NET_PROFIT                                            │   │
│  │  （若未命中，用 Embedding 做向量 Top-K 检索）                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  Step 2: 近邻扩散（仅当 intent_type == "analysis"）                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  从 FIELD_NET_PROFIT 出发，沿 SEMANTIC_SIMILAR_TO 关系扩散          │   │
│  │  取 level = "high" 和 "medium" 的所有邻居                            │   │
│  │  → 扩散结果: FIELD_REVENUE, FIELD_GROSS_PROFIT, FIELD_ROE,          │   │
│  │    FIELD_NET_PROFIT_MARGIN, FIELD_EBIT                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  Step 3: 数据源反查                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  遍历所有扩散到的 DataField，提取各自的 default_datasource_id        │   │
│  │  按 DataSource 分组，生成多源取数计划                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【Python 编排层】                                   │
│                                                                             │
│  1. 按取数计划依次调用 DataSource                                           │
│  2. 根据 DataField.standard_name 对返回的 DataFrame 做列切片                │
│  3. 合并多源数据（按报告期对齐）                                            │
│  4. 返回紧凑数据表格（仅包含需要的列）                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【LLM 分析层】                                      │
│  接收紧凑数据表格，结合用户原始问题进行深度分析，生成最终回答               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 两种意图模式的分支逻辑

```
                    用户问题
                        │
                        ▼
              ┌─────────────────┐
              │  LLM 判定意图类型 │
              └─────────────────┘
                        │
           ┌────────────┴────────────┐
           │                         │
           ▼                         ▼
   【事实查询 (fact)】        【分析查询 (analysis)】
   例:"净利润是多少"          例:"净利润表现如何"
           │                         │
           ▼                         ▼
   仅返回命中的              近邻扩散取全部
   1个DataField              medium及以上邻居
           │                         │
           └────────────┬────────────┘
                        │
                        ▼
                组装数据返回LLM
```

### 5.3 多源 DataField 的竞争与备选逻辑

```
同一个逻辑字段存在多个 DataField（如"净利润"有财报版和快报版）：

                    ┌─────────────────────┐
                    │  用户问题：净利润    │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  匹配到多个 DataField│
                    │  A: 净利润(财报)    │
                    │  B: 净利润(快报)    │
                    │  C: 净利润(行情)    │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  按综合评分排序       │
                    │  评分 = authority权重 │
                    │       + refresh权重   │
                    │       + reliability   │
                    └─────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ 首选 (Primary)│    │ 备选1       │    │ 备选2       │
    │ 综合评分最高  │    │ 评分次高    │    │ 评分最低    │
    └─────────────┘    └─────────────┘    └─────────────┘
           │
           ▼
    执行取数并返回
    （若失败则降级到备选）
```


## 六、开发实施步骤

### 第一阶段：环境准备（第 1-2 天）

**Step 1.1**：安装 Python 3.10+，创建虚拟环境

**Step 1.2**：安装基础依赖库：akshare、pandas、numpy、neo4j（或 networkx）

**Step 1.3**：安装并启动 Neo4j 图数据库（社区版即可），确认服务可访问

**Step 1.4**：下载 Qwen3-Embedding-4B GGUF Q4_K_M 量化模型文件（约 2.5GB）

**Step 1.5**：安装 llama-cpp-python 推理框架，验证模型可正常加载并生成向量

### 第二阶段：数据准备（第 3-4 天）

**Step 2.1**：遍历 akshare 核心接口，梳理所有可用的 DataField，记录字段名、同义词、描述、所属数据源

**Step 2.2**：为每个 akshare 接口创建 DataSource 条目，录入协议、函数名、参数模板、刷新时效、权威等级

**Step 2.3**：根据业务分析视角定义 10~15 个 IntentConcept（如盈利能力、成长能力、估值分析等）

**Step 2.4**：为每个 IntentConcept 配置 3~5 个默认种子字段（default_seed_fields）

**Step 2.5**：将上述数据整理为 CSV 文件，便于批量导入

### 第三阶段：图谱构建（第 5-7 天）

**Step 3.1**：连接 Neo4j，批量写入 IntentConcept、DataField、DataSource 三个类型的节点

**Step 3.2**：遍历所有 DataField，拼接文本（standard_name + alias + description），调用 Embedding 模型生成向量，写入节点属性

**Step 3.3**：遍历所有 IntentConcept，拼接文本（name + description），生成向量并写入节点属性

**Step 3.4**：两两计算 DataField 之间的余弦相似度，对相似度 ≥ 0.75 的字段对创建 SEMANTIC_SIMILAR_TO 关系，写入相似度值和级别档位

**Step 3.5**：根据 DataField 的 belongs_to_concepts 属性，创建 BELONGS_TO_CONCEPT 关系

### 第四阶段：查询与测试（第 8-9 天）

**Step 4.1**：实现 LLM 解析函数，接收用户问题，输出 target_metrics、entities、intent_type

**Step 4.2**：实现图谱查询函数：根据指标词匹配 DataField.alias，若未命中则用向量相似度检索

**Step 4.3**：实现近邻扩散函数：根据 intent_type 决定是否扩散，以及扩散的 level 范围

**Step 4.4**：实现数据源反查函数：遍历字段列表，按 DataSource 分组生成取数计划

**Step 4.5**：实现 Python 编排层：执行取数计划，对 DataFrame 做列切片，合并多源数据

**Step 4.6**：端到端测试覆盖 5 类核心场景（事实查询、分析查询、同义词匹配、概念兜底、多源备选）

### 第五阶段：优化与扩展（持续）

**Step 5.1**：引入向量索引库（Faiss/HNSW），将 Embedding 检索从 O(N²) 优化为 ANN 近似检索

**Step 5.2**：实现热点查询结果的 LRU 缓存，减少重复计算

**Step 5.3**：建立增量更新机制：新字段加入时，仅计算其与现有字段的相似度并建立关系

**Step 5.4**：封装为 FastAPI 服务，提供 HTTP 接口供上层应用调用

**Step 5.5**：加入日志与监控，追踪查询链路和响应时间


## 七、技术栈总结

| 组件 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 图数据库 | Neo4j 5.x | 生产推荐，支持属性图 |
| 轻量替代 | NetworkX + JSON | 开发原型快速验证 |
| Embedding 模型 | Qwen3-Embedding-4B (GGUF Q4_K_M) | 中文能力强，约 2.5GB 显存 |
| 推理框架 | llama-cpp-python | 支持 GGUF 量化模型高效推理 |
| Python 金融库 | akshare | 统一的数据源接口 |
| 数据处理 | pandas | DataFrame 切片与合并 |
| 向量加速 | faiss / hnswlib | 可选，提升大规模检索性能 |
| API 框架 | FastAPI | 封装图谱查询服务 |


## 八、设计优势总结

| 优势 | 说明 |
| :--- | :--- |
| **无人工维护负担** | 字段间关系由 Embedding 自动计算，新增字段增量挂接，无需专家遍历 |
| **无别名穷举** | 精确匹配走 alias 数组，兜底走向量相似度，双重保障 |
| **路由无冲突** | 字段直接指向 DataSource，不经过场景中转，消除二义性 |
| **多源融合友好** | 同名字段可建多个 DataField 节点，按时效/权威自动优选 |
| **可动态裁剪** | 关系带级别属性，可按需求取 high/medium/low 不同梯度的邻居 |
| **增量可扩展** | 新字段加入只需计算其与现有字段的相似度，连接自动建立 |
| **字段级时效/权威** | 每个 DataField 独立标记权威度和更新时效，支持精细化的数据源选择 |