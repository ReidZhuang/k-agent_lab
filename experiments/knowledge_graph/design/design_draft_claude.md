先读完所有文件再给方案。好，四份文档都读完了。现在我对你的落地场景有了清晰的认识——你有两类信息获取渠道：akshare Python API（结构化数据）和网页端（搜索+爬取）。下面直接给优化方案，不再讨论原方案的问题，直接给你可以落地的新设计。

---

## 优化后的知识图谱设计：IRKG v2

### 核心改变思路

原方案把"信息是什么"和"怎么拿到信息"混在一起设计，导致节点冗余、关系不清晰。新设计**严格分三层**：

```
信息需求层（Information Node）
        ↓ 映射
获取方案层（Access Plan Node）
        ↓ 执行
工具调用层（Tool Call Node）
```

LLM 只需要描述"我需要什么信息"，图谱输出"执行什么调用"，中间的优先级判断和路由完全在图谱里解决。

---

## Node 设计（5种，精简）

### N1：InformationNeed（信息需求节点）

图谱的**唯一入口**。描述"需要什么信息"，与具体数据源完全解耦。

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识，如 `info:financial_summary` |
| `name` | string | 标准名称，如 `财务概要` |
| `aliases` | list | 触发关键词，如 `["营收","净利润","毛利率","ROE"]` |
| `scope` | enum | `company` / `market` / `sector` / `macro` / `event` |
| `requires_entity` | list | 调用时必须提供的实体参数，如 `["stock_code"]` |
| `description` | string | 一句话描述 |

**设计原则**：InformationNeed 的 `aliases` 列表是 LLM 做意图识别的依据，必须覆盖所有自然语言表达方式。

---

### N2：AccessPlan（获取方案节点）

核心中间层。一个 InformationNeed 可能对应多个 AccessPlan（主选/备选），每个 AccessPlan 对应一种具体的获取方式。

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | string | 如 `plan:financial_summary:akshare_primary` |
| `channel` | enum | `akshare` / `web_scrape` / `web_search` |
| `priority` | int | 1=首选，2=备选，3=降级 |
| `freshness` | enum | `realtime` / `daily` / `quarterly` / `static` |
| `authority` | int | 1-5，信源权威程度 |
| `condition` | string | 触发条件，如 `"当akshare调用失败时"` |

---

### N3：AkshareCall（API调用节点）

对应一次具体的 akshare 函数调用。

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | string | 如 `api:stock_financial_abstract` |
| `function` | string | 函数名，如 `stock_financial_abstract` |
| `param_template` | dict | 参数模板，如 `{"symbol": "{stock_code}"}` |
| `key_columns` | list | 优先提取的关键列，如 `["归母净利润","营业总收入","ROE(加权)"]` |
| `code_format` | enum | `pure_num` / `SZ_prefix` / `SH_prefix` |
| `latency_ms` | int | 预期响应时间 |
| `notes` | string | 注意事项，如 `"东方财富系需要SZ/SH前缀"` |

---

### N4：WebTarget（网页目标节点）

对应一次网页搜索或爬取任务。

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | string | 如 `web:cninfo_announcement` |
| `site_name` | string | 如 `巨潮资讯网` |
| `site_url` | string | 如 `https://www.cninfo.com.cn` |
| `authority_level` | enum | `S` / `A` / `B` / `C` |（对应你的信源等级体系）
| `search_template` | string | 搜索词模板，如 `"{stock_name} 公告 {date_range}"` |
| `target_content` | string | 目标内容描述，如 `"公告标题列表及链接"` |
| `method` | enum | `site_search` / `direct_url` / `keyword_search` |

---

### N5：OutputSpec（输出规格节点）

描述这次调用的结果应该如何处理和传回给 LLM。这是原方案完全缺失的一层。

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | string | 如 `spec:financial_summary_output` |
| `format` | enum | `table` / `text_summary` / `list` / `raw` |
| `max_rows` | int | 最多返回行数，控制 token 消耗 |
| `key_fields` | list | 必须包含的字段 |
| `drop_fields` | list | 可以丢弃的字段 |

---

## Relationship 设计（6种，精简后）

