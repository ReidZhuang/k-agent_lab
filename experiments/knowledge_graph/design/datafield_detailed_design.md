# IRKG v3 完整 DataField 属性清单


## 文档说明

本文档为知识图谱中所有 **DataField 节点**的完整属性清单，按 IntentConcept 分组排列。

每个 DataField 包含以下属性：

| 属性 | 说明 |
| :--- | :--- |
| **ID** | 全局唯一标识符 |
| **standard_name** | 规范列名，与数据源返回字段名一致 |
| **alias** | 同义词数组，用于用户口语匹配 |
| **description** | 字段含义描述 |
| **data_type** | 数据类型：float / int / string / date / boolean |
| **unit** | 单位（如有） |
| **authority_level** | 权威等级：S/A/B/C |
| **refresh_time** | 更新时效 |
| **默认数据源 ID** | 该字段默认取数的 DataSource |

> **统计**：
> - 独立 DataField 节点：**405 个**
> - 文档生成层复用字段：**43 个**（不独立建节点）
> - 按 IntentConcept 分组：**41 个分组**


## 第一组：市场全景层（4 个 Concept，共 65 个 DataField）


### CONCEPT_MARKET_INDEX（市场整体行情）
> 默认数据源：DS_TUSHARE_INDEX_DAILY / DS_TUSHARE_INDEX_BASIC / DS_TUSHARE_INDEX_DB

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_INDEX_NAME | 指数名称 | `["指数名"]` | 指数的中文名称 | string | — | A | weekly | DS_TUSHARE_INDEX_BASIC |
| 2 | FIELD_INDEX_CODE | 指数代码 | `["代码","ts_code"]` | 指数TS代码 | string | — | A | weekly | DS_TUSHARE_INDEX_BASIC |
| 3 | FIELD_INDEX_PRICE | 当前点位 | `["指数点位","收盘价","close"]` | 指数收盘点位 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 4 | FIELD_INDEX_PCT_CHG | 涨跌幅 | `["涨幅","pct_chg"]` | 指数涨跌幅百分比 | float | % | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 5 | FIELD_INDEX_CHG | 涨跌额 | `["涨跌","change"]` | 指数涨跌点数 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 6 | FIELD_INDEX_HIGH | 最高点 | `["最高","high"]` | 当日最高点位 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 7 | FIELD_INDEX_LOW | 最低点 | `["最低","low"]` | 当日最低点位 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 8 | FIELD_INDEX_OPEN | 开盘价 | `["开盘","open"]` | 当日开盘点位 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 9 | FIELD_INDEX_PRE_CLOSE | 昨日收盘 | `["昨收","pre_close"]` | 前一交易日收盘点位 | float | 点 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 10 | FIELD_INDEX_VOL | 成交量 | `["量","vol"]` | 指数成交量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 11 | FIELD_INDEX_AMOUNT | 成交额 | `["额","amount"]` | 指数成交额（千元） | float | 千元 | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 12 | FIELD_INDEX_SWING | 振幅 | `["swing"]` | 指数当日振幅 | float | % | A | daily_17:00 | DS_TUSHARE_INDEX_DAILY |
| 13 | FIELD_INDEX_TOTAL_MV | 总市值 | `["市值","total_mv"]` | 指数成分股总市值 | float | 亿元 | A | daily_17:00 | DS_TUSHARE_INDEX_DB |
| 14 | FIELD_INDEX_FLOAT_MV | 流通市值 | `["流通市值","float_mv"]` | 指数成分股流通市值 | float | 亿元 | A | daily_17:00 | DS_TUSHARE_INDEX_DB |
| 15 | FIELD_INDEX_PE | 市盈率 | `["PE","pe"]` | 指数成分股加权市盈率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_INDEX_DB |
| 16 | FIELD_INDEX_PB | 市净率 | `["PB","pb"]` | 指数成分股加权市净率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_INDEX_DB |
| 17 | FIELD_INDEX_TURNOVER | 换手率 | `["换手","turnover_rate"]` | 指数成分股换手率 | float | % | A | daily_17:00 | DS_TUSHARE_INDEX_DB |


### CONCEPT_MARKET_SENTIMENT（市场情绪与快讯）
> 默认数据源：DS_LEVISTOCK_EMOTION / DS_LEVISTOCK_NEWS

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_MARKET_HEAT | 市场热度 | `["热度","market_degree"]` | 市场情绪综合热度0-100 | int | — | B | intraday | DS_LEVISTOCK_EMOTION |
| 2 | FIELD_MARKET_BALANCE | 两市成交额 | `["成交额","shsz_balance"]` | 沪深两市合计成交额 | float | 亿元 | B | intraday | DS_LEVISTOCK_EMOTION |
| 3 | FIELD_MARKET_UP_RATIO | 上涨占比 | `["涨跌比","up_ratio"]` | 上涨股票数量占比 | float | % | B | intraday | DS_LEVISTOCK_EMOTION |
| 4 | FIELD_MARKET_PROFIT_RATIO | 赚钱效应 | `["盈利效应","profit_ratio"]` | 盈利股票占比 | float | % | B | intraday | DS_LEVISTOCK_EMOTION |
| 5 | FIELD_LIMIT_UP_COUNT | 涨停家数 | `["涨停数"]` | 当日涨停股票数量 | int | 家 | B | intraday | DS_LEVISTOCK_EMOTION |
| 6 | FIELD_LIMIT_DOWN_COUNT | 跌停家数 | `["跌停数"]` | 当日跌停股票数量 | int | 家 | B | intraday | DS_LEVISTOCK_EMOTION |
| 7 | FIELD_LIMIT_UP_BOARD | 涨停梯队 | `["连板梯队"]` | 一板/二板/三板及以上数量 | string | — | B | intraday | DS_LEVISTOCK_EMOTION |
| 8 | FIELD_NEWS_TITLE | 快讯标题 | `["标题","title"]` | 财经快讯标题 | string | — | A | realtime | DS_LEVISTOCK_NEWS |
| 9 | FIELD_NEWS_CONTENT | 快讯内容 | `["内容","正文","content"]` | 财经快讯正文 | string | — | A | realtime | DS_LEVISTOCK_NEWS |
| 10 | FIELD_NEWS_TIME | 快讯时间 | `["时间","time"]` | 快讯发布时间 | date | — | A | realtime | DS_LEVISTOCK_NEWS |
| 11 | FIELD_UP_COUNT | 上涨家数 | `["涨家数","up_count"]` | 板块内上涨股票数量 | int | 家 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 12 | FIELD_DOWN_COUNT | 下跌家数 | `["跌家数","down_count"]` | 板块内下跌股票数量 | int | 家 | A | intraday | DS_AKSHARE_SECTOR_SPOT |


### CONCEPT_SECTOR_REALTIME（板块实时行情）
> 默认数据源：DS_AKSHARE_SECTOR_SPOT

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_SECTOR_NAME | 板块名称 | `["板块名","sector_name"]` | 行业/概念板块名称 | string | — | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 2 | FIELD_SECTOR_CODE | 板块代码 | `["sector_code"]` | 板块代码（如BK0441） | string | — | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 3 | FIELD_SECTOR_PRICE | 板块指数 | `["sector_price"]` | 板块当前指数点位 | float | 点 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 4 | FIELD_SECTOR_PCT_CHG | 板块涨跌幅 | `["涨幅","change_pct"]` | 板块指数涨跌幅 | float | % | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 5 | FIELD_SECTOR_AMOUNT | 板块成交额 | `["成交额","amount"]` | 板块当日成交额 | float | 亿元 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 6 | FIELD_SECTOR_TURNOVER | 板块换手率 | `["换手率","turnover_rate"]` | 板块成分股加权换手率 | float | % | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 7 | FIELD_SECTOR_AMPLITUDE | 板块振幅 | `["振幅","amplitude"]` | 板块指数振幅 | float | % | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 8 | FIELD_SECTOR_LEAD_STOCK | 领涨股名称 | `["领涨","lead_stock_name"]` | 板块内涨幅最大股票名称 | string | — | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 9 | FIELD_SECTOR_LEAD_CODE | 领涨股代码 | `["lead_stock_code"]` | 领涨股股票代码 | string | — | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 10 | FIELD_SECTOR_LEAD_CHG | 领涨股涨幅 | `["lead_stock_chg"]` | 领涨股当日涨跌幅 | float | % | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 11 | FIELD_SECTOR_MAIN_INFLOW | 主力净流入 | `["主力","main_inflow"]` | 板块主力资金净流入金额 | float | 亿元 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 12 | FIELD_SECTOR_UP_COUNT | 上涨家数 | `["涨家数","up_count"]` | 板块内上涨股票数量 | int | 家 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 13 | FIELD_SECTOR_DOWN_COUNT | 下跌家数 | `["跌家数","down_count"]` | 板块内下跌股票数量 | int | 家 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 14 | FIELD_SECTOR_TOTAL_MV | 总市值 | `["total_market"]` | 板块成分股总市值 | float | 亿元 | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 15 | FIELD_SECTOR_TOP_DROP | 领跌股名称 | `["top_drop_name"]` | 板块内跌幅最大股票名称 | string | — | A | intraday | DS_AKSHARE_SECTOR_SPOT |
| 16 | FIELD_SECTOR_TOP_DROP_CHG | 领跌股涨幅 | `["top_drop_chg"]` | 领跌股当日涨跌幅 | float | % | A | intraday | DS_AKSHARE_SECTOR_SPOT |


### CONCEPT_LHB_BLOCKTRADE（龙虎榜与大宗交易）
> 默认数据源：DS_TUSHARE_TOP_LIST / DS_TUSHARE_TOP_INST / DS_TUSHARE_BLOCK_TRADE

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_LHB_STOCK_NAME | 股票名称 | `["名称","name"]` | 上榜股票名称 | string | — | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 2 | FIELD_LHB_PCT_CHG | 涨跌幅 | `["涨幅","pct_change"]` | 股票当日涨跌幅 | float | % | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 3 | FIELD_LHB_TURNOVER | 换手率 | `["turnover_rate"]` | 股票当日换手率 | float | % | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 4 | FIELD_LHB_AMOUNT | 总成交额 | `["成交额","amount"]` | 股票当日总成交额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 5 | FIELD_LHB_BUY | 龙虎榜买入额 | `["买入额","l_buy"]` | 龙虎榜上榜买入金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 6 | FIELD_LHB_SELL | 龙虎榜卖出额 | `["卖出额","l_sell"]` | 龙虎榜上榜卖出金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 7 | FIELD_LHB_NET | 净买入额 | `["净额","net_amount"]` | 龙虎榜净买入金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 8 | FIELD_LHB_NET_RATE | 净买额占比 | `["net_rate"]` | 净买入额占总成交额比例 | float | % | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 9 | FIELD_LHB_AMOUNT_RATE | 龙虎榜成交占比 | `["amount_rate"]` | 龙虎榜成交额占总成交额比例 | float | % | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 10 | FIELD_LHB_REASON | 上榜理由 | `["原因","reason"]` | 龙虎榜上榜原因描述 | string | — | A | daily_20:00 | DS_TUSHARE_TOP_LIST |
| 11 | FIELD_LHB_EXALTER | 营业部名称 | `["exalter"]` | 参与交易的营业部名称 | string | — | A | daily_20:00 | DS_TUSHARE_TOP_INST |
| 12 | FIELD_LHB_SIDE | 买卖类型 | `["side"]` | 0-买入席,1-卖出席 | int | — | A | daily_20:00 | DS_TUSHARE_TOP_INST |
| 13 | FIELD_LHB_INST_BUY | 机构买入额 | `["buy"]` | 机构席位买入金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_INST |
| 14 | FIELD_LHB_INST_SELL | 机构卖出额 | `["sell"]` | 机构席位卖出金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_TOP_INST |
| 15 | FIELD_BLOCK_PRICE | 大宗交易价 | `["成交价","price"]` | 大宗交易成交价格 | float | 元 | A | daily_20:00 | DS_TUSHARE_BLOCK_TRADE |
| 16 | FIELD_BLOCK_VOL | 大宗交易量 | `["成交量","vol"]` | 大宗交易成交量 | float | 万股 | A | daily_20:00 | DS_TUSHARE_BLOCK_TRADE |
| 17 | FIELD_BLOCK_AMOUNT | 大宗交易额 | `["成交额","amount"]` | 大宗交易成交金额 | float | 万元 | A | daily_20:00 | DS_TUSHARE_BLOCK_TRADE |
| 18 | FIELD_BLOCK_BUYER | 买方营业部 | `["buyer"]` | 大宗交易买方营业部 | string | — | A | daily_20:00 | DS_TUSHARE_BLOCK_TRADE |
| 19 | FIELD_BLOCK_SELLER | 卖方营业部 | `["seller"]` | 大宗交易卖方营业部 | string | — | A | daily_20:00 | DS_TUSHARE_BLOCK_TRADE |


## 第二组：行业与产业链层（5 个 Concept，共 27 个 DataField）


