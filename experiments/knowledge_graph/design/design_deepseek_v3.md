以下是修改后的完整知识图谱设计方案报告：


# IRKG v3 知识图谱设计方案（最终版）


## 一、设计哲学

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
| **节点精简极致** | 仅 3 种核心节点 + 站内搜索类信源作为节点属性 |
| **关系带属性** | 关系承载级别、权重等量化属性，支持动态查询裁剪 |
| **多源可备选** | 同一字段可来自多个数据源，按时效性/权威性自动取舍 |


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
│  作用：当用户问题明确提及某类信息时，定位到具体概念            │
│  属性：id, name, description, embedding, seed_keywords,        │
│        requires_entity, default_seed_fields,                   │
│        site_search_urls（站内搜索入口）                        │
│  数量：37 个                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 2: DataField】最小数据原子单元 ★核心节点★            │
│  作用：代表一个具体可返回的数据列，是路由的真正终点            │
│  属性：id, standard_name, alias[], description, embedding,     │
│        default_datasource_id,                                  │
│        data_type, unit, authority_level, refresh_time          │
│  注意：不再存储 belongs_to_concepts 属性（由关系层唯一表达）   │
│  来源：各数据接口的返回字段                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  【Layer 3: DataSource】物理取数指令                           │
│  作用：封装调用接口/爬虫的全部技术细节                        │
│  属性：id, name, protocol, execution_meta, refresh_time,       │
│        authority_level, reliability_score, latency_ms,         │
│        code_format                                            │
│  示例：TuShare.pro_api(), akshare.xxx(), 站内搜索类           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 IntentConcept（意图概念节点）

**身份定义**：用户问题的高层次分类标签，是图谱的“路由入口”。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识，如 `CONCEPT_MARKET_SENTIMENT` |
| `name` | string | ✅ | 业务标准名称，如 `市场情绪与快讯` |
| `description` | text | ✅ | 详细描述，用于生成 Embedding 和向 LLM 解释 |
| `seed_keywords` | string[] | ✅ | 触发关键词（≤5个），用于 LLM 意图识别 |
| `embedding` | float[] | ✅ | 由 name + description 生成的向量，用于语义匹配兜底 |
| `requires_entity` | string[] | ❌ | 必需的实体参数列表，如 `["stock_code"]` |
| `default_seed_fields` | string[] | ✅ | 该概念默认推荐的 3~5 个核心字段 ID |
| `site_search_urls` | string[] | ❌ | 站内搜索入口 URL（如有），如 `site:cninfo.com.cn` |

**界定标准**（满足以下 2 条即可）：

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
| `data_type` | enum | ❌ | 数据类型：float / int / string / date |
| `unit` | string | ❌ | 单位，如 `%`、`亿元`、`倍` |
| `authority_level` | enum | ✅ | 权威等级：`S`/`A`/`B`/`C`，可继承自 DataSource 或覆写 |
| `refresh_time` | enum | ✅ | 更新时效：`realtime`/`intraday`/`daily_17:00`/`daily_20:00`/`weekly`/`quarterly` |

### 2.4 DataSource（数据源节点）

**身份定义**：封装获取数据的技术执行指令。它是图谱的物理执行末端。

**属性详解**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | ✅ | 全局唯一标识 |
| `name` | string | ✅ | 数据源名称 |
| `protocol` | enum | ✅ | 协议类型：`tushare` / `akshare` / `levistock` / `sina` / `tencent` / `xueqiu` / `web_search` |
| `execution_meta` | json | ✅ | 执行元数据。API 存函数名+参数模板；站内搜索存 URL 模板 |
| `refresh_time` | enum | ✅ | 更新时效 |
| `authority_level` | enum | ✅ | 权威等级：`S`/`A`/`B`/`C` |
| `reliability_score` | float | ✅ | 综合可靠度 0~1 |
| `latency_ms` | int | ❌ | 预估响应毫秒数 |
| `code_format` | string | ❌ | 参数格式化规则（如 `SZ_prefix`/`SH_prefix`/`pure_num`） |


## 三、关系设计（2 种核心关系）

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

**含义**：该字段可被用于某个业务场景的分析。**此关系是图谱路由的核心依据**——当用户命中的字段属于某 Concept 时，路由系统可通过此关系确认该字段的所属场景，确定返回哪些相关字段。

**关系属性**：

| 属性名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `relevance_score` | float | ✅ | 该字段对该概念的重要性（0~1），由 LLM 生成时赋值。1.0=核心必需，0.7=重要辅助，0.5=一般参考 |
| `is_approved` | boolean | ✅ | 是否已通过人工确认。初始为 false，管理员确认后改为 true |
| `is_auto_suggested` | boolean | ✅ | 是否为 LLM 自动生成的候选关系。true=待确认，false=已确认或手工添加 |

**建边策略**：**LLM 辅助梳理 + 人工确认**（详见第六部分开发步骤 6.3 和 6.4）

**重要说明**：
- `BELONGS_TO_CONCEPT` 关系是 `DataField` 与 `IntentConcept` 之间**唯一合法的表达方式**
- `DataField` 节点属性中**不再存储** `belongs_to_concepts[]`，避免数据冗余和不一致
- 判断”字段是否属于某 Concept“时，通过查询此关系实现，代码层可加缓存优化


