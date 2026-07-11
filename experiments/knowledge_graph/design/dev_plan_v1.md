# IRKG v3 开发实施计划（最终版）

> 基于 2026-07-11 讨论确认后的方案
> 前置条件：Docker 安装 → Neo4j 启动

---

## 一、架构总览

### 1.1 完整流程

```
用户问题
    |
    v
[LLM 解析层]
    提取：target_fields, entities, intent_type, time_range, conditions
    |
    v
[知识图谱路由层]
    Step 1: alias 精确匹配（dict O(1)）命中 -> 直接取 DataField
    Step 2: 未命中? -> query -> CPU embed -> Faiss Top-K 检索
    Step 3: BELONGS_TO_CONCEPT -> 取字段所属 Concept
    Step 4: SEMANTIC_SIMILAR_TO 近邻扩散（按 level 裁剪）
    Step 5: 反查 DataSource -> 分组取数计划
    |
    v
路由输出结构：
{
    "concept": "CONCEPT_FINANCIAL_SUMMARY",
    "fields": [{"id": "FIELD_FIN_GROSS_MARGIN", "standard_name": "毛利率", ...}],
    "datasource": {"id": "DS_TUSHARE_FINA_IND", "prompt_dir": "ds_prompts/DS_TUSHARE_FINA_IND/"},
    "conditions": {
        "entity": {"type": "stock_code", "value": "300750.SZ"},
        "time_range": {"start": "20250101", "end": "20260630"},
        "intent_type": "analysis"
    }
}
    |
    v
[SQL 生成层]（Phase 7 核心）
    读取 ds_prompts/{datasource_id}/{field.md + table.md + api.md}
    与路由输出合并 -> 构造完整 prompt
    -> prompt 模板：
        表结构：{table_doc}
        字段说明：{field_doc}
        API规则：{api_doc}
        本次需求：字段 {fields}，表 {table}，条件 {conditions}
        请生成对应查询代码。
    -> 送入本地 LLM（glm4:9b-chat-q3_K_M）
    -> LLM 输出 SQL / 类 SQL 代码
    |
    v
[Python 执行层]（固化逻辑）
    解析 LLM 输出 -> 匹配 API 调用模板 -> 执行取数 -> 字段切片
    |
    v
[LLM 分析层]
    接收数据表格 -> 用户原始问题 -> 深度分析 -> 回答
```

### 1.2 三层节点

| 节点 | 数量 | 存储位置 |
|:---|:---:|:---|
| IntentConcept | 41 | Neo4j |
| DataField | 405 | Neo4j + Faiss |
| DataSource | 65 | Neo4j |

### 1.3 DataSource 新增属性

| 属性 | 类型 | 说明 |
|:---|:---|:---|
| id | string | 全局唯一标识 |
| name | string | 数据源名称 |
| protocol | enum | tushare/akshare/levistock/sina/tencent/xueqiu/web_search/llm_gen/local_calc |
| execution_meta | json | API 函数名 + 参数模板 |
| prompt_dir | string | 指向 ds_prompts/DS_TUSHARE_DAILY/ |
| refresh_time | enum | 更新时效 |
| authority_level | enum | S/A/B/C |
| reliability_score | float | 0~1 |
| latency_ms | int | 预估响应毫秒数 |
| code_format | string | 参数格式化规则 |

### 1.4 SEMANTIC_SIMILAR_TO 三级

| 级别 | 阈值 | 含义 | 使用场景 |
|:---|:---:|:---|:---|
| high | >= 0.85 | 高度同义或极强关联 | fact 模式 |
| medium | 0.75 ~ 0.85 | 紧密语义邻居 | analysis 模式 |
| low | 0.65 ~ 0.75 | 弱关联补充 | explore 模式 |

三级全部建边，查询时用 level 属性动态裁剪。

---

## 二、开发阶段

### 第零步：环境准备（开发前完成）