### CONCEPT_INDUSTRY_CLASSIFY（行业分类与成分）
> 默认数据源：DS_TUSHARE_INDEX_CLASSIFY / DS_TUSHARE_INDEX_MEMBER

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_INDUSTRY_L1_CODE | 一级行业代码 | `["l1_code"]` | 申万一级行业代码 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 2 | FIELD_INDUSTRY_L1_NAME | 一级行业名称 | `["l1_name"]` | 申万一级行业名称 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 3 | FIELD_INDUSTRY_L2_CODE | 二级行业代码 | `["l2_code"]` | 申万二级行业代码 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 4 | FIELD_INDUSTRY_L2_NAME | 二级行业名称 | `["l2_name"]` | 申万二级行业名称 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 5 | FIELD_INDUSTRY_L3_CODE | 三级行业代码 | `["l3_code"]` | 申万三级行业代码 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 6 | FIELD_INDUSTRY_L3_NAME | 三级行业名称 | `["l3_name"]` | 申万三级行业名称 | string | — | A | weekly | DS_TUSHARE_INDEX_CLASSIFY |
| 7 | FIELD_INDUSTRY_MEMBER | 成分股票代码 | `["成分股","ts_code"]` | 行业成分股TS代码 | string | — | A | weekly | DS_TUSHARE_INDEX_MEMBER |
| 8 | FIELD_INDUSTRY_MEMBER_NAME | 成分股票名称 | `["name"]` | 行业成分股名称 | string | — | A | weekly | DS_TUSHARE_INDEX_MEMBER |
| 9 | FIELD_INDUSTRY_IN_DATE | 纳入日期 | `["in_date"]` | 股票纳入行业日期 | date | — | A | weekly | DS_TUSHARE_INDEX_MEMBER |
| 10 | FIELD_INDUSTRY_OUT_DATE | 剔除日期 | `["out_date"]` | 股票剔除行业日期 | date | — | A | weekly | DS_TUSHARE_INDEX_MEMBER |
| 11 | FIELD_INDUSTRY_IS_NEW | 是否最新 | `["is_new"]` | 是否为最新成分（Y/N） | string | — | A | weekly | DS_TUSHARE_INDEX_MEMBER |


### CONCEPT_INDUSTRY_BG（产业背景分析）
> 默认数据源：DS_WEB_SEARCH

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_INDUSTRY_BG_TECH | 技术图谱摘要 | `["技术路线"]` | 产业核心技术路径描述 | string | — | C | weekly | DS_WEB_SEARCH |
| 2 | FIELD_INDUSTRY_BG_CHAIN | 产业链结构图 | `["产业链","上下游"]` | 产业链各环节价值分布 | string | — | C | weekly | DS_WEB_SEARCH |
| 3 | FIELD_INDUSTRY_BG_POLICY | 关键政策列表 | `["政策","法规"]` | 相关产业政策汇总 | string | — | C | weekly | DS_WEB_SEARCH |
| 4 | FIELD_INDUSTRY_BG_PLAYERS | 全球主要玩家 | `["竞争对手","格局"]` | 全球及国内主要参与者 | string | — | C | weekly | DS_WEB_SEARCH |


### CONCEPT_PATH_ANALYSIS（投资路径分析）
> 默认数据源：DS_LLM_GEN

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_PATH_ID | 路径编号 | `["序号"]` | 投资路径唯一编号 | string | — | C | event_driven | DS_LLM_GEN |
| 2 | FIELD_PATH_DIMENSION | 分化维度 | `["维度"]` | 路径分化维度（技术/环节/地域等） | string | — | C | event_driven | DS_LLM_GEN |
| 3 | FIELD_PATH_DESC | 研究路径描述 | `["描述"]` | 具体投资路径说明 | string | — | C | event_driven | DS_LLM_GEN |
| 4 | FIELD_PATH_ENTRY | 关键切入点 | `["切入点","核心驱动"]` | 路径关键驱动因素 | string | — | C | event_driven | DS_LLM_GEN |
| 5 | FIELD_PATH_SIGNAL | 先行信号 | `["领先指标"]` | 路径启动的先行信号 | string | — | C | event_driven | DS_LLM_GEN |
| 6 | FIELD_PATH_PRIORITY | 优先级 | `["重要程度"]` | 路径建议优先级 | string | — | C | event_driven | DS_LLM_GEN |


### CONCEPT_POLICY_ORIGINAL（政策原文）
> 默认数据源：DS_WEB_SEARCH

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_POLICY_TITLE | 政策标题 | `["标题","title"]` | 政策文件标题 | string | — | S | realtime | DS_WEB_SEARCH |
| 2 | FIELD_POLICY_DEPT | 发文机关 | `["部门","dept"]` | 政策发布机关 | string | — | S | realtime | DS_WEB_SEARCH |
| 3 | FIELD_POLICY_DATE | 发布时间 | `["日期","date"]` | 政策发布日期 | date | — | S | realtime | DS_WEB_SEARCH |
| 4 | FIELD_POLICY_TYPE | 政策类型 | `["类型","type"]` | 政策分类（法规/通知/批复等） | string | — | S | realtime | DS_WEB_SEARCH |
| 5 | FIELD_POLICY_FULLTEXT | 政策全文 | `["正文","原文","content"]` | 政策文件完整内容 | string | — | S | realtime | DS_WEB_SEARCH |
| 6 | FIELD_POLICY_LINK | 政策链接 | `["url"]` | 政策原文URL | string | — | S | realtime | DS_WEB_SEARCH |


## 第三组：公司基本面层（7 个 Concept，共 112 个 DataField）


### CONCEPT_REALTIME_QUOTE（实时行情与估值）
> 默认数据源：DS_TENCENT_QUOTE（优先）/ DS_TUSHARE_DAILY_BASIC（备选）

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_QUOTE_NAME | 股票名称 | `["名称","name"]` | 股票中文名称 | string | — | B | realtime | DS_TENCENT_QUOTE |
| 2 | FIELD_QUOTE_CODE | 股票代码 | `["code"]` | 股票代码 | string | — | B | realtime | DS_TENCENT_QUOTE |
| 3 | FIELD_QUOTE_PRICE | 当前价 | `["价格","股价","price"]` | 最新成交价 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 4 | FIELD_QUOTE_PCT_CHG | 涨跌幅 | `["涨幅","pct_chg"]` | 当日涨跌幅百分比 | float | % | B | realtime | DS_TENCENT_QUOTE |
| 5 | FIELD_QUOTE_CHG | 涨跌额 | `["涨跌","chg"]` | 当日涨跌金额 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 6 | FIELD_QUOTE_VOL | 成交量 | `["量","volume"]` | 当日成交量（手） | float | 手 | B | realtime | DS_TENCENT_QUOTE |
| 7 | FIELD_QUOTE_AMOUNT | 成交额 | `["额","amount"]` | 当日成交额 | float | 万元 | B | realtime | DS_TENCENT_QUOTE |
| 8 | FIELD_QUOTE_HIGH | 最高价 | `["最高","high"]` | 当日最高价 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 9 | FIELD_QUOTE_LOW | 最低价 | `["最低","low"]` | 当日最低价 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 10 | FIELD_QUOTE_OPEN | 开盘价 | `["开盘","open"]` | 当日开盘价 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 11 | FIELD_QUOTE_PRE_CLOSE | 昨收价 | `["昨收","昨收盘","pre_close"]` | 前一交易日收盘价 | float | 元 | B | realtime | DS_TENCENT_QUOTE |
| 12 | FIELD_TOTAL_MV | 总市值 | `["市值","总市值","total_mv"]` | 公司总市值 | float | 亿元 | B | realtime | DS_TENCENT_QUOTE |
| 13 | FIELD_FLOAT_MV | 流通市值 | `["流通市值","float_mv"]` | 流通股本市值 | float | 亿元 | B | realtime | DS_TENCENT_QUOTE |
| 14 | FIELD_PE_DYNAMIC | 市盈率(动态) | `["PE","pe_dynamic"]` | 动态市盈率 | float | 倍 | B | realtime | DS_TENCENT_QUOTE |
| 15 | FIELD_PE_TTM | 市盈率TTM | `["PE_TTM","pe_ttm"]` | 滚动市盈率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 16 | FIELD_PB | 市净率 | `["PB","市净","pb"]` | 市净率 | float | 倍 | B | realtime | DS_TENCENT_QUOTE |
| 17 | FIELD_PS_TTM | 市销率 | `["PS","市销率","ps_ttm"]` | 滚动市销率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 18 | FIELD_TURNOVER_RATE | 换手率 | `["换手","turnover_rate"]` | 流通股本换手率 | float | % | B | realtime | DS_TENCENT_QUOTE |
| 19 | FIELD_VOLUME_RATIO | 量比 | `["量比","volume_ratio"]` | 当日量比 | float | 倍 | B | realtime | DS_TENCENT_QUOTE |
| 20 | FIELD_AMPLITUDE | 振幅 | `["amplitude"]` | 当日价格振幅 | float | % | B | realtime | DS_TENCENT_QUOTE |
| 21 | FIELD_DIVIDEND_YIELD | 股息率 | `["股息","dv_ttm"]` | 滚动股息率 | float | % | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 22 | FIELD_LIMIT_UP | 涨停价 | `["涨停","up_limit"]` | 当日涨停价格 | float | 元 | A | intraday | DS_TUSHARE_STK_LIMIT |
| 23 | FIELD_LIMIT_DOWN | 跌停价 | `["跌停","down_limit"]` | 当日跌停价格 | float | 元 | A | intraday | DS_TUSHARE_STK_LIMIT |
| 24 | FIELD_HIGH_52W | 52周最高 | `["年高","high52w"]` | 过去52周最高价 | float | 元 | B | daily_17:00 | DS_TENCENT_QUOTE |
| 25 | FIELD_LOW_52W | 52周最低 | `["年低","low52w"]` | 过去52周最低价 | float | 元 | B | daily_17:00 | DS_TENCENT_QUOTE |
| 26 | FIELD_YTD_PCT | 年初至今涨幅 | `["ytd","current_year_percent"]` | 年初至今累计涨幅 | float | % | B | daily_17:00 | DS_TENCENT_QUOTE |


### CONCEPT_HISTORICAL_KLINE（历史K线）
> 默认数据源：DS_TUSHARE_DAILY / DS_TUSHARE_ADJ_FACTOR / DS_TUSHARE_STK_FACTOR

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_KLINE_DATE | 日期 | `["交易日","trade_date"]` | K线交易日期 | date | — | A | daily_17:00 | DS_TUSHARE_DAILY |
| 2 | FIELD_KLINE_OPEN | 开盘价 | `["开盘","open"]` | 当日开盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 3 | FIELD_KLINE_HIGH | 最高价 | `["最高","high"]` | 当日最高价 | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 4 | FIELD_KLINE_LOW | 最低价 | `["最低","low"]` | 当日最低价 | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 5 | FIELD_KLINE_CLOSE | 收盘价 | `["收盘","close"]` | 当日收盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 6 | FIELD_KLINE_PRE_CLOSE | 昨日收盘 | `["昨收","pre_close"]` | 前收盘价（除权价） | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 7 | FIELD_KLINE_CHG | 涨跌额 | `["涨跌","change"]` | 涨跌金额 | float | 元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 8 | FIELD_KLINE_PCT_CHG | 涨跌幅 | `["涨幅","pct_chg"]` | 涨跌幅百分比 | float | % | A | daily_17:00 | DS_TUSHARE_DAILY |
| 9 | FIELD_KLINE_VOL | 成交量 | `["量","vol"]` | 成交量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 10 | FIELD_KLINE_AMOUNT | 成交额 | `["额","amount"]` | 成交额（千元） | float | 千元 | A | daily_17:00 | DS_TUSHARE_DAILY |
| 11 | FIELD_ADJ_FACTOR | 复权因子 | `["复权","adj_factor"]` | 复权因子 | float | — | A | daily_17:00 | DS_TUSHARE_ADJ_FACTOR |
| 12 | FIELD_MACD_DIF | MACD_DIF | `["DIF","macd_dif"]` | MACD指标DIF线 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 13 | FIELD_MACD_DEA | MACD_DEA | `["DEA","macd_dea"]` | MACD指标DEA线 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 14 | FIELD_MACD | MACD柱 | `["MACD","macd"]` | MACD柱状线 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 15 | FIELD_KDJ_K | KDJ_K | `["K值","kdj_k"]` | KDJ指标K值 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 16 | FIELD_KDJ_D | KDJ_D | `["D值","kdj_d"]` | KDJ指标D值 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 17 | FIELD_KDJ_J | KDJ_J | `["J值","kdj_j"]` | KDJ指标J值 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 18 | FIELD_RSI_6 | RSI_6 | `["6日RSI","rsi_6"]` | 6日相对强弱指标 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 19 | FIELD_RSI_12 | RSI_12 | `["12日RSI","rsi_12"]` | 12日相对强弱指标 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 20 | FIELD_RSI_24 | RSI_24 | `["24日RSI","rsi_24"]` | 24日相对强弱指标 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 21 | FIELD_BOLL_UPPER | BOLL上轨 | `["上轨","boll_upper"]` | 布林线上轨 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 22 | FIELD_BOLL_MID | BOLL中轨 | `["中轨","boll_mid"]` | 布林线中轨 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 23 | FIELD_BOLL_LOWER | BOLL下轨 | `["下轨","boll_lower"]` | 布林线下轨 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |
| 24 | FIELD_CCI | CCI | `["cci"]` | 顺势指标 | float | — | A | daily_17:00 | DS_TUSHARE_STK_FACTOR |


