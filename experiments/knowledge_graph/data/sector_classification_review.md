# 板块分类系统权威评级清单

## 数据源概述

## DS_TUSHARE_SW_DAILY

- **名称**: TuShare sw_daily
- **协议**: tushare
- **表**: sw_daily
- **字段数**: 13

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_SW_DAILY_AMOUNT | 成交额（万元） | amount | 日频,板块级别 |
| FIELD_SW_DAILY_CHANGE | 涨跌点位 | change | 日频,板块级别 |
| FIELD_SW_DAILY_CLOSE | 收盘点位 | close | 日频,板块级别 |
| FIELD_SW_DAILY_FLOAT_MV | 流通市值（万元） | float_mv | 日频,板块级别 |
| FIELD_SW_DAILY_HIGH | 最高点位 | high | 日频,板块级别 |
| FIELD_SW_DAILY_LOW | 最低点位 | low | 日频,板块级别 |
| FIELD_SW_DAILY_NAME | 指数名称 | name | 日频,板块级别 |
| FIELD_SW_DAILY_OPEN | 开盘点位 | open | 日频,板块级别 |
| FIELD_SW_DAILY_PB | 市净率 | pb | 日频,板块级别 |
| FIELD_SW_DAILY_PCT_CHANGE | 涨跌幅 | pct_change | 日频,板块级别 |
| FIELD_SW_DAILY_PE | 市盈率 | pe | 日频,板块级别 |
| FIELD_SW_DAILY_TOTAL_MV | 总市值（万元） | total_mv | 日频,板块级别 |
| FIELD_SW_DAILY_VOL | 成交量（万股） | vol | 日频,板块级别 |

## DS_TUSHARE_CI_DAILY

- **名称**: TuShare ci_daily
- **协议**: tushare
- **表**: ci_daily
- **字段数**: 9

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_CI_DAILY_AMOUNT | 成交额（万元） | amount | 日频,板块级别 |
| FIELD_CI_DAILY_CHANGE | 涨跌点位 | change | 日频,板块级别 |
| FIELD_CI_DAILY_CLOSE | 收盘点位 | close | 日频,板块级别 |
| FIELD_CI_DAILY_HIGH | 最高点位 | high | 日频,板块级别 |
| FIELD_CI_DAILY_LOW | 最低点位 | low | 日频,板块级别 |
| FIELD_CI_DAILY_OPEN | 开盘点位 | open | 日频,板块级别 |
| FIELD_CI_DAILY_PCT_CHANGE | 涨跌幅 | pct_change | 日频,板块级别 |
| FIELD_CI_DAILY_PRE_CLOSE | 昨日收盘点位 | pre_close | 日频,板块级别 |
| FIELD_CI_DAILY_VOL | 成交量（万股） | vol | 日频,板块级别 |

## DS_TUSHARE_DC_DAILY

- **名称**: TuShare dc_daily
- **协议**: tushare
- **表**: dc_daily
- **字段数**: 11

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_DC_DAILY_AMOUNT | 成交额(元) | amount | 日频,板块级别 |
| FIELD_DC_DAILY_CATEGORY | category | category | 日频,板块级别 |
| FIELD_DC_DAILY_CHANGE | 涨跌点位 | change | 日频,板块级别 |
| FIELD_DC_DAILY_CLOSE | 收盘点位 | close | 日频,板块级别 |
| FIELD_DC_DAILY_HIGH | 最高点位 | high | 日频,板块级别 |
| FIELD_DC_DAILY_LOW | 最低点位 | low | 日频,板块级别 |
| FIELD_DC_DAILY_OPEN | 开盘点位 | open | 日频,板块级别 |
| FIELD_DC_DAILY_PCT_CHANGE | 涨跌幅 | pct_change | 日频,板块级别 |
| FIELD_DC_DAILY_SWING | 振幅 | swing | 日频,板块级别 |
| FIELD_DC_DAILY_TURNOVER_RATE | 换手率 | turnover_rate | 日频,板块级别 |
| FIELD_DC_DAILY_VOL | 成交量(股) | vol | 日频,板块级别 |

## DS_TUSHARE_TDX_DAILY