## 四、完整 IntentConcept 清单（37 个）

### 第一组：市场全景层（4 个）


#### 1. 市场整体行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARKET_INDEX` |
| **name** | 市场整体行情 |
| **description** | 主要股票市场指数的实时表现和历史走势，包括A股指数（上证综指、深证成指、创业板指、科创50、沪深300、中证500等）、港股（恒生指数、恒生科技）、美股（道琼斯、纳斯达克、标普500）、欧洲（德国DAX、英国富时100、法国CAC40）、亚太（日经225、韩国KOSPI、台湾加权、印度Sensex）等 |
| **seed_keywords** | 指数、大盘、上证、恒生、纳斯达克、道琼斯 |
| **requires_entity** | [] |
| **default_seed_fields** | 指数名称、当前点位、涨跌幅、最高点、最低点、成交量、成交额 |
| **site_search_urls** | `site:eastmoney.com` 指数行情页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `index_daily`, `index_global` |
| 2 | 🟢 akshare | `index_zh_a_hist`, `index_global_spot_em` |
| 3 | 🟡 levistock | `market_index_em`, `market_index_all_em` |


#### 2. 市场情绪与快讯

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARKET_SENTIMENT` |
| **name** | 市场情绪与快讯 |
| **description** | 全市场情绪指标（市场热度、上涨占比、赚钱效应、涨停梯队、涨跌分布）和实时财经快讯（财联社、华尔街见闻等） |
| **seed_keywords** | 情绪、热度、赚钱效应、快讯、电报、涨停梯队 |
| **requires_entity** | [] |
| **default_seed_fields** | 市场热度、成交额、上涨占比、赚钱效应、涨停梯队列表、涨跌家数、快讯标题、快讯内容 |
| **site_search_urls** | `site:cls.cn` 快讯栏目；`site:xueqiu.com` 热门讨论 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🟡 levistock | `market_emotion_cls`, `news_telegraph_cls` |
| 2 | 🔵 TuShare | `daily_basic`（涨跌停状态）, `news`, `major_news` |
| 3 | 🌐 站内搜索 | 财联社 `site:cls.cn` |


#### 3. 板块实时行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_SECTOR_REALTIME` |
| **name** | 板块实时行情 |
| **description** | 申万行业板块（31个一级、134个二级、346个三级）和概念板块的实时表现，包括涨跌幅、成交额、换手率、领涨股、主力资金净流入等 |
| **seed_keywords** | 板块、行业、概念、领涨、轮动 |
| **requires_entity** | [`sector_name`] |
| **default_seed_fields** | 板块名称、涨跌幅、成交额、换手率、领涨股、主力资金净流入 |
| **site_search_urls** | `site:eastmoney.com` 板块行情页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🟢 akshare | `stock_board_industry_spot_em`, `stock_board_concept_spot_em` |
| 1 | 🔵 TuShare | `sw_daily`（含PE/PB） |
| 2 | 🟡 levistock | `sector_em`, `get_sector_hot_plates` |


#### 4. 龙虎榜与大宗交易

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_LHB_BLOCKTRADE` |
| **name** | 龙虎榜与大宗交易 |
| **description** | 每日龙虎榜上榜股票详情（买入/卖出金额、净买入额、上榜理由、营业部明细）和大宗交易数据（成交量、成交价、折溢价率、买卖营业部） |
| **seed_keywords** | 龙虎榜、机构席位、大宗交易、折溢价、营业部 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 股票名称、涨跌幅、换手率、龙虎榜买入额、净买入额、上榜理由、大宗交易折溢价率 |
| **site_search_urls** | `site:eastmoney.com` 龙虎榜页面 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `top_list`, `top_inst` |
| 2 | 🟢 akshare | `stock_lhb_detail_em`, `stock_dzjy_mrtj` |


### 第二组：行业与产业链层（4 个）


#### 5. 行业分类与成分

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INDUSTRY_CLASSIFY` |
| **name** | 行业分类与成分 |
| **description** | 申万行业分类体系及每个行业的成分股列表（含纳入/剔除日期），以及个股的行业归属查询 |
| **seed_keywords** | 行业分类、申万、成分股、行业归属 |
| **requires_entity** | [`industry_code`] |
| **default_seed_fields** | 一级行业名称、二级行业名称、三级行业名称、成分股票代码、纳入日期 |
| **site_search_urls** | `site:10jqka.com.cn` 概念板块页面 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `index_classify`, `index_member_all` |
| 2 | 🟢 akshare | `stock_industry_category_cninfo` |


#### 6. 产业背景分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INDUSTRY_BG` |
| **name** | 产业背景分析 |
| **description** | 目标产业或技术领域的系统性背景信息：技术图谱、产业链结构、政策与标准、全球竞争版图、历史演进、商业盈利模式 |
| **seed_keywords** | 产业、产业链、技术路线、竞争格局、产业背景 |
| **requires_entity** | [`industry_name`] |
| **default_seed_fields** | 技术图谱摘要、产业链结构图、关键政策列表、全球主要玩家列表 |
| **site_search_urls** | `site:stcn.com` 政策解读；`site:cls.cn` 行业深度 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🌐 站内搜索 | 证券时报网 `site:stcn.com`；财联社 `site:cls.cn` |
| 2 | 🔵 TuShare | `news`, `major_news`, `npr` |