### CONCEPT_FINANCIAL_SUMMARY（财务摘要）
> 默认数据源：DS_TUSHARE_FINA_IND

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FIN_END_DATE | 报告期 | `["日期","end_date"]` | 财务报告截止日期 | date | — | A | quarterly | DS_TUSHARE_FINA_IND |
| 2 | FIELD_FIN_ROE_WAA | ROE(加权) | `["净资产收益率","roe_waa"]` | 加权平均净资产收益率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 3 | FIELD_FIN_ROE_DILUTED | ROE(摊薄) | `["摊薄ROE","roe_diluted"]` | 摊薄净资产收益率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 4 | FIELD_FIN_GROSS_MARGIN | 毛利率 | `["毛利","gross_margin"]` | 销售毛利率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 5 | FIELD_FIN_NET_MARGIN | 净利率 | `["净利","net_margin"]` | 销售净利率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 6 | FIELD_FIN_OP_MARGIN | 营业利润率 | `["营业利润","op_of_gr"]` | 营业利润/营业总收入 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 7 | FIELD_FIN_REVENUE_YOY | 营收同比增速 | `["营收增速","or_yoy"]` | 营业收入同比增长率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 8 | FIELD_FIN_PROFIT_YOY | 净利同比增速 | `["利润增速","netprofit_yoy"]` | 净利润同比增长率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 9 | FIELD_FIN_DEBT_RATIO | 资产负债率 | `["负债率","debt_to_assets"]` | 总负债/总资产 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 10 | FIELD_FIN_EQUITY_MULT | 权益乘数 | `["杠杆","assets_to_eqt"]` | 总资产/股东权益 | float | 倍 | A | quarterly | DS_TUSHARE_FINA_IND |
| 11 | FIELD_FIN_ASSETS_TURN | 总资产周转率 | `["资产周转","assets_turn"]` | 营业收入/总资产 | float | 次 | A | quarterly | DS_TUSHARE_FINA_IND |
| 12 | FIELD_FIN_INV_TURN | 存货周转率 | `["存货周转","inv_turn"]` | 营业成本/平均存货 | float | 次 | A | quarterly | DS_TUSHARE_FINA_IND |
| 13 | FIELD_FIN_AR_TURN | 应收账款周转率 | `["应收周转","ar_turn"]` | 营业收入/平均应收账款 | float | 次 | A | quarterly | DS_TUSHARE_FINA_IND |
| 14 | FIELD_FIN_OCF_TO_OR | 经营现金流/营收 | `["现金流占比","ocf_to_or"]` | 经营现金流/营业收入 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 15 | FIELD_FIN_EPS | 基本每股收益 | `["EPS","eps"]` | 基本每股收益 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 16 | FIELD_FIN_DT_EPS | 稀释每股收益 | `["稀释EPS","dt_eps"]` | 稀释每股收益 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 17 | FIELD_FIN_BPS | 每股净资产 | `["BPS","bps"]` | 每股净资产 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 18 | FIELD_FIN_OCFPS | 每股经营现金流 | `["每股现金流","ocfps"]` | 每股经营活动现金流 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 19 | FIELD_FIN_CAPITAL_RESERVE | 每股资本公积 | `["资本公积","capital_rese_ps"]` | 每股资本公积金 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 20 | FIELD_FIN_UNDIST_PROFIT | 每股未分配利润 | `["未分配利润","undist_profit_ps"]` | 每股未分配利润 | float | 元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 21 | FIELD_FIN_RD_RATIO | 研发费用占比 | `["研发占比","rd_exp"]` | 研发费用/营业收入 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |


### CONCEPT_FINANCIAL_DEEP（深度财务指标）
> 默认数据源：DS_TUSHARE_FINA_IND

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FIN_ROIC | ROIC | `["投入资本回报率","roic"]` | 投入资本回报率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 2 | FIELD_FIN_ROE_DT | ROE(扣非) | `["扣非ROE","roe_dt"]` | 扣除非经常损益后ROE | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 3 | FIELD_FIN_EBIT | EBIT | `["息税前利润","ebit"]` | 息税前利润 | float | 亿元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 4 | FIELD_FIN_EBITDA | EBITDA | `["息税折旧摊销前利润","ebitda"]` | 息税折旧摊销前利润 | float | 亿元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 5 | FIELD_FIN_EBIT_RATIO | EBIT/营业总收入 | `["ebit_of_gr"]` | EBIT占营业总收入比例 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 6 | FIELD_FIN_INTEREST_COVER | 已获利息倍数 | `["利息保障","ebit_to_interest"]` | EBIT/利息费用 | float | 倍 | A | quarterly | DS_TUSHARE_FINA_IND |
| 7 | FIELD_FIN_DEBT_TO_CAPITAL | 带息债务/全部投入资本 | `["债务资本比","int_to_talcap"]` | 带息债务/全部投入资本 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 8 | FIELD_FIN_FCFF | 企业自由现金流 | `["FCFF","fcff"]` | 企业自由现金流 | float | 亿元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 9 | FIELD_FIN_FCFE | 股权自由现金流 | `["FCFE","fcfe"]` | 股权自由现金流 | float | 亿元 | A | quarterly | DS_TUSHARE_FINA_IND |
| 10 | FIELD_FIN_FA_TURN | 固定资产周转率 | `["固定周转","fa_turn"]` | 营业收入/平均固定资产 | float | 次 | A | quarterly | DS_TUSHARE_FINA_IND |
| 11 | FIELD_FIN_CA_TURN | 流动资产周转率 | `["流动周转","ca_turn"]` | 营业收入/平均流动资产 | float | 次 | A | quarterly | DS_TUSHARE_FINA_IND |
| 12 | FIELD_FIN_Q_ROE | 单季度ROE | `["季度ROE","q_roe"]` | 单季度净资产收益率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 13 | FIELD_FIN_Q_GROSS_MARGIN | 单季度毛利率 | `["季度毛利率","q_gsprofit_margin"]` | 单季度毛利率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 14 | FIELD_FIN_Q_NET_MARGIN | 单季度净利率 | `["季度净利率","q_netprofit_margin"]` | 单季度净利率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 15 | FIELD_FIN_Q_REVENUE_YOY | 单季度营收增速 | `["季度营收","q_gr_yoy"]` | 单季度营收同比增长率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 16 | FIELD_FIN_Q_PROFIT_YOY | 单季度净利增速 | `["季度净利","q_netprofit_yoy"]` | 单季度净利润同比增长率 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 17 | FIELD_FIN_IMPAIR_RATIO | 资产减值损失/营收 | `["impai_ttm"]` | 资产减值损失占营收比例 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |
| 18 | FIELD_FIN_INVEST_INCOME_RATIO | 价值变动净收益/利润总额 | `["investincome_of_ebt"]` | 价值变动净收益占利润总额比例 | float | % | A | quarterly | DS_TUSHARE_FINA_IND |


### CONCEPT_FINANCIAL_STATEMENTS（三大财务报表）
> 默认数据源：DS_TUSHARE_INCOME / DS_TUSHARE_BALANCE / DS_TUSHARE_CASHFLOW

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FS_END_DATE | 报告期 | `["end_date"]` | 财务报表截止日期 | date | — | A | quarterly | DS_TUSHARE_INCOME |
| 2 | FIELD_FS_TOTAL_REVENUE | 营业总收入 | `["营收","revenue"]` | 营业总收入 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 3 | FIELD_FS_REVENUE | 营业收入 | `["收入","oper_revenue"]` | 营业收入 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 4 | FIELD_FS_TOTAL_COGS | 营业总成本 | `["总成本","total_cogs"]` | 营业总成本 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 5 | FIELD_FS_OPER_COST | 营业成本 | `["成本","oper_cost"]` | 营业成本 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 6 | FIELD_FS_SELL_EXP | 销售费用 | `["营销费用","sell_exp"]` | 销售费用 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 7 | FIELD_FS_ADMIN_EXP | 管理费用 | `["管理费","admin_exp"]` | 管理费用 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 8 | FIELD_FS_RD_EXP | 研发费用 | `["研发","rd_exp"]` | 研发费用 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 9 | FIELD_FS_FIN_EXP | 财务费用 | `["利息","fin_exp"]` | 财务费用 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 10 | FIELD_FS_OPER_PROFIT | 营业利润 | `["经营利润","operate_profit"]` | 营业利润 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 11 | FIELD_FS_TOTAL_PROFIT | 利润总额 | `["税前利润","total_profit"]` | 利润总额 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 12 | FIELD_FS_NET_PROFIT | 净利润 | `["净利","n_income"]` | 净利润 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 13 | FIELD_FS_NET_PROFIT_ATTR | 归母净利润 | `["归母净利","n_income_attr_p"]` | 归属母公司股东净利润 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 14 | FIELD_FS_MINORITY_GAIN | 少数股东损益 | `["minority_gain"]` | 少数股东损益 | float | 亿元 | A | quarterly | DS_TUSHARE_INCOME |
| 15 | FIELD_FS_BASIC_EPS | 基本每股收益 | `["EPS","basic_eps"]` | 基本每股收益 | float | 元 | A | quarterly | DS_TUSHARE_INCOME |
| 16 | FIELD_FS_DILUTED_EPS | 稀释每股收益 | `["稀释EPS","diluted_eps"]` | 稀释每股收益 | float | 元 | A | quarterly | DS_TUSHARE_INCOME |
| 17 | FIELD_FS_TOTAL_ASSETS | 总资产 | `["total_assets"]` | 资产总计 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 18 | FIELD_FS_TOTAL_LIAB | 总负债 | `["total_liab"]` | 负债总计 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 19 | FIELD_FS_TOTAL_EQUITY | 股东权益 | `["净资产","total_hldr_eqy"]` | 所有者权益合计 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 20 | FIELD_FS_MONEY_CAP | 货币资金 | `["现金","money_cap"]` | 货币资金 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 21 | FIELD_FS_ACCOUNTS_RECV | 应收账款 | `["应收","accts_receiv"]` | 应收账款 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 22 | FIELD_FS_INVENTORY | 存货 | `["库存","inventories"]` | 存货 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 23 | FIELD_FS_FIXED_ASSETS | 固定资产 | `["固定","fix_assets"]` | 固定资产 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 24 | FIELD_FS_CIP | 在建工程 | `["在建","cip"]` | 在建工程 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 25 | FIELD_FS_INTAN_ASSETS | 无形资产 | `["intan_assets"]` | 无形资产 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 26 | FIELD_FS_GOODWILL | 商誉 | `["goodwill"]` | 商誉 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 27 | FIELD_FS_ST_BORR | 短期借款 | `["短贷","st_borr"]` | 短期借款 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 28 | FIELD_FS_LT_BORR | 长期借款 | `["长贷","lt_borr"]` | 长期借款 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 29 | FIELD_FS_ACCOUNTS_PAY | 应付账款 | `["应付","accts_pay"]` | 应付账款 | float | 亿元 | A | quarterly | DS_TUSHARE_BALANCE |
| 30 | FIELD_FS_OPER_CF | 经营现金流净额 | `["经营现金流","oper_cf"]` | 经营活动现金流净额 | float | 亿元 | A | quarterly | DS_TUSHARE_CASHFLOW |
| 31 | FIELD_FS_INVEST_CF | 投资现金流净额 | `["投资现金流","invest_cf"]` | 投资活动现金流净额 | float | 亿元 | A | quarterly | DS_TUSHARE_CASHFLOW |
| 32 | FIELD_FS_FINANCE_CF | 筹资现金流净额 | `["筹资现金流","finance_cf"]` | 筹资活动现金流净额 | float | 亿元 | A | quarterly | DS_TUSHARE_CASHFLOW |
| 33 | FIELD_FS_END_CASH | 期末现金余额 | `["现金余额","end_bal_cash"]` | 期末现金及等价物余额 | float | 亿元 | A | quarterly | DS_TUSHARE_CASHFLOW |
| 34 | FIELD_FS_FREE_CF | 自由现金流 | `["free_cashflow"]` | 自由现金流 | float | 亿元 | A | quarterly | DS_TUSHARE_CASHFLOW |


