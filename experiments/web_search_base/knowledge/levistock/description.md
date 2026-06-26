# levistock 财经数据接口参考手册

> 版本: 最新版 | 安装: `pip install levistock`
> 多数据源一站式 SDK，整合东方财富 + 财联社 + 同花顺 + 开盘红 + 问财
> 无需 Token，无需 Cookie，直接调用

---

## 总览

levistock 共 **46 个公开 API**，覆盖六大类数据：

- **板块**（10 个）— 行业/概念板块列表、成分股、归属、轮动
- **涨停/跌停/异动**（9 个）— 涨停池、跌停池、昨日涨停、异动
- **大盘指数**（2 个）— 主要指数、全量指数
- **市场情绪/风口**（7 个）— 财联社情绪、风口板块、快讯、市场主线
- **个股数据**（5 个）— A股全量行情、K线、分时、热度排名
- **工具**（3 个）— 交易日历、新闻、策略选股

数据源标识：
- `_em` = 东方财富
- `_cls` = 财联社
- `_kph` = 开盘红
- `_ths` = 同花顺

---

## 一、板块数据

### 1.1 板块列表（sector_em）

```python
sector_em(sector_type='industry') -> list[dict]
```

**参数**: `sector_type` 可选值:

| 类型 | 数量 | 说明 |
|------|:----:|------|
| `'industry'` | ~496 | 行业板块（全部分级） |
| `'concept'` | ~494 | 概念板块 |
| `'industry_l1'` | — | 行业一级 |
| `'industry_l2'` | — | 行业二级 |
| `'industry_l3'` | — | 行业三级 |

**返回字段**（每个板块）:

| 字段 | 类型 | 含义 |
|------|:----:|------|
| sector_code | str | 板块代码（如 BK0441） |
| sector_name | str | 板块名称 |
| price | float | 板块指数 |
| change_pct | float | 涨跌幅% |
| change_amt | float | 涨跌值 |
| volume | int | 成交量 |
| amount | float | 成交额 |
| amplitude | float | 振幅% |
| turnover_rate | float | 换手率% |
| total_market | float | 总市值 |
| **main_inflow** | float | **主力资金净流入** |
| lead_stock_name | str | 领涨股名称 |
| lead_stock_code | str | 领涨股代码 |
| lead_stock_chg | float | 领涨股涨幅% |
| up_count | int | 上涨家数 |
| down_count | int | 下跌家数 |
| top_drop_name | str | 领跌股名称 |
| top_drop_code | str | 领跌股代码 |

### 1.2 板块成分股

```python
sector_stocks_em(sector_code: str) -> list[dict]
```

获取指定板块的所有成分股。

```python
sector_stocks_his_kph(date: str, zs_type: str) -> list[dict]
```

开盘红板块历史成分（需指定日期和指数类型）。

### 1.3 股票→行业归属

```python
sector_stock_belong_em(stock_codes: list) -> list[dict]
```

**示例**:
```python
lk.sector_stock_belong_em(['300750', '002594'])
# → [{'stock_code':'300750', 'stock_name':'宁德时代', 'sector_name':'电池'},
#     {'stock_code':'002594', 'stock_name':'比亚迪', 'sector_name':'乘用车'}]
```

注意：只返回**主行业**（1个），不返回概念板块标签。

### 1.4 板块排名 / 轮动 / 热度

```python
sector_ranking_kph(date: str, zs_type: str, fetch_all: bool = False) -> list[dict]
# 开盘红板块排名，按日期和指数类型

get_sector_rotation() -> list[dict]
# 板块轮动分析

get_sector_heat() -> list
# 板块热度数据
```

### 1.5 行业板块指数 / 信息

```python
SECTOR_INDUSTRY    # 行业板块常量
SECTOR_REGION      # 地区板块常量
SECTOR_SELECTED    # 精选板块常量
sector()            # 板块查询
sector_industry_cls() -> list  # 财联社行业分类
```

---

## 二、涨停/跌停/异动

### 2.1 涨停板股票池

```python
stock_zt_pool_em(date: str = None) -> list[dict]
```

日期格式 `YYYYMMDD`，不传则默认当天。

**返回字段**:

| 字段 | 含义 |
|------|------|
| date | 日期 |
| stock_code | 股票代码 |
| stock_name | 股票名称 |
| price | 当前价 |
| change_pct | 涨停涨幅% |
| amount | 成交额 |
| circ_market | 流通市值 |
| turnover_rate | 换手率% |
| **continuous** | **连板数** |
| **first_zt_time** | **首次封板时间（如 92500=9:25）** |
| **last_zt_time** | **最后封板时间** |
| **open_times** | **开板次数** |
| **sector** | **所属行业板块** |
| **main_inflow** | **主力资金净流入** |
| zt_days | 历史涨停天数 |
| zt_count | 涨停次数 |

### 2.2 跌停板股票池

```python
stock_dt_pool_em(date: str = None) -> list[dict]
```

格式同涨停池。

### 2.3 昨日涨停表现

```python
stock_yesterday_zt_em() -> list[dict]
```

昨日涨停股今天表现追踪。

### 2.4 股票异动

```python
stock_changes_em() -> list
# 股票异动列表

stock_changes_detail_em() -> list
# 异动明细
```

### 2.5 涨停历史 / 跌停历史

```python
limit_up_his_kph() -> list    # 开盘红涨停历史
limit_down_his_kph() -> list  # 开盘红跌停历史
get_zttt() -> list            # 涨停天天
get_pmsl() -> list            # 破板率
get_his_limit_resumption() -> list  # 历史涨停复盘
wind_vane_his_kph() -> list   # 开盘红风向标历史
```

---

## 三、大盘指数

### 3.1 主要指数

```python
market_index_em() -> list[dict]
```

返回：上证指数、深证成指、创业板指、科创50、沪深300、中证500

**每个指数**:

| 字段 | 含义 |
|------|------|
| name | 指数名称 |
| code | 指数代码 |
| price | 当前点位 |
| change_pct | 涨跌幅% |
| change_amt | 涨跌值 |
| volume | 成交量 |
| amount | 成交额 |
| high/low | 最高/最低 |
| open | 开盘 |
| pre_close | 昨收 |

### 3.2 全量指数

```python
market_index_all_em() -> list
```

更多指数的详细数据。

---

## 四、市场情绪与风口（财联社独有）

### 4.1 市场情绪

```python
market_emotion_cls() -> dict
```

**返回字段**:

| 字段 | 含义 |
|------|------|
| market_degree | 市场热度（0-100） |
| shsz_balance | 沪深两市成交额 |
| shsz_balance_change_px | 成交额变化 |
| up_ratio | 上涨占比% |
| up_open_ratio | 开盘涨停占比% |
| profit_ratio | 赚钱效应% |
| **limit_up_board** | **涨停梯队**（一板/二板/三板/高度板数量及晋级率） |
| **up_down_dis** | **涨跌分布**（上涨/下跌/涨停/跌停家数） |

### 4.2 开盘红情绪

```python
market_emotion_kph(date: str = None) -> dict
```

开盘红市场情绪指标。

### 4.3 风口板块

```python
get_sector_hot_plates() -> list[dict]
```

当前市场最热板块，每个板块包含：

| 字段 | 含义 |
|------|------|
| secu_code | 板块代码 |
| secu_name | 板块名称 |
| change | 板块涨跌幅 |
| **up_reason** | **上涨原因分析（自然语言描述）** |
| plate_stock_up_num | 板块内上涨股数 |
| **stock_list** | **成分股列表**（含股票名称、涨幅、**涨停标签**） |

### 4.4 快讯（电报）

```python
news_telegraph_cls(date: str = None, category: str = 'important') -> list[dict]
```

**参数**: `category` 可选 `'important'`(重要) / `'all'`(全部)

**返回**: `[{title, content, time}, ...]`

### 4.5 市场主线 / 风向

```python
market_mainline_cls() -> list        # 市场主线分析
market_wind_cls() -> list            # 市场风口
market_wind_stocks_cls() -> list     # 风口成分股
wind_vane_his_kph() -> list          # 风向标历史
```

---

## 五、个股数据

### 5.1 全量A股行情

```python
stocks_all_em(filter_st: bool = True) -> list[dict]
# 全市场A股实时行情（5000+只）
```

### 5.2 个股K线（财联社）

```python
stock_kline_cls(code: str) -> list
# 个股日K线数据（财联社源）
```

### 5.3 个股分时（财联社）

