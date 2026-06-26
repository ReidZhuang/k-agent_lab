# pysnowball 财经数据接口参考手册

> 版本: 0.1.8 | 安装: `pip install pysnowball`
> 本质: 雪球网 (xueqiu.com) 内部 API 的非官方 Python 封装
> 特点: **需要登录 Token**，大部分接口需 Token 才能调用

---

## 总览

pysnowball 是对雪球网后端 API 的 Python 封装，共 **75 个公开 API 函数**，覆盖：

- **实时行情与估值** — 含 PE/PB/市值/股息率（雪球强项）
- **K线数据** — 含 PE/PB 历史曲线同步，北向资金/融资余额叠加
- **财务数据** — 三大报表 + 财务指标（JSON格式，免解析）
- **资金流向** — 主力/大单/中单/小单细分
- **股东数据** — 十大股东、机构持仓、分红
- **行业分析** — 行业归属、行业估值对比
- **资金面** — 融资融券、大宗交易、北向资金持股
- **基金数据** — 蛋卷基金接口（基金详情/净值/业绩）

### Token 门槛

| 权限级别 | 无需 Token | 需要 Token |
|:--------:|:----------:|:----------:|
| 接口数量 | 2 个 | 约 70+ 个 |
| 典型接口 | `quotec`, `pankou` | 其余全部 |
| 数据范围 | 基础行情+盘口 | 全部财务/资金/股东/K线 |

---

## 一、实时行情（Quotec）

### 1.1 quotec — 基础行情（无需 Token）

```python
ball.quotec('SZ300750,SH600519,SZ002594')
```

**返回字段**:

| 字段 | 类型 | 含义 |
|------|:----:|------|
| symbol | str | 股票代码 |
| current | float | 当前价 |
| percent | float | 涨跌幅% |
| chg | float | 涨跌额 |
| high/low/open | float | 最高/最低/开盘 |
| last_close | float | 昨收 |
| volume | int | 成交量 |
| amount | float | 成交额 |
| **market_capital** | float | **总市值** |
| **float_market_capital** | float | **流通市值** |
| **turnover_rate** | float | **换手率%** |
| amplitude | float | 振幅% |
| avg_price | float | 均价 |
| current_year_percent | float | 年初至今涨幅% |

### 1.2 quote_detail — 详细行情（需 Token）

```python
ball.quote_detail('SZ300750')
```

**所有基础行情字段 + 额外字段**:

| 字段 | 含义 |
|------|------|
| **pe_ttm** | 市盈率 TTM |
| **pe_lyr** | 市盈率（静态） |
| **pe_forecast** | 预测市盈率 |
| **pb** | 市净率 |
| **eps** | 每股收益 |
| **navps** | 每股净资产 |
| **dividend** | 每股股息 |
| **dividend_yield** | 股息率% |
| **volume_ratio** | 量比 |
| high52w/low52w | 52周高/低 |
| **profit_four** | 最近4个季度净利润合计 |
| **profit_forecast** | 预测净利润 |
| **pledge_ratio** | 质押比例% |
| goodwill_in_net_assets | 商誉占净资产% |
| total_shares | 总股本 |
| float_shares | 流通股本 |

---

## 二、K线数据（需 Token）

```python
ball.kline('SZ300750', period='day', count=284)
```

**参数**: 
- `period`: `'day'`(日) / `'week'`(周) / `'month'`(月)
- `count`: 返回条数

**返回字段**（每根K线含 24+ 列）:

| 字段 | 含义 |
|------|------|
| timestamp, volume, open, high, low, close | 标准K线 |
| chg, percent | 涨跌额/百分比 |
| turnoverrate, amount | 换手率/成交额 |
| **pe, pb, ps, pcf** | **估值同步曲线** |
| **market_capital** | **市值曲线** |
| **balance** | **融资余额** |
| hold_volume_cn, hold_ratio_cn, net_volume_cn | 北向资金持股 |
| hold_volume_hk, hold_ratio_hk, net_volume_hk | 港股通持股 |

---

## 三、财务数据（需 Token）

### 3.1 利润表

```python
ball.income('SZ300750', is_annals=1, count=4)
```