### CONCEPT_VALUATION_COMPARE（估值对比分析）
> 默认数据源：DS_TUSHARE_DAILY_BASIC / DS_XUEQIU_IND_COMPARE / DS_LOCAL_CALC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_VAL_PE_TTM | PE_TTM | `["市盈率","pe_ttm"]` | 滚动市盈率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 2 | FIELD_VAL_PE_PCT | PE历史分位数 | `["PE分位","pe_pct"]` | 近3/5年PE分位数 | float | % | A | daily_17:00 | DS_LOCAL_CALC |
| 3 | FIELD_VAL_PB | PB | `["市净率","pb"]` | 市净率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 4 | FIELD_VAL_PB_PCT | PB历史分位数 | `["PB分位","pb_pct"]` | 近3/5年PB分位数 | float | % | A | daily_17:00 | DS_LOCAL_CALC |
| 5 | FIELD_VAL_PS_TTM | PS_TTM | `["市销率","ps_ttm"]` | 滚动市销率 | float | 倍 | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 6 | FIELD_VAL_PS_PCT | PS历史分位数 | `["PS分位","ps_pct"]` | 近3/5年PS分位数 | float | % | A | daily_17:00 | DS_LOCAL_CALC |
| 7 | FIELD_VAL_IND_PE | 行业平均PE | `["行业PE","ind_pe"]` | 同行业公司PE中位数 | float | 倍 | A | quarterly | DS_XUEQIU_IND_COMPARE |
| 8 | FIELD_VAL_IND_PB | 行业平均PB | `["行业PB","ind_pb"]` | 同行业公司PB中位数 | float | 倍 | A | quarterly | DS_XUEQIU_IND_COMPARE |
| 9 | FIELD_VAL_IND_ROE | 行业平均ROE | `["行业ROE","ind_roe"]` | 同行业公司ROE中位数 | float | % | A | quarterly | DS_XUEQIU_IND_COMPARE |
| 10 | FIELD_VAL_RATING | 估值评级 | `["评级","rating"]` | 综合估值评级（低估/合理/高估） | string | — | A | daily_17:00 | DS_LOCAL_CALC |


### CONCEPT_COMPANY_PROFILE（公司概况）
> 默认数据源：DS_TUSHARE_STOCK_BASIC / DS_TUSHARE_STOCK_COMPANY / DS_TUSHARE_NAMECHANGE

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_PROFILE_FULLNAME | 公司全称 | `["fullname"]` | 公司完整名称 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 2 | FIELD_PROFILE_NAME | 股票简称 | `["name"]` | 股票交易简称 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 3 | FIELD_PROFILE_CODE | 股票代码 | `["ts_code"]` | TS股票代码 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 4 | FIELD_PROFILE_INDUSTRY | 所属行业 | `["industry"]` | 申万行业分类 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 5 | FIELD_PROFILE_AREA | 所属地域 | `["area"]` | 注册地省份 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 6 | FIELD_PROFILE_LIST_DATE | 上市日期 | `["上市","list_date"]` | 首次上市日期 | date | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 7 | FIELD_PROFILE_DELIST_DATE | 退市日期 | `["delist_date"]` | 退市日期（如有） | date | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 8 | FIELD_PROFILE_ACT_NAME | 实控人名称 | `["实际控制人","act_name"]` | 实际控制人姓名/机构 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 9 | FIELD_PROFILE_ACT_TYPE | 实控人性质 | `["act_ent_type"]` | 实控人企业性质 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 10 | FIELD_PROFILE_IS_HS | 是否沪深港通 | `["is_hs"]` | 是否沪深港通标的（N/H/S） | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 11 | FIELD_PROFILE_EXCHANGE | 交易所代码 | `["exchange"]` | 上市交易所 | string | — | A | weekly | DS_TUSHARE_STOCK_BASIC |
| 12 | FIELD_PROFILE_CHAIRMAN | 法人代表 | `["chairman"]` | 公司法人代表 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 13 | FIELD_PROFILE_MANAGER | 总经理 | `["manager","CEO"]` | 公司总经理 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 14 | FIELD_PROFILE_SECRETARY | 董秘 | `["secretary"]` | 董事会秘书 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 15 | FIELD_PROFILE_REG_CAPITAL | 注册资本 | `["资本","reg_capital"]` | 注册资本（万元） | float | 万元 | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 16 | FIELD_PROFILE_SETUP_DATE | 注册日期 | `["setup_date"]` | 公司注册成立日期 | date | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 17 | FIELD_PROFILE_EMPLOYEES | 员工人数 | `["员工","employees"]` | 公司员工总数 | int | 人 | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 18 | FIELD_PROFILE_WEBSITE | 公司主页 | `["website"]` | 公司官网URL | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 19 | FIELD_PROFILE_OFFICE | 办公地址 | `["office"]` | 办公地址 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 20 | FIELD_PROFILE_MAIN_BUSINESS | 主要业务 | `["主营业务","main_business"]` | 主要业务及产品 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 21 | FIELD_PROFILE_BUSINESS_SCOPE | 经营范围 | `["business_scope"]` | 经营范围描述 | string | — | A | weekly | DS_TUSHARE_STOCK_COMPANY |
| 22 | FIELD_PROFILE_NAME_HISTORY | 曾用名 | `["name_history"]` | 历史曾用名称 | string | — | A | weekly | DS_TUSHARE_NAMECHANGE |


## 第四组：公司治理与事件层（6 个 Concept，共 51 个 DataField）


### CONCEPT_TOP_HOLDERS（前十大股东）
> 默认数据源：DS_TUSHARE_TOP10

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_HOLDER_ANN_DATE | 公告日期 | `["ann_date"]` | 股东披露公告日期 | date | — | A | quarterly | DS_TUSHARE_TOP10 |
| 2 | FIELD_HOLDER_END_DATE | 报告期 | `["end_date"]` | 股东数据截止日期 | date | — | A | quarterly | DS_TUSHARE_TOP10 |
| 3 | FIELD_HOLDER_NAME | 股东名称 | `["名称","holder_name"]` | 股东名称 | string | — | A | quarterly | DS_TUSHARE_TOP10 |
| 4 | FIELD_HOLDER_SHARES | 持股数量 | `["股数","hold_amount"]` | 持股数量（股） | float | 股 | A | quarterly | DS_TUSHARE_TOP10 |
| 5 | FIELD_HOLDER_RATIO | 占总股本比例 | `["持股比例","hold_ratio"]` | 占总股本比例 | float | % | A | quarterly | DS_TUSHARE_TOP10 |
| 6 | FIELD_HOLDER_FLOAT_RATIO | 占流通股本比例 | `["流通占比","hold_float_ratio"]` | 占流通股本比例 | float | % | A | quarterly | DS_TUSHARE_TOP10 |
| 7 | FIELD_HOLDER_CHANGE | 持股变动 | `["增减","hold_change"]` | 较上期持股变动 | float | % | A | quarterly | DS_TUSHARE_TOP10 |
| 8 | FIELD_HOLDER_TYPE | 股东类型 | `["类型","holder_type"]` | 股东类型分类 | string | — | A | quarterly | DS_TUSHARE_TOP10 |


### CONCEPT_INSTITUTION_RATING（机构持仓与评级）
> 默认数据源：DS_AKSHARE_INST_HOLD / DS_TUSHARE_REPORT_RC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_INST_END_DATE | 报告期 | `["end_date"]` | 机构持仓截止日期 | date | — | A | quarterly | DS_AKSHARE_INST_HOLD |
| 2 | FIELD_INST_COUNT | 持仓机构数量 | `["机构数","org_count"]` | 持有该股的机构家数 | int | 家 | A | quarterly | DS_AKSHARE_INST_HOLD |
| 3 | FIELD_INST_RATIO | 持仓比例 | `["机构持仓","holding_ratio"]` | 机构持股占总股本比例 | float | % | A | quarterly | DS_AKSHARE_INST_HOLD |
| 4 | FIELD_INST_CHANGE | 季度持仓变动 | `["变动","change_ratio"]` | 较上季度持仓变动 | float | % | A | quarterly | DS_AKSHARE_INST_HOLD |
| 5 | FIELD_INST_ORG_NAME | 机构名称 | `["org_name"]` | 研究机构名称 | string | — | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 6 | FIELD_INST_REPORT_DATE | 研报日期 | `["report_date"]` | 研报发布日期 | date | — | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 7 | FIELD_INST_REPORT_TITLE | 研报标题 | `["report_title"]` | 研报标题 | string | — | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 8 | FIELD_INST_RATING | 卖方评级 | `["评级","rating"]` | 券商评级（买入/增持/中性等） | string | — | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 9 | FIELD_INST_FORECAST_EPS | 预测EPS | `["forecast_eps"]` | 券商预测每股收益 | float | 元 | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 10 | FIELD_INST_FORECAST_ROE | 预测ROE | `["forecast_roe"]` | 券商预测净资产收益率 | float | % | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 11 | FIELD_INST_TARGET_MAX | 预测最高目标价 | `["max_price"]` | 券商预测最高目标价 | float | 元 | A | daily_17:00 | DS_TUSHARE_REPORT_RC |
| 12 | FIELD_INST_TARGET_MIN | 预测最低目标价 | `["min_price"]` | 券商预测最低目标价 | float | 元 | A | daily_17:00 | DS_TUSHARE_REPORT_RC |


### CONCEPT_ANNOUNCEMENT（公司公告）
> 默认数据源：DS_AKSHARE_CNINFO

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_ANNOUNCE_TITLE | 公告标题 | `["标题","title"]` | 公告标题 | string | — | S | realtime | DS_AKSHARE_CNINFO |
| 2 | FIELD_ANNOUNCE_DATE | 公告时间 | `["时间","ann_date"]` | 公告发布时间 | date | — | S | realtime | DS_AKSHARE_CNINFO |
| 3 | FIELD_ANNOUNCE_TYPE | 公告类型 | `["类型","ann_type"]` | 公告分类类型 | string | — | S | realtime | DS_AKSHARE_CNINFO |
| 4 | FIELD_ANNOUNCE_LINK | 公告链接 | `["链接","url"]` | 公告原文URL | string | — | S | realtime | DS_AKSHARE_CNINFO |


### CONCEPT_IRM_QA（互动易问答）
> 默认数据源：DS_AKSHARE_IRM

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_IRM_QUESTION | 提问内容 | `["问题","question"]` | 投资者提问内容 | string | — | S | realtime | DS_AKSHARE_IRM |
| 2 | FIELD_IRM_QUESTION_DATE | 提问时间 | `["时间","ask_date"]` | 提问发布时间 | date | — | S | realtime | DS_AKSHARE_IRM |
| 3 | FIELD_IRM_ANSWER | 回答内容 | `["回复","answer"]` | 公司回复内容 | string | — | S | realtime | DS_AKSHARE_IRM |
| 4 | FIELD_IRM_ANSWER_DATE | 回答时间 | `["回复时间","answer_date"]` | 公司回复时间 | date | — | S | realtime | DS_AKSHARE_IRM |
| 5 | FIELD_IRM_ASKER | 提问人 | `["asker"]` | 提问者名称 | string | — | S | realtime | DS_AKSHARE_IRM |


### CONCEPT_IPO_INFO（IPO信息）
> 默认数据源：DS_TUSHARE_NEW_SHARE

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_IPO_CODE | 股票代码 | `["ts_code"]` | 新股上市代码 | string | — | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 2 | FIELD_IPO_NAME | 股票名称 | `["name"]` | 新股名称 | string | — | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 3 | FIELD_IPO_PRICE | 发行价 | `["价格","price"]` | 首次公开发行价格 | float | 元 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 4 | FIELD_IPO_AMOUNT | 发行总量 | `["发行量","amount"]` | 发行总量（万股） | float | 万股 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 5 | FIELD_IPO_MARKET_AMOUNT | 上网发行量 | `["网上发行","market_amount"]` | 网上发行量（万股） | float | 万股 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 6 | FIELD_IPO_LIMIT_AMOUNT | 个人申购上限 | `["申购上限","limit_amount"]` | 个人申购上限（万股） | float | 万股 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 7 | FIELD_IPO_FUNDS | 募集资金 | `["募资","funds"]` | 募集资金总额（亿元） | float | 亿元 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 8 | FIELD_IPO_PE | 发行市盈率 | `["发行PE","pe"]` | 发行市盈率 | float | 倍 | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 9 | FIELD_IPO_BALLOT | 中签率 | `["ballot"]` | 网上发行中签率 | float | % | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 10 | FIELD_IPO_IPO_DATE | 上网发行日期 | `["发行日","ipo_date"]` | 网上发行日期 | date | — | A | event_driven | DS_TUSHARE_NEW_SHARE |
| 11 | FIELD_IPO_LIST_DATE | 上市日期 | `["上市","list_date"]` | 正式上市日期 | date | — | A | event_driven | DS_TUSHARE_NEW_SHARE |


