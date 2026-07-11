# IRKG v3 知识图谱设计方案与开发实施文档（完整版）


## 第一部分：设计哲学

### 1.1 核心定位

```
用户问题 → LLM（大脑） → 知识图谱（路由） → 数据源 → 数据 → 组装 → 回答
```

知识图谱不存储金融知识，只存储 **“从信息需求到数据获取路径”** 的路由表。它是连接 LLM 大脑与数据世界的桥梁。

### 1.2 设计原则

| 原则 | 说明 |
| :--- | :--- |
| **字段优先路由** | 路由起点是具体数据字段，而非业务场景，避免二义性 |
| **向量驱动近邻** | 字段间关系由 Embedding 相似度自动计算，零人工维护 |
| **节点精简极致** | 仅 3 种核心节点：IntentConcept、DataField、DataSource |
| **关系带属性** | 关系承载级别、权重等量化属性，支持动态查询裁剪 |
| **多源可备选** | 同一字段可来自多个数据源，按时效性/权威性自动取舍 |
| **从属关系自动化** | BELONGS_TO_CONCEPT 由 LLM 辅助推断 + 人工确认，降低维护成本 |
| **关系唯一表达** | 字段与概念的从属关系由关系层唯一表达，消除数据冗余 |


## 第二部分：节点设计

### 2.1 节点总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户问题                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 1: IntentConcept】业务场景分类器                      │
│  作用：用户问题的高层次分类标签，是图谱的路由入口              │
│  属性：id, name, description, seed_keywords, embedding,        │
│        requires_entity, default_seed_fields, site_search_urls  │
│  数量：41 个                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 2: DataField】最小数据原子单元 ★核心节点★            │
│  作用：代表一个具体可返回的数据列，所有路由最终收敛到它        │
│  属性：id, standard_name, alias[], description,                │
│        embedding, default_datasource_id,                       │
│        data_type, unit, authority_level, refresh_time          │
│  数量：405 个（独立）                                          │
│  📄 详细属性清单见独立文档：datafield_detailed_design.md      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 3: DataSource】物理取数指令                           │
│  作用：封装调用接口/爬虫的全部技术细节                        │
│  属性：id, name, protocol, execution_meta, refresh_time,       │
│        authority_level, reliability_score, latency_ms,         │
│        code_format                                            │
│  数量：65 个                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 IntentConcept（意图概念节点）

**身份定义**：用户问题的高层次分类标签，是图谱的“路由入口”。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识，如 `CONCEPT_MARKET_SENTIMENT` |
| `name` | string | ✅ | 业务标准名称 |
| `description` | text | ✅ | 详细描述，用于生成 Embedding 和向 LLM 解释 |
| `seed_keywords` | string[] | ✅ | 触发关键词（≤5个），用于 LLM 意图识别 |
| `embedding` | float[] | ✅ | 由 name + description 生成的向量，用于语义匹配兜底 |
| `requires_entity` | string[] | ❌ | 必需的实体参数列表，如 `["stock_code"]` |
| `default_seed_fields` | string[] | ✅ | 该概念默认推荐的 3~5 个核心字段 ID |
| `site_search_urls` | string[] | ❌ | 站内搜索入口 URL（如有），如 `site:cninfo.com.cn` |

**界定标准**：

| 标准 | 说明 |
| :--- | :--- |
| **独立分析视角** | 该概念代表一种独立的分析维度（如盈利、估值、资金、政策） |
| **关键词可收敛** | 3~5 个核心词即可让 LLM 准确识别 |
| **字段可聚合** | 该概念下能找到 3~10 个核心字段组成默认套餐 |

### 2.3 DataField（数据字段节点）★核心节点★

**身份定义**：最小的、不可再分的数据信息单元。所有路由最终都收敛到它。

**关键约束**：
- 每个 `DataField` 必须且只能指向一个 **默认 DataSource**
- 同一个逻辑字段若来自不同数据源，须创建多个 `DataField` 节点
- 多个 `DataField` 可通过 `SEMANTIC_SIMILAR_TO` 关系互连
- **不再存储 `belongs_to_concepts` 属性**，该信息由关系层 `BELONGS_TO_CONCEPT` 唯一表达

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识 |
| `standard_name` | string | ✅ | 规范列名，与 DataSource 返回的列名完全一致 |
| `alias` | string[] | ✅ | 同义词数组，用于精确匹配用户口语 |
| `description` | text | ✅ | 字段含义描述，用于 Embedding 生成 |
| `embedding` | float[] | ✅ | 由 standard_name + alias + description 生成的向量 |
| `default_datasource_id` | string | ✅ | 默认取数来源的 DataSource ID |
| `data_type` | enum | ✅ | 数据类型：`float` / `int` / `string` / `date` / `boolean` |
| `unit` | string | ❌ | 单位，如 `%`、`亿元`、`倍` |
| `authority_level` | enum | ✅ | 权威等级：`S`/`A`/`B`/`C`，可继承自 DataSource 或覆写 |
| `refresh_time` | enum | ✅ | 更新时效：`realtime`/`intraday`/`daily_17:00`/`daily_20:00`/`weekly`/`quarterly` |

> **📄 完整 DataField 详细属性清单**：因 DataField 数量众多（405 个独立节点），完整的字段属性（含每个字段的 ID、standard_name、alias、description、data_type、unit、authority_level、refresh_time、默认数据源 ID）已整理至独立文档 **`datafield_detailed_design.md`**，请结合本文档一并查阅。

### 2.4 DataSource（数据源节点）

**身份定义**：封装获取数据的技术执行指令。它是图谱的物理执行末端。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识 |
| `name` | string | ✅ | 数据源名称 |
| `protocol` | enum | ✅ | 协议类型：`tushare` / `akshare` / `levistock` / `sina` / `tencent` / `xueqiu` / `web_search` / `llm_gen` / `local_calc` |
| `execution_meta` | json | ✅ | 执行元数据。API 存函数名+参数模板；站内搜索存 URL 模板 |
| `refresh_time` | enum | ✅ | 更新时效 |
| `authority_level` | enum | ✅ | 权威等级：`S`/`A`/`B`/`C` |
| `reliability_score` | float | ✅ | 综合可靠度 0~1 |
| `latency_ms` | int | ❌ | 预估响应毫秒数 |
| `code_format` | string | ❌ | 参数格式化规则（如 `SZ_prefix`/`SH_prefix`/`pure_num`） |


## 第三部分：关系设计

### 3.1 SEMANTIC_SIMILAR_TO（语义近邻关系）

**方向**：`DataField` → `DataField`（双向）

**含义**：两个字段在向量空间中语义相似度高（余弦相似度 ≥ 阈值），构成近邻关系。替代传统人工维护的 FieldGroup，实现自动化、动态的字段聚合。

**关系属性**：

| 属性名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `cosine_similarity` | float | 余弦相似度原始值（0~1） |
| `level` | enum | 相似度档位：`high` / `medium` / `low` |

**阈值分级标准**：

| 级别 | 阈值范围 | 含义 |
| :--- | :--- | :--- |
| **high** | ≥ 0.85 | 高度同义或极强关联，可互换使用 |
| **medium** | 0.75 ~ 0.85 | 紧密语义邻居，分析时最常搭配 |
| **low** | 0.65 ~ 0.75 | 有一定关联，可作补充参考 |

**建边策略**：
1. 计算所有 `DataField` 两两之间的余弦相似度
2. 仅当相似度 ≥ 0.75 时，在图谱中创建 `SEMANTIC_SIMILAR_TO` 关系
3. 相似度在 0.65~0.75 之间的不创建关系（仅用于检索时的软匹配）

### 3.2 BELONGS_TO_CONCEPT（从属概念关系）★核心关系★

**方向**：`DataField` → `IntentConcept`（多对多）

**含义**：该字段可被用于某个业务场景的分析。**此关系是图谱路由的核心依据**——当用户命中的字段属于某 Concept 时，路由系统可通过此关系确认该字段的所属场景。

**关系属性**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `relevance_score` | float | ✅ | 该字段对该概念的重要性（0~1），由 LLM 生成时赋值 |
| `is_approved` | boolean | ✅ | 是否已通过人工确认。初始为 false |
| `is_auto_suggested` | boolean | ✅ | 是否为 LLM 自动生成的候选关系 |

**建边策略**：LLM 辅助梳理 + 人工确认（详见第九部分开发步骤 4.1-4.6）

**重要说明**：
- `BELONGS_TO_CONCEPT` 关系是 `DataField` 与 `IntentConcept` 之间**唯一合法的表达方式**
- `DataField` 节点属性中**不再存储** `belongs_to_concepts[]`，避免数据冗余和不一致


## 第四部分：IntentConcept 完整清单（41 个）

### 第一组：市场全景层（4 个）

#### 1. 市场整体行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARKET_INDEX` |
| **name** | 市场整体行情 |
| **description** | 主要股票市场指数的实时表现和历史走势，包括A股指数（上证综指、深证成指、创业板指、科创50、沪深300、中证500等）、港股（恒生指数、恒生科技）、美股（道琼斯、纳斯达克、标普500）、欧洲（德国DAX、英国富时100、法国CAC40）、亚太（日经225、韩国KOSPI、台湾加权、印度Sensex）等 |
| **seed_keywords** | 指数、大盘、上证、恒生、纳斯达克、道琼斯 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_INDEX_NAME, FIELD_INDEX_PRICE, FIELD_INDEX_PCT_CHG, FIELD_INDEX_HIGH, FIELD_INDEX_LOW, FIELD_INDEX_VOL, FIELD_INDEX_AMOUNT |
| **site_search_urls** | `site:eastmoney.com` 指数行情页 |

#### 2. 市场情绪与快讯

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARKET_SENTIMENT` |
| **name** | 市场情绪与快讯 |
| **description** | 全市场情绪指标（市场热度、上涨占比、赚钱效应、涨停梯队、涨跌分布）和实时财经快讯（财联社、华尔街见闻等） |
| **seed_keywords** | 情绪、热度、赚钱效应、快讯、电报、涨停梯队 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_MARKET_HEAT, FIELD_MARKET_BALANCE, FIELD_MARKET_UP_RATIO, FIELD_MARKET_PROFIT_RATIO, FIELD_LIMIT_UP_BOARD, FIELD_NEWS_TITLE, FIELD_NEWS_CONTENT |
| **site_search_urls** | `site:cls.cn` 快讯栏目；`site:xueqiu.com` 热门讨论 |

#### 3. 板块实时行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_SECTOR_REALTIME` |
| **name** | 板块实时行情 |
| **description** | 申万行业板块（31个一级、134个二级、346个三级）和概念板块的实时表现，包括涨跌幅、成交额、换手率、领涨股、主力资金净流入等 |
| **seed_keywords** | 板块、行业、概念、领涨、轮动 |
| **requires_entity** | [`sector_name`] |
| **default_seed_fields** | FIELD_SECTOR_NAME, FIELD_SECTOR_PCT_CHG, FIELD_SECTOR_AMOUNT, FIELD_SECTOR_TURNOVER, FIELD_SECTOR_LEAD_STOCK, FIELD_SECTOR_MAIN_INFLOW |
| **site_search_urls** | `site:eastmoney.com` 板块行情页 |