#### 7. 投资路径分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_PATH_ANALYSIS` |
| **name** | 投资路径分析 |
| **description** | 从一条资讯或投资主题出发，系统性地分化出多条潜在投资路径（技术路线/产业链环节/地域/时间维度等） |
| **seed_keywords** | 投资路径、分化、切入点、先行信号 |
| **requires_entity** | [`topic`] |
| **default_seed_fields** | 路径编号、分化维度、研究路径描述、关键切入点、先行信号、优先级 |
| **site_search_urls** | `site:cls.cn` 产业快讯；`site:stcn.com` 行业分析 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🌐 站内搜索 | 财联社 `site:cls.cn`；证券时报网 `site:stcn.com` |


#### 8. 政策原文

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_POLICY_ORIGINAL` |
| **name** | 政策原文 |
| **description** | 国家行政机关（医保局、药监局、工信部、发改委、财政部、证监会、央行等）公开披露的法规、条例、批复、通知等文本数据 |
| **seed_keywords** | 政策、法规、通知、批复、文件、原文 |
| **requires_entity** | [`policy_keyword`] |
| **default_seed_fields** | 政策标题、发文机关、发布时间、政策类型、政策全文、政策链接 |
| **site_search_urls** | `site:gov.cn` 政策文件库；各部委官网各自独立域名 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🌐 站内搜索 | 中国政府网 `site:gov.cn`；各部委官网 |
| 2 | 🔵 TuShare | `npr`（国家政策库） |


### 第三组：公司基本面层（7 个）


#### 9. 实时行情与估值

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_REALTIME_QUOTE` |
| **name** | 实时行情与估值 |
| **description** | 个股实时价格、涨跌幅、成交量、成交额，以及关键估值指标（PE_TTM、PB、PS_TTM、总市值、流通市值、换手率、量比、股息率） |
| **seed_keywords** | 股价、行情、PE、PB、市值、换手率、量比 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 当前价、涨跌幅、总市值、PE_TTM、PB、换手率、量比、股息率 |
| **site_search_urls** | `site:eastmoney.com` 个股行情页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔴 腾讯财经 | `web.sqt.gtimg.cn/q=` |
| 1 | 🔵 TuShare | `rt_k`, `rt_min`, `daily_basic` |
| 2 | 🟣 雪球 | `quotec`, `quote_detail`（需Token） |


#### 10. 历史K线

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_HISTORICAL_KLINE` |
| **name** | 历史K线 |
| **description** | 个股日/周/月K线及分钟K线数据，支持前复权/后复权/不复权，以及技术面因子（MACD、KDJ、RSI、BOLL、CCI） |
| **seed_keywords** | K线、日线、周线、月线、分钟线、技术指标 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 日期、开盘价、收盘价、最高价、最低价、成交量、涨跌幅、MACD、KDJ |
| **site_search_urls** | `site:eastmoney.com` 个股K线页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `daily`, `weekly`, `monthly`, `pro_bar`, `adj_factor`, `stk_factor` |
| 2 | 🟢 akshare | `stock_zh_a_hist`, `stock_zh_a_hist_min_em` |
| 3 | 🟠 新浪财经 | 分钟K线接口 |


#### 11. 财务摘要

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_SUMMARY` |
| **name** | 财务摘要 |
| **description** | 公司核心财务指标的快速概览：盈利能力（ROE、毛利率、净利率）、成长能力（营收/净利同比增速）、资本结构（资产负债率）、营运能力（总资产周转率）、每股指标（EPS、每股净资产） |
| **seed_keywords** | 财务、ROE、毛利率、净利、营收、EPS |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | ROE(加权)、毛利率、净利率、营收同比增速、净利同比增速、资产负债率、EPS、每股净资产 |
| **site_search_urls** | `site:finance.sina.com.cn` 财务数据页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fina_indicator`（200+指标） |
| 2 | 🟢 akshare | `stock_financial_abstract`（80指标） |
| 3 | 🟣 雪球 | `indicator`（需Token） |


#### 12. 深度财务指标

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_DEEP` |
| **name** | 深度财务指标 |
| **description** | ROIC、杜邦分解（净利率×总资产周转率×权益乘数）、ROE扣非、EBIT/EBITDA、已获利息倍数、单季度指标（单季度ROE/毛利率/营收增速） |
| **seed_keywords** | ROIC、杜邦、EBIT、利息保障、单季度 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | ROIC、ROE(扣非)、EBIT/营业总收入、已获利息倍数、权益乘数(杜邦)、单季度ROE |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fina_indicator`（含roic/roe_dt/ebit/单季度系列） |
| 2 | 🟢 akshare | `stock_financial_analysis_indicator_em` |


#### 13. 三大财务报表

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FINANCIAL_STATEMENTS` |
| **name** | 三大财务报表 |
| **description** | 完整的利润表、资产负债表、现金流量表，Excel级详细科目，支持银行/保险/证券专用科目 |
| **seed_keywords** | 利润表、资产负债表、现金流量表、财报 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 营业总收入、营业成本、净利润、货币资金、总资产、总负债、经营现金流净额、期末现金余额 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `income`, `balancesheet`, `cashflow` |
| 2 | 🟢 akshare | `stock_profit_sheet_by_report_em`, etc. |
| 3 | 🟠 新浪财经 | HTML解析三大报表 |