- `is_annals=1`: 年报 / `=0`: 全部报告期
- `count`: 返回期数

**返回字段**: 净利润、营收、营业利润（均含同比增速）

### 3.2 资产负债表

```python
ball.balance('SZ300750', is_annals=1, count=4)
```

**返回字段**: 总资产、总负债、资产负债率（均含同比变动）

### 3.3 现金流量表

```python
ball.cash_flow('SZ300750', is_annals=1, count=4)
```

**返回字段**: 经营活动/投资活动/筹资活动现金流净额（均含同比增速）

### 3.4 财务指标

```python
ball.indicator('SZ300750', is_annals=1, count=4)
```

**返回字段**:

| 字段 | 含义 |
|------|------|
| avg_roe | ROE(%) |
| basic_eps | 基本每股收益 |
| np_per_share | 每股净资产 |
| operate_cash_flow_ps | 每股经营现金流 |
| gross_selling_rate | 毛利率% |
| net_interest_of_total_assets | 总资产净利率 |
| capital_reserve | 每股资本公积金 |
| undistri_profit_ps | 每股未分配利润 |

### 3.5 主要指标一览

```python
ball.main_indicator('SZ300750')
```

一次性返回: PE_TTM、PB、总市值、流通市值、ROE、毛利率、净利率、营收/净利增速、资产负债率、总股本、EPS、股息率、质押比例

---

## 四、资金流向数据（需 Token）

### 4.1 当日资金流向

```python
ball.capital_flow('SZ300750')
```

逐分钟资金净流入数据（正=净流入，负=净流出）

### 4.2 历史资金流向

```python
ball.capital_history('SZ300750', count=20)
```

**返回**: 每日资金净流入 + `sum3/sum5/sum10/sum20`（3/5/10/20日累计净流入）

### 4.3 资金细分

```python
from pysnowball.capital import capital_assort
capital_assort('SZ300750')
```

**返回字段**:

| 字段 | 含义 |
|------|------|
| buy_large | 大单买入额 |
| sell_large | 大单卖出额 |
| buy_medium | 中单买入额 |
| sell_medium | 中单卖出额 |
| buy_small | 小单买入额 |
| sell_small | 小单卖出额 |

---

## 五、股东数据（需 Token）

### 5.1 十大股东

```python
ball.top_holders('SZ300750')
```

**返回**: 前10大股东（持股数/比例/变动）+ 新进股东 + 退出股东 + 总体持股比例

### 5.2 机构持仓变动

```python
ball.org_holding_change('SZ300750')
```

**返回**: 每期机构数、持仓比例、变动幅度、持仓均价

### 5.3 分红数据

```python
ball.bonus('SZ300750')
```

**返回**: 历年分红方案（"10派X元"）、除权日、增发记录

---

## 六、行业分析（需 Token）

### 6.1 行业归属 + 概念板块（★ 股票→概念聚类 核心接口）

```python
ball.industry('SZ300750')
```

**返回数据结构**:

```
{
    "industry": {"ind_name": "电池", "ind_code": "BK0096"},   # 所属行业
    "concept": [                                               # 所属所有概念板块
        {"ind_name": "融资融券", "ind_code": "BK0409"},
        {"ind_name": "新能源汽车", "ind_code": "BK0441"},
        {"ind_name": "深股通", "ind_code": "BK0547"},
        {"ind_name": "宁德时代概念", "ind_code": "BK0615"},
        {"ind_name": "同花顺漂亮100", "ind_code": "BK0740"},
        {"ind_name": "储能", "ind_code": "BK0747"},
        {"ind_name": "锂电池概念", "ind_code": "BK0557"},
        {"ind_name": "固态电池", "ind_code": "BK0856"},
        ...
    ]
}
```

**核心用途**: 给定一只股票，反向查出它归属的所有概念板块。
这是目前所有数据源中，唯一一个一次调用即可完成**股票→概念板块聚类**的接口。

- akshare 只有正向（概念→成分股），无反向映射
- 雪球 `industry()` 一次调用返回全部概念标签 ★
- 多个股票：分别调 `industry()` 然后交叉取交集即可聚类

**比对示例**:

```python
# 宁德时代 vs 比亚迪 — 共同概念板块
catl = ball.industry('SZ300750')  # 概念: 储能, 锂电池, 新能源汽车...
byd  = ball.industry('SZ002594')  # 概念: 新能源汽车, 比亚迪概念...
共同板块 = set(c['ind_name'] for c in catl['concept']) & \
         set(c['ind_name'] for c in byd['concept'])
```

### 6.2 行业估值对比

```python
ball.industry_compare('SZ300750')
```

**返回**: 同行业公司的 PE/PB/ROE/毛利率/营收/净利对比 + 行业均值/最大/最小

---

## 七、其他数据

| 数据 | 函数 | 说明 |
|------|------|------|
| 大宗交易 | `ball.blocktrans('SZ300750')` | 大宗交易折溢价率、买卖营业部 |
| 融资融券 | `ball.margin('SZ300750')` | 融资余额、融券余额、净买入额 |
| 北向资金 | `ball.northbound_shareholding_sh()` | 沪股通所有持股明细 |
| 股票搜索 | `ball.suggest_stock('宁德时代')` | 中文名搜索→股票代码/板块代码 |
| 自选股 | `ball.watch_list()` | 用户自选股列表 |
| 研报 | `ball.report('SZ300750')` | 最新研报 |
| 业绩预告 | `ball.earningforecast('SZ300750')` | 业绩预告 |
| 基金详情 | `ball.fund_info('000001')` | 蛋卷基金数据 |
| 基金净值 | `ball.fund_nav_history('000001')` | 基金历史净值 |
| 可转债 | `ball.convertible_bond(20, 1)` | 可转债列表 |

---

## 八、速度与可靠性

| 接口 | 响应时间 | Token需求 | 稳定性 |
|------|:--------:|:--------:|:------:|
| quotec | ~0.1s | ❌ 免Token | ⭐⭐⭐⭐⭐ |
| pankou | ~0.1s | ❌ 免Token | ⭐⭐⭐⭐⭐ |
| quote_detail | ~0.2s | ✅ | ⭐⭐⭐⭐⭐ |
| kline | ~0.3s | ✅ | ⭐⭐⭐⭐⭐ |
| income/balance/cash_flow | ~0.3s | ✅ | ⭐⭐⭐⭐ |
| capital_flow/history | ~0.3s | ✅ | ⭐⭐⭐⭐ |
| capital_assort | ~0.3s | ✅ | ⭐⭐⭐⭐ |
| top_holders | ~0.3s | ✅ | ⭐⭐⭐⭐ |
| industry/industry_compare | ~0.3s | ✅ | ⭐⭐⭐⭐ |

---

## 九、与现有数据源对比

| 数据类型 | 雪球(pysnowball) | 当前已有 | 结论 |
|---------|:---------------:|:--------:|:----:|
| 实时行情(含市值) | ✅ quotec | ✅ 腾讯财经 | **可替换**，JSON免解析 |
| PE/PB/估值 | ✅ quote_detail | ✅ 腾讯财经 | **可替换**，更稳定 |
| K线(含估值曲线) | ✅ kline | ✅ akshare | **补充**，雪球含PE/PB历史 |
| 利润表 | ✅ income(JSON) | 🔲 新浪(HTML) | **替代**，免HTML解析 |
| 资产负债表 | ✅ balance(JSON) | 🔲 新浪(HTML) | **替代**，免HTML解析 |
| 现金流量表 | ✅ cash_flow(JSON) | 🔲 新浪(HTML) | **替代**，免HTML解析 |
| 财务指标 | ✅ indicator(JSON) | ✅ akshare | **补充**，格式更友好 |
| 资金流向 | ✅ capital_assort | ✅ akshare | **补充**，细分更详细 |
| 十大股东 | ✅ top_holders | ✅ akshare | **补充**，含新进/退出 |
| 行业估值对比 | ✅ industry_compare | ❌ 无 | **独有**，非常有价值 |
| 机构持仓变动 | ✅ org_holding_change | ❌ 无 | **独有** |
| 融资融券 | ✅ margin | ❌ 无 | **独有** |
| 大宗交易 | ✅ blocktrans | ❌ 无 | **独有** |