#### 4. 龙虎榜与大宗交易

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_LHB_BLOCKTRADE` |
| **name** | 龙虎榜与大宗交易 |
| **description** | 每日龙虎榜上榜股票详情（买入/卖出金额、净买入额、上榜理由、营业部明细）和大宗交易数据（成交量、成交价、折溢价率、买卖营业部） |
| **seed_keywords** | 龙虎榜、机构席位、大宗交易、折溢价、营业部 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_LHB_STOCK_NAME, FIELD_LHB_PCT_CHG, FIELD_LHB_BUY, FIELD_LHB_SELL, FIELD_LHB_NET, FIELD_LHB_REASON, FIELD_BLOCK_PRICE, FIELD_BLOCK_VOL |
| **site_search_urls** | `site:eastmoney.com` 龙虎榜页面 |

### 第二组：行业与产业链层（5 个）

#### 5. 行业分类与成分

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INDUSTRY_CLASSIFY` |
| **name** | 行业分类与成分 |
| **description** | 申万行业分类体系及每个行业的成分股列表（含纳入/剔除日期），以及个股的行业归属查询 |
| **seed_keywords** | 行业分类、申万、成分股、行业归属 |
| **requires_entity** | [`industry_code`] |
| **default_seed_fields** | FIELD_INDUSTRY_L1_NAME, FIELD_INDUSTRY_L2_NAME, FIELD_INDUSTRY_L3_NAME, FIELD_INDUSTRY_MEMBER, FIELD_INDUSTRY_IN_DATE |
| **site_search_urls** | `site:10jqka.com.cn` 概念板块页面 |

#### 6. 产业背景分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INDUSTRY_BG` |
| **name** | 产业背景分析 |
| **description** | 目标产业或技术领域的系统性背景信息：技术图谱、产业链结构、政策与标准、全球竞争版图、历史演进、商业盈利模式 |
| **seed_keywords** | 产业、产业链、技术路线、竞争格局、产业背景 |
| **requires_entity** | [`industry_name`] |
| **default_seed_fields** | FIELD_INDUSTRY_BG_TECH, FIELD_INDUSTRY_BG_CHAIN, FIELD_INDUSTRY_BG_POLICY, FIELD_INDUSTRY_BG_PLAYERS |
| **site_search_urls** | `site:stcn.com` 政策解读；`site:cls.cn` 行业深度 |

#### 7. 投资路径分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_PATH_ANALYSIS` |
| **name** | 投资路径分析 |
| **description** | 从一条资讯或投资主题出发，系统性地分化出多条潜在投资路径（技术路线/产业链环节/地域/时间维度等） |
| **seed_keywords** | 投资路径、分化、切入点、先行信号 |
| **requires_entity** | [`topic`] |
| **default_seed_fields** | FIELD_PATH_ID, FIELD_PATH_DIMENSION, FIELD_PATH_DESC, FIELD_PATH_ENTRY, FIELD_PATH_SIGNAL, FIELD_PATH_PRIORITY |
| **site_search_urls** | `site:cls.cn` 产业快讯；`site:stcn.com` 行业分析 |

#### 8. 政策原文

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_POLICY_ORIGINAL` |
| **name** | 政策原文 |
| **description** | 国家行政机关（医保局、药监局、工信部、发改委、财政部、证监会、央行等）公开披露的法规、条例、批复、通知等文本数据 |
| **seed_keywords** | 政策、法规、通知、批复、文件、原文 |
| **requires_entity** | [`policy_keyword`] |
| **default_seed_fields** | FIELD_POLICY_TITLE, FIELD_POLICY_DEPT, FIELD_POLICY_DATE, FIELD_POLICY_TYPE, FIELD_POLICY_FULLTEXT, FIELD_POLICY_LINK |
| **site_search_urls** | `site:gov.cn` 政策文件库；各部委官网 |

### 第三组：公司基本面层（7 个）

#### 9. 实时行情与估值

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_REALTIME_QUOTE` |
| **name** | 实时行情与估值 |
| **description** | 个股实时价格、涨跌幅、成交量、成交额，以及关键估值指标（PE_TTM、PB、PS_TTM、总市值、流通市值、换手率、量比、股息率） |
| **seed_keywords** | 股价、行情、PE、PB、市值、换手率、量比 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_QUOTE_PRICE, FIELD_QUOTE_PCT_CHG, FIELD_TOTAL_MV, FIELD_PE_TTM, FIELD_PB, FIELD_TURNOVER_RATE, FIELD_VOLUME_RATIO |
| **site_search_urls** | `site:eastmoney.com` 个股行情页 |

#### 10. 历史K线

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_HISTORICAL_KLINE` |
| **name** | 历史K线 |
| **description** | 个股日/周/月K线及分钟K线数据，支持前复权/后复权/不复权，以及技术面因子（MACD、KDJ、RSI、BOLL、CCI） |
| **seed_keywords** | K线、日线、周线、月线、分钟线、技术指标 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_KLINE_DATE, FIELD_KLINE_OPEN, FIELD_KLINE_HIGH, FIELD_KLINE_LOW, FIELD_KLINE_CLOSE, FIELD_KLINE_VOL, FIELD_KLINE_PCT_CHG, FIELD_MACD_DIF, FIELD_KDJ_K |
| **site_search_urls** | `site:eastmoney.com` 个股K线页 |

#### 11. 财务摘要

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_SUMMARY` |
| **name** | 财务摘要 |
| **description** | 公司核心财务指标的快速概览：盈利能力（ROE、毛利率、净利率）、成长能力（营收/净利同比增速）、资本结构（资产负债率）、营运能力（总资产周转率）、每股指标（EPS、每股净资产） |
| **seed_keywords** | 财务、ROE、毛利率、净利、营收、EPS |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_FIN_ROE_WAA, FIELD_FIN_GROSS_MARGIN, FIELD_FIN_NET_MARGIN, FIELD_FIN_REVENUE_YOY, FIELD_FIN_PROFIT_YOY, FIELD_FIN_DEBT_RATIO, FIELD_FIN_EPS, FIELD_FIN_BPS |
| **site_search_urls** | `site:finance.sina.com.cn` 财务数据页 |

#### 12. 深度财务指标

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_DEEP` |
| **name** | 深度财务指标 |
| **description** | ROIC、杜邦分解（净利率×总资产周转率×权益乘数）、ROE扣非、EBIT/EBITDA、已获利息倍数、单季度指标（单季度ROE/毛利率/营收增速） |
| **seed_keywords** | ROIC、杜邦、EBIT、利息保障、单季度 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_FIN_ROIC, FIELD_FIN_ROE_DT, FIELD_FIN_EBIT_RATIO, FIELD_FIN_INTEREST_COVER, FIELD_FIN_EQUITY_MULT, FIELD_FIN_Q_ROE |
| **site_search_urls** | — |

#### 13. 三大财务报表

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_STATEMENTS` |
| **name** | 三大财务报表 |
| **description** | 完整的利润表、资产负债表、现金流量表，Excel级详细科目，支持银行/保险/证券专用科目 |
| **seed_keywords** | 利润表、资产负债表、现金流量表、财报 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_FS_TOTAL_REVENUE, FIELD_FS_OPER_COST, FIELD_FS_NET_PROFIT, FIELD_FS_TOTAL_ASSETS, FIELD_FS_TOTAL_LIAB, FIELD_FS_TOTAL_EQUITY, FIELD_FS_OPER_CF, FIELD_FS_END_CASH |
| **site_search_urls** | — |

#### 14. 估值对比分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_VALUATION_COMPARE` |
| **name** | 估值对比分析 |
| **description** | 公司历史估值水平（PE/PB/PS历史分位数）和同行业估值对比（行业平均PE/PB、行业内估值排名） |
| **seed_keywords** | 估值分位、历史PE、行业PE、低估高估 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_VAL_PE_TTM, FIELD_VAL_PE_PCT, FIELD_VAL_PB, FIELD_VAL_PB_PCT, FIELD_VAL_IND_PE, FIELD_VAL_RATING |
| **site_search_urls** | — |

#### 15. 公司概况

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_COMPANY_PROFILE` |
| **name** | 公司概况 |
| **description** | 公司全面基础信息：股票代码、所属行业、上市日期、实控人、法人代表、注册资本、员工人数、主营业务 |
| **seed_keywords** | 公司介绍、主营业务、实控人、注册资本、员工 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_PROFILE_FULLNAME, FIELD_PROFILE_INDUSTRY, FIELD_PROFILE_LIST_DATE, FIELD_PROFILE_ACT_NAME, FIELD_PROFILE_REG_CAPITAL, FIELD_PROFILE_EMPLOYEES, FIELD_PROFILE_MAIN_BUSINESS |
| **site_search_urls** | `site:cninfo.com.cn` 公司概况页 |

### 第四组：公司治理与事件层（6 个）

#### 16. 前十大股东

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_TOP_HOLDERS` |
| **name** | 前十大股东 |
| **description** | 公司前十大股东和前十大流通股东名单、持股数量、持股比例、较上期变动、股东类型 |
| **seed_keywords** | 十大股东、持股、机构持仓、股东变动 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_HOLDER_NAME, FIELD_HOLDER_SHARES, FIELD_HOLDER_RATIO, FIELD_HOLDER_CHANGE, FIELD_HOLDER_TYPE |
| **site_search_urls** | `site:cninfo.com.cn` 股东信息页 |