### CONCEPT_DIVIDEND（分红送配）
> 默认数据源：DS_TUSHARE_DIVIDEND

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_DIV_END_DATE | 分红年度 | `["年度","end_date"]` | 分红对应的财务年度 | date | — | A | event_driven | DS_TUSHARE_DIVIDEND |
| 2 | FIELD_DIV_ANN_DATE | 预案公告日 | `["ann_date"]` | 分红预案公告日期 | date | — | A | event_driven | DS_TUSHARE_DIVIDEND |
| 3 | FIELD_DIV_PROC | 实施进度 | `["div_proc"]` | 实施进度（预案/实施/取消） | string | — | A | event_driven | DS_TUSHARE_DIVIDEND |
| 4 | FIELD_DIV_CASH | 每股分红(税后) | `["税后派息","cash_div"]` | 每股税后现金分红 | float | 元 | A | event_driven | DS_TUSHARE_DIVIDEND |
| 5 | FIELD_DIV_CASH_TAX | 每股分红(税前) | `["税前派息","cash_div_tax"]` | 每股税前现金分红 | float | 元 | A | event_driven | DS_TUSHARE_DIVIDEND |
| 6 | FIELD_DIV_STK | 每股送转 | `["送转","stk_div"]` | 每股送股+转增合计 | float | 股 | A | event_driven | DS_TUSHARE_DIVIDEND |
| 7 | FIELD_DIV_STK_BO | 每股送股比例 | `["送股","stk_bo_rate"]` | 每股送股比例 | float | 股 | A | event_driven | DS_TUSHARE_DIVIDEND |
| 8 | FIELD_DIV_STK_CO | 每股转增比例 | `["转增","stk_co_rate"]` | 每股转增比例 | float | 股 | A | event_driven | DS_TUSHARE_DIVIDEND |
| 9 | FIELD_DIV_RECORD_DATE | 股权登记日 | `["登记日","record_date"]` | 股权登记日期 | date | — | A | event_driven | DS_TUSHARE_DIVIDEND |
| 10 | FIELD_DIV_EX_DATE | 除权除息日 | `["除权日","ex_date"]` | 除权除息日期 | date | — | A | event_driven | DS_TUSHARE_DIVIDEND |
| 11 | FIELD_DIV_PAY_DATE | 派息日 | `["pay_date"]` | 现金红利派发日期 | date | — | A | event_driven | DS_TUSHARE_DIVIDEND |


## 第五组：资金与交易层（5 个 Concept，共 55 个 DataField）


### CONCEPT_FUND_FLOW（个股资金流向）
> 默认数据源：DS_TUSHARE_MONEYFLOW

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FLOW_DATE | 日期 | `["trade_date"]` | 交易日 | date | — | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 2 | FIELD_FLOW_SMALL_BUY_VOL | 小单买入量 | `["小单买入","buy_sm_vol"]` | 小单买入成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 3 | FIELD_FLOW_SMALL_BUY_AMT | 小单买入额 | `["buy_sm_amount"]` | 小单买入金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 4 | FIELD_FLOW_SMALL_SELL_VOL | 小单卖出量 | `["小单卖出","sell_sm_vol"]` | 小单卖出成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 5 | FIELD_FLOW_SMALL_SELL_AMT | 小单卖出额 | `["sell_sm_amount"]` | 小单卖出金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 6 | FIELD_FLOW_MEDIUM_BUY_VOL | 中单买入量 | `["中单买入","buy_md_vol"]` | 中单买入成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 7 | FIELD_FLOW_MEDIUM_BUY_AMT | 中单买入额 | `["buy_md_amount"]` | 中单买入金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 8 | FIELD_FLOW_MEDIUM_SELL_VOL | 中单卖出量 | `["中单卖出","sell_md_vol"]` | 中单卖出成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 9 | FIELD_FLOW_MEDIUM_SELL_AMT | 中单卖出额 | `["sell_md_amount"]` | 中单卖出金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 10 | FIELD_FLOW_LARGE_BUY_VOL | 大单买入量 | `["大单买入","buy_lg_vol"]` | 大单买入成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 11 | FIELD_FLOW_LARGE_BUY_AMT | 大单买入额 | `["buy_lg_amount"]` | 大单买入金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 12 | FIELD_FLOW_LARGE_SELL_VOL | 大单卖出量 | `["大单卖出","sell_lg_vol"]` | 大单卖出成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 13 | FIELD_FLOW_LARGE_SELL_AMT | 大单卖出额 | `["sell_lg_amount"]` | 大单卖出金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 14 | FIELD_FLOW_ELG_BUY_VOL | 特大单买入量 | `["特大单买入","buy_elg_vol"]` | 特大单买入成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 15 | FIELD_FLOW_ELG_BUY_AMT | 特大单买入额 | `["buy_elg_amount"]` | 特大单买入金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 16 | FIELD_FLOW_ELG_SELL_VOL | 特大单卖出量 | `["特大单卖出","sell_elg_vol"]` | 特大单卖出成交量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 17 | FIELD_FLOW_ELG_SELL_AMT | 特大单卖出额 | `["sell_elg_amount"]` | 特大单卖出金额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 18 | FIELD_FLOW_NET_VOL | 净流入量 | `["net_mf_vol"]` | 主力净流入量（手） | float | 手 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |
| 19 | FIELD_FLOW_NET_AMT | 净流入额 | `["主力净流入","net_mf_amount"]` | 主力净流入额（万元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MONEYFLOW |


### CONCEPT_NORTHBOUND（北向资金）
> 默认数据源：DS_TUSHARE_HSGT / DS_TUSHARE_HK_HOLD / DS_TUSHARE_HSGT_TOP10

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_NORTH_DATE | 日期 | `["trade_date"]` | 交易日期 | date | — | A | intraday | DS_TUSHARE_HSGT |
| 2 | FIELD_NORTH_NET | 北向资金净流入 | `["北向","north_money"]` | 北向资金净流入（百万元） | float | 百万元 | A | intraday | DS_TUSHARE_HSGT |
| 3 | FIELD_NORTH_SH_NET | 沪股通净流入 | `["沪股通","hgt"]` | 沪股通净流入（百万元） | float | 百万元 | A | intraday | DS_TUSHARE_HSGT |
| 4 | FIELD_NORTH_SZ_NET | 深股通净流入 | `["深股通","sgt"]` | 深股通净流入（百万元） | float | 百万元 | A | intraday | DS_TUSHARE_HSGT |
| 5 | FIELD_NORTH_GGT_SS | 港股通(沪) | `["ggt_ss"]` | 港股通（上海）资金 | float | 百万元 | A | intraday | DS_TUSHARE_HSGT |
| 6 | FIELD_NORTH_GGT_SZ | 港股通(深) | `["ggt_sz"]` | 港股通（深圳）资金 | float | 百万元 | A | intraday | DS_TUSHARE_HSGT |
| 7 | FIELD_NORTH_HOLD_VOL | 持股数量 | `["持股","vol"]` | 北向资金持股数量（股） | float | 股 | A | daily_20:00 | DS_TUSHARE_HK_HOLD |
| 8 | FIELD_NORTH_HOLD_RATIO | 持股占比 | `["占比","ratio"]` | 持股占已发行股份比例 | float | % | A | daily_20:00 | DS_TUSHARE_HK_HOLD |
| 9 | FIELD_NORTH_TOP10 | 十大成交股 | `["top10"]` | 沪深股通十大成交股列表 | string | — | A | daily_20:00 | DS_TUSHARE_HSGT_TOP10 |
| 10 | FIELD_NORTH_TOP10_AMT | 成交金额 | `["amount"]` | 十大成交股成交金额 | float | 亿元 | A | daily_20:00 | DS_TUSHARE_HSGT_TOP10 |
| 11 | FIELD_NORTH_TOP10_NET | 净成交金额 | `["net_amount"]` | 十大成交股净买入金额 | float | 亿元 | A | daily_20:00 | DS_TUSHARE_HSGT_TOP10 |


### CONCEPT_MARGIN（融资融券）
> 默认数据源：DS_TUSHARE_MARGIN

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_MARGIN_DATE | 日期 | `["trade_date"]` | 交易日期 | date | — | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 2 | FIELD_MARGIN_BALANCE | 融资余额 | `["融资金额","rzye"]` | 融资余额（元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 3 | FIELD_MARGIN_BUY | 融资买入额 | `["买入额","rzmre"]` | 融资买入额（元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 4 | FIELD_MARGIN_REPAY | 融资偿还额 | `["偿还额","rzche"]` | 融资偿还额（元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 5 | FIELD_MARGIN_SHORT_BALANCE | 融券余额 | `["rqye"]` | 融券余额（元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 6 | FIELD_MARGIN_SHORT_VOL | 融券卖出量 | `["融券量","rqmcl"]` | 融券卖出量（股） | float | 股 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 7 | FIELD_MARGIN_SHORT_RESERVE | 融券余量 | `["rqyl"]` | 融券余量（股） | float | 股 | A | daily_20:00 | DS_TUSHARE_MARGIN |
| 8 | FIELD_MARGIN_TOTAL | 融资融券余额 | `["两融余额","rzrqye"]` | 融资融券合计余额（元） | float | 万元 | A | daily_20:00 | DS_TUSHARE_MARGIN |


### CONCEPT_LIMIT_UP_DOWN（涨停跌停分析）
> 默认数据源：DS_TUSHARE_STK_LIMIT / DS_TUSHARE_DAILY_BASIC / DS_LEVISTOCK_ZT_POOL

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_LIMIT_DATE | 日期 | `["trade_date"]` | 交易日期 | date | — | A | intraday | DS_TUSHARE_STK_LIMIT |
| 2 | FIELD_LIMIT_CODE | 股票代码 | `["ts_code"]` | 股票TS代码 | string | — | A | intraday | DS_TUSHARE_STK_LIMIT |
| 3 | FIELD_LIMIT_PRE_CLOSE | 昨日收盘 | `["pre_close"]` | 昨日收盘价（除权价） | float | 元 | A | intraday | DS_TUSHARE_STK_LIMIT |
| 4 | FIELD_LIMIT_UP_PRICE | 涨停价 | `["涨停","up_limit"]` | 当日涨停价格 | float | 元 | A | intraday | DS_TUSHARE_STK_LIMIT |
| 5 | FIELD_LIMIT_DOWN_PRICE | 跌停价 | `["跌停","down_limit"]` | 当日跌停价格 | float | 元 | A | intraday | DS_TUSHARE_STK_LIMIT |
| 6 | FIELD_LIMIT_STATUS | 涨跌停状态 | `["状态","limit_status"]` | 0平/1涨(非停)/2涨停(非一字)/3一字涨停/4跌(非停)/5跌停(非一字)/6一字跌停 | int | — | A | daily_17:00 | DS_TUSHARE_DAILY_BASIC |
| 7 | FIELD_LIMIT_CONTINUOUS | 连板数 | `["连板","continuous"]` | 连续涨停天数 | int | 天 | B | intraday | DS_LEVISTOCK_ZT_POOL |
| 8 | FIELD_LIMIT_FIRST_TIME | 首次封板时间 | `["封板","first_zt_time"]` | 首次涨停封板时间 | string | — | B | intraday | DS_LEVISTOCK_ZT_POOL |
| 9 | FIELD_LIMIT_LAST_TIME | 最后封板时间 | `["last_zt_time"]` | 最后涨停封板时间 | string | — | B | intraday | DS_LEVISTOCK_ZT_POOL |
| 10 | FIELD_LIMIT_OPEN_TIMES | 开板次数 | `["开板","open_times"]` | 涨停开板次数 | int | 次 | B | intraday | DS_LEVISTOCK_ZT_POOL |
| 11 | FIELD_LIMIT_SECTOR | 所属行业 | `["sector"]` | 涨停股票所属行业板块 | string | — | B | intraday | DS_LEVISTOCK_ZT_POOL |


### CONCEPT_PLEDGE_HOLDER_TRADE（股权质押与增减持）
> 默认数据源：DS_TUSHARE_PLEDGE / DS_TUSHARE_PLEDGE_STAT / DS_TUSHARE_HOLDER_TRADE

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_PLEDGE_HOLDER | 股东名称 | `["holder_name"]` | 质押股东名称 | string | — | A | event_driven | DS_TUSHARE_PLEDGE |
| 2 | FIELD_PLEDGE_AMOUNT | 质押数量 | `["质押","pledge_amount"]` | 质押股票数量（万股） | float | 万股 | A | event_driven | DS_TUSHARE_PLEDGE |
| 3 | FIELD_PLEDGE_RATIO | 质押比例 | `["质押占比","pledge_ratio"]` | 质押占总股本比例 | float | % | A | event_driven | DS_TUSHARE_PLEDGE_STAT |
| 4 | FIELD_PLEDGE_PLEDGOR | 质押方 | `["pledgor"]` | 质押接受方机构 | string | — | A | event_driven | DS_TUSHARE_PLEDGE |
| 5 | FIELD_PLEDGE_START | 质押开始日期 | `["start_date"]` | 质押开始日期 | date | — | A | event_driven | DS_TUSHARE_PLEDGE |
| 6 | FIELD_PLEDGE_END | 质押结束日期 | `["end_date"]` | 质押结束日期 | date | — | A | event_driven | DS_TUSHARE_PLEDGE |
| 7 | FIELD_PLEDGE_IS_RELEASE | 是否已解押 | `["is_release"]` | 是否已解押（Y/N） | string | — | A | event_driven | DS_TUSHARE_PLEDGE |
| 8 | FIELD_TRADE_ANN_DATE | 公告日期 | `["ann_date"]` | 增减持公告日期 | date | — | A | event_driven | DS_TUSHARE_HOLDER_TRADE |
| 9 | FIELD_TRADE_TYPE | 增减持类型 | `["增持/减持","in_de"]` | IN增持/DE减持 | string | — | A | event_driven | DS_TUSHARE_HOLDER_TRADE |
| 10 | FIELD_TRADE_VOL | 变动数量 | `["change_vol"]` | 变动数量（股） | float | 股 | A | event_driven | DS_TUSHARE_HOLDER_TRADE |
| 11 | FIELD_TRADE_AFTER_SHARE | 变动后持股 | `["after_share"]` | 变动后持股数量（股） | float | 股 | A | event_driven | DS_TUSHARE_HOLDER_TRADE |
| 12 | FIELD_TRADE_AVG_PRICE | 平均价格 | `["均价","avg_price"]` | 交易平均价格（元） | float | 元 | A | event_driven | DS_TUSHARE_HOLDER_TRADE |