#### 14. 估值对比分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_VALUATION_COMPARE` |
| **name** | 估值对比分析 |
| **description** | 公司历史估值水平（PE/PB/PS历史分位数）和同行业估值对比（行业平均PE/PB、行业内估值排名） |
| **seed_keywords** | 估值分位、历史PE、行业PE、低估高估 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | PE_TTM、PE历史分位数、PB、PB历史分位数、行业平均PE、估值评级 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `daily_basic`（历史序列）+ 本地分位数计算 |
| 1 | 🟣 雪球 | `industry_compare`（需Token） |
| 2 | 🟢 akshare | `stock_zh_valuation_comparison_em` |


#### 15. 公司概况

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_COMPANY_PROFILE` |
| **name** | 公司概况 |
| **description** | 公司全面基础信息：股票代码、所属行业、上市日期、实控人、法人代表、注册资本、员工人数、主营业务 |
| **seed_keywords** | 公司介绍、主营业务、实控人、注册资本、员工 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 公司全称、所属行业、上市日期、实控人、注册资本、员工人数、主营业务 |
| **site_search_urls** | `site:cninfo.com.cn` 公司概况页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `stock_basic`, `stock_company` |
| 2 | 🟢 akshare | `stock_profile_cninfo`, `stock_individual_info_em` |


### 第四组：公司治理与事件层（6 个）


#### 16. 前十大股东

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_TOP_HOLDERS` |
| **name** | 前十大股东 |
| **description** | 公司前十大股东和前十大流通股东名单、持股数量、持股比例、较上期变动、股东类型 |
| **seed_keywords** | 十大股东、持股、机构持仓、股东变动 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 股东名称、持股数量、持股比例、持股变动、股东类型 |
| **site_search_urls** | `site:cninfo.com.cn` 股东信息页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `top10_holders`, `top10_floatholders` |
| 2 | 🟢 akshare | `stock_gdfx_top_10_em` |
| 3 | 🟣 雪球 | `top_holders`（需Token） |


#### 17. 机构持仓与评级

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_INSTITUTION_RATING` |
| **name** | 机构持仓与评级 |
| **description** | 机构投资者持仓汇总（机构数量、持仓比例、季度变动）和券商研究报告（评级、目标价、盈利预测） |
| **seed_keywords** | 机构持仓、券商评级、目标价、研报 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 机构数量、持仓比例、最新评级、目标价、预测EPS |
| **site_search_urls** | `site:eastmoney.com` 研报页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🟢 akshare | `stock_institute_hold`, `stock_institute_recommend_detail`, `stock_research_report_em` |
| 2 | 🔵 TuShare | `report_rc`（8000积分）, `broker_recommend` |


#### 18. 公司公告

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_ANNOUNCEMENT` |
| **name** | 公司公告 |
| **description** | 上市公司在交易所法定披露的正式公告（财报、重大事项、并购重组、定增、回购、人事变动等），S级权威信息来源 |
| **seed_keywords** | 公告、披露、重大事项、定增、回购、并购 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 公告标题、公告时间、公告类型、公告链接 |
| **site_search_urls** | `site:cninfo.com.cn` 公告检索页；`site:stcn.com` 公告解读 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🟢 akshare | `stock_zh_a_disclosure_report_cninfo`, `stock_zh_a_gbjg_em` |
| 1 | 🌐 站内搜索 | 巨潮资讯网 `site:cninfo.com.cn` |


#### 19. 互动易问答

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_IRM_QA` |
| **name** | 互动易问答 |
| **description** | 投资者在互动易平台的提问及公司回复内容，反映公司沟通态度和信息透明度 |
| **seed_keywords** | 互动易、投资者问答、IR、公司回复 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 提问内容、提问时间、回答内容、回答时间 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🟢 akshare | `stock_irm_cninfo` |


#### 20. IPO信息

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_IPO_INFO` |
| **name** | IPO信息 |
| **description** | 公司上市时的详细信息：发行价、发行总量、募集资金、发行市盈率、中签率、上市日期 |
| **seed_keywords** | IPO、发行价、中签率、上市日期、募资 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 发行价、发行总量、募集资金、发行市盈率、中签率、上市日期 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `new_share` |
| 2 | 🟢 akshare | `stock_ipo_summary_cninfo`, `stock_new_ipo_cninfo` |


#### 21. 分红送配

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DIVIDEND` |
| **name** | 分红送配 |
| **description** | 公司历年分红送配方案：每10股派息金额、每股送转比例、股权登记日、除权除息日 |
| **seed_keywords** | 分红、派息、送转、除权、股息率 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 分红年度、每股分红、每股送转、股权登记日、除权除息日 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `dividend` |
| 2 | 🟢 akshare | `stock_dividend_cninfo`, `stock_fhps_em` |


### 第五组：资金与交易层（5 个）


#### 22. 个股资金流向

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUND_FLOW` |
| **name** | 个股资金流向 |
| **description** | 个股主力资金细分流向：小单/中单/大单/特大单的买入卖出量及金额、净流入额 |
| **seed_keywords** | 资金流向、主力、大单、净流入、特大单 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 主力净流入、大单净流入、特大单净流入、中单净流入、小单净流入 |
| **site_search_urls** | `site:eastmoney.com` 资金流向页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `moneyflow`, `moneyflow_dc`, `moneyflow_ths` |
| 2 | 🟢 akshare | `stock_individual_fund_flow` |
| 3 | 🟣 雪球 | `capital_assort`（需Token） |