- [ ] 安装 Docker Engine（WSL2）
- [ ] Docker 拉取 neo4j:5-community 镜像
- [ ] 启动 Neo4j 容器（映射 7474:7474, 7687:7687）
- [ ] 验证 Neo4j 浏览器访问 http://localhost:7474
- [ ] Python 环境安装 neo4j 驱动
- [ ] 安装 Faiss（pip install faiss-cpu）


### Phase 1：数据骨架构建（可测试产出：Neo4j 中有 3 类节点）

- [ ] 根据 kg_design_deepseek_v4.md 第四部分，整理 41 个 IntentConcept 为 CSV
  - 字段：id, name, description, seed_keywords, requires_entity, default_seed_fields, site_search_urls
  - embedding 暂留空
- [ ] 根据 kg_design_deepseek_v4.md 第五部分，整理 65 个 DataSource 为 CSV
  - 字段：全部属性含 execution_meta、authority_level 等
  - prompt_dir 先设占位值
- [ ] 根据 datafield_detailed_design.md，整理 405 个 DataField 为 CSV
  - 字段：全部属性含 alias[]（作为 JSON 字符串）、data_type、unit 等
  - embedding 暂留空
- [ ] 编写 Python 脚本批量导入 Neo4j
  - 使用 UNWIND + CREATE 批量写入
  - 索引：为 id 属性创建唯一约束
- [ ] 验证：Neo4j 浏览器中 MATCH 能看到节点，按标签分组计数

**依赖**：第零步
**预计工时**：1-2 天


### Phase 2：Embedding 与语义关系（可测试产出：Faiss 索引 + SIMILAR_TO 关系）

- [ ] 下载 Qwen3-Embedding-4B GGUF Q4_K_M 模型
- [ ] 编译 llama-cpp-python 的 CUDA 后端（CMAKE_ARGS="-DLLAMA_CUDA=on" pip install）
- [ ] 编写 embedding 生成脚本（GPU 推理）
  - DataField 拼接规则：standard_name + " " + join(alias) + " " + description
  - IntentConcept 拼接规则：name + " " + description
- [ ] 停掉 ollama 服务，释放显存
- [ ] GPU 推理：生成 405 个 DataField embedding + 41 个 IntentConcept embedding
- [ ] 写回 Neo4j：每个节点的 embedding 属性
- [ ] 建 Faiss 索引
  - index_fields = IndexFlatIP(1024) + index.add(field_embeddings)
  - index_concepts = IndexFlatIP(1024) + index.add(concept_embeddings)
  - 写入磁盘：faiss.write_index()
- [ ] 计算 SEMANTIC_SIMILAR_TO 关系
  - 405 个字段两两余弦相似度（81,810 对）
  - >= 0.85: level=high, 建双向边
  - 0.75-0.85: level=medium, 建双向边
  - 0.65-0.75: level=low, 建双向边
  - < 0.65: 跳过
- [ ] 恢复 ollama 服务
- [ ] 验证：给定查询文本，Faiss 返回 Top-5 语义相似字段

**依赖**：Phase 1（Neo4j 中已有节点）
**预计工时**：2-3 天


### Phase 3：路由核心逻辑（可测试产出：Python 路由模块）

- [ ] 构建 alias 倒排索引（dict: alias -> field_id）
- [ ] 构建 Faiss 检索封装（向量化 query -> Top-K 搜索）
- [ ] 实现同步双查策略：
  - 同时做 alias 精确匹配 + Faiss 模糊检索
  - 如果 alias 命中，以 alias 结果为准
  - 如果未命中，取 Faiss Top-3 作为候选
- [ ] 实现 BELONGS_TO_CONCEPT 图查询（先临时建少量手工关系用于测试）
- [ ] 实现 SEMANTIC_SIMILAR_TO 近邻扩散（level 参数控制）
- [ ] 实现数据源反查（按 DataSource 分组）
- [ ] 实现路由输出结构（RouteResult 数据类）
- [ ] 编写 10+ 单元测试覆盖全部路径：
  1. 精确命中（"净利润" -> FIELD_FS_NET_PROFIT）
  2. 同义词命中（"PE" -> FIELD_PE_TTM）
  3. 兜底检索（"公司赚了多少钱" -> Faiss 返回 FIELD_FS_NET_PROFIT）
  4. 概念归属（字段 -> Concept）
  5. 近邻扩散 fact 模式
  6. 近邻扩散 analysis 模式
  7. 近邻扩散 explore 模式
  8. 多源分组
  9. 空结果处理
  10. entities 参数传递