- **名称**: TuShare tdx_daily
- **协议**: tushare
- **表**: tdx_daily
- **字段数**: 37

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_DC_INDEX_UP_NUM | 上涨家数 | up_num | 日频,板块级别 |
| FIELD_TDX_DAILY_10DAY | 10日涨幅% | 10day | 日频,板块级别 |
| FIELD_TDX_DAILY_1YEAR | 一年涨幅% | 1year | 日频,板块级别 |
| FIELD_TDX_DAILY_20DAY | 20日涨幅% | 20day | 日频,板块级别 |
| FIELD_TDX_DAILY_3DAY | 3日涨幅% | 3day | 日频,板块级别 |
| FIELD_TDX_DAILY_5DAY | 5日涨幅% | 5day | 日频,板块级别 |
| FIELD_TDX_DAILY_60DAY | 60日涨幅% | 60day | 日频,板块级别 |
| FIELD_TDX_DAILY_AB_TOTAL_MV | AB股总市值（亿） | ab_total_mv | 日频,板块级别 |
| FIELD_TDX_DAILY_AMOUNT | 成交额（万元）, 对于期货指数，该字段存储持仓量 | amount | 日频,板块级别 |
| FIELD_TDX_DAILY_BM_BUY_NET | 主买净额(元) | bm_buy_net | 日频,板块级别 |
| FIELD_TDX_DAILY_BM_BUY_RATIO | 主买占比% | bm_buy_ratio | 日频,板块级别 |
| FIELD_TDX_DAILY_BM_NET | 主力净额 | bm_net | 日频,板块级别 |
| FIELD_TDX_DAILY_BM_RATIO | 主力占比% | bm_ratio | 日频,板块级别 |
| FIELD_TDX_DAILY_CHANGE | 涨跌点位 | change | 日频,板块级别 |
| FIELD_TDX_DAILY_CLOSE | 收盘点位 | close | 日频,板块级别 |
| FIELD_TDX_DAILY_DOWN_NUM | 下跌家数 | down_num | 日频,板块级别 |
| FIELD_TDX_DAILY_FLOAT_MV | 流通市值(亿) | float_mv | 日频,板块级别 |
| FIELD_TDX_DAILY_FLOAT_SHARE | 流通股(亿) | float_share | 日频,板块级别 |
| FIELD_TDX_DAILY_HIGH | 最高点位 | high | 日频,板块级别 |
| FIELD_TDX_DAILY_LIMIT_DOWN_NUM | 跌停家数 | limit_down_num | 日频,板块级别 |
| FIELD_TDX_DAILY_LIMIT_UP_NUM | 涨停家数 | limit_up_num | 日频,板块级别 |
| FIELD_TDX_DAILY_LOW | 最低点位 | low | 日频,板块级别 |
| FIELD_TDX_DAILY_LU_DAYS | 连涨天数 | lu_days | 日频,板块级别 |
| FIELD_TDX_DAILY_MTD | 月初至今% | mtd | 日频,板块级别 |
| FIELD_TDX_DAILY_OPEN | 开盘点位 | open | 日频,板块级别 |
| FIELD_TDX_DAILY_PB | 市净率 | pb | 日频,板块级别 |
| FIELD_TDX_DAILY_PCT_CHANGE | 涨跌幅% | pct_change | 日频,板块级别 |
| FIELD_TDX_DAILY_PE | 市盈率 | pe | 日频,板块级别 |
| FIELD_TDX_DAILY_PRE_CLOSE | 昨日收盘点 | pre_close | 日频,板块级别 |
| FIELD_TDX_DAILY_RISE | 收盘涨速% | rise | 日频,板块级别 |
| FIELD_TDX_DAILY_SWING | 振幅% | swing | 日频,板块级别 |
| FIELD_TDX_DAILY_TOTAL_SHARE | 总股本(亿) | total_share | 日频,板块级别 |
| FIELD_TDX_DAILY_TURNOVER_RATE | 换手% | turnover_rate | 日频,板块级别 |
| FIELD_TDX_DAILY_UP_NUM | 上涨家数 | up_num | 日频,板块级别 |
| FIELD_TDX_DAILY_VOL | 成交量（手） | vol | 日频,板块级别 |
| FIELD_TDX_DAILY_VOL_RATIO | 量比 | vol_ratio | 日频,板块级别 |
| FIELD_TDX_DAILY_YTD | 年初至今% | ytd | 日频,板块级别 |