## 第六组：宏观与跨资产层（8 个 Concept，共 95 个 DataField）


### CONCEPT_MACRO_ECONOMY（宏观经济指标）
> 默认数据源：DS_TUSHARE_CN_MACRO / DS_TUSHARE_US_TYCR / DS_TUSHARE_LIBOR

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_MACRO_QUARTER | 季度 | `["quarter"]` | 数据对应的季度 | string | — | A | quarterly | DS_TUSHARE_CN_MACRO |
| 2 | FIELD_MACRO_GDP | GDP累计值 | `["GDP","gdp"]` | 国内生产总值累计值 | float | 亿元 | A | quarterly | DS_TUSHARE_CN_MACRO |
| 3 | FIELD_MACRO_GDP_YOY | GDP当季同比 | `["经济增速","gdp_yoy"]` | GDP当季同比增速 | float | % | A | quarterly | DS_TUSHARE_CN_MACRO |
| 4 | FIELD_MACRO_GDP_PI | 第一产业累计值 | `["pi"]` | 第一产业GDP累计值 | float | 亿元 | A | quarterly | DS_TUSHARE_CN_MACRO |
| 5 | FIELD_MACRO_GDP_SI | 第二产业累计值 | `["si"]` | 第二产业GDP累计值 | float | 亿元 | A | quarterly | DS_TUSHARE_CN_MACRO |
| 6 | FIELD_MACRO_GDP_TI | 第三产业累计值 | `["ti"]` | 第三产业GDP累计值 | float | 亿元 | A | quarterly | DS_TUSHARE_CN_MACRO |
| 7 | FIELD_MACRO_CPI_VAL | CPI当月值 | `["cpi_nt"]` | 全国CPI当月值 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 8 | FIELD_MACRO_CPI_YOY | CPI同比 | `["cpi_yoy"]` | CPI当月同比增速 | float | % | A | monthly | DS_TUSHARE_CN_MACRO |
| 9 | FIELD_MACRO_CPI_MOM | CPI环比 | `["cpi_mom"]` | CPI当月环比增速 | float | % | A | monthly | DS_TUSHARE_CN_MACRO |
| 10 | FIELD_MACRO_PPI_YOY | PPI同比 | `["ppi_yoy"]` | PPI当月同比增速 | float | % | A | monthly | DS_TUSHARE_CN_MACRO |
| 11 | FIELD_MACRO_PPI_MOM | PPI环比 | `["ppi_mom"]` | PPI当月环比增速 | float | % | A | monthly | DS_TUSHARE_CN_MACRO |
| 12 | FIELD_MACRO_PMI | 制造业PMI | `["PMI","pmi"]` | 制造业PMI指数 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 13 | FIELD_MACRO_NON_PMI | 非制造业PMI | `["服务业PMI","pmi_services"]` | 非制造业商务活动指数 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 14 | FIELD_MACRO_COMPOSITE_PMI | 综合PMI | `["pmi_composite"]` | 综合PMI产出指数 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 15 | FIELD_MACRO_PMI_PRODUCTION | PMI生产指数 | `["pmi_production"]` | PMI生产指数 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 16 | FIELD_MACRO_PMI_NEW_ORDERS | PMI新订单指数 | `["pmi_new_orders"]` | PMI新订单指数 | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 17 | FIELD_MACRO_PMI_LARGE | 大型企业PMI | `["pmi_large"]` | 大型企业PMI | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 18 | FIELD_MACRO_PMI_MEDIUM | 中型企业PMI | `["pmi_medium"]` | 中型企业PMI | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 19 | FIELD_MACRO_PMI_SMALL | 小型企业PMI | `["pmi_small"]` | 小型企业PMI | float | — | A | monthly | DS_TUSHARE_CN_MACRO |
| 20 | FIELD_MACRO_M0 | M0 | `["m0"]` | 流通中现金（亿元） | float | 亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 21 | FIELD_MACRO_M1 | M1 | `["m1"]` | 狭义货币供应量（亿元） | float | 亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 22 | FIELD_MACRO_M2 | M2 | `["m2"]` | 广义货币供应量（亿元） | float | 亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 23 | FIELD_MACRO_M2_YOY | M2同比 | `["m2_yoy"]` | M2同比增速 | float | % | A | monthly | DS_TUSHARE_CN_MACRO |
| 24 | FIELD_MACRO_SF_MONTH | 社融增量 | `["社会融资","inc_month"]` | 当月社融增量（亿元） | float | 亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 25 | FIELD_MACRO_SF_CUM | 社融累计值 | `["inc_cumval"]` | 社融累计值（亿元） | float | 亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 26 | FIELD_MACRO_SF_STOCK | 社融存量 | `["stk_endval"]` | 社融存量（万亿元） | float | 万亿元 | A | monthly | DS_TUSHARE_CN_MACRO |
| 27 | FIELD_MACRO_US_10Y | 美债10年期收益率 | `["10年美债","y10"]` | 美国10年期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 28 | FIELD_MACRO_US_2Y | 美债2年期收益率 | `["2年美债","y2"]` | 美国2年期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 29 | FIELD_MACRO_US_1M | 美债1月期收益率 | `["m1"]` | 美国1月期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 30 | FIELD_MACRO_US_3M | 美债3月期收益率 | `["m3"]` | 美国3月期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 31 | FIELD_MACRO_US_6M | 美债6月期收益率 | `["m6"]` | 美国6月期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 32 | FIELD_MACRO_US_5Y | 美债5年期收益率 | `["y5"]` | 美国5年期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 33 | FIELD_MACRO_US_30Y | 美债30年期收益率 | `["y30"]` | 美国30年期国债收益率 | float | % | A | daily_17:00 | DS_TUSHARE_US_TYCR |
| 34 | FIELD_MACRO_LIBOR_ON | Libor隔夜 | `["libor_on"]` | Libor隔夜利率 | float | % | A | daily_17:00 | DS_TUSHARE_LIBOR |
| 35 | FIELD_MACRO_LIBOR_3M | Libor3月 | `["libor_3m"]` | Libor3个月利率 | float | % | A | daily_17:00 | DS_TUSHARE_LIBOR |
| 36 | FIELD_MACRO_LIBOR_6M | Libor6月 | `["libor_6m"]` | Libor6个月利率 | float | % | A | daily_17:00 | DS_TUSHARE_LIBOR |


### CONCEPT_INTEREST_RATE（利率与债券收益率）
> 默认数据源：DS_TUSHARE_SHIBOR / DS_TUSHARE_LPR / DS_TUSHARE_WZ / DS_TUSHARE_GZ / DS_TUSHARE_HIBOR

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_RATE_DATE | 日期 | `["date"]` | 利率日期 | date | — | A | daily | DS_TUSHARE_SHIBOR |
| 2 | FIELD_RATE_SHIBOR_ON | Shibor隔夜 | `["shibor_on"]` | Shibor隔夜利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 3 | FIELD_RATE_SHIBOR_1W | Shibor1周 | `["shibor_1w"]` | Shibor1周利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 4 | FIELD_RATE_SHIBOR_2W | Shibor2周 | `["shibor_2w"]` | Shibor2周利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 5 | FIELD_RATE_SHIBOR_1M | Shibor1月 | `["shibor_1m"]` | Shibor1个月利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 6 | FIELD_RATE_SHIBOR_3M | Shibor3月 | `["shibor_3m"]` | Shibor3个月利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 7 | FIELD_RATE_SHIBOR_6M | Shibor6月 | `["shibor_6m"]` | Shibor6个月利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 8 | FIELD_RATE_SHIBOR_9M | Shibor9月 | `["shibor_9m"]` | Shibor9个月利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 9 | FIELD_RATE_SHIBOR_1Y | Shibor1年 | `["shibor_1y"]` | Shibor1年期利率 | float | % | A | daily | DS_TUSHARE_SHIBOR |
| 10 | FIELD_RATE_LPR_1Y | LPR1年期 | `["lpr_1y"]` | 1年期贷款基础利率 | float | % | A | monthly_20 | DS_TUSHARE_LPR |
| 11 | FIELD_RATE_LPR_5Y | LPR5年期 | `["lpr_5y"]` | 5年期贷款基础利率 | float | % | A | monthly_20 | DS_TUSHARE_LPR |
| 12 | FIELD_RATE_WZ_COMP | 温州综合利率 | `["wz_comp_rate"]` | 温州民间借贷综合利率 | float | % | A | weekly | DS_TUSHARE_WZ |
| 13 | FIELD_RATE_WZ_1M | 温州1月期利率 | `["wz_m1_rate"]` | 温州1月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_WZ |
| 14 | FIELD_RATE_WZ_3M | 温州3月期利率 | `["wz_m3_rate"]` | 温州3月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_WZ |
| 15 | FIELD_RATE_WZ_6M | 温州6月期利率 | `["wz_m6_rate"]` | 温州6月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_WZ |
| 16 | FIELD_RATE_WZ_12M | 温州12月期利率 | `["wz_m12_rate"]` | 温州12月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_WZ |
| 17 | FIELD_RATE_GZ_1M | 广州1月期利率 | `["gz_m1_rate"]` | 广州1月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_GZ |
| 18 | FIELD_RATE_GZ_3M | 广州3月期利率 | `["gz_m3_rate"]` | 广州3月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_GZ |
| 19 | FIELD_RATE_GZ_6M | 广州6月期利率 | `["gz_m6_rate"]` | 广州6月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_GZ |
| 20 | FIELD_RATE_GZ_12M | 广州12月期利率 | `["gz_m12_rate"]` | 广州12月期民间借贷利率 | float | % | A | weekly | DS_TUSHARE_GZ |
| 21 | FIELD_RATE_HIBOR_ON | Hibor隔夜 | `["hibor_on"]` | Hibor隔夜利率 | float | % | A | daily | DS_TUSHARE_HIBOR |
| 22 | FIELD_RATE_HIBOR_1W | Hibor1周 | `["hibor_1w"]` | Hibor1周利率 | float | % | A | daily | DS_TUSHARE_HIBOR |
| 23 | FIELD_RATE_HIBOR_1M | Hibor1月 | `["hibor_1m"]` | Hibor1个月利率 | float | % | A | daily | DS_TUSHARE_HIBOR |
| 24 | FIELD_RATE_HIBOR_3M | Hibor3月 | `["hibor_3m"]` | Hibor3个月利率 | float | % | A | daily | DS_TUSHARE_HIBOR |


### CONCEPT_FOREX_MAJOR（主要外汇汇率）
> 默认数据源：DS_TUSHARE_FX_DAILY / DS_TUSHARE_FX_OBASIC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FOREX_PAIR | 货币对 | `["ts_code"]` | 外汇货币对代码 | string | — | A | daily | DS_TUSHARE_FX_DAILY |
| 2 | FIELD_FOREX_DATE | 交易日期 | `["trade_date"]` | 交易日期（GMT） | date | — | A | daily | DS_TUSHARE_FX_DAILY |
| 3 | FIELD_FOREX_BID_OPEN | 买入开盘价 | `["bid_open"]` | 买入价开盘 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 4 | FIELD_FOREX_BID_CLOSE | 买入收盘价 | `["bid_close"]` | 买入价收盘 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 5 | FIELD_FOREX_BID_HIGH | 买入最高价 | `["bid_high"]` | 买入价最高 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 6 | FIELD_FOREX_BID_LOW | 买入最低价 | `["bid_low"]` | 买入价最低 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 7 | FIELD_FOREX_ASK_OPEN | 卖出开盘价 | `["ask_open"]` | 卖出价开盘 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 8 | FIELD_FOREX_ASK_CLOSE | 卖出收盘价 | `["ask_close"]` | 卖出价收盘 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 9 | FIELD_FOREX_ASK_HIGH | 卖出最高价 | `["ask_high"]` | 卖出价最高 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 10 | FIELD_FOREX_ASK_LOW | 卖出最低价 | `["ask_low"]` | 卖出价最低 | float | — | A | daily | DS_TUSHARE_FX_DAILY |
| 11 | FIELD_FOREX_EXCHANGE | 交易商 | `["exchange"]` | 外汇交易商名称 | string | — | A | weekly | DS_TUSHARE_FX_OBASIC |
| 12 | FIELD_FOREX_PIP | 点值 | `["pip"]` | 外汇点值 | float | — | A | weekly | DS_TUSHARE_FX_OBASIC |