#### 23. 北向资金

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_NORTHBOUND` |
| **name** | 北向资金 |
| **description** | 沪深港通北向资金每日净流入流出、持股明细、十大成交股，以及南向资金每日成交统计 |
| **seed_keywords** | 北向资金、陆股通、外资流入、持股明细 |
| **requires_entity** | [] |
| **default_seed_fields** | 北向资金净流入、沪股通净流入、深股通净流入、持股数量、十大成交股列表 |
| **site_search_urls** | `site:eastmoney.com` 北向资金页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `moneyflow_hsgt`, `hk_hold`, `hsgt_top10`, `ggt_daily` |
| 2 | 🟢 akshare | `stock_hsgt_hist_em`, `stock_hsgt_fund_flow_summary_em` |


#### 24. 融资融券

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MARGIN` |
| **name** | 融资融券 |
| **description** | 全市场及个股融资余额、融资买入额、融资偿还额、融券余额、融券卖出量（T+1更新） |
| **seed_keywords** | 融资、融券、杠杆、两融、融资余额 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 融资余额、融资买入额、融资偿还额、融券余额、融资融券余额 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `margin`, `margin_detail` |
| 2 | 🟣 雪球 | `margin`（需Token） |
| 3 | 🟢 akshare | `stock_margin_sse`, `stock_margin_szse` |


#### 25. 涨停跌停分析

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_LIMIT_UP_DOWN` |
| **name** | 涨停跌停分析 |
| **description** | 每日涨停/跌停股详细数据：涨跌停价格、涨跌停状态、连板数、首次封板时间、开板次数 |
| **seed_keywords** | 涨停、跌停、连板、封板、一字板 |
| **requires_entity** | [] |
| **default_seed_fields** | 股票名称、涨停价、跌停价、涨跌停状态、连板数、首次封板时间 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `stk_limit`, `daily_basic.limit_status` |
| 1 | 🟡 levistock | `stock_zt_pool_em`, `stock_dt_pool_em` |
| 2 | 🟢 akshare | `stock_zt_pool_em`, `stock_dt_pool_em` |


#### 26. 股权质押与增减持

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_PLEDGE_HOLDER_TRADE` |
| **name** | 股权质押与增减持 |
| **description** | 大股东股权质押统计数据（质押比例、质押次数）和明细（质押方、起止日期、是否解押），以及重要股东增减持记录 |
| **seed_keywords** | 股权质押、增减持、质押比例、解押、预警线 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 股东名称、质押比例、质押方、质押起止日期、是否解押、增减持类型、变动数量 |
| **site_search_urls** | `site:cninfo.com.cn` 质押/增减持公告 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `pledge_stat`, `pledge_detail`, `stk_holdertrade` |
| 2 | 🟢 akshare | `stock_gpzy_profile_em`, `stock_cg_equity_mortgage_cninfo` |


### 第六组：宏观与跨资产层（5 个）


#### 27. 宏观经济指标

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_MACRO_ECONOMY` |
| **name** | 宏观经济指标 |
| **description** | 中国及全球主要经济体的宏观经济指标：GDP、CPI、PPI、PMI、M2、LPR、Shibor、社融、美债收益率曲线 |
| **seed_keywords** | GDP、CPI、PPI、PMI、M2、LPR、社融、非农 |
| **requires_entity** | [] |
| **default_seed_fields** | GDP增速、CPI同比、PPI同比、制造业PMI、M2增速、LPR(1年期)、Shibor(隔夜)、美债10年期收益率 |
| **site_search_urls** | `site:gov.cn` 经济数据发布页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `cn_gdp`, `cn_cpi`, `cn_ppi`, `cn_pmi`, `cn_m`, `shibor_lpr`, `shibor`, `sf_month`, `us_tycr` |
| 2 | 🟢 akshare | `macro_china_*`, `macro_usa_*` |


#### 28. 期货行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUTURES` |
| **name** | 期货行情 |
| **description** | 国内期货主力合约日线行情、主力与连续合约映射、每日持仓排名、仓单日报、结算参数 |
| **seed_keywords** | 期货、主力合约、持仓、仓单、结算 |
| **requires_entity** | [`future_code`] |
| **default_seed_fields** | 合约名称、收盘价、涨跌幅、成交量、持仓量、结算价、仓单量 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fut_daily`, `fut_basic`, `fut_mapping`, `fut_holding`, `fut_wsr`, `fut_settle` |
| 2 | 🟢 akshare | `futures_zh_realtime`, `futures_zh_daily_sina` |


#### 29. 可转债行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_CONVERTIBLE_BOND` |
| **name** | 可转债行情 |
| **description** | 可转债日线行情、基础信息（转股价、债券余额、票面利率、信用评级）、转股价值、转股溢价率、纯债价值、强赎状态 |
| **seed_keywords** | 可转债、转股、溢价率、强赎、纯债 |
| **requires_entity** | [`bond_code`] |
| **default_seed_fields** | 转债名称、当前价、转股价、转股价值、转股溢价率、强赎状态、债券余额 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `cb_daily`, `cb_basic`, `cb_issue`, `cb_share` |
| 2 | 🟢 akshare | `bond_zh_cov`, `bond_zh_cov_value_analysis` |