#### 17. 机构持仓与评级

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INSTITUTION_RATING` |
| **name** | 机构持仓与评级 |
| **description** | 机构投资者持仓汇总（机构数量、持仓比例、季度变动）和券商研究报告（评级、目标价、盈利预测） |
| **seed_keywords** | 机构持仓、券商评级、目标价、研报 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_INST_COUNT, FIELD_INST_RATIO, FIELD_INST_CHANGE, FIELD_INST_RATING, FIELD_INST_TARGET_MAX, FIELD_INST_FORECAST_EPS |
| **site_search_urls** | `site:eastmoney.com` 研报页 |

#### 18. 公司公告

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_ANNOUNCEMENT` |
| **name** | 公司公告 |
| **description** | 上市公司在交易所法定披露的正式公告（财报、重大事项、并购重组、定增、回购、人事变动等），S级权威信息来源 |
| **seed_keywords** | 公告、披露、重大事项、定增、回购、并购 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_ANNOUNCE_TITLE, FIELD_ANNOUNCE_DATE, FIELD_ANNOUNCE_TYPE, FIELD_ANNOUNCE_LINK |
| **site_search_urls** | `site:cninfo.com.cn` 公告检索页；`site:stcn.com` 公告解读 |

#### 19. 互动易问答

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_IRM_QA` |
| **name** | 互动易问答 |
| **description** | 投资者在互动易平台的提问及公司回复内容，反映公司沟通态度和信息透明度 |
| **seed_keywords** | 互动易、投资者问答、IR、公司回复 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_IRM_QUESTION, FIELD_IRM_QUESTION_DATE, FIELD_IRM_ANSWER, FIELD_IRM_ANSWER_DATE |
| **site_search_urls** | — |

#### 20. IPO信息

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_IPO_INFO` |
| **name** | IPO信息 |
| **description** | 公司上市时的详细信息：发行价、发行总量、募集资金、发行市盈率、中签率、上市日期 |
| **seed_keywords** | IPO、发行价、中签率、上市日期、募资 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_IPO_PRICE, FIELD_IPO_AMOUNT, FIELD_IPO_FUNDS, FIELD_IPO_PE, FIELD_IPO_BALLOT, FIELD_IPO_LIST_DATE |
| **site_search_urls** | — |

#### 21. 分红送配

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DIVIDEND` |
| **name** | 分红送配 |
| **description** | 公司历年分红送配方案：每10股派息金额、每股送转比例、股权登记日、除权除息日 |
| **seed_keywords** | 分红、派息、送转、除权、股息率 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_DIV_END_DATE, FIELD_DIV_CASH, FIELD_DIV_STK, FIELD_DIV_RECORD_DATE, FIELD_DIV_EX_DATE |
| **site_search_urls** | — |

### 第五组：资金与交易层（5 个）

#### 22. 个股资金流向

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUND_FLOW` |
| **name** | 个股资金流向 |
| **description** | 个股主力资金细分流向：小单/中单/大单/特大单的买入卖出量及金额、净流入额 |
| **seed_keywords** | 资金流向、主力、大单、净流入、特大单 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_FLOW_NET_AMT, FIELD_FLOW_LARGE_BUY_AMT, FIELD_FLOW_ELG_BUY_AMT, FIELD_FLOW_MEDIUM_BUY_AMT, FIELD_FLOW_SMALL_BUY_AMT |
| **site_search_urls** | `site:eastmoney.com` 资金流向页 |

#### 23. 北向资金

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_NORTHBOUND` |
| **name** | 北向资金 |
| **description** | 沪深港通北向资金每日净流入流出、持股明细、十大成交股，以及南向资金每日成交统计 |
| **seed_keywords** | 北向资金、陆股通、外资流入、持股明细 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_NORTH_NET, FIELD_NORTH_SH_NET, FIELD_NORTH_SZ_NET, FIELD_NORTH_HOLD_VOL, FIELD_NORTH_TOP10 |
| **site_search_urls** | `site:eastmoney.com` 北向资金页 |

#### 24. 融资融券

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARGIN` |
| **name** | 融资融券 |
| **description** | 全市场及个股融资余额、融资买入额、融资偿还额、融券余额、融券卖出量（T+1更新） |
| **seed_keywords** | 融资、融券、杠杆、两融、融资余额 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_MARGIN_BALANCE, FIELD_MARGIN_BUY, FIELD_MARGIN_REPAY, FIELD_MARGIN_SHORT_BALANCE, FIELD_MARGIN_TOTAL |
| **site_search_urls** | — |

#### 25. 涨停跌停分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_LIMIT_UP_DOWN` |
| **name** | 涨停跌停分析 |
| **description** | 每日涨停/跌停股详细数据：涨跌停价格、涨跌停状态、连板数、首次封板时间、开板次数 |
| **seed_keywords** | 涨停、跌停、连板、封板、一字板 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_LIMIT_UP_PRICE, FIELD_LIMIT_DOWN_PRICE, FIELD_LIMIT_STATUS, FIELD_LIMIT_CONTINUOUS, FIELD_LIMIT_FIRST_TIME, FIELD_LIMIT_OPEN_TIMES |
| **site_search_urls** | — |

#### 26. 股权质押与增减持

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_PLEDGE_HOLDER_TRADE` |
| **name** | 股权质押与增减持 |
| **description** | 大股东股权质押统计数据（质押比例、质押次数）和明细（质押方、起止日期、是否解押），以及重要股东增减持记录 |
| **seed_keywords** | 股权质押、增减持、质押比例、解押、预警线 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_PLEDGE_HOLDER, FIELD_PLEDGE_RATIO, FIELD_PLEDGE_PLEDGOR, FIELD_PLEDGE_START, FIELD_PLEDGE_END, FIELD_PLEDGE_IS_RELEASE, FIELD_TRADE_TYPE, FIELD_TRADE_VOL |
| **site_search_urls** | `site:cninfo.com.cn` 质押/增减持公告 |

### 第六组：宏观与跨资产层（8 个）

#### 27. 宏观经济指标

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MACRO_ECONOMY` |
| **name** | 宏观经济指标 |
| **description** | 中国及全球主要经济体的宏观经济指标：GDP、CPI、PPI、PMI、M2、LPR、Shibor、社融、美债收益率曲线 |
| **seed_keywords** | GDP、CPI、PPI、PMI、M2、LPR、社融、非农 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_MACRO_GDP_YOY, FIELD_MACRO_CPI_YOY, FIELD_MACRO_PPI_YOY, FIELD_MACRO_PMI, FIELD_MACRO_M2_YOY, FIELD_MACRO_SF_MONTH, FIELD_MACRO_US_10Y |
| **site_search_urls** | `site:gov.cn` 经济数据发布页 |

#### 28. 利率与债券收益率

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INTEREST_RATE` |
| **name** | 利率与债券收益率 |
| **description** | Shibor各期限利率（隔夜/1周/2周/1月/3月/6月/9月/1年）、LPR（1年期/5年期）、Libor/Hibor各期限，以及温州/广州民间借贷利率 |
| **seed_keywords** | Shibor、LPR、Libor、利率、拆借、民间利率 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_RATE_SHIBOR_ON, FIELD_RATE_SHIBOR_1W, FIELD_RATE_SHIBOR_1M, FIELD_RATE_SHIBOR_3M, FIELD_RATE_LPR_1Y, FIELD_RATE_LPR_5Y, FIELD_RATE_WZ_COMP, FIELD_RATE_HIBOR_ON |
| **site_search_urls** | — |

#### 29. 主要外汇汇率

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FOREX_MAJOR` |
| **name** | 主要外汇汇率 |
| **description** | 主要货币对即期汇率和历史走势（美元/人民币、欧元/美元等），以及外汇基础信息 |
| **seed_keywords** | 汇率、外汇、美元、人民币、欧元 |
| **requires_entity** | [`currency_pair`] |
| **default_seed_fields** | FIELD_FOREX_PAIR, FIELD_FOREX_BID_CLOSE, FIELD_FOREX_ASK_CLOSE, FIELD_FOREX_BID_HIGH, FIELD_FOREX_BID_LOW |
| **site_search_urls** | — |

#### 30. 债券收益率曲线

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_BOND_YIELD_CURVE` |
| **name** | 债券收益率曲线 |
| **description** | 中国国债各期限（1/2/5/10/30年期）收益率，以及中美10年期利差 |
| **seed_keywords** | 国债收益率、债券、利差、中美利差 |
| **requires_entity** | [] |
| **default_seed_fields** | FIELD_BOND_CURVE_1Y, FIELD_BOND_CURVE_2Y, FIELD_BOND_CURVE_5Y, FIELD_BOND_CURVE_10Y, FIELD_BOND_CURVE_30Y, FIELD_BOND_CURVE_SPREAD |
| **site_search_urls** | — |

#### 31. 期货行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUTURES` |
| **name** | 期货行情 |
| **description** | 国内期货主力合约日线行情、主力与连续合约映射、每日持仓排名、仓单日报、结算参数 |
| **seed_keywords** | 期货、主力合约、持仓、仓单、结算 |
| **requires_entity** | [`future_code`] |
| **default_seed_fields** | FIELD_FUT_TS_CODE, FIELD_FUT_CLOSE, FIELD_FUT_PCT_CHG, FIELD_FUT_VOL, FIELD_FUT_OI, FIELD_FUT_SETTLE |
| **site_search_urls** | — |

#### 32. 期货明细数据

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUTURES_DETAIL` |
| **name** | 期货明细数据 |
| **description** | 期货每日持仓排名（各期货公司会员成交量/持买仓量/持卖仓量及变化）、仓单日报（各仓库仓单量及增减）、结算参数（交易手续费率/保证金率） |
| **seed_keywords** | 持仓排名、仓单、保证金、手续费、交割 |
| **requires_entity** | [`future_code`] |
| **default_seed_fields** | FIELD_FUT_DETAIL_BROKER, FIELD_FUT_DETAIL_VOL, FIELD_FUT_DETAIL_LONG, FIELD_FUT_DETAIL_SHORT, FIELD_FUT_WSR_VOL, FIELD_FUT_SETTLE_MARGIN |
| **site_search_urls** | — |

#### 33. 可转债行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_CONVERTIBLE_BOND` |
| **name** | 可转债行情 |
| **description** | 可转债日线行情、基础信息（转股价、债券余额、票面利率、信用评级）、转股价值、转股溢价率、纯债价值、强赎状态 |
| **seed_keywords** | 可转债、转股、溢价率、强赎、纯债 |
| **requires_entity** | [`bond_code`] |
| **default_seed_fields** | FIELD_CB_NAME, FIELD_CB_CLOSE, FIELD_CB_PCT_CHG, FIELD_CB_CONV_PRICE, FIELD_CB_CB_VALUE, FIELD_CB_CB_OVER_RATE, FIELD_CB_REMAIN_SIZE |
| **site_search_urls** | — |