### CONCEPT_BOND_YIELD_CURVE（债券收益率曲线）
> 默认数据源：DS_AKSHARE_BOND_YIELD / DS_LOCAL_CALC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_BOND_CURVE_DATE | 日期 | `["date"]` | 收益率日期 | date | — | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 2 | FIELD_BOND_CURVE_1Y | 国债1年期收益率 | `["1年国债","y1"]` | 中国1年期国债收益率 | float | % | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 3 | FIELD_BOND_CURVE_2Y | 国债2年期收益率 | `["2年国债","y2"]` | 中国2年期国债收益率 | float | % | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 4 | FIELD_BOND_CURVE_5Y | 国债5年期收益率 | `["5年国债","y5"]` | 中国5年期国债收益率 | float | % | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 5 | FIELD_BOND_CURVE_10Y | 国债10年期收益率 | `["10年国债","y10"]` | 中国10年期国债收益率 | float | % | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 6 | FIELD_BOND_CURVE_30Y | 国债30年期收益率 | `["30年国债","y30"]` | 中国30年期国债收益率 | float | % | A | daily_17:00 | DS_AKSHARE_BOND_YIELD |
| 7 | FIELD_BOND_CURVE_SPREAD | 中美利差(10年) | `["中美利差"]` | 中美10年期国债利差 | float | % | A | daily_17:00 | DS_LOCAL_CALC |


### CONCEPT_FUTURES（期货行情）
> 默认数据源：DS_TUSHARE_FUT_DAILY / DS_TUSHARE_FUT_BASIC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FUT_TS_CODE | 合约代码 | `["ts_code"]` | 期货合约TS代码 | string | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 2 | FIELD_FUT_NAME | 合约名称 | `["name"]` | 期货合约中文名称 | string | — | A | weekly | DS_TUSHARE_FUT_BASIC |
| 3 | FIELD_FUT_DATE | 交易日期 | `["trade_date"]` | 交易日 | date | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 4 | FIELD_FUT_PRE_CLOSE | 昨收盘价 | `["pre_close"]` | 昨日收盘价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 5 | FIELD_FUT_PRE_SETTLE | 昨结算价 | `["pre_settle"]` | 昨日结算价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 6 | FIELD_FUT_OPEN | 开盘价 | `["open"]` | 当日开盘价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 7 | FIELD_FUT_HIGH | 最高价 | `["high"]` | 当日最高价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 8 | FIELD_FUT_LOW | 最低价 | `["low"]` | 当日最低价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 9 | FIELD_FUT_CLOSE | 收盘价 | `["close"]` | 当日收盘价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 10 | FIELD_FUT_SETTLE | 结算价 | `["settle"]` | 当日结算价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 11 | FIELD_FUT_CHG1 | 涨跌1 | `["change1"]` | 收盘价-昨结算价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 12 | FIELD_FUT_CHG2 | 涨跌2 | `["change2"]` | 结算价-昨结算价 | float | — | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 13 | FIELD_FUT_VOL | 成交量 | `["vol"]` | 成交量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 14 | FIELD_FUT_AMOUNT | 成交额 | `["amount"]` | 成交金额（万元） | float | 万元 | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 15 | FIELD_FUT_OI | 持仓量 | `["oi"]` | 持仓量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |
| 16 | FIELD_FUT_OI_CHG | 持仓变化 | `["oi_chg"]` | 持仓量变化 | float | 手 | A | daily_17:00 | DS_TUSHARE_FUT_DAILY |


### CONCEPT_FUTURES_DETAIL（期货明细数据）
> 默认数据源：DS_TUSHARE_FUT_HOLDING / DS_TUSHARE_FUT_WSR / DS_TUSHARE_FUT_SETTLE

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FUT_DETAIL_BROKER | 期货公司会员 | `["broker"]` | 期货公司会员简称 | string | — | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 2 | FIELD_FUT_DETAIL_VOL | 成交量 | `["vol"]` | 期货公司成交量 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 3 | FIELD_FUT_DETAIL_VOL_CHG | 成交量变化 | `["vol_chg"]` | 成交量变化 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 4 | FIELD_FUT_DETAIL_LONG | 持买仓量 | `["long_hld"]` | 多头持仓量 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 5 | FIELD_FUT_DETAIL_LONG_CHG | 持买仓量变化 | `["long_chg"]` | 多头持仓量变化 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 6 | FIELD_FUT_DETAIL_SHORT | 持卖仓量 | `["short_hld"]` | 空头持仓量 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 7 | FIELD_FUT_DETAIL_SHORT_CHG | 持卖仓量变化 | `["short_chg"]` | 空头持仓量变化 | int | 手 | A | daily_17:00 | DS_TUSHARE_FUT_HOLDING |
| 8 | FIELD_FUT_WSR_WAREHOUSE | 仓库名称 | `["warehouse"]` | 交割仓库名称 | string | — | A | daily_17:00 | DS_TUSHARE_FUT_WSR |
| 9 | FIELD_FUT_WSR_PRE_VOL | 昨日仓单量 | `["pre_vol"]` | 昨日仓单数量 | float | 手/吨 | A | daily_17:00 | DS_TUSHARE_FUT_WSR |
| 10 | FIELD_FUT_WSR_VOL | 今日仓单量 | `["vol"]` | 今日仓单数量 | float | 手/吨 | A | daily_17:00 | DS_TUSHARE_FUT_WSR |
| 11 | FIELD_FUT_WSR_VOL_CHG | 增减量 | `["vol_chg"]` | 仓单增减量 | float | 手/吨 | A | daily_17:00 | DS_TUSHARE_FUT_WSR |
| 12 | FIELD_FUT_WSR_PD | 升贴水 | `["pd"]` | 仓单升贴水 | int | — | A | daily_17:00 | DS_TUSHARE_FUT_WSR |
| 13 | FIELD_FUT_SETTLE_FEE | 交易手续费率 | `["trading_fee_rate"]` | 交易手续费率 | float | % | A | daily_17:00 | DS_TUSHARE_FUT_SETTLE |
| 14 | FIELD_FUT_SETTLE_MARGIN | 交易保证金率 | `["long_margin_rate"]` | 投机交易保证金率 | float | % | A | daily_17:00 | DS_TUSHARE_FUT_SETTLE |


### CONCEPT_CONVERTIBLE_BOND（可转债行情）
> 默认数据源：DS_TUSHARE_CB_DAILY / DS_TUSHARE_CB_BASIC

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_CB_TS_CODE | 转债代码 | `["ts_code"]` | 可转债TS代码 | string | — | A | daily_17:00 | DS_TUSHARE_CB_BASIC |
| 2 | FIELD_CB_NAME | 转债名称 | `["bond_short_name"]` | 可转债简称 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 3 | FIELD_CB_STK_CODE | 正股代码 | `["stk_code"]` | 正股股票代码 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 4 | FIELD_CB_STK_NAME | 正股简称 | `["stk_short_name"]` | 正股股票简称 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 5 | FIELD_CB_TYPE | 转债类型 | `["cb_type"]` | CB可转债/EB可交换债 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 6 | FIELD_CB_DATE | 交易日期 | `["trade_date"]` | 交易日 | date | — | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 7 | FIELD_CB_OPEN | 开盘价 | `["open"]` | 当日开盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 8 | FIELD_CB_HIGH | 最高价 | `["high"]` | 当日最高价 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 9 | FIELD_CB_LOW | 最低价 | `["low"]` | 当日最低价 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 10 | FIELD_CB_CLOSE | 收盘价 | `["close"]` | 当日收盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 11 | FIELD_CB_PCT_CHG | 涨跌幅 | `["pct_chg"]` | 当日涨跌幅 | float | % | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 12 | FIELD_CB_VOL | 成交量 | `["vol"]` | 成交量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 13 | FIELD_CB_AMOUNT | 成交额 | `["amount"]` | 成交金额（万元） | float | 万元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 14 | FIELD_CB_BOND_VALUE | 纯债价值 | `["bond_value"]` | 纯债价值 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 15 | FIELD_CB_BOND_OVER_RATE | 纯债溢价率 | `["bond_over_rate"]` | 纯债溢价率 | float | % | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 16 | FIELD_CB_CB_VALUE | 转股价值 | `["cb_value"]` | 转股价值 | float | 元 | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 17 | FIELD_CB_CB_OVER_RATE | 转股溢价率 | `["cb_over_rate"]` | 转股溢价率 | float | % | A | daily_17:00 | DS_TUSHARE_CB_DAILY |
| 18 | FIELD_CB_ISSUE_SIZE | 发行总额 | `["issue_size"]` | 发行总额（元） | float | 亿元 | A | weekly | DS_TUSHARE_CB_BASIC |
| 19 | FIELD_CB_REMAIN_SIZE | 债券余额 | `["remain_size"]` | 债券余额（元） | float | 亿元 | A | weekly | DS_TUSHARE_CB_BASIC |
| 20 | FIELD_CB_COUPON_RATE | 票面利率 | `["coupon_rate"]` | 票面利率 | float | % | A | weekly | DS_TUSHARE_CB_BASIC |
| 21 | FIELD_CB_FIRST_CONV_PRICE | 初始转股价 | `["first_conv_price"]` | 初始转股价格 | float | 元 | A | weekly | DS_TUSHARE_CB_BASIC |
| 22 | FIELD_CB_CONV_PRICE | 最新转股价 | `["conv_price"]` | 最新转股价格 | float | 元 | A | weekly | DS_TUSHARE_CB_BASIC |
| 23 | FIELD_CB_CONV_START_DATE | 转股起始日 | `["conv_start_date"]` | 转股起始日期 | date | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 24 | FIELD_CB_MATURITY_DATE | 到期日 | `["maturity_date"]` | 债券到期日期 | date | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 25 | FIELD_CB_RATING | 信用评级 | `["newest_rating"]` | 最新信用评级 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 26 | FIELD_CB_CALL_CLAUSE | 强赎条款 | `["call_clause"]` | 赎回条款 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |
| 27 | FIELD_CB_PUT_CLAUSE | 回售条款 | `["put_clause"]` | 回售条款 | string | — | A | weekly | DS_TUSHARE_CB_BASIC |


### CONCEPT_FUND_ETF（基金与ETF行情）
> 默认数据源：DS_TUSHARE_FUND_DAILY / DS_TUSHARE_FUND_BASIC / DS_TUSHARE_FUND_NAV / DS_TUSHARE_FUND_SHARE / DS_TUSHARE_FUND_PORT / DS_TUSHARE_FUND_MANAGER / DS_TUSHARE_FUND_ADJ

| # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源 ID |
|:---:|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| 1 | FIELD_FUND_TS_CODE | 基金代码 | `["ts_code"]` | 基金TS代码 | string | — | A | daily_17:00 | DS_TUSHARE_FUND_BASIC |
| 2 | FIELD_FUND_NAME | 基金名称 | `["name"]` | 基金简称 | string | — | A | daily_17:00 | DS_TUSHARE_FUND_BASIC |
| 3 | FIELD_FUND_DATE | 交易日期 | `["trade_date"]` | 交易日 | date | — | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 4 | FIELD_FUND_OPEN | 开盘价 | `["open"]` | 当日开盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 5 | FIELD_FUND_HIGH | 最高价 | `["high"]` | 当日最高价 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 6 | FIELD_FUND_LOW | 最低价 | `["low"]` | 当日最低价 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 7 | FIELD_FUND_CLOSE | 收盘价 | `["close"]` | 当日收盘价 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 8 | FIELD_FUND_PCT_CHG | 涨跌幅 | `["pct_chg"]` | 当日涨跌幅 | float | % | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 9 | FIELD_FUND_VOL | 成交量 | `["vol"]` | 成交量（手） | float | 手 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 10 | FIELD_FUND_AMOUNT | 成交额 | `["amount"]` | 成交额（千元） | float | 千元 | A | daily_17:00 | DS_TUSHARE_FUND_DAILY |
| 11 | FIELD_FUND_UNIT_NAV | 单位净值 | `["unit_nav"]` | 单位净值 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_NAV |
| 12 | FIELD_FUND_ACCUM_NAV | 累计净值 | `["accum_nav"]` | 累计净值 | float | 元 | A | daily_17:00 | DS_TUSHARE_FUND_NAV |
| 13 | FIELD_FUND_ADJ_FACTOR | 复权因子 | `["adj_factor"]` | 基金复权因子 | float | — | A | event_driven | DS_TUSHARE_FUND_ADJ |
| 14 | FIELD_FUND_SHARES | 基金份额 | `["fd_share"]` | 基金份额（万份） | float | 万份 | A | daily_17:00 | DS_TUSHARE_FUND_SHARE |
| 15 | FIELD_FUND_MANAGEMENT | 管理人 | `["management"]` | 基金管理人 | string | — | A | weekly | DS_TUSHARE_FUND_BASIC |
| 16 | FIELD_FUND_CUSTODIAN | 托管人 | `["custodian"]` | 基金托管人 | string | — | A | weekly | DS_TUSHARE_FUND_BASIC |
| 17 | FIELD_FUND_TYPE | 基金类型 | `["fund_type"]` | 投资类型分类 | string | — | A | weekly | DS_TUSHARE_FUND_BASIC |
| 18 | FIELD_FUND_FOUND_DATE | 成立日期 | `["found_date"]` | 基金成立日期 | date | — | A | weekly | DS_TUSHARE_FUND_BASIC |
| 19 | FIELD_FUND_LIST_DATE | 上市日期 | `["list_date"]` | 基金上市日期 | date | — | A | weekly | DS_TUSHARE_FUND_BASIC |
| 20 | FIELD_FUND_M_FEE | 管理费 | `["m_fee"]` | 管理费率 | float | % | A | weekly | DS_TUSHARE_FUND_BASIC |
| 21 | FIELD_FUND_C_FEE | 托管费 | `["c_fee"]` | 托管费率 | float | % | A | weekly | DS_TUSHARE_FUND_BASIC |
| 22 | FIELD_FUND_MANAGER_NAME | 基金经理 | `["manager_name"]` | 基金经理姓名 | string | — | A | weekly | DS_TUSHARE_FUND_MANAGER |
| 23 | FIELD_FUND_PORT_SYMBOL | 持仓股票代码 | `["symbol"]` | 持仓股票代码 | string | — | A | quarterly | DS_TUSHARE_FUND_PORT |
| 24 | FIELD_FUND_PORT_MKV | 持股市值 | `["mkv"]` | 持仓股票市值（元） | float | 亿元 | A | quarterly | DS_TUSHARE_FUND_PORT |
| 25 | FIELD_FUND_PORT_STK_RATIO | 占股票市值比 | `["stk_mkv_ratio"]` | 占基金股票市值比例 | float | % | A | quarterly | DS_TUSHARE_FUND_PORT |
| 26 | FIELD_FUND_PORT_FLOAT_RATIO | 占流通股本比 | `["stk_float_ratio"]` | 占流通股本比例 | float | % | A | quarterly | DS_TUSHARE_FUND_PORT |