| 关系 | 方向 | 含义 |
|------|------|------|
| `MAPS_TO` | InformationNeed → AccessPlan | 某信息需求对应某获取方案（含优先级） |
| `USES_API` | AccessPlan → AkshareCall | 方案使用的具体API调用 |
| `USES_WEB` | AccessPlan → WebTarget | 方案使用的具体网页目标 |
| `FALLBACK_TO` | AccessPlan → AccessPlan | 失败时的降级方案 |
| `PRODUCES` | AccessPlan → OutputSpec | 方案产出的输出规格 |
| `RELATED_TO` | InformationNeed → InformationNeed | 常见的关联查询（用于自动扩展） |

**关系属性**（放在 `MAPS_TO` 关系上，不是节点属性）：

```json
{
  "priority": 1,
  "condition": "always",
  "freshness_fit": ["realtime", "daily"],
  "note": "akshare首选，覆盖80个财务指标"
}
```

---

## 完整图谱实例

以下用 JSON 展示三个典型信息需求的完整链路，可直接作为图数据库（Neo4j / TigerGraph / 或简单 JSON 文件）的数据导入格式。

### 实例一：财务概要

```json
{
  "nodes": [
    {
      "type": "InformationNeed",
      "id": "info:financial_summary",
      "name": "财务概要",
      "aliases": ["营收","净利润","毛利率","ROE","EPS","利润","盈利能力","每股收益","成长能力","财务指标","业绩","经营现金流"],
      "scope": "company",
      "requires_entity": ["stock_code"],
      "description": "公司核心财务指标的多期概览，含盈利/成长/偿债/营运四类"
    },
    {
      "type": "AccessPlan",
      "id": "plan:financial_summary:primary",
      "channel": "akshare",
      "priority": 1,
      "freshness": "quarterly",
      "authority": 4
    },
    {
      "type": "AccessPlan",
      "id": "plan:financial_summary:deep",
      "channel": "akshare",
      "priority": 2,
      "freshness": "quarterly",
      "authority": 4,
      "condition": "当用户明确要求杜邦分析、ROIC、利息保障倍数等深度指标时"
    },
    {
      "type": "AccessPlan",
      "id": "plan:financial_summary:web_fallback",
      "channel": "web_scrape",
      "priority": 3,
      "freshness": "daily",
      "authority": 3,
      "condition": "当akshare调用连续失败2次后"
    },
    {
      "type": "AkshareCall",
      "id": "api:stock_financial_abstract",
      "function": "stock_financial_abstract",
      "param_template": {"symbol": "{stock_code}"},
      "key_columns": ["归母净利润","营业总收入","毛利率","净利率","ROE(加权)","资产负债率","经营活动现金流净额"],
      "code_format": "pure_num",
      "latency_ms": 300,
      "notes": "纯数字代码，返回80指标×42报告期，默认取最近8期"
    },
    {
      "type": "AkshareCall",
      "id": "api:stock_financial_analysis_indicator_em",
      "function": "stock_financial_analysis_indicator_em",
      "param_template": {"symbol": "{stock_code}.{market_suffix}", "indicator": "按报告期"},
      "key_columns": ["EPS(基本)","ROE(加权)","ROIC","毛利率","净利率","利息保障倍数","总资产周转率"],
      "code_format": "SZ_prefix",
      "latency_ms": 300,
      "notes": "东方财富系，代码需SZ/SH后缀，返回140指标，含同比增速"
    },
    {
      "type": "WebTarget",
      "id": "web:sina_financial",
      "site_name": "新浪财经",
      "site_url": "https://finance.sina.com.cn",
      "authority_level": "B",
      "search_template": "{stock_name} 财务数据 财报",
      "target_content": "财务报表摘要、关键财务比率",
      "method": "keyword_search"
    },
    {
      "type": "OutputSpec",
      "id": "spec:financial_summary",
      "format": "table",
      "max_rows": 8,
      "key_fields": ["报告期","归母净利润","营业总收入","毛利率","ROE(加权)","同比增速"],
      "drop_fields": ["每股公积金","每股未分配利润"]
    }
  ],
  "relationships": [
    {"type": "MAPS_TO", "from": "info:financial_summary", "to": "plan:financial_summary:primary", "priority": 1, "condition": "always"},
    {"type": "MAPS_TO", "from": "info:financial_summary", "to": "plan:financial_summary:deep", "priority": 2, "condition": "深度指标关键词触发"},
    {"type": "MAPS_TO", "from": "info:financial_summary", "to": "plan:financial_summary:web_fallback", "priority": 3, "condition": "api失败降级"},
    {"type": "USES_API", "from": "plan:financial_summary:primary", "to": "api:stock_financial_abstract"},
    {"type": "USES_API", "from": "plan:financial_summary:deep", "to": "api:stock_financial_analysis_indicator_em"},
    {"type": "USES_WEB", "from": "plan:financial_summary:web_fallback", "to": "web:sina_financial"},
    {"type": "FALLBACK_TO", "from": "plan:financial_summary:primary", "to": "plan:financial_summary:web_fallback"},
    {"type": "PRODUCES", "from": "plan:financial_summary:primary", "to": "spec:financial_summary"},
    {"type": "RELATED_TO", "from": "info:financial_summary", "to": "info:cashflow", "note": "常见关联：查财务时常需同步查现金流"},
    {"type": "RELATED_TO", "from": "info:financial_summary", "to": "info:valuation", "note": "常见关联：财务指标常配合估值判断"}
  ]
}
```