#### 34. 基金与ETF行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUND_ETF` |
| **name** | 基金与ETF行情 |
| **description** | ETF日线行情、基金基础信息（管理人、基金类型、管理费）、基金份额规模、基金净值、基金持仓明细、基金分红、基金经理信息 |
| **seed_keywords** | ETF、基金、净值、规模、基金经理、持仓 |
| **requires_entity** | [`fund_code`] |
| **default_seed_fields** | FIELD_FUND_NAME, FIELD_FUND_UNIT_NAV, FIELD_FUND_PCT_CHG, FIELD_FUND_SHARES, FIELD_FUND_MANAGEMENT, FIELD_FUND_MANAGER_NAME, FIELD_FUND_PORT_SYMBOL |
| **site_search_urls** | `site:eastmoney.com` 基金页 |

### 第七组：文档生成层（6 个）

#### 35. 午间收盘信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_MIDDAY` |
| **name** | 午间收盘信息文档 |
| **description** | 交易日午间收盘后（11:35-12:00）生成的上午半日行情摘要、板块地位、驱动因素变化、资金博弈迹象、技术面关键位置及风险提示 |
| **seed_keywords** | 午间、上午收盘、半日行情、午间文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_QUOTE_PCT_CHG, FIELD_QUOTE_AMOUNT, FIELD_TURNOVER_RATE, FIELD_SECTOR_PCT_CHG, FIELD_NEWS_CONTENT, FIELD_KLINE_CLOSE（5/10/20日均值） |
| **site_search_urls** | 联网搜索 |

#### 36. 收盘后信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_CLOSE` |
| **name** | 收盘后信息文档 |
| **description** | 交易日收盘后三阶段生成（17:30/19:30/次日9:30）：行情概览、涨停驱动因素、财务摘要、技术面分析、资金博弈、融资融券变化 |
| **seed_keywords** | 收盘、盘后、全天行情、收盘文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_QUOTE_PCT_CHG, FIELD_QUOTE_AMOUNT, FIELD_TURNOVER_RATE, FIELD_LIMIT_UP, FIELD_FLOW_NET_AMT, FIELD_MARGIN_BALANCE, FIELD_KLINE_CLOSE(5/10/20日均值), FIELD_VAL_PE_TTM, FIELD_VAL_PB |
| **site_search_urls** | 联网搜索 |

#### 37. 公司潜在价值信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_VALUE` |
| **name** | 公司潜在价值信息文档 |
| **description** | 公司长期价值档案：产业链位置、市场规模、核心项目、技术壁垒、管理团队、竞争格局、财务质量（近3年）、风险与不确定性、反证分析 |
| **seed_keywords** | 潜在价值、公司价值、长期价值、价值文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | CONCEPT_INDUSTRY_CLASSIFY全部字段, FIELD_FS_CIP, FIELD_PROFILE_CHAIRMAN, FIELD_PROFILE_MANAGER, CONCEPT_FINANCIAL_SUMMARY全部字段, CONCEPT_VALUATION_COMPARE全部字段, CONCEPT_PLEDGE_HOLDER_TRADE全部字段 |
| **site_search_urls** | `site:cninfo.com.cn`；`site:stcn.com` |

#### 38. 风险控制文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_RISK` |
| **name** | 风险控制文档 |
| **description** | 全维度风险梳理：题材风险、板块退潮风险、财务风险、股东风险、技术路线风险、估值风险、流动性风险、监管风险、信息可信度风险 |
| **seed_keywords** | 风险、风控、风险评估、风险文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | CONCEPT_SECTOR_REALTIME, CONCEPT_FINANCIAL_SUMMARY全部字段, CONCEPT_TOP_HOLDERS全部字段, CONCEPT_PLEDGE_HOLDER_TRADE全部字段, CONCEPT_VALUATION_COMPARE（PE分位数）, FIELD_TURNOVER_RATE, FIELD_ANNOUNCE_TYPE |
| **site_search_urls** | `site:cninfo.com.cn`；`site:stcn.com` |

#### 39. 反证文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_COUNTER` |
| **name** | 反证文档 |
| **description** | 从“为什么这笔投资可能是错的”角度出发的系统性批判：产业路径反证、产业链环节反证、公司真实受益反证、龙头属性反证、项目兑现反证、估值反证、替代公司反证 |
| **seed_keywords** | 反证、批判、风险验证、反证文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | CONCEPT_INDUSTRY_BG全部字段, CONCEPT_POLICY_ORIGINAL全部字段, FIELD_FS_TOTAL_REVENUE, CONCEPT_INDUSTRY_CLASSIFY全部字段, CONCEPT_VALUATION_COMPARE（PE分位数） |
| **site_search_urls** | `site:cninfo.com.cn`；`site:stcn.com` |

#### 40. 估值辅助文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_VALUATION` |
| **name** | 估值辅助文档 |
| **description** | 系统化估值参考框架：当前估值水位、成长性支撑、产业背景对估值的影响、风险对估值折价的影响、估值情景分析（乐观/中性/悲观）、估值参考结论 |
| **seed_keywords** | 估值文档、估值辅助、情景分析、估值参考 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | FIELD_QUOTE_PRICE, FIELD_TOTAL_MV, FIELD_VAL_PE_TTM, FIELD_VAL_PB, FIELD_VAL_PE_PCT, FIELD_VAL_IND_PE, FIELD_FIN_REVENUE_YOY, FIELD_FIN_PROFIT_YOY, FIELD_FIN_GROSS_MARGIN, FIELD_FIN_NET_MARGIN |
| **site_search_urls** | — |