## 第七组：文档生成层（6 个 Concept，共 43 个复用字段）

> 说明：以下字段全部复用前面各层的 DataField，不独立创建节点。路由时将直接引用源字段的数据源配置。

### CONCEPT_DOC_MIDDAY（午间收盘信息文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID | standard_name | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|:---|
| 1 | FIELD_QUOTE_PCT_CHG | 上午涨跌幅 | 半日涨跌幅 | CONCEPT_REALTIME_QUOTE |
| 2 | FIELD_QUOTE_AMOUNT | 上午成交额 | 半日成交 | CONCEPT_REALTIME_QUOTE |
| 3 | FIELD_TURNOVER_RATE | 换手率(估算) | 半日换手 | CONCEPT_REALTIME_QUOTE |
| 4 | FIELD_QUOTE_HIGH | 最高价 | 半日高点 | CONCEPT_REALTIME_QUOTE |
| 5 | FIELD_QUOTE_LOW | 最低价 | 半日低点 | CONCEPT_REALTIME_QUOTE |
| 6 | FIELD_SECTOR_PCT_CHG | 板块今日涨跌 | 板块表现对比 | CONCEPT_SECTOR_REALTIME |
| 7 | （计算字段） | 个股vs板块表现 | 相对强弱 | CONCEPT_REALTIME_QUOTE + CONCEPT_SECTOR_REALTIME |
| 8 | FIELD_SECTOR_UP_COUNT | 板块内排名估算 | 板块排名参考 | CONCEPT_SECTOR_REALTIME |
| 9 | FIELD_NEWS_CONTENT | 上午新驱动 | 驱动因素 | CONCEPT_MARKET_SENTIMENT |
| 10 | FIELD_KLINE_CLOSE（5日均值） | MA5(估算) | 5日均线 | CONCEPT_HISTORICAL_KLINE |
| 11 | FIELD_KLINE_CLOSE（10日均值） | MA10(估算) | 10日均线 | CONCEPT_HISTORICAL_KLINE |
| 12 | FIELD_KLINE_CLOSE（20日均值） | MA20(估算) | 20日均线 | CONCEPT_HISTORICAL_KLINE |


### CONCEPT_DOC_CLOSE（收盘后信息文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID | standard_name | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|:---|
| 1 | FIELD_QUOTE_PCT_CHG | 今日涨跌幅 | 全天涨幅 | CONCEPT_REALTIME_QUOTE |
| 2 | FIELD_QUOTE_AMOUNT | 成交额 | 全天成交 | CONCEPT_REALTIME_QUOTE |
| 3 | FIELD_TURNOVER_RATE | 换手率 | 全天换手 | CONCEPT_REALTIME_QUOTE |
| 4 | FIELD_AMPLITUDE | 振幅 | 波动幅度 | CONCEPT_REALTIME_QUOTE |
| 5 | FIELD_QUOTE_PRICE | 收盘价 | 收盘价 | CONCEPT_REALTIME_QUOTE |
| 6 | FIELD_LIMIT_UP | 是否涨停 | 触及涨停判断 | CONCEPT_REALTIME_QUOTE |
| 7 | FIELD_SECTOR_UP_COUNT | 板块内排名 | 行业排名 | CONCEPT_SECTOR_REALTIME |
| 8 | FIELD_NEWS_CONTENT | 涨停驱动因素 | 驱动分析 | CONCEPT_MARKET_SENTIMENT |
| 9 | FIELD_PROFILE_MAIN_BUSINESS | 公司基本面信息 | 基本情况 | CONCEPT_COMPANY_PROFILE |
| 10 | CONCEPT_FINANCIAL_SUMMARY 全部字段 | 财务摘要 | 财务概览 | CONCEPT_FINANCIAL_SUMMARY |
| 11 | FIELD_FLOW_NET_AMT | 资金博弈分析 | 主力净流入 | CONCEPT_FUND_FLOW |
| 12 | FIELD_MARGIN_BALANCE | 融资融券变化 | 融资余额 | CONCEPT_MARGIN |
| 13 | FIELD_KLINE_CLOSE（5日均值） | MA5 | 5日均线 | CONCEPT_HISTORICAL_KLINE |
| 14 | FIELD_KLINE_CLOSE（10日均值） | MA10 | 10日均线 | CONCEPT_HISTORICAL_KLINE |
| 15 | FIELD_KLINE_CLOSE（20日均值） | MA20 | 20日均线 | CONCEPT_HISTORICAL_KLINE |
| 16 | FIELD_VAL_PE_TTM | PE(TTM) | 市盈率 | CONCEPT_VALUATION_COMPARE |
| 17 | FIELD_VAL_PB | PB | 市净率 | CONCEPT_VALUATION_COMPARE |
| 18 | FIELD_TOTAL_MV | 总市值 | 市值 | CONCEPT_REALTIME_QUOTE |


### CONCEPT_DOC_VALUE（公司潜在价值信息文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID / Concept | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|
| 1 | CONCEPT_INDUSTRY_CLASSIFY 全部字段 | 产业链位置 | CONCEPT_INDUSTRY_CLASSIFY |
| 2 | CONCEPT_INDUSTRY_BG 全部字段 | 市场规模与空间 | CONCEPT_INDUSTRY_BG |
| 3 | FIELD_FS_CIP | 核心项目/募投 | CONCEPT_FINANCIAL_STATEMENTS |
| 4 | FIELD_PROFILE_CHAIRMAN / FIELD_PROFILE_MANAGER | 管理团队 | CONCEPT_COMPANY_PROFILE |
| 5 | CONCEPT_INDUSTRY_CLASSIFY（同类公司） | 竞争格局 | CONCEPT_INDUSTRY_CLASSIFY |
| 6 | CONCEPT_FINANCIAL_SUMMARY + CONCEPT_FINANCIAL_STATEMENTS | 财务质量（近3年） | CONCEPT_FINANCIAL_SUMMARY / CONCEPT_FINANCIAL_STATEMENTS |
| 7 | CONCEPT_VALUATION_COMPARE | 估值辅助 | CONCEPT_VALUATION_COMPARE |
| 8 | CONCEPT_PLEDGE_HOLDER_TRADE + CONCEPT_INSTITUTION_RATING | 风险与不确定性 | CONCEPT_PLEDGE_HOLDER_TRADE / CONCEPT_INSTITUTION_RATING |


### CONCEPT_DOC_RISK（风险控制文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID / Concept | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|
| 1 | CONCEPT_SECTOR_REALTIME | 题材风险 | CONCEPT_SECTOR_REALTIME |
| 2 | CONCEPT_FINANCIAL_SUMMARY + CONCEPT_FINANCIAL_STATEMENTS | 财务风险 | CONCEPT_FINANCIAL_SUMMARY / CONCEPT_FINANCIAL_STATEMENTS |
| 3 | CONCEPT_TOP_HOLDERS + CONCEPT_PLEDGE_HOLDER_TRADE | 股东风险 | CONCEPT_TOP_HOLDERS / CONCEPT_PLEDGE_HOLDER_TRADE |
| 4 | CONCEPT_VALUATION_COMPARE（PE分位数） | 估值风险 | CONCEPT_VALUATION_COMPARE |
| 5 | FIELD_TURNOVER_RATE / FIELD_QUOTE_AMOUNT | 流动性风险 | CONCEPT_REALTIME_QUOTE |
| 6 | FIELD_ANNOUNCE_TYPE | 监管风险 | CONCEPT_ANNOUNCEMENT |


### CONCEPT_DOC_COUNTER（反证文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID / Concept | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|
| 1 | CONCEPT_INDUSTRY_BG + CONCEPT_POLICY_ORIGINAL | 产业路径反证 | CONCEPT_INDUSTRY_BG / CONCEPT_POLICY_ORIGINAL |
| 2 | FIELD_FS_TOTAL_REVENUE（主营业务构成） | 公司真实受益反证 | CONCEPT_FINANCIAL_STATEMENTS |
| 3 | CONCEPT_INDUSTRY_CLASSIFY + CONCEPT_COMPANY_PROFILE | 龙头属性反证 | CONCEPT_INDUSTRY_CLASSIFY / CONCEPT_COMPANY_PROFILE |
| 4 | CONCEPT_VALUATION_COMPARE（PE分位数） | 估值反证 | CONCEPT_VALUATION_COMPARE |


### CONCEPT_DOC_VALUATION（估值辅助文档）
> 该文档的 default_seed_fields 指向以下复用的 DataField：

| # | 字段 ID | standard_name | 在文档中的用途 | 源 Concept |
|:---:|:---|:---|:---|:---|
| 1 | FIELD_QUOTE_PRICE | 当前股价 | 当前价格 | CONCEPT_REALTIME_QUOTE |
| 2 | FIELD_TOTAL_MV | 总市值 | 市值 | CONCEPT_REALTIME_QUOTE |
| 3 | FIELD_VAL_PE_TTM | PE_TTM | 市盈率 | CONCEPT_VALUATION_COMPARE |
| 4 | FIELD_VAL_PB | PB | 市净率 | CONCEPT_VALUATION_COMPARE |
| 5 | FIELD_VAL_PE_PCT | PE历史分位数 | PE分位 | CONCEPT_VALUATION_COMPARE |
| 6 | FIELD_VAL_IND_PE | 行业平均PE | 行业PE | CONCEPT_VALUATION_COMPARE |
| 7 | FIELD_FIN_REVENUE_YOY（序列） | 近三年营收增速 | 营收CAGR | CONCEPT_FINANCIAL_SUMMARY |
| 8 | FIELD_FIN_PROFIT_YOY（序列） | 近三年利润增速 | 利润CAGR | CONCEPT_FINANCIAL_SUMMARY |
| 9 | FIELD_FIN_GROSS_MARGIN | 毛利率 | 毛利 | CONCEPT_FINANCIAL_SUMMARY |
| 10 | FIELD_FIN_NET_MARGIN | 净利率 | 净利 | CONCEPT_FINANCIAL_SUMMARY |


## 附录：统计汇总

| 分组 | Concept 数量 | 独立 DataField 数量 | 复用字段数 |
|:---|:---:|:---:|:---:|
| 第一组：市场全景层 | 4 | 65 | 0 |
| 第二组：行业与产业链层 | 5 | 27 | 0 |
| 第三组：公司基本面层 | 7 | 112 | 0 |
| 第四组：公司治理与事件层 | 6 | 51 | 0 |
| 第五组：资金与交易层 | 5 | 55 | 0 |
| 第六组：宏观与跨资产层 | 8 | 95 | 0 |
| 第七组：文档生成层 | 6 | 0 | 43 |
| **总计** | **41** | **405** | **43** |

| 项目 | 数量 |
|:---|:---:|
| DataSource 节点总数 | 65 |
| IntentConcept 节点总数 | 41 |
| DataField 节点总数（独立） | 405 |
| DataField 引用次数（含复用） | 448 |

---

**文档结束。**