## DS_TUSHARE_THS_DAILY

- **名称**: TuShare ths_daily
- **协议**: tushare
- **表**: ths_daily
- **字段数**: 10

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_THS_DAILY_AVG_PRICE | 平均价 | avg_price | 日频,板块级别 |
| FIELD_THS_DAILY_CHANGE | 涨跌点位 | change | 日频,板块级别 |
| FIELD_THS_DAILY_CLOSE | 收盘点位 | close | 日频,板块级别 |
| FIELD_THS_DAILY_HIGH | 最高点位 | high | 日频,板块级别 |
| FIELD_THS_DAILY_LOW | 最低点位 | low | 日频,板块级别 |
| FIELD_THS_DAILY_OPEN | 开盘点位 | open | 日频,板块级别 |
| FIELD_THS_DAILY_PCT_CHANGE | 涨跌幅 | pct_change | 日频,板块级别 |
| FIELD_THS_DAILY_PRE_CLOSE | 昨日收盘点 | pre_close | 日频,板块级别 |
| FIELD_THS_DAILY_TURNOVER_RATE | 换手率（%） | turnover_rate | 日频,板块级别 |
| FIELD_THS_DAILY_VOL | 成交量（手） | vol | 日频,板块级别 |

## DS_AKSHARE_SECTOR_SPOT

- **名称**: akshare 板块实时行情
- **协议**: akshare
- **表**: stock_board_industry_spot_em
- **字段数**: 10

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_DOWN_COUNT | 下跌家数 | 下跌家数 | 日频,板块级别 |
| FIELD_SECTOR_AMPLITUDE | 板块振幅 | 振幅 | 日频,板块级别 |
| FIELD_SECTOR_CODE | 板块代码 | 板块代码 | 日频,板块级别 |
| FIELD_SECTOR_LEAD_CODE | 领涨股代码 | 领涨股票 | 日频,板块级别 |
| FIELD_SECTOR_PRICE | 板块指数 | 板块指数 | 日频,板块级别 |
| FIELD_SECTOR_TOP_DROP | 领跌股名称 | 领跌股 | 日频,板块级别 |
| FIELD_SECTOR_TOP_DROP_CHG | 领跌股涨幅 | 领跌股涨幅 | 日频,板块级别 |
| FIELD_SECTOR_TOTAL_MV | 总市值 | 总市值 | 日频,板块级别 |
| FIELD_SECTOR_TURNOVER | 板块换手率 | 换手率 | 日频,板块级别 |
| FIELD_UP_COUNT | 上涨家数 | 上涨家数 | 日频,板块级别 |

## DS_AKSHARE_SECTOR_THS

- **名称**: 同花顺板块行情
- **协议**: akshare
- **表**: stock_board_industry_summary_ths
- **字段数**: 13

| 字段ID | 标准名 | api_column | 粒度 |
|--------|--------|-----------|------|
| FIELD_CONCEPT_THS_DRIVER | 概念驱动事件 | 驱动事件 | 日频,板块级别 |
| FIELD_CONCEPT_THS_LEADER | 概念龙头股 | 龙头股 | 日频,板块级别 |
| FIELD_CONCEPT_THS_MEMBER_COUNT | 概念成分股数量 | 成分股数量 | 日频,板块级别 |
| FIELD_SECTOR_AMOUNT | 板块成交额 | 总成交额 | 日频,板块级别 |
| FIELD_SECTOR_DOWN_COUNT | 下跌家数 | 下跌家数 | 日频,板块级别 |
| FIELD_SECTOR_LEAD_CHG | 领涨股涨幅 | 领涨股-涨跌幅 | 日频,板块级别 |
| FIELD_SECTOR_LEAD_STOCK | 领涨股名称 | 领涨股 | 日频,板块级别 |
| FIELD_SECTOR_MAIN_INFLOW | 主力净流入 | 净流入 | 日频,板块级别 |
| FIELD_SECTOR_NAME | 板块名称 | 板块 | 日频,板块级别 |
| FIELD_SECTOR_PCT_CHG | 板块涨跌幅 | 涨跌幅 | 日频,板块级别 |
| FIELD_SECTOR_THS_AVG_PRICE | 板块均价 | 均价 | 日频,板块级别 |
| FIELD_SECTOR_THS_VOLUME | 板块总成交量 | 总成交量 | 日频,板块级别 |
| FIELD_SECTOR_UP_COUNT | 上涨家数 | 上涨家数 | 日频,板块级别 |