#### 41. 财务报表细项

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_DETAIL` |
| **name** | 财务报表细项 |
| **description** | 三大报表中未被财务摘要和深度指标覆盖的详细科目：利润表细项（信用减值损失、公允价值变动收益、投资收益等）、资产负债表细项（交易性金融资产、长期股权投资、递延所得税资产等）、现金流量表细项（收到/支付其他与经营活动有关的现金等），以及银行/保险/证券专用科目 |
| **seed_keywords** | 财务报表细项、信用减值、投资收益、递延所得税、保险专用 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 待补充（由三大报表中未被覆盖的详细科目构成） |
| **site_search_urls** | — |


## 第五部分：DataSource 完整清单（65 个）

### 5.1 TuShare 数据源（48 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_TUSHARE_DAILY | TuShare 日线行情 | tushare | A | daily_17:00 | 0.95 |
| DS_TUSHARE_DAILY_BASIC | TuShare 每日指标 | tushare | A | daily_17:00 | 0.95 |
| DS_TUSHARE_STK_LIMIT | TuShare 涨跌停价 | tushare | A | intraday | 0.95 |
| DS_TUSHARE_ADJ_FACTOR | TuShare 复权因子 | tushare | A | daily_17:00 | 0.95 |
| DS_TUSHARE_STK_FACTOR | TuShare 技术面因子 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_INDEX_DAILY | TuShare 指数日线 | tushare | A | daily_17:00 | 0.95 |
| DS_TUSHARE_INDEX_BASIC | TuShare 指数基础信息 | tushare | A | weekly | 0.95 |
| DS_TUSHARE_INDEX_DB | TuShare 指数每日指标 | tushare | A | daily_17:00 | 0.95 |
| DS_TUSHARE_FINA_IND | TuShare 财务指标 | tushare | A | quarterly | 0.95 |
| DS_TUSHARE_INCOME | TuShare 利润表 | tushare | A | quarterly | 0.95 |
| DS_TUSHARE_BALANCE | TuShare 资产负债表 | tushare | A | quarterly | 0.95 |
| DS_TUSHARE_CASHFLOW | TuShare 现金流量表 | tushare | A | quarterly | 0.95 |
| DS_TUSHARE_MONEYFLOW | TuShare 个股资金流向 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_HSGT | TuShare 沪深港通资金流向 | tushare | A | intraday | 0.90 |
| DS_TUSHARE_HK_HOLD | TuShare 北向持股明细 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_HSGT_TOP10 | TuShare 沪深港通十大成交 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_MARGIN | TuShare 融资融券 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_TOP_LIST | TuShare 龙虎榜 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_TOP_INST | TuShare 龙虎榜机构交易 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_BLOCK_TRADE | TuShare 大宗交易 | tushare | A | daily_20:00 | 0.90 |
| DS_TUSHARE_TOP10 | TuShare 前十大股东 | tushare | A | quarterly | 0.90 |
| DS_TUSHARE_PLEDGE_STAT | TuShare 股权质押统计 | tushare | A | event_driven | 0.90 |
| DS_TUSHARE_PLEDGE | TuShare 股权质押明细 | tushare | A | event_driven | 0.90 |
| DS_TUSHARE_HOLDER_TRADE | TuShare 股东增减持 | tushare | A | event_driven | 0.90 |
| DS_TUSHARE_NEW_SHARE | TuShare IPO新股 | tushare | A | event_driven | 0.95 |
| DS_TUSHARE_DIVIDEND | TuShare 分红送配 | tushare | A | event_driven | 0.95 |
| DS_TUSHARE_STOCK_BASIC | TuShare 股票基础信息 | tushare | A | weekly | 0.95 |
| DS_TUSHARE_STOCK_COMPANY | TuShare 公司信息 | tushare | A | weekly | 0.95 |
| DS_TUSHARE_NAMECHANGE | TuShare 股票曾用名 | tushare | A | weekly | 0.95 |
| DS_TUSHARE_REPORT_RC | TuShare 券商盈利预测 | tushare | A | daily_17:00 | 0.85 |
| DS_TUSHARE_CN_MACRO | TuShare 中国宏观 | tushare | A | monthly | 0.90 |
| DS_TUSHARE_US_TYCR | TuShare 美债收益率 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_LIBOR | TuShare Libor | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_SHIBOR | TuShare Shibor | tushare | A | daily | 0.90 |
| DS_TUSHARE_LPR | TuShare LPR | tushare | A | monthly_20 | 0.90 |
| DS_TUSHARE_WZ | TuShare 温州民间利率 | tushare | A | weekly | 0.85 |
| DS_TUSHARE_GZ | TuShare 广州民间利率 | tushare | A | weekly | 0.85 |
| DS_TUSHARE_HIBOR | TuShare Hibor | tushare | A | daily | 0.90 |
| DS_TUSHARE_FUT_DAILY | TuShare 期货日线 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUT_BASIC | TuShare 期货基础信息 | tushare | A | weekly | 0.90 |
| DS_TUSHARE_FUT_HOLDING | TuShare 期货持仓排名 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUT_WSR | TuShare 期货仓单 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUT_SETTLE | TuShare 期货结算参数 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_CB_DAILY | TuShare 可转债日线 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_CB_BASIC | TuShare 可转债基础信息 | tushare | A | weekly | 0.90 |
| DS_TUSHARE_FUND_DAILY | TuShare 基金日线 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUND_BASIC | TuShare 基金基础信息 | tushare | A | weekly | 0.90 |
| DS_TUSHARE_FUND_NAV | TuShare 基金净值 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUND_SHARE | TuShare 基金份额 | tushare | A | daily_17:00 | 0.90 |
| DS_TUSHARE_FUND_PORT | TuShare 基金持仓 | tushare | A | quarterly | 0.90 |
| DS_TUSHARE_FUND_MANAGER | TuShare 基金经理 | tushare | A | weekly | 0.90 |
| DS_TUSHARE_FUND_ADJ | TuShare 基金复权因子 | tushare | A | event_driven | 0.90 |
| DS_TUSHARE_FX_DAILY | TuShare 外汇日线 | tushare | A | daily | 0.90 |
| DS_TUSHARE_FX_OBASIC | TuShare 外汇基础信息 | tushare | A | weekly | 0.90 |
| DS_TUSHARE_INDEX_CLASSIFY | TuShare 申万行业分类 | tushare | A | weekly | 0.95 |
| DS_TUSHARE_INDEX_MEMBER | TuShare 行业成分股 | tushare | A | weekly | 0.95 |

### 5.2 akshare 数据源（6 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_AKSHARE_SECTOR_SPOT | akshare 板块实时行情 | akshare | A | intraday | 0.85 |
| DS_AKSHARE_SECTOR_CONS | akshare 板块成分股 | akshare | A | intraday | 0.85 |
| DS_AKSHARE_CNINFO | akshare 巨潮公告 | akshare | S | realtime | 0.95 |
| DS_AKSHARE_IRM | akshare 互动易 | akshare | S | realtime | 0.95 |
| DS_AKSHARE_INST_HOLD | akshare 机构持仓 | akshare | A | quarterly | 0.85 |
| DS_AKSHARE_BOND_YIELD | akshare 国债收益率 | akshare | A | daily_17:00 | 0.85 |

### 5.3 levistock 数据源（4 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_LEVISTOCK_EMOTION | levistock 市场情绪 | levistock | B | intraday | 0.80 |
| DS_LEVISTOCK_NEWS | levistock 快讯 | levistock | A | realtime | 0.85 |
| DS_LEVISTOCK_ZT_POOL | levistock 涨停池 | levistock | B | intraday | 0.80 |
| DS_LEVISTOCK_SECTOR | levistock 板块 | levistock | B | intraday | 0.80 |

### 5.4 腾讯财经数据源（1 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_TENCENT_QUOTE | 腾讯财经实时行情 | tencent | B | realtime | 0.85 |

### 5.5 雪球数据源（1 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_XUEQIU_IND_COMPARE | 雪球行业估值对比 | xueqiu | A | quarterly | 0.85 |

### 5.6 特殊类型数据源（5 个）

| ID | name | protocol | authority_level | refresh_time | reliability_score |
| :--- | :--- | :--- | :---: | :---: | :---: |
| DS_WEB_SEARCH | 站内搜索 | web_search | S/C | realtime | 0.70 |
| DS_LLM_GEN | LLM 生成分析 | llm_gen | C | event_driven | 0.65 |
| DS_LOCAL_CALC | 本地计算 | local_calc | A | event_driven | 1.00 |


## 第六部分：DataField 汇总（按 Concept 分组）

> **📄 完整属性清单**：每个 DataField 的完整属性（含 ID、standard_name、alias、description、data_type、unit、authority_level、refresh_time、默认数据源 ID）已整理至独立文档 **`datafield_detailed_design.md`**，本部分仅提供各 Concept 下的 DataField ID 列表，便于整体概览。

### 6.1 第一组：市场全景层（4 个 Concept）

**CONCEPT_MARKET_INDEX（17 个）：**
FIELD_INDEX_NAME, FIELD_INDEX_CODE, FIELD_INDEX_PRICE, FIELD_INDEX_PCT_CHG, FIELD_INDEX_CHG, FIELD_INDEX_HIGH, FIELD_INDEX_LOW, FIELD_INDEX_OPEN, FIELD_INDEX_PRE_CLOSE, FIELD_INDEX_VOL, FIELD_INDEX_AMOUNT, FIELD_INDEX_SWING, FIELD_INDEX_TOTAL_MV, FIELD_INDEX_FLOAT_MV, FIELD_INDEX_PE, FIELD_INDEX_PB, FIELD_INDEX_TURNOVER

**CONCEPT_MARKET_SENTIMENT（13 个）：**
FIELD_MARKET_HEAT, FIELD_MARKET_BALANCE, FIELD_MARKET_UP_RATIO, FIELD_MARKET_PROFIT_RATIO, FIELD_LIMIT_UP_COUNT, FIELD_LIMIT_DOWN_COUNT, FIELD_LIMIT_UP_BOARD, FIELD_NEWS_TITLE, FIELD_NEWS_CONTENT, FIELD_NEWS_TIME, FIELD_UP_COUNT, FIELD_DOWN_COUNT

**CONCEPT_SECTOR_REALTIME（16 个）：**
FIELD_SECTOR_NAME, FIELD_SECTOR_CODE, FIELD_SECTOR_PRICE, FIELD_SECTOR_PCT_CHG, FIELD_SECTOR_AMOUNT, FIELD_SECTOR_TURNOVER, FIELD_SECTOR_AMPLITUDE, FIELD_SECTOR_LEAD_STOCK, FIELD_SECTOR_LEAD_CODE, FIELD_SECTOR_LEAD_CHG, FIELD_SECTOR_MAIN_INFLOW, FIELD_SECTOR_UP_COUNT, FIELD_SECTOR_DOWN_COUNT, FIELD_SECTOR_TOTAL_MV, FIELD_SECTOR_TOP_DROP, FIELD_SECTOR_TOP_DROP_CHG

**CONCEPT_LHB_BLOCKTRADE（19 个）：**
FIELD_LHB_STOCK_NAME, FIELD_LHB_PCT_CHG, FIELD_LHB_TURNOVER, FIELD_LHB_AMOUNT, FIELD_LHB_BUY, FIELD_LHB_SELL, FIELD_LHB_NET, FIELD_LHB_NET_RATE, FIELD_LHB_AMOUNT_RATE, FIELD_LHB_REASON, FIELD_LHB_EXALTER, FIELD_LHB_SIDE, FIELD_LHB_INST_BUY, FIELD_LHB_INST_SELL, FIELD_BLOCK_PRICE, FIELD_BLOCK_VOL, FIELD_BLOCK_AMOUNT, FIELD_BLOCK_BUYER, FIELD_BLOCK_SELLER

### 6.2 第二组：行业与产业链层（5 个 Concept）

**CONCEPT_INDUSTRY_CLASSIFY（11 个）：**
FIELD_INDUSTRY_L1_CODE, FIELD_INDUSTRY_L1_NAME, FIELD_INDUSTRY_L2_CODE, FIELD_INDUSTRY_L2_NAME, FIELD_INDUSTRY_L3_CODE, FIELD_INDUSTRY_L3_NAME, FIELD_INDUSTRY_MEMBER, FIELD_INDUSTRY_MEMBER_NAME, FIELD_INDUSTRY_IN_DATE, FIELD_INDUSTRY_OUT_DATE, FIELD_INDUSTRY_IS_NEW

**CONCEPT_INDUSTRY_BG（4 个）：**
FIELD_INDUSTRY_BG_TECH, FIELD_INDUSTRY_BG_CHAIN, FIELD_INDUSTRY_BG_POLICY, FIELD_INDUSTRY_BG_PLAYERS

**CONCEPT_PATH_ANALYSIS（6 个）：**
FIELD_PATH_ID, FIELD_PATH_DIMENSION, FIELD_PATH_DESC, FIELD_PATH_ENTRY, FIELD_PATH_SIGNAL, FIELD_PATH_PRIORITY

**CONCEPT_POLICY_ORIGINAL（6 个）：**
FIELD_POLICY_TITLE, FIELD_POLICY_DEPT, FIELD_POLICY_DATE, FIELD_POLICY_TYPE, FIELD_POLICY_FULLTEXT, FIELD_POLICY_LINK

### 6.3 第三组：公司基本面层（7 个 Concept）

**CONCEPT_REALTIME_QUOTE（26 个）：**
FIELD_QUOTE_NAME, FIELD_QUOTE_CODE, FIELD_QUOTE_PRICE, FIELD_QUOTE_PCT_CHG, FIELD_QUOTE_CHG, FIELD_QUOTE_VOL, FIELD_QUOTE_AMOUNT, FIELD_QUOTE_HIGH, FIELD_QUOTE_LOW, FIELD_QUOTE_OPEN, FIELD_QUOTE_PRE_CLOSE, FIELD_TOTAL_MV, FIELD_FLOAT_MV, FIELD_PE_DYNAMIC, FIELD_PE_TTM, FIELD_PB, FIELD_PS_TTM, FIELD_TURNOVER_RATE, FIELD_VOLUME_RATIO, FIELD_AMPLITUDE, FIELD_DIVIDEND_YIELD, FIELD_LIMIT_UP, FIELD_LIMIT_DOWN, FIELD_HIGH_52W, FIELD_LOW_52W, FIELD_YTD_PCT

**CONCEPT_HISTORICAL_KLINE（24 个）：**
FIELD_KLINE_DATE, FIELD_KLINE_OPEN, FIELD_KLINE_HIGH, FIELD_KLINE_LOW, FIELD_KLINE_CLOSE, FIELD_KLINE_PRE_CLOSE, FIELD_KLINE_CHG, FIELD_KLINE_PCT_CHG, FIELD_KLINE_VOL, FIELD_KLINE_AMOUNT, FIELD_ADJ_FACTOR, FIELD_MACD_DIF, FIELD_MACD_DEA, FIELD_MACD, FIELD_KDJ_K, FIELD_KDJ_D, FIELD_KDJ_J, FIELD_RSI_6, FIELD_RSI_12, FIELD_RSI_24, FIELD_BOLL_UPPER, FIELD_BOLL_MID, FIELD_BOLL_LOWER, FIELD_CCI

**CONCEPT_FINANCIAL_SUMMARY（21 个）：**
FIELD_FIN_END_DATE, FIELD_FIN_ROE_WAA, FIELD_FIN_ROE_DILUTED, FIELD_FIN_GROSS_MARGIN, FIELD_FIN_NET_MARGIN, FIELD_FIN_OP_MARGIN, FIELD_FIN_REVENUE_YOY, FIELD_FIN_PROFIT_YOY, FIELD_FIN_DEBT_RATIO, FIELD_FIN_EQUITY_MULT, FIELD_FIN_ASSETS_TURN, FIELD_FIN_INV_TURN, FIELD_FIN_AR_TURN, FIELD_FIN_OCF_TO_OR, FIELD_FIN_EPS, FIELD_FIN_DT_EPS, FIELD_FIN_BPS, FIELD_FIN_OCFPS, FIELD_FIN_CAPITAL_RESERVE, FIELD_FIN_UNDIST_PROFIT, FIELD_FIN_RD_RATIO

**CONCEPT_FINANCIAL_DEEP（18 个）：**
FIELD_FIN_ROIC, FIELD_FIN_ROE_DT, FIELD_FIN_EBIT, FIELD_FIN_EBITDA, FIELD_FIN_EBIT_RATIO, FIELD_FIN_INTEREST_COVER, FIELD_FIN_DEBT_TO_CAPITAL, FIELD_FIN_FCFF, FIELD_FIN_FCFE, FIELD_FIN_FA_TURN, FIELD_FIN_CA_TURN, FIELD_FIN_Q_ROE, FIELD_FIN_Q_GROSS_MARGIN, FIELD_FIN_Q_NET_MARGIN, FIELD_FIN_Q_REVENUE_YOY, FIELD_FIN_Q_PROFIT_YOY, FIELD_FIN_IMPAIR_RATIO, FIELD_FIN_INVEST_INCOME_RATIO

**CONCEPT_FINANCIAL_STATEMENTS（34 个）：**
FIELD_FS_END_DATE, FIELD_FS_TOTAL_REVENUE, FIELD_FS_REVENUE, FIELD_FS_TOTAL_COGS, FIELD_FS_OPER_COST, FIELD_FS_SELL_EXP, FIELD_FS_ADMIN_EXP, FIELD_FS_RD_EXP, FIELD_FS_FIN_EXP, FIELD_FS_OPER_PROFIT, FIELD_FS_TOTAL_PROFIT, FIELD_FS_NET_PROFIT, FIELD_FS_NET_PROFIT_ATTR, FIELD_FS_MINORITY_GAIN, FIELD_FS_BASIC_EPS, FIELD_FS_DILUTED_EPS, FIELD_FS_TOTAL_ASSETS, FIELD_FS_TOTAL_LIAB, FIELD_FS_TOTAL_EQUITY, FIELD_FS_MONEY_CAP, FIELD_FS_ACCOUNTS_RECV, FIELD_FS_INVENTORY, FIELD_FS_FIXED_ASSETS, FIELD_FS_CIP, FIELD_FS_INTAN_ASSETS, FIELD_FS_GOODWILL, FIELD_FS_ST_BORR, FIELD_FS_LT_BORR, FIELD_FS_ACCOUNTS_PAY, FIELD_FS_OPER_CF, FIELD_FS_INVEST_CF, FIELD_FS_FINANCE_CF, FIELD_FS_END_CASH, FIELD_FS_FREE_CF

**CONCEPT_VALUATION_COMPARE（10 个）：**
FIELD_VAL_PE_TTM, FIELD_VAL_PE_PCT, FIELD_VAL_PB, FIELD_VAL_PB_PCT, FIELD_VAL_PS_TTM, FIELD_VAL_PS_PCT, FIELD_VAL_IND_PE, FIELD_VAL_IND_PB, FIELD_VAL_IND_ROE, FIELD_VAL_RATING

**CONCEPT_COMPANY_PROFILE（22 个）：**
FIELD_PROFILE_FULLNAME, FIELD_PROFILE_NAME, FIELD_PROFILE_CODE, FIELD_PROFILE_INDUSTRY, FIELD_PROFILE_AREA, FIELD_PROFILE_LIST_DATE, FIELD_PROFILE_DELIST_DATE, FIELD_PROFILE_ACT_NAME, FIELD_PROFILE_ACT_TYPE, FIELD_PROFILE_IS_HS, FIELD_PROFILE_EXCHANGE, FIELD_PROFILE_CHAIRMAN, FIELD_PROFILE_MANAGER, FIELD_PROFILE_SECRETARY, FIELD_PROFILE_REG_CAPITAL, FIELD_PROFILE_SETUP_DATE, FIELD_PROFILE_EMPLOYEES, FIELD_PROFILE_WEBSITE, FIELD_PROFILE_OFFICE, FIELD_PROFILE_MAIN_BUSINESS, FIELD_PROFILE_BUSINESS_SCOPE, FIELD_PROFILE_NAME_HISTORY

### 6.4 第四组：公司治理与事件层（6 个 Concept）

**CONCEPT_TOP_HOLDERS（8 个）：**
FIELD_HOLDER_ANN_DATE, FIELD_HOLDER_END_DATE, FIELD_HOLDER_NAME, FIELD_HOLDER_SHARES, FIELD_HOLDER_RATIO, FIELD_HOLDER_FLOAT_RATIO, FIELD_HOLDER_CHANGE, FIELD_HOLDER_TYPE

**CONCEPT_INSTITUTION_RATING（12 个）：**
FIELD_INST_END_DATE, FIELD_INST_COUNT, FIELD_INST_RATIO, FIELD_INST_CHANGE, FIELD_INST_ORG_NAME, FIELD_INST_REPORT_DATE, FIELD_INST_REPORT_TITLE, FIELD_INST_RATING, FIELD_INST_FORECAST_EPS, FIELD_INST_FORECAST_ROE, FIELD_INST_TARGET_MAX, FIELD_INST_TARGET_MIN

**CONCEPT_ANNOUNCEMENT（4 个）：**
FIELD_ANNOUNCE_TITLE, FIELD_ANNOUNCE_DATE, FIELD_ANNOUNCE_TYPE, FIELD_ANNOUNCE_LINK

**CONCEPT_IRM_QA（5 个）：**
FIELD_IRM_QUESTION, FIELD_IRM_QUESTION_DATE, FIELD_IRM_ANSWER, FIELD_IRM_ANSWER_DATE, FIELD_IRM_ASKER

**CONCEPT_IPO_INFO（11 个）：**
FIELD_IPO_CODE, FIELD_IPO_NAME, FIELD_IPO_PRICE, FIELD_IPO_AMOUNT, FIELD_IPO_MARKET_AMOUNT, FIELD_IPO_LIMIT_AMOUNT, FIELD_IPO_FUNDS, FIELD_IPO_PE, FIELD_IPO_BALLOT, FIELD_IPO_IPO_DATE, FIELD_IPO_LIST_DATE

**CONCEPT_DIVIDEND（11 个）：**
FIELD_DIV_END_DATE, FIELD_DIV_ANN_DATE, FIELD_DIV_PROC, FIELD_DIV_CASH, FIELD_DIV_CASH_TAX, FIELD_DIV_STK, FIELD_DIV_STK_BO, FIELD_DIV_STK_CO, FIELD_DIV_RECORD_DATE, FIELD_DIV_EX_DATE, FIELD_DIV_PAY_DATE

### 6.5 第五组：资金与交易层（5 个 Concept）

**CONCEPT_FUND_FLOW（19 个）：**
FIELD_FLOW_DATE, FIELD_FLOW_SMALL_BUY_VOL, FIELD_FLOW_SMALL_BUY_AMT, FIELD_FLOW_SMALL_SELL_VOL, FIELD_FLOW_SMALL_SELL_AMT, FIELD_FLOW_MEDIUM_BUY_VOL, FIELD_FLOW_MEDIUM_BUY_AMT, FIELD_FLOW_MEDIUM_SELL_VOL, FIELD_FLOW_MEDIUM_SELL_AMT, FIELD_FLOW_LARGE_BUY_VOL, FIELD_FLOW_LARGE_BUY_AMT, FIELD_FLOW_LARGE_SELL_VOL, FIELD_FLOW_LARGE_SELL_AMT, FIELD_FLOW_ELG_BUY_VOL, FIELD_FLOW_ELG_BUY_AMT, FIELD_FLOW_ELG_SELL_VOL, FIELD_FLOW_ELG_SELL_AMT, FIELD_FLOW_NET_VOL, FIELD_FLOW_NET_AMT

**CONCEPT_NORTHBOUND（11 个）：**
FIELD_NORTH_DATE, FIELD_NORTH_NET, FIELD_NORTH_SH_NET, FIELD_NORTH_SZ_NET, FIELD_NORTH_GGT_SS, FIELD_NORTH_GGT_SZ, FIELD_NORTH_HOLD_VOL, FIELD_NORTH_HOLD_RATIO, FIELD_NORTH_TOP10, FIELD_NORTH_TOP10_AMT, FIELD_NORTH_TOP10_NET

**CONCEPT_MARGIN（8 个）：**
FIELD_MARGIN_DATE, FIELD_MARGIN_BALANCE, FIELD_MARGIN_BUY, FIELD_MARGIN_REPAY, FIELD_MARGIN_SHORT_BALANCE, FIELD_MARGIN_SHORT_VOL, FIELD_MARGIN_SHORT_RESERVE, FIELD_MARGIN_TOTAL

**CONCEPT_LIMIT_UP_DOWN（11 个）：**
FIELD_LIMIT_DATE, FIELD_LIMIT_CODE, FIELD_LIMIT_PRE_CLOSE, FIELD_LIMIT_UP_PRICE, FIELD_LIMIT_DOWN_PRICE, FIELD_LIMIT_STATUS, FIELD_LIMIT_CONTINUOUS, FIELD_LIMIT_FIRST_TIME, FIELD_LIMIT_LAST_TIME, FIELD_LIMIT_OPEN_TIMES, FIELD_LIMIT_SECTOR

**CONCEPT_PLEDGE_HOLDER_TRADE（12 个）：**
FIELD_PLEDGE_HOLDER, FIELD_PLEDGE_AMOUNT, FIELD_PLEDGE_RATIO, FIELD_PLEDGE_PLEDGOR, FIELD_PLEDGE_START, FIELD_PLEDGE_END, FIELD_PLEDGE_IS_RELEASE, FIELD_TRADE_ANN_DATE, FIELD_TRADE_TYPE, FIELD_TRADE_VOL, FIELD_TRADE_AFTER_SHARE, FIELD_TRADE_AVG_PRICE

### 6.6 第六组：宏观与跨资产层（8 个 Concept）

**CONCEPT_MACRO_ECONOMY（36 个）：**
FIELD_MACRO_QUARTER, FIELD_MACRO_GDP, FIELD_MACRO_GDP_YOY, FIELD_MACRO_GDP_PI, FIELD_MACRO_GDP_SI, FIELD_MACRO_GDP_TI, FIELD_MACRO_CPI_VAL, FIELD_MACRO_CPI_YOY, FIELD_MACRO_CPI_MOM, FIELD_MACRO_PPI_YOY, FIELD_MACRO_PPI_MOM, FIELD_MACRO_PMI, FIELD_MACRO_NON_PMI, FIELD_MACRO_COMPOSITE_PMI, FIELD_MACRO_PMI_PRODUCTION, FIELD_MACRO_PMI_NEW_ORDERS, FIELD_MACRO_PMI_LARGE, FIELD_MACRO_PMI_MEDIUM, FIELD_MACRO_PMI_SMALL, FIELD_MACRO_M0, FIELD_MACRO_M1, FIELD_MACRO_M2, FIELD_MACRO_M2_YOY, FIELD_MACRO_SF_MONTH, FIELD_MACRO_SF_CUM, FIELD_MACRO_SF_STOCK, FIELD_MACRO_US_10Y, FIELD_MACRO_US_2Y, FIELD_MACRO_US_1M, FIELD_MACRO_US_3M, FIELD_MACRO_US_6M, FIELD_MACRO_US_5Y, FIELD_MACRO_US_30Y, FIELD_MACRO_LIBOR_ON, FIELD_MACRO_LIBOR_3M, FIELD_MACRO_LIBOR_6M

**CONCEPT_INTEREST_RATE（24 个）：**
FIELD_RATE_DATE, FIELD_RATE_SHIBOR_ON, FIELD_RATE_SHIBOR_1W, FIELD_RATE_SHIBOR_2W, FIELD_RATE_SHIBOR_1M, FIELD_RATE_SHIBOR_3M, FIELD_RATE_SHIBOR_6M, FIELD_RATE_SHIBOR_9M, FIELD_RATE_SHIBOR_1Y, FIELD_RATE_LPR_1Y, FIELD_RATE_LPR_5Y, FIELD_RATE_WZ_COMP, FIELD_RATE_WZ_1M, FIELD_RATE_WZ_3M, FIELD_RATE_WZ_6M, FIELD_RATE_WZ_12M, FIELD_RATE_GZ_1M, FIELD_RATE_GZ_3M, FIELD_RATE_GZ_6M, FIELD_RATE_GZ_12M, FIELD_RATE_HIBOR_ON, FIELD_RATE_HIBOR_1W, FIELD_RATE_HIBOR_1M, FIELD_RATE_HIBOR_3M

**CONCEPT_FOREX_MAJOR（12 个）：**
FIELD_FOREX_PAIR, FIELD_FOREX_DATE, FIELD_FOREX_BID_OPEN, FIELD_FOREX_BID_CLOSE, FIELD_FOREX_BID_HIGH, FIELD_FOREX_BID_LOW, FIELD_FOREX_ASK_OPEN, FIELD_FOREX_ASK_CLOSE, FIELD_FOREX_ASK_HIGH, FIELD_FOREX_ASK_LOW, FIELD_FOREX_EXCHANGE, FIELD_FOREX_PIP

**CONCEPT_BOND_YIELD_CURVE（7 个）：**
FIELD_BOND_CURVE_DATE, FIELD_BOND_CURVE_1Y, FIELD_BOND_CURVE_2Y, FIELD_BOND_CURVE_5Y, FIELD_BOND_CURVE_10Y, FIELD_BOND_CURVE_30Y, FIELD_BOND_CURVE_SPREAD

**CONCEPT_FUTURES（16 个）：**
FIELD_FUT_TS_CODE, FIELD_FUT_NAME, FIELD_FUT_DATE, FIELD_FUT_PRE_CLOSE, FIELD_FUT_PRE_SETTLE, FIELD_FUT_OPEN, FIELD_FUT_HIGH, FIELD_FUT_LOW, FIELD_FUT_CLOSE, FIELD_FUT_SETTLE, FIELD_FUT_CHG1, FIELD_FUT_CHG2, FIELD_FUT_VOL, FIELD_FUT_AMOUNT, FIELD_FUT_OI, FIELD_FUT_OI_CHG

**CONCEPT_FUTURES_DETAIL（14 个）：**
FIELD_FUT_DETAIL_BROKER, FIELD_FUT_DETAIL_VOL, FIELD_FUT_DETAIL_VOL_CHG, FIELD_FUT_DETAIL_LONG, FIELD_FUT_DETAIL_LONG_CHG, FIELD_FUT_DETAIL_SHORT, FIELD_FUT_DETAIL_SHORT_CHG, FIELD_FUT_WSR_WAREHOUSE, FIELD_FUT_WSR_PRE_VOL, FIELD_FUT_WSR_VOL, FIELD_FUT_WSR_VOL_CHG, FIELD_FUT_WSR_PD, FIELD_FUT_SETTLE_FEE, FIELD_FUT_SETTLE_MARGIN

**CONCEPT_CONVERTIBLE_BOND（27 个）：**
FIELD_CB_TS_CODE, FIELD_CB_NAME, FIELD_CB_STK_CODE, FIELD_CB_STK_NAME, FIELD_CB_TYPE, FIELD_CB_DATE, FIELD_CB_OPEN, FIELD_CB_HIGH, FIELD_CB_LOW, FIELD_CB_CLOSE, FIELD_CB_PCT_CHG, FIELD_CB_VOL, FIELD_CB_AMOUNT, FIELD_CB_BOND_VALUE, FIELD_CB_BOND_OVER_RATE, FIELD_CB_CB_VALUE, FIELD_CB_CB_OVER_RATE, FIELD_CB_ISSUE_SIZE, FIELD_CB_REMAIN_SIZE, FIELD_CB_COUPON_RATE, FIELD_CB_FIRST_CONV_PRICE, FIELD_CB_CONV_PRICE, FIELD_CB_CONV_START_DATE, FIELD_CB_MATURITY_DATE, FIELD_CB_RATING, FIELD_CB_CALL_CLAUSE, FIELD_CB_PUT_CLAUSE

**CONCEPT_FUND_ETF（26 个）：**
FIELD_FUND_TS_CODE, FIELD_FUND_NAME, FIELD_FUND_DATE, FIELD_FUND_OPEN, FIELD_FUND_HIGH, FIELD_FUND_LOW, FIELD_FUND_CLOSE, FIELD_FUND_PCT_CHG, FIELD_FUND_VOL, FIELD_FUND_AMOUNT, FIELD_FUND_UNIT_NAV, FIELD_FUND_ACCUM_NAV, FIELD_FUND_ADJ_FACTOR, FIELD_FUND_SHARES, FIELD_FUND_MANAGEMENT, FIELD_FUND_CUSTODIAN, FIELD_FUND_TYPE, FIELD_FUND_FOUND_DATE, FIELD_FUND_LIST_DATE, FIELD_FUND_M_FEE, FIELD_FUND_C_FEE, FIELD_FUND_MANAGER_NAME, FIELD_FUND_PORT_SYMBOL, FIELD_FUND_PORT_MKV, FIELD_FUND_PORT_STK_RATIO, FIELD_FUND_PORT_FLOAT_RATIO

### 6.7 第七组：文档生成层（6 个 Concept，全部复用）

> 文档生成层的 DataField 全部复用前面各层的字段，不独立创建节点。完整复用清单及映射关系详见 **`datafield_detailed_design.md`** 第七组。


## 第七部分：站内搜索信源映射

| 信源名称 | site:url | 标签 | 关联 IntentConcept |
| :--- | :--- | :--- | :--- |
| 东方财富网 | `site:eastmoney.com` | `#行情数据` `#资金流向` `#公司公告` | 1, 3, 4, 9, 10, 18, 22, 23, 34 |
| 新浪财经 | `site:finance.sina.com.cn` | `#行情数据` `#财务数据` `#财经新闻` | 2, 9, 11 |
| 证券时报网 | `site:stcn.com` | `#官方媒体` `#政策发布` `#公告解读` | 2, 6, 7, 8, 18, 37, 38, 39 |
| 同花顺 | `site:10jqka.com.cn` | `#行情数据` `#概念板块` `#数据核实` | 3, 5 |
| 中国政府网及各部委官网 | `site:gov.cn` | `#政策原文` `#权威信源` | 8, 27 |
| 巨潮资讯网 | `site:cninfo.com.cn` | `#法定披露` `#官方公告` `#权威信源` | 15, 16, 18, 26, 37, 38, 39 |
| 财联社 | `site:cls.cn` | `#即时新闻` `#快讯` `#政策解读` | 2, 6, 7, 8 |
| 第一财经 | `site:yicai.com` | `#财经新闻` `#深度报道` | 2, 6 |
| 雪球 | `site:xueqiu.com` | `#投资者社区` `#市场情绪` `#UGC` | 2 |