### 实例二：公司公告

```json
{
  "nodes": [
    {
      "type": "InformationNeed",
      "id": "info:announcement",
      "name": "公司公告",
      "aliases": ["公告","披露","公告查询","重大事项","业绩预告","定增","回购","股权激励","并购","分红公告"],
      "scope": "event",
      "requires_entity": ["stock_code"],
      "description": "上市公司在交易所法定披露的正式公告，是S级信源"
    },
    {
      "type": "AccessPlan",
      "id": "plan:announcement:cninfo_api",
      "channel": "akshare",
      "priority": 1,
      "freshness": "daily",
      "authority": 5,
      "condition": "always"
    },
    {
      "type": "AccessPlan",
      "id": "plan:announcement:eastmoney_web",
      "channel": "web_scrape",
      "priority": 2,
      "freshness": "daily",
      "authority": 4,
      "condition": "当akshare失败，或需要获取公告全文正文时"
    },
    {
      "type": "AkshareCall",
      "id": "api:stock_zh_a_disclosure_report_cninfo",
      "function": "stock_zh_a_disclosure_report_cninfo",
      "param_template": {"symbol": "{stock_code}"},
      "key_columns": ["公告标题","公告时间","公告链接"],
      "code_format": "pure_num",
      "latency_ms": 500,
      "notes": "巨潮资讯官方接口，S级权威，返回公告列表含链接"
    },
    {
      "type": "WebTarget",
      "id": "web:eastmoney_announcement",
      "site_name": "东方财富网",
      "site_url": "https://www.eastmoney.com",
      "authority_level": "A",
      "search_template": "{stock_name} {stock_code} 公告",
      "target_content": "公告标题、时间、内容摘要",
      "method": "site_search"
    },
    {
      "type": "WebTarget",
      "id": "web:cninfo_direct",
      "site_name": "巨潮资讯网",
      "site_url": "https://www.cninfo.com.cn",
      "authority_level": "S",
      "search_template": "stock_code={stock_code}",
      "target_content": "完整公告原文PDF链接",
      "method": "direct_url"
    },
    {
      "type": "OutputSpec",
      "id": "spec:announcement",
      "format": "list",
      "max_rows": 10,
      "key_fields": ["公告标题","公告时间","公告链接"],
      "drop_fields": []
    }
  ],
  "relationships": [
    {"type": "MAPS_TO", "from": "info:announcement", "to": "plan:announcement:cninfo_api", "priority": 1, "condition": "always"},
    {"type": "MAPS_TO", "from": "info:announcement", "to": "plan:announcement:eastmoney_web", "priority": 2, "condition": "需要正文或api失败"},
    {"type": "USES_API", "from": "plan:announcement:cninfo_api", "to": "api:stock_zh_a_disclosure_report_cninfo"},
    {"type": "USES_WEB", "from": "plan:announcement:eastmoney_web", "to": "web:eastmoney_announcement"},
    {"type": "FALLBACK_TO", "from": "plan:announcement:cninfo_api", "to": "plan:announcement:eastmoney_web"},
    {"type": "PRODUCES", "from": "plan:announcement:cninfo_api", "to": "spec:announcement"}
  ]
}
```

### 实例三：资金流向（含多类型）