## 跨数据源相似指标对比

以下是指标名相同或相近但来自不同板块分类体系的字段：

### 涨跌幅

| 数据源 | 字段ID | 粒度 |
|--------|--------|------|
| DS_TUSHARE_SW_DAILY | FIELD_SW_DAILY_PCT_CHANGE | 日频,板块级别 |
| DS_TUSHARE_CI_DAILY | FIELD_CI_DAILY_PCT_CHANGE | 日频,板块级别 |
| DS_TUSHARE_DC_DAILY | FIELD_DC_DAILY_PCT_CHANGE | 日频,板块级别 |
| DS_TUSHARE_TDX_DAILY | FIELD_TDX_DAILY_PCT_CHANGE | 日频,板块级别 |
| DS_TUSHARE_THS_DAILY | FIELD_THS_DAILY_PCT_CHANGE | 日频,板块级别 |
| DS_AKSHARE_SECTOR_THS | FIELD_SECTOR_PCT_CHG | 日频,板块级别 |

### 收盘点位

| 数据源 | 字段ID | 粒度 |
|--------|--------|------|
| DS_TUSHARE_SW_DAILY | FIELD_SW_DAILY_CLOSE | 日频,板块级别 |
| DS_TUSHARE_CI_DAILY | FIELD_CI_DAILY_PRE_CLOSE | 日频,板块级别 |
| DS_TUSHARE_CI_DAILY | FIELD_CI_DAILY_CLOSE | 日频,板块级别 |
| DS_TUSHARE_DC_DAILY | FIELD_DC_DAILY_CLOSE | 日频,板块级别 |
| DS_TUSHARE_TDX_DAILY | FIELD_TDX_DAILY_CLOSE | 日频,板块级别 |
| DS_TUSHARE_THS_DAILY | FIELD_THS_DAILY_CLOSE | 日频,板块级别 |

### 成交额

| 数据源 | 字段ID | 粒度 |
|--------|--------|------|
| DS_TUSHARE_SW_DAILY | FIELD_SW_DAILY_AMOUNT | 日频,板块级别 |
| DS_TUSHARE_CI_DAILY | FIELD_CI_DAILY_AMOUNT | 日频,板块级别 |
| DS_TUSHARE_DC_DAILY | FIELD_DC_DAILY_AMOUNT | 日频,板块级别 |
| DS_TUSHARE_TDX_DAILY | FIELD_TDX_DAILY_AMOUNT | 日频,板块级别 |
| DS_AKSHARE_SECTOR_THS | FIELD_SECTOR_AMOUNT | 日频,板块级别 |

### 成交量

| 数据源 | 字段ID | 粒度 |
|--------|--------|------|
| DS_TUSHARE_SW_DAILY | FIELD_SW_DAILY_VOL | 日频,板块级别 |
| DS_TUSHARE_CI_DAILY | FIELD_CI_DAILY_VOL | 日频,板块级别 |
| DS_TUSHARE_DC_DAILY | FIELD_DC_DAILY_VOL | 日频,板块级别 |
| DS_TUSHARE_TDX_DAILY | FIELD_TDX_DAILY_VOL | 日频,板块级别 |
| DS_TUSHARE_THS_DAILY | FIELD_THS_DAILY_VOL | 日频,板块级别 |
| DS_AKSHARE_SECTOR_THS | FIELD_SECTOR_THS_VOLUME | 日频,板块级别 |


## 结论（供决策）

这5套板块分类体系**不是重复字段**，而是5种不同的行业分类标准：

| 体系 | 维护方 | 特点 |
|------|--------|------|
| **SW（申万）** | 申万宏源 | 最权威，31个一级行业，分L1/L2/L3三级 |
| **CI（中信）** | 中信证券 | 另一主流分类，29个一级行业 |
| **DC（东方财富）** | 东方财富 | 互联网分类，更新快，含概念板块 |
| **TDX（通达信）** | 通达信 | 含行业/概念/地域多维度 |
| **THS（同花顺）** | 同花顺 | 含概念/行业/地域多维度 |