## 第八部分：工作流程图

### 8.1 整体架构流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             用户输入问题                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【LLM 解析层】                                      │
│  1. 提取目标指标词（如"净利润"）                                            │
│  2. 提取实体参数（如 stock_code: "300750"）                                │
│  3. 判断意图类型（analysis/fact）                                          │
│  4. 匹配 IntentConcept（通过 seed_keywords 分类）                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【知识图谱路由层】                                   │
│                                                                             │
│  Step 1: 精准寻的                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  用目标指标词匹配 DataField.alias                                    │   │
│  │  → 命中具体 DataField                                               │   │
│  │  （若未命中，用 Embedding 做向量 Top-K 检索）                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  Step 2: 查询 BELONGS_TO_CONCEPT 关系，获取字段所属的 Concept              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MATCH (f:DataField)-[:BELONGS_TO_CONCEPT]->(c:IntentConcept)      │   │
│  │  WHERE f.id = $field_id                                            │   │
│  │  RETURN c.id                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  Step 3: 近邻扩散（仅当 intent_type == "analysis"）                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  从命中的 DataField 出发，沿 SEMANTIC_SIMILAR_TO 关系扩散            │   │
│  │  取 level = "high" 和 "medium" 的所有邻居                            │   │
│  │  → 扩散出相关字段集群                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  Step 4: 数据源反查                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  遍历所有扩散到的 DataField，提取各自的 default_datasource_id        │   │
│  │  按 DataSource 分组，生成多源取数计划                                 │   │
│  │  若为站内搜索类，生成 site_search_urls + 关键词组合                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【Python 编排层】                                   │
│                                                                             │
│  1. 按取数计划依次调用 DataSource（API 或站内搜索）                         │
│  2. 根据 DataField.standard_name 对返回数据做字段切片                       │
│  3. 合并多源数据                                                            │
│  4. 返回紧凑数据表格                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【LLM 分析层】                                      │
│  接收紧凑数据表格，结合用户原始问题进行深度分析，生成最终回答               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 两种意图模式的分支逻辑

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


