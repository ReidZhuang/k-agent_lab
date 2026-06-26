# levistock 知识图谱

> 查询入口: 按"查询意图 → 数据源/接口"查找
> 接口细节见同目录下的 `instruction.md`

---

## 一、实体关系图

```
市场情绪
    ├── 财联社情绪 → market_emotion_cls()
    │   ├── 市场热度 / 上涨占比 / 赚钱效应
    │   └── 涨停梯队（一板/二板/三板/高度板及晋级率）
    └── 开盘红情绪 → market_emotion_kph(date)

风口板块 → get_sector_hot_plates()
    ├── 热点板块名称/涨跌幅
    ├── 上涨原因分析（★ 自然语言描述）
    ├── 成分股（★ 涨停标签/涨停原因）
    └── 市场主线 → market_mainline_cls / market_wind_cls

快讯 → news_telegraph_cls(date, category)
    └── 财联社实时电报（标题/内容/时间）

板块
    ├── 板块列表 → sector_em('industry'/'concept'/'industry_l1/2/3')
    │   ├── 行业板块(~496) / 概念板块(~494)
    │   └── 每板块含: 涨跌/资金/换手/领涨股/涨跌家数
    ├── 板块成分股 → sector_stocks_em(code)
    ├── 板块历史成分 → sector_stocks_his_kph(date, type)
    ├── 股票→行业归属 → sector_stock_belong_em([codes])
    ├── 板块排名 → sector_ranking_kph(date, type)
    ├── 板块轮动 → get_sector_rotation()
    ├── 板块热度 → get_sector_heat()
    └── 行业分类 → sector_industry_cls()

涨停/跌停
    ├── 涨停池 → stock_zt_pool_em(date)
    │   ├── 连板数 / 封板时间 / 开板次数 / 行业归属
    │   └── 主力资金 / 换手率 / 流通市值
    ├── 跌停池 → stock_dt_pool_em(date)
    ├── 昨日涨停表现 → stock_yesterday_zt_em()
    ├── 涨停历史 → limit_up_his_kph()
    ├── 跌停历史 → limit_down_his_kph()
    ├── 破板率 → get_pmsl()
    ├── 涨停复盘 → get_his_limit_resumption()
    └── 涨停天天 → get_zttt()

异动
    ├── 异动列表 → stock_changes_em()
    └── 异动明细 → stock_changes_detail_em()

大盘指数
    ├── 主要指数(6个) → market_index_em()
    └── 全量指数 → market_index_all_em()

个股
    ├── 全量A股行情(5000+) → stocks_all_em()
    ├── 个股K线 → stock_kline_cls(code)
    ├── 个股分时 → stock_timeline_cls(code)
    ├── 热度排名 → stock_hot_rank_ths(limit)
    └── 选股 → stock_strategy_wencai(query)

工具
    ├── 新闻 → news(category)
    ├── 交易日历 → get_trade_days()
    └── 是否交易日 → is_trade_day(date)
```

---

## 二、查询路径索引

### 2.1 市场情绪/风口

| 问题 | 调用路径 |
|------|---------|
| "今天市场情绪怎么样" | `market_emotion_cls()` |
| "今天哪些板块最热" | `get_sector_hot_plates()` |
| "为什么芯片板块涨了" | `get_sector_hot_plates()` → 找芯片 → `up_reason` |
| "今天涨停梯队" | `market_emotion_cls()` → `limit_up_board` |
| "今天赚钱效应如何" | `market_emotion_cls()` → `profit_ratio` |
| "有最新快讯吗" | `news_telegraph_cls()` |
| "市场主线是什么" | `market_mainline_cls()` |

### 2.2 板块

| 问题 | 调用路径 |
|------|---------|
| "有哪些行业板块" | `sector_em('industry')` |
| "有哪些概念板块" | `sector_em('concept')` |
| "新能源汽车板块成分股" | `sector_stocks_em('BK0441')` |
| "宁德时代属于什么行业" | `sector_stock_belong_em(['300750'])` |
| "板块轮动情况" | `get_sector_rotation()` |
| "板块热度排名" | `get_sector_heat()` |
| "哪个板块主力资金流入最多" | `sector_em('industry')` → 按 `main_inflow` 排序 |

### 2.3 涨停/跌停

| 问题 | 调用路径 |
|------|---------|
| "今天涨停板有哪些" | `stock_zt_pool_em()` |
| "哪些股连板最多" | `stock_zt_pool_em()` → 按 `continuous` 排序 |
| "首次封板时间最早的" | `stock_zt_pool_em()` → 按 `first_zt_time` 排序 |
| "今天跌停股" | `stock_dt_pool_em()` |
| "昨天涨停的今天怎么样" | `stock_yesterday_zt_em()` |
| "涨停历史复盘" | `get_his_limit_resumption()` |
| "今天破板率多少" | `get_pmsl()` |
| "有股票异动吗" | `stock_changes_em()` |

### 2.4 大盘/个股

| 问题 | 调用路径 |
|------|---------|
| "今天大盘指数" | `market_index_em()` |
| "今天成交额多少" | `market_index_em()` → 上证 `amount` |
| "宁德时代K线" | `stock_kline_cls('SZ300750')` |
| "宁德时代分时" | `stock_timeline_cls('SZ300750')` |
| "今天最热的股票" | `stock_hot_rank_ths()` |

---

## 三、数据源优先级矩阵

| 查询类型 | levistock | akshare | 雪球 | 最佳选择 |
|---------|:---------:|:-------:|:----:|:--------:|
| **市场情绪/涨停梯队** | ✅ **独家** | ❌ | ❌ | **levistock** |
| **风口板块+上涨原因** | ✅ **独家** | ❌ | ❌ | **levistock** |
| **财联社快讯** | ✅ **独家** | ❌ | ❌ | **levistock** |
| **涨停池（封板时间/连板）** | ✅ 更详细 | ✅ 基础 | ❌ | **levistock** |
| 板块列表 (industry/concept) | ✅ | ✅ | ❌ | 重复 |
| 板块成分股 | ✅ | ✅ | ❌ | 重复 |
| 股票→行业归属 | ✅ | ✅ | ❌ | 重复 |
| 大盘指数 | ✅ | ✅ | ❌ | 重复 |
| A股全量行情 | ✅ | ✅ | ❌ | 重复 |
| 个股K线 | ✅ | ✅ | ✅ | 重复 |
| 概念板块聚类(反向) | ❌ | ❌ | ✅ | 雪球 |
| 财务数据 | ❌ | ✅ | ✅ | akshare/雪球 |