```python
stock_timeline_cls(code: str) -> list
# 当日分时走势
```

### 5.4 选股

```python
stock_strategy_wencai(query: str, page: int = 1, limit: int = 50) -> dict
# 问财策略选股
```

### 5.5 热度排名

```python
stock_hot_rank_ths(limit: int = 100) -> list[dict]
# 同花顺个股热度排名（前100）
```

---

## 六、工具函数

```python
news(category: str) -> list
# 财联社新闻

get_trade_days() -> list
# 交易日历

is_trade_day(date: str) -> bool
# 判断是否为交易日

utils
# 工具模块
```

---

## 七、函数完整清单

| # | 函数 | 数据源 | 分类 |
|:-:|------|:------:|------|
| 1 | `sector_em(type)` | 东方财富 | 板块 |
| 2 | `sector_stocks_em(code)` | 东方财富 | 板块 |
| 3 | `sector_stock_belong_em(codes)` | 东方财富 | 板块 |
| 4 | `sector_ranking_kph(date, type)` | 开盘红 | 板块 |
| 5 | `get_sector_rotation()` | — | 板块 |
| 6 | `get_sector_heat()` | — | 板块 |
| 7 | `sector()` | — | 板块 |
| 8 | `sector_industry_cls()` | 财联社 | 板块 |
| 9 | `SECTOR_INDUSTRY` | — | 板块（常量） |
| 10 | `SECTOR_REGION` | — | 板块（常量） |
| 11 | `SECTOR_SELECTED` | — | 板块（常量） |
| 12 | `stock_zt_pool_em(date)` | 东方财富 | 涨停 |
| 13 | `stock_dt_pool_em(date)` | 东方财富 | 跌停 |
| 14 | `stock_yesterday_zt_em()` | 东方财富 | 涨停 |
| 15 | `stock_changes_em()` | 东方财富 | 异动 |
| 16 | `stock_changes_detail_em()` | 东方财富 | 异动 |
| 17 | `limit_up_his_kph()` | 开盘红 | 涨停 |
| 18 | `limit_down_his_kph()` | 开盘红 | 跌停 |
| 19 | `get_zttt()` | — | 涨停 |
| 20 | `get_pmsl()` | — | 涨停 |
| 21 | `get_his_limit_resumption()` | — | 涨停 |
| 22 | `wind_vane_his_kph()` | 开盘红 | 风向标 |
| 23 | `market_index_em()` | 东方财富 | 大盘 |
| 24 | `market_index_all_em()` | 东方财富 | 大盘 |
| 25 | `market_emotion_cls()` | 财联社 | 情绪 |
| 26 | `market_emotion_kph(date)` | 开盘红 | 情绪 |
| 27 | `get_sector_hot_plates()` | 财联社 | 风口 |
| 28 | `market_mainline_cls()` | 财联社 | 主线 |
| 29 | `market_wind_cls()` | 财联社 | 风口 |
| 30 | `market_wind_stocks_cls()` | 财联社 | 风口 |
| 31 | `news_telegraph_cls(date, cat)` | 财联社 | 快讯 |
| 32 | `stocks_all_em(filter_st)` | 东方财富 | 个股 |
| 33 | `stock_kline_cls(code)` | 财联社 | 个股 |
| 34 | `stock_timeline_cls(code)` | 财联社 | 个股 |
| 35 | `stock_hot_rank_ths(limit)` | 同花顺 | 个股 |
| 36 | `stock_strategy_wencai(query)` | 问财 | 选股 |
| 37 | `news(category)` | 财联社 | 新闻 |
| 38 | `get_trade_days()` | — | 工具 |
| 39 | `is_trade_day(date)` | — | 工具 |
| 40 | `utils` | — | 工具 |
| 41-46 | `market`, `stock` (模块) | — | — |

---

## 八、速度与可靠性

| 数据源 | 响应时间 | 稳定性 |
|--------|:--------:|:------:|
| 东方财富 (`_em`) | 0.2-0.5s | ⭐⭐⭐⭐⭐ |
| 财联社 (`_cls`) | 0.3-1.0s | ⭐⭐⭐⭐ |
| 开盘红 (`_kph`) | 0.3-0.8s | ⭐⭐⭐ |
| 同花顺 (`_ths`) | 0.3-0.5s | ⭐⭐⭐⭐ |