**依赖**：Phase 1 + Phase 2
**预计工时**：3-4 天


### Phase 4：BELONGS_TO_CONCEPT 关系构建（可测试产出：完整路由链路）

- [ ] 将 DataField 清单 + IntentConcept 清单整理为 LLM 辅助输入
- [ ] DataField 分批（每批 50 个），每批附带完整 41 个 Concept 列表
- [ ] 调用 DeepSeek-V4（或当前可用 LLM）推断候选关系
  - 输出格式：[{field_id, concept_id, relevance_score}]
- [ ] 人工确认流程（命令行交互版）
  - 按 Concept 分组展示
  - 接受/拒绝/修改分数
  - 批量接受 >= 0.8 的候选
- [ ] 写入 Neo4j 关系
- [ ] 移除 Phase 3 中用于测试的临时关系
- [ ] 验证：全量路由测试——对每个 Concept 的核心字段确认路由正确

**依赖**：Phase 3
**预计工时**：3-5 天（含人工确认时间）


### Phase 5：Python 服务模块封装（可测试产出：可 pip install 的 Python 包）

- [ ] 将路由逻辑封装为独立模块：
  - `irkg/` 包结构
  - `irkg/graph.py` - Neo4j 连接与查询
  - `irkg/embedding.py` - Faiss 检索
  - `irkg/matcher.py` - alias 精确匹配
  - `irkg/router.py` - 路由主逻辑
  - `irkg/types.py` - 数据类定义
- [ ] 配置文件分离（config.yaml）
- [ ] 异常处理 + 可配置日志
- [ ] 生成 `prompts/` 目录结构（先创建空模板）
  - `prompts/llm_parse.md` - LLM 解析用户问题 prompt
  - `prompts/sql_generation.md` - SQL 生成 prompt（预留）
  - `prompts/llm_analysis.md` - LLM 分析回答 prompt（预留）
- [ ] 生成 `ds_prompts/` 目录结构（首批 5 个核心 DataSource Prompt 文件）
  - 从 knowledge/ 中各接口的 instruction.md + description.md + graph.md 精简提炼
  - 首批 5 个：DS_TUSHARE_DAILY, DS_TUSHARE_FINA_IND, DS_TUSHARE_DAILY_BASIC, DS_TENCENT_QUOTE, DS_LEVISTOCK_EMOTION
- [ ] 验证：`pip install -e .` 后可 import irkg

**依赖**：Phase 4
**预计工时**：2-3 天


### Phase 6：站内搜索集成（可测试产出：DS_WEB_SEARCH 路由链路）

- [ ] 梳理 web_bot_agent/version_1.0 API 的调用方式
- [ ] 编写 DS_WEB_SEARCH 数据源的 Python 适配器
- [ ] 完善 site_search_urls 属性在路由中的传递
- [ ] 验证：路由到含 site 信息的 Concept 时，输出包含搜索范围限定

**依赖**：Phase 5
**预计工时**：2-3 天


### Phase 7：SQL 生成实验（可测试产出：端到端取数链路）

- [ ] 编写完整的 ds_prompts/ 文件（全部 65 个 DataSource 的 field.md + table.md + api.md）
- [ ] 实现 SQL prompt 装配逻辑（路由输出 + prompt 文件 -> 完整 prompt）
- [ ] 实现 Python 执行层：
  - tushare 适配器（pro.xxx() 调用）
  - akshare 适配器（ak.xxx() 调用）
  - levistock 适配器（lk.xxx() 调用）
  - 腾讯财经适配器
  - 站内搜索适配器