```json
{
  "nodes": [
    {
      "type": "InformationNeed",
      "id": "info:fund_flow_individual",
      "name": "个股资金流向",
      "aliases": ["主力资金","大单净流入","超大单","资金流向","主力净流入","机构买入","游资动向"],
      "scope": "company",
      "requires_entity": ["stock_code", "market"],
      "description": "个股维度的主力/大单/中单/小单资金净流向"
    },
    {
      "type": "InformationNeed",
      "id": "info:fund_flow_northbound",
      "name": "北向资金",
      "aliases": ["北向资金","陆股通","沪深港通","外资流入","北水","外资持股"],
      "scope": "market",
      "requires_entity": [],
      "description": "沪深港通北向资金的净流入情况和持股明细"
    },
    {
      "type": "InformationNeed",
      "id": "info:fund_flow_sector",
      "name": "板块资金流向",
      "aliases": ["行业资金","板块主力","行业资金流向","哪个板块有资金","板块轮动"],
      "scope": "sector",
      "requires_entity": [],
      "description": "行业/概念板块维度的资金流向排名"
    },
    {
      "type": "AccessPlan",
      "id": "plan:fund_flow_individual:primary",
      "channel": "akshare",
      "priority": 1,
      "freshness": "daily",
      "authority": 4
    },
    {
      "type": "AkshareCall",
      "id": "api:stock_individual_fund_flow",
      "function": "stock_individual_fund_flow",
      "param_template": {"stock": "{stock_code}", "market": "{market}"},
      "key_columns": ["日期","主力净流入","超大单净流入","大单净流入","中单净流入","小单净流入","收盘价","涨跌幅"],
      "code_format": "pure_num",
      "latency_ms": 400,
      "notes": "market参数: sh=沪市, sz=深市, bj=北交所，需要提前确定市场"
    },
    {
      "type": "AccessPlan",
      "id": "plan:fund_flow_individual:web",
      "channel": "web_scrape",
      "priority": 2,
      "freshness": "daily",
      "authority": 4,
      "condition": "akshare失败时"
    },
    {
      "type": "WebTarget",
      "id": "web:eastmoney_fund_flow",
      "site_name": "东方财富网",
      "site_url": "https://www.eastmoney.com",
      "authority_level": "B",
      "search_template": "{stock_name} 主力资金流向",
      "target_content": "主力净流入金额、占比、趋势图数据",
      "method": "site_search"
    },
    {
      "type": "OutputSpec",
      "id": "spec:fund_flow_individual",
      "format": "table",
      "max_rows": 5,
      "key_fields": ["日期","主力净流入","超大单净流入","收盘价","涨跌幅"],
      "drop_fields": ["中单净流入","小单净流入"]
    }
  ],
  "relationships": [
    {"type": "MAPS_TO", "from": "info:fund_flow_individual", "to": "plan:fund_flow_individual:primary", "priority": 1},
    {"type": "MAPS_TO", "from": "info:fund_flow_individual", "to": "plan:fund_flow_individual:web", "priority": 2},
    {"type": "USES_API", "from": "plan:fund_flow_individual:primary", "to": "api:stock_individual_fund_flow"},
    {"type": "USES_WEB", "from": "plan:fund_flow_individual:web", "to": "web:eastmoney_fund_flow"},
    {"type": "FALLBACK_TO", "from": "plan:fund_flow_individual:primary", "to": "plan:fund_flow_individual:web"},
    {"type": "PRODUCES", "from": "plan:fund_flow_individual:primary", "to": "spec:fund_flow_individual"},
    {"type": "RELATED_TO", "from": "info:fund_flow_individual", "to": "info:fund_flow_northbound", "note": "个股资金流常配合北向资金判断机构动向"},
    {"type": "RELATED_TO", "from": "info:fund_flow_sector", "to": "info:fund_flow_individual", "note": "板块有资金流入时，再查个股层面确认"}
  ]
}
```

---

## 完整 InformationNeed 节点清单

基于你的信息源，这是需要建立的全部 InformationNeed 节点，供你一次性建库：