#### 30. 基金与ETF行情

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FUND_ETF` |
| **name** | 基金与ETF行情 |
| **description** | ETF日线行情、基金基础信息（管理人、基金类型、管理费）、基金份额规模、基金净值、基金持仓明细、基金分红、基金经理信息 |
| **seed_keywords** | ETF、基金、净值、规模、基金经理、持仓 |
| **requires_entity** | [`fund_code`] |
| **default_seed_fields** | 基金名称、单位净值、日涨跌幅、规模、管理费、基金经理、持仓明细 |
| **site_search_urls** | `site:eastmoney.com` 基金页 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fund_daily`, `fund_basic`, `fund_share`, `fund_nav`, `fund_portfolio`, `fund_div`, `fund_manager`, `etf_share_size` |
| 2 | 🟢 akshare | `fund_etf_spot_em`, `fund_etf_hist_em` |


#### 31. 外汇汇率

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_FOREX` |
| **name** | 外汇汇率 |
| **description** | 主要货币对即期汇率和历史走势（美元/人民币、欧元/美元等），以及外汇基础信息 |
| **seed_keywords** | 汇率、外汇、美元、人民币、欧元 |
| **requires_entity** | [`currency_pair`] |
| **default_seed_fields** | 货币对、买入价、卖出价、中间价、涨跌幅 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fx_daily`, `fx_obasic` |
| 2 | 🟢 akshare | `currency_boc_sina`, `forex_hist_em` |


### 第七组：文档生成层（6 个）


#### 32. 午间收盘信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_MIDDAY` |
| **name** | 午间收盘信息文档 |
| **description** | 交易日午间收盘后（11:35-12:00）生成的上午半日行情摘要、板块地位、驱动因素变化、资金博弈迹象、技术面关键位置及风险提示 |
| **seed_keywords** | 午间、上午收盘、半日行情、午间文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 上午涨跌幅、上午成交额、换手率、个股vs板块表现、上午新驱动、主力资金净流入(估算)、MA5/MA10/MA20估算 |
| **site_search_urls** | 联网搜索（盘中财经网站） |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `daily`（前一日）, `daily_basic`（前一日） |
| 2 | 🟢 akshare | `stock_zh_a_spot_em`（盘中） |
| 3 | 🌐 站内搜索 | 联网搜索（盘中数据） |


#### 33. 收盘后信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_CLOSE` |
| **name** | 收盘后信息文档 |
| **description** | 交易日收盘后三阶段生成（17:30/19:30/次日9:30）：行情概览、涨停驱动因素、财务摘要、技术面分析、资金博弈、融资融券变化 |
| **seed_keywords** | 收盘、盘后、全天行情、收盘文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 今日涨跌幅、成交额、换手率、是否涨停、板块内涨幅排名、资金博弈分析、融资融券变化、MA5/MA10/MA20 |
| **site_search_urls** | 联网搜索（盘中/盘后舆情） |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `daily`, `daily_basic`, `stk_limit`, `fina_indicator`, `moneyflow`, `margin`, `stk_holdertrade`, `pledge_stat` |
| 2 | 🌐 站内搜索 | 联网搜索（舆情和驱动因素） |


#### 34. 公司潜在价值信息文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_VALUE` |
| **name** | 公司潜在价值信息文档 |
| **description** | 公司长期价值档案：产业链位置、市场规模、核心项目、技术壁垒、管理团队、竞争格局、财务质量（近3年）、风险与不确定性、反证分析 |
| **seed_keywords** | 潜在价值、公司价值、长期价值、价值文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 产业链位置、市场规模、核心项目、技术壁垒、财务质量(近3年)、风险与不确定性、反证分析 |
| **site_search_urls** | `site:cninfo.com.cn` 公司公告；`site:stcn.com` 行业分析 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fina_indicator`, `income`, `balancesheet`, `cashflow`, `daily_basic`, `pledge_stat`, `stk_holdertrade` |
| 2 | 🌐 站内搜索 | 巨潮资讯网 `site:cninfo.com.cn`；证券时报网 `site:stcn.com` |


#### 35. 风险控制文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_RISK` |
| **name** | 风险控制文档 |
| **description** | 全维度风险梳理：题材风险、板块退潮风险、财务风险、股东风险、技术路线风险、估值风险、流动性风险、监管风险、信息可信度风险 |
| **seed_keywords** | 风险、风控、风险评估、风险文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 风险总览表、财务风险详情、股东风险详情、估值风险详情、监管风险详情、综合风险结论 |
| **site_search_urls** | `site:cninfo.com.cn` 监管公告；`site:stcn.com` 风险报道 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fina_indicator`, `stk_holdertrade`, `pledge_stat`, `block_trade`, `top_list`, `daily_basic`, `daily` |
| 2 | 🌐 站内搜索 | 巨潮资讯网 `site:cninfo.com.cn`；证券时报网 `site:stcn.com` |


#### 36. 反证文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_COUNTER` |
| **name** | 反证文档 |
| **description** | 从“为什么这笔投资可能是错的”角度出发的系统性批判：产业路径反证、产业链环节反证、公司真实受益反证、龙头属性反证、项目兑现反证、估值反证、替代公司反证 |
| **seed_keywords** | 反证、批判、风险验证、反证文档 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 各维度反证(7个维度)、综合反证结论、最有力反证、需解答问题清单 |
| **site_search_urls** | `site:cninfo.com.cn` 公告验证；`site:stcn.com` 行业分析 |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `fina_indicator`, `daily_basic`, `stk_holdertrade` |
| 2 | 🌐 站内搜索 | 巨潮资讯网 `site:cninfo.com.cn`；证券时报网 `site:stcn.com` |