- [ ] LLM SQL 输出解析器（从 LLM 回复中提取可执行代码）
- [ ] 反复测试+调优 prompt：
  - 简单场景：单字段单表无时间维
  - 中间场景：多字段 + 时间范围
  - 复杂场景：多源 join + 聚合
  - 边界情况：limit 控制、错误 API 调用
- [ ] 调优 prompt 分离文件（prompts/sql_generation.md）
- [ ] 验证：端到端跑通 10 个真实查询

**依赖**：Phase 5
**预计工时**：5-7 天（反复实验）


### Phase 8：全场景端到端测试（可测试产出：验收通过）

- [ ] 联调 LLM 解析层 + 路由层 + SQL 层 + 分析层
- [ ] 测试 41 个 Concept 各至少 1 个场景
- [ ] 多源融合场景（实时行情+财务+资金流向）
- [ ] 文档生成场景（午间文档/收盘文档）
- [ ] 边界条件测试（空结果、非法 entity、网络超时）
- [ ] 性能基准：路由延迟、embedding 延迟、SQL 生成延迟

**依赖**：所有 Phase
**预计工时**：2-3 天


### 总工时预估：20-30 天

---

## 三、目录结构

```
project_root/
  irkg/                       # Python 服务模块
    __init__.py
    graph.py                  # Neo4j 连接与查询
    embedding.py              # Faiss 检索
    matcher.py                # alias 精确匹配
    router.py                 # 路由主逻辑
    types.py                  # 数据类定义
    adapters/                 # 数据源适配器（Phase 7）
      tushare.py
      akshare.py
      levistock.py
      tencent.py
      web_search.py
    executor.py               # LLM SQL 解析 + 执行（Phase 7）
  prompts/                    # Prompt 模板（与代码分离）
    llm_parse.md              # LLM 解析用户问题
    sql_generation.md          # SQL 生成（含路由输出装配逻辑说明）
    llm_analysis.md           # LLM 分析回答
    belongs_to_concept.md     # BELONGS_TO_CONCEPT 推断
  ds_prompts/                 # DataSource prompt 文件
    DS_TUSHARE_DAILY/
      field.md                # 字段清单
      table.md                # 表结构
      api.md                  # API 调用规则
    DS_TUSHARE_FINA_IND/
      field.md
      table.md
      api.md
    DS_TUSHARE_DAILY_BASIC/
      ...
    DS_TENCENT_QUOTE/
      ...
    DS_LEVISTOCK_EMOTION/
      ...
    ...（共 65 个 DataSource）
  data/
    concepts.csv              # IntentConcept 源数据
    fields.csv                # DataField 源数据
    sources.csv               # DataSource 源数据
    faiss/                    # Faiss 索引文件
      fields.index
      concepts.index
  config.yaml                 # Neo4j 连接、模型路径等配置
  setup.py                    # pip 安装
```

---

## 四、关键设计决策记录

| 决策 | 结论 |
|:---|:---|
| 图数据库 | Neo4j 5.x 社区版（Docker）|
| Embedding 模型 | Qwen3-Embedding-4B GGUF Q4_K_M |
| Embedding 建库 | GPU（llama-cpp-python CUDA） |
| Embedding 查询 | CPU |
| 向量存储 | Neo4j 属性 + Faiss 索引（并存）|
| SEMANTIC_SIMILAR_TO | 三级全建边（>= 0.85 / 0.75-0.85 / 0.65-0.75）|
| 本地 LLM | glm4:9b-chat-q3_K_M（必要时升 q4_K_M）|
| IntentConcept | 41 个，以 kg_design_deepseek_v4.md 为准 |
| SQL 生成 | LLM 写类 SQL 代码，Python 固化执行 |
| Prompt | 与代码分离，存 prompts/ |
| DataSource Prompt | 3 文件/DS（field.md + table.md + api.md），存 ds_prompts/ |
| 站内搜索 | 占位实现，后期集成 web_bot_agent |
