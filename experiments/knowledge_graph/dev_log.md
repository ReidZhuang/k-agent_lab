# 开发日志

## Phase 1：数据骨架构建 ✅ （2026-07-11）
- Neo4j: 41 IntentConcept + 71 DataSource + 520 DataField + HAS_DATASOURCE

## Phase 2：Embedding 与语义关系 ✅ （2026-07-11）
- GPU 11s 完成 520+41 embedding
- Faiss 索引 + SEMANTIC_SIMILAR_TO 1,967 条关系

## Phase 3：路由核心逻辑 ✅ （2026-07-11）

### 完成内容
- [x] 4 级 alias 匹配器（qualified > simple > business_tag > synonym）
- [x] Alias 文件全量审查：19 处 qualified 优化 + 4 处口径区分
- [x] Faiss 向量检索兜底（CPU 推理）
- [x] SEMANTIC_SIMILAR_TO 近邻扩散（3 级意图控制）
- [x] BELONGS_TO_CONCEPT 图查询（占位，待 Phase 4）
- [x] 数据源反查（Neo4j HAS_DATASOURCE）
- [x] 路由结果结构 RouteResult.to_dict()
- [x] 20 个单元测试全部通过

### 索引规模
- simple: 436 条
- qualified: 1,003 条（多级中最具消歧能力）
- business_tag: 1,319 条
- synonym: 1,833 条

### 待后续
- Phase 4: BELONGS_TO_CONCEPT 关系构建
- Phase 5: Python 服务模块封装

## Phase 4：BELONGS_TO_CONCEPT 关系构建 ✅ （2026-07-12）
- [x] 修复 41 个 Concept ID 反引号问题
- [x] 写入 520 条 BELONGS_TO_CONCEPT 关系
- [x] 验证：毛利率 → CONCEPT_FINANCIAL_SUMMARY（财务摘要）
- [x] 路由全链路：alias -> concept -> similar fields -> datasource

## 增量接入：同花顺板块 + 巨潮公司概况 ✅ （2026-07-13）

按 `design/data_source_onboarding_playbook.md` 标准流程执行：

- Step 1-3: 需求评估 + 连通性验证 + 字段映射 ✅
- Step 4: 新增 2 个 DataSource（DS_AKSHARE_SECTOR_THS, DS_AKSHARE_CNINFO_PROFILE）
- Step 5: 创建 ds_prompts 各 3 个文件 ✅
- Step 6: 新增 8 个 DataField（含同花顺独有字段：净流入/驱动事件/龙头股等）
- Step 7: alias CSV 追加 8 行，无冲突 ✅
- Step 8: GPU Embedding 生成 + Faiss 索引更新（551 条）
- Step 9: 审计 46/46 全部通过 ✅

### 同花顺独有字段（东方财富没有的）
| 字段 | 说明 | 
|:---|:---|
| 板块总成交量 | 成交量维度 |
| 板块净流入 | 资金流向维度 |
| 板块均价 | 价格维度 |
| 概念驱动事件 | 题材催化逻辑 |
| 概念龙头股 | 龙头标的 |
| 概念成分股数量 | 题材覆盖广度 |

### 巨潮新增字段
公司网址、注册地址（S 级官方来源）

## tushare 6000+ 增量接入 ✅ （2026-07-13）

### 已完成
- [x] DataSource 新增 table_name 属性（78/80 个）
- [x] 接入 stk_managers（管理层）+ repurchase（回购）+ ths_index（同花顺概念）
- [x] 新增 6 个 DataField（高管姓名/职务/薪酬、回购金额、同花顺概念名称/成分数）
- [x] EOF 新增 4 个 ds_prompts 目录（各 3 个文件）
- [x] alias CSV 557 行，无冲突
- [x] Embedding + Faiss 更新
- [x] 审计 46/46 全部通过

### 审计框架
- [x] 审计流程文档：design/kg_audit_playbook.md（9 维度覆盖）
- [x] DataSource 质量审计：table_name 维度

### 暂缓接入
- stk_mins（频率限制 1次/小时，场景窄）
- npr（需 8000 分）
- fund_portfolio（已有 DS 占位，等待数据校验）
- limit_list_d 的封板字段（FIELD_LIMIT_FIRST/LAST_TIME 已存在）

## 主备机制设计 ✅ （2026-07-13）
- [x] 设计文档：design/backup_mechanism.md
- [x] 配置入口：config/backup_weights.json
- [x] HAS_BACKUP_DATASOURCE 关系设计（priority + api_column + unit）
- [x] 审计现有字段：31 个同名组，无真正主备冲突