#### 37. 估值辅助文档

| 属性 | 内容 |
| :--- | :--- |
| **id** | `CONCEPT_DOC_VALUATION` |
| **name** | 估值辅助文档 |
| **description** | 系统化估值参考框架：当前估值水位、成长性支撑、产业背景对估值的影响、风险对估值折价的影响、估值情景分析（乐观/中性/悲观）、估值参考结论 |
| **seed_keywords** | 估值文档、估值辅助、情景分析、估值参考 |
| **requires_entity** | [`stock_code`] |
| **default_seed_fields** | 当前估值水位、成长性支撑、估值情景分析、估值参考结论 |
| **site_search_urls** | — |

**数据源**：
| 优先级 | 数据源 | 接口/方式 |
| :---: | :--- | :--- |
| 1 | 🔵 TuShare | `daily_basic`, `fina_indicator`, `income` |


## 五、站内搜索类信源映射总览

| 信源名称 | site:url | 标签 | 关联 IntentConcept |
| :--- | :--- | :--- | :--- |
| 东方财富网 | `site:eastmoney.com` | `#行情数据` `#资金流向` `#公司公告` | 1, 3, 4, 9, 10, 18, 22, 23, 30 |
| 新浪财经 | `site:finance.sina.com.cn` | `#行情数据` `#财务数据` `#财经新闻` | 2, 9, 11 |
| 证券时报网 | `site:stcn.com` | `#官方媒体` `#政策发布` `#公告解读` | 2, 6, 7, 8, 18, 34, 35, 36 |
| 同花顺 | `site:10jqka.com.cn` | `#行情数据` `#概念板块` `#数据核实` | 3, 5 |
| 中国政府网及各部委官网 | `site:gov.cn` | `#政策原文` `#权威信源` | 8, 27 |
| 巨潮资讯网 | `site:cninfo.com.cn` | `#法定披露` `#官方公告` `#权威信源` | 15, 16, 18, 26, 34, 35, 36 |
| 财联社 | `site:cls.cn` | `#即时新闻` `#快讯` `#政策解读` | 2, 6, 7, 8 |
| 第一财经 | `site:yicai.com` | `#财经新闻` `#深度报道` | 2, 6 |
| 雪球 | `site:xueqiu.com` | `#投资者社区` `#市场情绪` `#UGC` | 2 |


## 六、工作流程图

### 6.1 整体架构流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             用户输入问题                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         【LLM 解析层】                                      │
│  1. 提取目标指标词（如“净利润”）                                            │
│  2. 提取实体参数（如 stock_code: "300750"）                               │
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

### 6.2 两种意图模式的分支逻辑

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


## 七、开发实施步骤

### 第一阶段：环境准备（第 1-2 天）

- 安装 Python 3.10+，创建虚拟环境
- 安装基础依赖库：akshare、tushare、pandas、numpy、neo4j
- 安装并启动 Neo4j 图数据库（社区版）
- 下载 Qwen3-Embedding-4B GGUF Q4_K_M 量化模型（约 2.5GB）
- 安装 llama-cpp-python，验证模型可正常加载并生成向量
- 配置 TuShare Token 环境变量


### 第二阶段：数据准备（第 3-4 天）

- 遍历所有数据源接口，梳理 DataField 清单（名称/别名/描述/所属数据源）
- 为每个数据源创建 DataSource 条目（协议/函数名/参数模板/刷新时效/权威等级）
- 根据 37 个 IntentConcept 定义，为每个概念配置 default_seed_fields
- 为每个 IntentConcept 配置 site_search_urls（如有站内搜索入口）
- 将上述数据整理为 CSV 文件，便于批量导入


### 第三阶段：图谱构建 - 节点写入与 Embedding 生成（第 5-7 天）

> **本阶段是核心开发步骤，需详细执行。**

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

**注意事项**：
- 若 alias 为空数组，则只拼接 `standard_name + " " + description`
- description 可能为空，此时仅拼接 `standard_name + " " + " ".join(alias)`
- 首次生成时建议使用批量处理（batch inference），提升效率

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

**目的**：自动建立 DataField 之间的语义近邻关系，替代人工维护的字段分组。

**执行方式**：