## 第九部分：开发实施步骤

### 第一阶段：环境准备（第 1-2 天）

- 安装 Python 3.10+，创建虚拟环境
- 安装基础依赖库：akshare、tushare、levistock、pandas、numpy、neo4j
- 安装并启动 Neo4j 图数据库（社区版）
- 下载 Qwen3-Embedding-4B GGUF Q4_K_M 量化模型（约 2.5GB）
- 安装 llama-cpp-python，验证模型可正常加载并生成向量
- 配置 TuShare Token 环境变量


### 第二阶段：数据准备（第 3-4 天）

- 遍历所有数据源接口，按本设计文档第五部分创建 DataSource 清单
- 按 `datafield_detailed_design.md` 创建 DataField 清单（含所有属性的初始值）
- 按本设计文档第四部分创建 IntentConcept 清单
- 为每个 IntentConcept 配置 site_search_urls（如有站内搜索入口）
- 将上述数据整理为 CSV 文件，便于批量导入


### 第三阶段：图谱构建 - 节点写入与 Embedding 生成（第 5-7 天）

#### 3.1 批量写入节点

- 连接 Neo4j，批量写入 IntentConcept、DataField、DataSource 节点
- 写入时仅填充结构化属性（id、name、description、seed_keywords 等），不包含 embedding