```
【公司维度】
info:financial_summary        财务概要（营收/利润/ROE/毛利率）
info:financial_deep           深度财务（ROIC/杜邦/利息保障）
info:income_statement         利润表（完整三大报表）
info:balance_sheet            资产负债表
info:cashflow_statement       现金流量表
info:valuation                估值指标（PE/PB/PS/市值）
info:stock_price_realtime     实时股价行情
info:stock_price_history      历史K线
info:announcement             公司公告（法定披露）
info:irm_qa                   互动易问答
info:major_holders            前十大股东
info:actual_controller        实际控制人
info:executive_info           高管信息
info:shareholder_change       股东变动
info:equity_pledge            股权质押
info:institute_holding        机构持仓
info:analyst_rating           分析师评级
info:research_report          机构研报
info:dividend_history         历史分红
info:performance_forecast     业绩预告/快报
info:company_profile          公司概况（工商信息/主营业务）
info:ipo_info                 IPO/上市信息
info:governance_risk          公司治理风险（质押/担保/诉讼）

【资金维度】
info:fund_flow_individual     个股资金流向
info:fund_flow_northbound     北向资金（陆股通）
info:fund_flow_sector         板块资金流向
info:fund_flow_market         全市场资金流向

【板块维度】
info:sector_industry_realtime 行业板块实时行情
info:sector_concept_realtime  概念板块实时行情
info:sector_member            板块成分股
info:sector_history           板块历史K线
info:hot_stocks               热搜/涨停/异动股票池

【宏观维度】
info:macro_china_gdp          中国GDP
info:macro_china_cpi_ppi      CPI/PPI
info:macro_china_pmi          PMI（制造业/非制造业）
info:macro_china_money        货币供应（M2/社融）
info:macro_china_lpr          LPR/利率
info:macro_china_trade        进出口数据
info:macro_global_rate        中美利率对比
info:macro_bdi                BDI航运指数

【其他资产】
info:futures_realtime         期货实时行情
info:bond_convertible         可转债
info:fund_etf                 ETF/基金
info:forex                    汇率/外汇
info:gold_price               黄金/贵金属
info:global_index             全球主要指数

【舆情/新闻】
info:news_economic            财经新闻
info:news_policy              政策文件/政策解读
info:sentiment_social         市场情绪/社区讨论（雪球等）
```

---

## 执行流程（给开发参考）

```
1. LLM 输出意图识别结果（JSON）
   {
     "info_needs": ["info:financial_summary", "info:fund_flow_individual"],
     "entities": {"stock_code": "300750", "market": "sz", "stock_name": "宁德时代"}
   }

2. 图谱查询（伪代码）
   for need in info_needs:
       plans = graph.query("MATCH (n:InformationNeed {id: need})-[r:MAPS_TO]->(p:AccessPlan)
                           RETURN p ORDER BY r.priority")
       selected_plan = plans[0]  # 取最高优先级
       
       if selected_plan.channel == "akshare":
           call = graph.query("MATCH (p)-[:USES_API]->(c:AkshareCall) WHERE p.id=? RETURN c")
           params = fill_template(call.param_template, entities)
           # 执行 akshare 调用
           
       elif selected_plan.channel in ["web_scrape", "web_search"]:
           target = graph.query("MATCH (p)-[:USES_WEB]->(w:WebTarget) WHERE p.id=? RETURN w")
           query = fill_template(target.search_template, entities)
           # 执行网页搜索或爬取

3. 获取 OutputSpec，对结果进行裁剪（控制返回给 LLM 的 token 量）
   spec = graph.query("MATCH (p)-[:PRODUCES]->(s:OutputSpec) WHERE p.id=? RETURN s")
   result = truncate(result, max_rows=spec.max_rows, keep_fields=spec.key_fields)

4. 结果送进 LLM 组装和分析
```

---

## 与原方案的关键差异对比

| 维度 | 原方案 | 新方案 |
|------|--------|--------|
| 节点数量 | 8种节点（含冗余） | 5种节点（精简无冗余） |
| 数据质量/时效属性 | 放在关系上，但关系太多导致维护困难 | 放在 AccessPlan 节点上，一次维护全部生效 |
| 降级策略 | `fallback_to` 在 Source 之间，但 Source 粒度太粗 | `FALLBACK_TO` 在 AccessPlan 之间，粒度精确到调用方式 |
| 输出控制 | 完全缺失 | OutputSpec 节点，精确控制返回字段和行数 |
| akshare 参数 | 没有设计 | AkshareCall 含 param_template，运行时直接填充 |
| 网页搜索模板 | 有 Search Template 但与 Source 绑定不清晰 | WebTarget 独立节点，含方法类型区分 |
| 关联查询 | 无 | `RELATED_TO` 关系，支持自动扩展相关信息查询 |