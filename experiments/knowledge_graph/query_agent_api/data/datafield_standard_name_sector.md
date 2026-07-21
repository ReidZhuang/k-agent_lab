# standard_name 匹配「板块」— 带数据源信息

关键词: `板块` → **15** 个 DataField

| ID | standard_name | 说明 | 粒度 | 别名(简) | 单位 | 数据类型 | 数据源 | 协议 | refresh_time | 权威等级 | 有备份 |
|:--|:-------------|:-----|:----|:---------|:----:|:--------|:------|:----:|:-----------|:-------:|:-----:|
| FIELD_DC_INDEX_IDX_TYPE | 板块类型(行业板块、概念板块、地域板块) | idx_type（东方财富） | 日频,板块级别(东方财富) | 板块类型(行业板块、概念板块、地域板块)(东方财富) |  | float | TuShare dc_index | tushare |  | S |  |
| FIELD_KPL_LIST_THEME | 板块 | theme | 日频,市场级别 | 板块 |  | float | TuShare kpl_list | tushare |  |  |  |
| FIELD_MONEYFLOW_CNT_THS_INDUSTRY_INDEX | 板块指数点位 | industry_index | 日频,个股级别 | 板块指数点位 |  | float | TuShare moneyflow_cnt_ths | tushare |  |  |  |
| FIELD_MONEYFLOW_CNT_THS_NAME | 板块名称 | name | 日频,个股级别 | 板块名称(同花顺概念) |  | float | TuShare moneyflow_cnt_ths | tushare |  |  |  |
| FIELD_MONEYFLOW_IND_DC_CLOSE | 板块最新指数 | close | 日频,个股级别 | 板块最新指数 |  | float | TuShare moneyflow_ind_dc | tushare |  |  |  |
| FIELD_MONEYFLOW_IND_DC_NAME | 板块名称 | name | 日频,个股级别 | 板块名称(东方财富板块) |  | float | TuShare moneyflow_ind_dc | tushare |  |  |  |
| FIELD_MONEYFLOW_IND_DC_PCT_CHANGE | 板块涨跌幅（%） | pct_change | 日频,个股级别 | 板块涨跌幅（%） |  | float | TuShare moneyflow_ind_dc | tushare |  |  |  |
| FIELD_MONEYFLOW_IND_THS_INDUSTRY | 板块名称 | industry | 日频,个股级别 | 板块名称(同花顺行业) |  | float | TuShare moneyflow_ind_ths | tushare |  |  |  |
| FIELD_SECTOR_AMOUNT | 板块成交额 | 板块当日成交额（同花顺(akshare)） | 日频,板块级别(同花顺(akshare)) | 成交额(同花顺(akshare)) | 亿元 | float | 同花顺板块行情 | akshare | intraday | S | True |
| FIELD_SECTOR_NAME | 板块名称 | 行业/概念板块名称（同花顺(akshare)） | 日频,板块级别(同花顺(akshare)) | 板块名称(同花顺(akshare)) | — | string | 同花顺板块行情 | akshare | intraday | S | True |
| FIELD_SECTOR_PCT_CHG | 板块涨跌幅 | 板块指数涨跌幅（同花顺(akshare)） | 日频,板块级别(同花顺(akshare)) | 涨跌幅(同花顺(akshare)) | % | float | 同花顺板块行情 | akshare | intraday | S | True |
| FIELD_SECTOR_THS_AVG_PRICE | 板块均价 | 同花顺行业板块均价，按板块粒度（同花顺(akshare)） | 日频,板块级别(同花顺(akshare)) | 同花顺板块平均价(同花顺(akshare)) | 元 | float | 同花顺板块行情 | akshare |  | S |  |
| FIELD_SECTOR_THS_VOLUME | 板块总成交量 | 同花顺行业板块总成交量(手)，按板块粒度（同花顺(akshare)） | 日频,板块级别(同花顺(akshare)) | 同花顺行业总成交量(同花顺(akshare)) | 手 | float | 同花顺板块行情 | akshare |  | S |  |
| FIELD_TDX_INDEX_IDX_TYPE | 板块类型 | 板块类型 | 低频,板块级别 | 板块类型 |  | str | TuShare tdx_index | tushare |  | A |  |
| FIELD_TDX_INDEX_NAME | 板块名称 | 板块名称 | 低频,板块级别 | 板块名称 |  | str | TuShare tdx_index | tushare |  | A |  |

---
*查询时间: 2026-07-17*