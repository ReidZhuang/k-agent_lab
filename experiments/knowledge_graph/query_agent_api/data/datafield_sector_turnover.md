# 板块 / 换手率 相关 DataField

**搜索关键词**: 板块, 换手率, sector, turnover, board

**匹配结果**: 30 个

| ID | 名称 | 说明 | 别名(简) | 粒度 | 单位 | 数据类型 | 数据源 | 协议 |
|:--|:----|:-----|:---------|:----:|:----:|:--------|:------|:----:|
| FIELD_INDEX_TURNOVER |  | 指数成分股换手率 | 换手率 | 日频,指数级别 | % | float | DS_TUSHARE_INDEX_DB | tushare |
| FIELD_SECTOR_NAME |  | 行业/概念板块名称（同花顺(akshare)） | 板块名称(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | — | string | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_PCT_CHG |  | 板块指数涨跌幅（同花顺(akshare)） | 涨跌幅(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | % | float | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_AMOUNT |  | 板块当日成交额（同花顺(akshare)） | 成交额(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 亿元 | float | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_LEAD_STOCK |  | 板块内涨幅最大股票名称（同花顺(akshare)） | 领涨股(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | — | string | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_MAIN_INFLOW |  | 板块主力资金净流入金额（同花顺(akshare)） | 主力净流入(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 亿元 | float | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_UP_COUNT |  | 板块内上涨股票数量（同花顺(akshare)） | 上涨家数(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 家 | int | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_DOWN_COUNT |  | 板块内下跌股票数量（同花顺(akshare)） | 下跌家数(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 家 | int | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_LHB_TURNOVER |  | 股票当日换手率 | 换手率 | 日频,个股级别 | % | float | DS_TUSHARE_TOP_LIST | tushare |
| FIELD_TURNOVER_RATE |  | 流通股本换手率 | 换手率 | 实时,个股级别 | % | float | DS_TENCENT_QUOTE | tencent |
| FIELD_LIMIT_SECTOR |  | 涨停股票所属行业板块 | 所属行业 | 实时,个股级别 | — | string | DS_LEVISTOCK_ZT_POOL | levistock |
| FIELD_SECTOR_THS_VOLUME |  | 同花顺行业板块总成交量(手)，按板块粒度（同花顺(akshare)） | 同花顺行业总成交量(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 手 | float | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_SECTOR_THS_AVG_PRICE |  | 同花顺行业板块均价，按板块粒度（同花顺(akshare)） | 同花顺板块平均价(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 元 | float | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_CONCEPT_THS_DRIVER |  | 同花顺概念板块驱动事件描述，按概念粒度（同花顺(akshare)） | 同花顺概念驱动(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) |  | string | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_CONCEPT_THS_LEADER |  | 同花顺概念板块龙头股名称，按概念粒度（同花顺(akshare)） | 同花顺概念领涨股(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) |  | string | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_CONCEPT_THS_MEMBER_COUNT |  | 同花顺概念板块的成分股数量，按概念粒度（同花顺(akshare)） | 同花顺成分股总数(同花顺(akshare)) | 日频,板块级别(同花顺(akshare)) | 家 | int | DS_AKSHARE_SECTOR_THS | akshare |
| FIELD_TDX_INDEX_NAME |  | 板块名称 | 板块名称 | 低频,板块级别 |  | str | DS_TUSHARE_TDX_INDEX | tushare |
| FIELD_TDX_INDEX_IDX_TYPE |  | 板块类型 | 板块类型 | 低频,板块级别 |  | str | DS_TUSHARE_TDX_INDEX | tushare |
| FIELD_BAK_DAILY_AVG_TURNOVER |  | avg_turnover | 笔换手 | 日频,个股级别 |  | float | DS_TUSHARE_BAK_DAILY | tushare |
| FIELD_DC_DAILY_TURNOVER_RATE |  | turnover_rate（东方财富） | 换手率(东方财富) | 日频,板块级别(东方财富) |  | float | DS_TUSHARE_DC_DAILY | tushare |
| FIELD_DC_INDEX_TURNOVER_RATE |  | turnover_rate（东方财富） | 换手率(东方财富) | 日频,板块级别(东方财富) |  | float | DS_TUSHARE_DC_INDEX | tushare |
| FIELD_KPL_LIST_BID_TURNOVER |  | bid_turnover | 竞价换手% | 日频,市场级别 |  | float | DS_TUSHARE_KPL_LIST | tushare |
| FIELD_KPL_LIST_TURNOVER_RATE |  | turnover_rate | 换手率% | 日频,市场级别 |  | float | DS_TUSHARE_KPL_LIST | tushare |
| FIELD_STK_FACTOR_PRO_TURNOVER_RATE |  | turnover_rate | 换手率（%） | 日频,个股级别 |  | float | DS_TUSHARE_STK_FACTOR_PRO | tushare |
| FIELD_STK_FACTOR_PRO_TURNOVER_RATE_F |  | turnover_rate_f | 换手率（自由流通股） | 日频,个股级别 |  | float | DS_TUSHARE_STK_FACTOR_PRO | tushare |
| FIELD_TDX_DAILY_TURNOVER_RATE |  | turnover_rate（通达信） | 换手%(通达信) | 日频,板块级别(通达信) |  | float | DS_TUSHARE_TDX_DAILY | tushare |
| FIELD_THS_DAILY_TURNOVER_RATE |  | turnover_rate（同花顺） | 换手率（%）(同花顺) | 日频,板块级别(同花顺) |  | float | DS_TUSHARE_THS_DAILY | tushare |
| FIELD_DAILY_BASIC_TURNOVER_RATE |  | turnover_rate | turnover_rate | 日频,个股级别 |  | float | DS_TUSHARE_DAILY_BASIC | tushare |
| FIELD_DAILY_BASIC_TURNOVER_RATE_F |  | turnover_rate_f | turnover_rate_f | 日频,个股级别 |  | float | DS_TUSHARE_DAILY_BASIC | tushare |
| FIELD_INDEX_DAILYBASIC_TURNOVER_RATE_F |  | turnover_rate_f | 换手率(基于自由流通股本) | 日频,指数级别 |  | float | DS_TUSHARE_INDEX_DB | tushare |


---

*查询时间: 2026-07-17*