#### 3.2 生成 DataField 的 Embedding

**目的**：为每个 DataField 生成语义向量，用于后续的 SEMANTIC_SIMILAR_TO 关系计算和向量检索兜底。

**拼接文本规则**：
```
embedding_text = standard_name + " " + " ".join(alias) + " " + description
```

**执行方式**：
```
对每个 DataField 节点：
    1. 按上述规则拼接文本
    2. 调用 Embedding 模型（Qwen3-Embedding-4B）生成 1024 维向量
    3. 将向量写回 DataField 节点的 embedding 属性
    4. 每处理 50 个字段输出一次进度，记录日志
```

#### 3.3 生成 IntentConcept 的 Embedding

**目的**：为每个 IntentConcept 生成语义向量，用于 LLM 意图识别失败时的向量检索兜底。

**拼接文本规则**：
```
embedding_text = name + " " + description
```

**执行方式**：
```
对每个 IntentConcept 节点：
    1. 按上述规则拼接文本
    2. 调用 Embedding 模型生成 1024 维向量
    3. 将向量写回 IntentConcept 节点的 embedding 属性
```

#### 3.4 计算 SEMANTIC_SIMILAR_TO 关系

**执行方式**：
```
获取所有 DataField 的 id 和 embedding
N = DataField 总数（约 405 个）

对每对 (i, j)，其中 i < j：
    1. 计算余弦相似度：cos_sim = dot(embedding_i, embedding_j) / (norm_i * norm_j)
    2. 若 cos_sim >= 0.75：
        创建 SEMANTIC_SIMILAR_TO 双向关系
        设置属性：
          - cosine_similarity = cos_sim
          - level = "high" if cos_sim >= 0.85 else "medium"
    3. 若 0.65 <= cos_sim < 0.75：
        不创建关系，仅记录到日志
    4. 每完成 1000 对计算输出一次进度
```

**性能估算**：
- 总计算量：405 × 404 / 2 ≈ 81,810 对
- 预计耗时：约 15-25 分钟（单次推理约 10-20ms）

#### 3.5 向量索引建立（可选，用于查询优化）

- 将所有 DataField 的 embedding 导出到 Faiss 索引，用于查询时的 Top-K 向量检索
- 将所有 IntentConcept 的 embedding 导出到另一个 Faiss 索引，用于意图兜底匹配


### 第四阶段：图谱构建 - BELONGS_TO_CONCEPT 关系建立（第 7-9 天）

#### 4.1 设计思路

采用 **"LLM 辅助梳理 + 人工确认"** 的半自动流程：
1. LLM 根据 DataField 的字段含义和 IntentConcept 的业务描述，自动推断从属关系
2. 生成候选关系列表，标记为 `is_auto_suggested = true`、`is_approved = false`
3. 管理员在后台确认/修正后，批量写入图数据库

#### 4.2 准备 LLM 输入数据

将 DataField 和 IntentConcept 的完整信息整理为结构化输入：
- DataField 列表（含 id、standard_name、alias、description）—— 从 `datafield_detailed_design.md` 提取
- IntentConcept 列表（含 id、name、description、default_seed_fields）

**数据量估算**：
- DataField：约 405 个
- IntentConcept：41 个
- 理论最大配对：405 × 41 = 16,605 对（但实际只有语义相关的才会被输出）

#### 4.3 调用 LLM 生成候选关系

**Prompt 设计要点**：
- 明确要求 LLM 为每个 DataField 判断其属于哪些 IntentConcept
- 输出格式为 JSON 数组，每项包含 `field_id`、`concept_id`、`relevance_score`（0-1）
- 允许一个字段属于多个 Concept
- relevance_score 定义：1.0=核心必需，0.7=重要辅助，0.5=一般参考

**分批处理策略**：
- 将 DataField 分批（每批 50-80 个）分别调用 LLM
- 每批的 Prompt 中仍包含完整的 41 个 IntentConcept 列表

#### 4.4 人工确认

**后台界面设计**：
- 按 Concept 分组展示待确认的候选字段列表（按 relevance_score 降序排列）
- 每个条目显示：字段名、字段描述、relevance_score、操作按钮（接受/拒绝/修改分数）
- 管理员可批量接受（如 relevance_score ≥ 0.8 的全部接受）
- 管理员可手动添加未被 LLM 推荐的字段

**确认流程**：
```
1. 管理员登录后台，进入"关系确认"页面
2. 选择需要确认的 Concept
3. 查看候选字段列表，逐个或批量确认
4. 确认后，关系属性更新：is_approved = true
5. 所有关系确认后，方可进入下一阶段
```

**预估工作量**：
- 全量初筛：约 2-3 天可完成
- 增量更新：新增字段时只需处理新增候选

#### 4.5 写入图数据库

```
对每条已确认的关系（is_approved = true）：
    CREATE (f:DataField {id: $field_id})-[:BELONGS_TO_CONCEPT {
        relevance_score: $score,
        is_approved: true,
        is_auto_suggested: false
    }]->(c:IntentConcept {id: $concept_id})
```

#### 4.6 增量更新机制

**当新 DataField 加入时**：
```
1. 为新字段生成 embedding
2. 计算新字段与所有现有 DataField 的相似度，创建 SEMANTIC_SIMILAR_TO 关系
3. 将新字段加入下一批 LLM 推断队列
4. 管理员确认从属关系后写入 BELONGS_TO_CONCEPT
5. 更新 Faiss 向量索引
```


### 第五阶段：查询与测试（第 9-10 天）

- 实现 LLM 解析函数（提取 target_metrics、entities、intent_type）
- 实现图谱查询函数（匹配 DataField.alias，未命中则用向量检索）
- 实现 BELONGS_TO_CONCEPT 关系查询（获取字段所属 Concept）
- 实现近邻扩散函数（根据 intent_type 决定扩散范围）
- 实现数据源反查函数（按 DataSource 分组生成取数计划）
- 实现 Python 编排层（执行取数、字段切片、多源合并）
- 端到端测试覆盖 5 类核心场景（事实查询、分析查询、同义词匹配、概念兜底、多源备选）


### 第六阶段：优化与扩展（持续）

- 引入向量索引库（Faiss/HNSW），优化 Embedding 检索性能
- 实现热点查询结果 LRU 缓存
- 封装为 FastAPI 服务，提供 HTTP 接口
- 建立关系确认的自动化监控


## 第十部分：技术栈总结

| 组件 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 图数据库 | Neo4j 5.x | 生产推荐，支持属性图 |
| 轻量替代 | NetworkX + JSON | 开发原型快速验证 |
| Embedding 模型 | Qwen3-Embedding-4B (GGUF Q4_K_M) | 中文能力强，约 2.5GB 显存 |
| 推理框架 | llama-cpp-python | 支持 GGUF 量化模型高效推理 |
| Python 金融库 | akshare / tushare / levistock | 多数据源统一接入 |
| 数据处理 | pandas | DataFrame 切片与合并 |
| 向量加速 | faiss / hnswlib | 可选，提升大规模检索性能 |
| API 框架 | FastAPI | 封装图谱查询服务 |
| LLM 辅助 | DeepSeek-V4 | BELONGS_TO_CONCEPT 关系推断 |


## 第十一部分：设计优势总结

| 优势 | 说明 |
| :--- | :--- |
| **无人工维护负担** | 字段间关系由 Embedding 自动计算，新增字段增量挂接 |
| **无别名穷举** | 精确匹配走 alias 数组，兜底走向量相似度，双重保障 |
| **路由无冲突** | 字段直接指向 DataSource，不经过场景中转，消除二义性 |
| **多源融合友好** | 同名字段可建多个 DataField 节点，按时效/权威自动优选 |
| **可动态裁剪** | 关系带级别属性，可按需求取不同梯度的邻居 |
| **增量可扩展** | 新字段加入只需计算其与现有字段的相似度 |
| **字段级时效/权威** | 每个 DataField 独立标记权威度和更新时效 |
| **站内搜索集成** | 统一建模 API 数据和网页端数据，路由层透明处理 |
| **从属关系自动化** | LLM 辅助推断 + 人工确认，比纯手工快 20 倍以上 |
| **单一事实来源** | BELONGS_TO_CONCEPT 由关系层唯一表达，消除数据冗余 |
| **41 个业务场景覆盖** | 从市场全景到文档生成，完整覆盖投资研究全链路 |
| **405 个数据字段** | 覆盖 65 个数据源，字段级精细路由 |


## 附录：文档依赖关系

| 文档 | 用途 | 依赖关系 |
| :--- | :--- | :--- |
| **本文档** | 整体设计与开发方案 | 主文档 |
| **datafield_detailed_design.md** | 405 个 DataField 的完整属性清单 | 被本文档引用，作为 DataField 的详细设计附录 |
| **akshare_description.md** | akshare 接口参考 | 数据源实现参考 |
| **tushare_description.md** | TuShare 接口参考 | 数据源实现参考 |
| **levistock_description.md** | levistock 接口参考 | 数据源实现参考 |
| **需求汇总-完整需求规格说明书v2.22_融合版.md** | 业务需求来源 | 设计输入 |


**文档结束。**