# standard_name 匹配「换手率」

关键词: `换手率` → **12** 个 DataField

| ID | standard_name | 说明 | 粒度 | 别名(简) | 单位 | 数据类型 | 数据源 | 协议 | DS refresh |
|:--|:-------------|:-----|:----|:---------|:----:|:--------|:------|:----:|:----------|
| FIELD_BAK_DAILY_TURN_OVER | 换手率 | turn_over | 日频,个股级别 | 换手率(备用行情) |  | float | TuShare bak_daily | tushare |  |
| FIELD_DAILY_INFO_TR | 换手率（％），注：深交所暂无此列 | tr | 日频,个股级别 | 换手率（％），注：深交所暂无此列 |  | float | TuShare daily_info | tushare |  |
| FIELD_DC_DAILY_TURNOVER_RATE | 换手率 | turnover_rate（东方财富） | 日频,板块级别(东方财富) | 换手率(东方财富) |  | float | TuShare dc_daily | tushare |  |
| FIELD_DC_INDEX_TURNOVER_RATE | 换手率 | turnover_rate（东方财富） | 日频,板块级别(东方财富) | 换手率(东方财富) |  | float | TuShare dc_index | tushare |  |
| FIELD_INDEX_DAILYBASIC_TURNOVER_RATE_F | 换手率(基于自由流通股本) | turnover_rate_f | 日频,指数级别 | 换手率(基于自由流通股本) |  | float | TuShare 指数每日指标 | tushare | daily_17:00 |
| FIELD_INDEX_TURNOVER | 换手率 | 指数成分股换手率 | 日频,指数级别 | 换手率 | % | float | TuShare 指数每日指标 | tushare | daily_17:00 |
| FIELD_KPL_LIST_TURNOVER_RATE | 换手率% | turnover_rate | 日频,市场级别 | 换手率% |  | float | TuShare kpl_list | tushare |  |
| FIELD_LHB_TURNOVER | 换手率 | 股票当日换手率 | 日频,个股级别 | 换手率 | % | float | TuShare 龙虎榜 | tushare | daily_20:00 |
| FIELD_STK_FACTOR_PRO_TURNOVER_RATE | 换手率（%） | turnover_rate | 日频,个股级别 | 换手率（%） |  | float | TuShare stk_factor_pro | tushare |  |
| FIELD_STK_FACTOR_PRO_TURNOVER_RATE_F | 换手率（自由流通股） | turnover_rate_f | 日频,个股级别 | 换手率（自由流通股） |  | float | TuShare stk_factor_pro | tushare |  |
| FIELD_THS_DAILY_TURNOVER_RATE | 换手率（%） | turnover_rate（同花顺） | 日频,板块级别(同花顺) | 换手率（%）(同花顺) |  | float | TuShare ths_daily | tushare |  |
| FIELD_TURNOVER_RATE | 换手率 | 流通股本换手率 | 实时,个股级别 | 换手率 | % | float | 腾讯财经实时行情 | tencent | realtime |

---
*查询时间: 2026-07-17*