```
获取所有 DataField 的 id 和 embedding
N = DataField 总数（预计 200-500 个）

对每对 (i, j)，其中 i < j：
    1. 计算余弦相似度：cos_sim = dot(embedding_i, embedding_j) / (norm_i * norm_j)
    2. 若 cos_sim >= 0.75：
        创建 SEMANTIC_SIMILAR_TO 双向关系
        设置属性：
          - cosine_similarity = cos_sim
          - level = "high" if cos_sim >= 0.85 else "medium"
    3. 若 0.65 <= cos_sim < 0.75：
        不创建关系，仅记录到日志（用于后续阈值调优参考）
    4. 每完成 1000 对计算输出一次进度
```

**性能优化建议**：
- N=500 时，总计算量为 500×499/2 = 124,750 对，单次推理约 10ms，总耗时约 20-30 分钟
- 若需加速，可使用 Faiss 或 hnswlib 做 ANN 近似检索，但本阶段 N 较小，直接计算即可
- 计算时建议使用 GPU 加速（llama-cpp-python 默认支持）

#### 3.5 向量索引建立（可选，用于查询优化）

- 将所有 DataField 的 embedding 导出到 Faiss 索引，用于查询时的 Top-K 向量检索
- 将所有 IntentConcept 的 embedding 导出到另一个 Faiss 索引，用于意图兜底匹配


### 第四阶段：图谱构建 - BELONGS_TO_CONCEPT 关系建立（第 7-8 天）

> **本阶段是核心开发步骤，需详细执行。**

#### 4.1 设计思路

`BELONGS_TO_CONCEPT` 关系是图谱路由的核心依据之一。为降低人工维护成本，采用 **“LLM 辅助梳理 + 人工确认”** 的半自动流程：

1. LLM 根据 DataField 的字段含义和 IntentConcept 的业务描述，自动推断从属关系
2. 生成候选关系列表，标记为 `is_auto_suggested = true`、`is_approved = false`
3. 管理员在后台确认/修正后，批量写入图数据库

#### 4.2 准备 LLM 输入数据

将 DataField 和 IntentConcept 的完整信息整理为结构化输入：

```
DataField 列表（取全部字段，含 id、standard_name、alias、description）
IntentConcept 列表（取全部概念，含 id、name、description、default_seed_fields）
```

**数据量估算**：
- DataField：约 200-500 个（取决于接入的数据源数量）
- IntentConcept：37 个
- 理论最大配对：200 × 37 = 7,400 对（但实际只有语义相关的才会被输出）

#### 4.3 调用 LLM 生成候选关系

**Prompt 设计要点**：
- 明确要求 LLM 为每个 DataField 判断其属于哪些 IntentConcept
- 输出格式为 JSON 数组，每项包含 `field_id`、`concept_id`、`relevance_score`（0-1）
- 要求 LLM 给出 `relevance_score`：1.0=核心必需，0.7=重要辅助，0.5=一般参考
- 允许一个字段属于多个 Concept

**执行方式**：

```
将 DataField 列表和 IntentConcept 列表拼接成完整 Prompt
调用 LLM（DeepSeek-V4）生成候选关系列表
保存原始输出到日志（便于追溯和调优）
```

**分批处理策略**：
- 若 DataField 数量超过 200 个，可将字段分批（每批 50-80 个）分别调用 LLM
- 每批的 Prompt 中仍包含完整的 37 个 IntentConcept 列表

#### 4.4 人工确认

**后台界面设计**：

- 按 Concept 分组展示待确认的候选字段列表（按 relevance_score 降序排列）
- 每个条目显示：字段名、字段描述、relevance_score、操作按钮（接受/拒绝/修改分数）
- 管理员可批量接受（如 relevance_score ≥ 0.8 的全部接受）
- 管理员可手动添加未被 LLM 推荐的字段

**确认流程**：

```
1. 管理员登录后台，进入“关系确认”页面
2. 选择需要确认的 Concept
3. 查看候选字段列表，逐个或批量确认
4. 确认后，关系属性更新：is_approved = true
5. 所有关系确认后，方可进入下一阶段
```

**预估工作量**：
- 全量初筛：200 个字段 × 37 个 Concept，LLM 输出约 300-500 条候选关系
- 人工确认：约 1-2 天可完成
- 增量更新：新增字段时，只需为新字段运行 LLM 推断，确认约 3-5 个候选

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
1. 为新字段生成 embedding（参考 3.2 节）
2. 计算新字段与所有现有 DataField 的相似度，创建 SEMANTIC_SIMILAR_TO 关系（参考 3.4 节）
3. 将新字段加入下一批 LLM 推断队列
4. 管理员确认从属关系后写入 BELONGS_TO_CONCEPT
5. 更新 Faiss 向量索引
```

**当新 IntentConcept 加入时**：

```
1. 为新概念生成 embedding（参考 3.3 节）
2. 将所有现有 DataField 与新概念组合，调用 LLM 推断候选关系
3. 管理员确认后批量写入 BELONGS_TO_CONCEPT
```


### 第五阶段：查询与测试（第 8-9 天）

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
- 建立关系确认的自动化监控（定期检查是否有未确认的候选关系）


## 八、技术栈总结

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


## 九、设计优势总结

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
| **单一事实来源** | `BELONGS_TO_CONCEPT` 由关系层唯一表达，消除数据冗余 |