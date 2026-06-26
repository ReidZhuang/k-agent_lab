# pysnowball 知识图谱

> 查询入口: 根据用户问题，按"查询意图 → 数据源/接口路径"查找
> 接口调用细节见同目录下的 `instruction.md` | Token 见 `token.md`

---

## 一、实体关系图

```
股票 (code → SH/SZ + code)
    │
    ├── 行情数据
    │   ├── 实时行情（含市值/换手率）→ quotec()          [免Token]
    │   ├── 详细行情（含PE/PB/EPS/股息率）→ quote_detail() [需Token]  ★
    │   ├── 盘口数据（五档买卖）→ pankou()               [免Token]
    │   └── K线（含PE/PB历史曲线）→ kline()              [需Token]  ★
    │
    ├── 财务数据                                        [均需Token]
    │   ├── 利润表 → income()
    │   ├── 资产负债表 → balance()
    │   ├── 现金流量表 → cash_flow()
    │   ├── 财务指标（ROE/EPS/毛利率）→ indicator()
    │   └── 主要指标一览 → main_indicator()
    │
    ├── 资金流向                                        [均需Token]  ★
    │   ├── 当日逐分钟资金流向 → capital_flow()
    │   ├── 历史资金净流入（3/5/10/20日）→ capital_history()
    │   ├── 资金细分（大单/中单/小单）→ capital_assort()  ★
    │   ├── 大宗交易 → blocktrans()
    │   └── 融资融券余额 → margin()                      ★ 独有
    │
    ├── 股东数据                                        [均需Token]  ★
    │   ├── 十大股东（含新进/退出）→ top_holders()
    │   ├── 机构持仓变动 → org_holding_change()
    │   └── 分红送配 → bonus()
    │
    ├── 行业数据                                        [均需Token]
    │   ├── 行业归属 → industry() → .industry
    │   ├── 所有概念板块（★ 股票→概念聚类）→ industry() → .concept
    │   └── 行业估值对比（PE/PB/ROE行业均值）→ industry_compare()  ★ 独有
    │
    ├── 北向资金                                        [需Token]
    │   ├── 沪股通持股明细 → northbound_shareholding_sh()
    │   └── 深股通持股明细 → northbound_shareholding_sz()
    │
    └── 搜索 → suggest_stock()                          [需Token]
```

---

## 二、查询路径索引

### 2.1 行情估值类

| 问题 | 调用路径 |
|------|---------|
| "宁德时代PE/PB多少" | `quote_detail('SZ300750')` → `pe_ttm`, `pb` |
| "宁德时代市值多少" | `quotec('SZ300750')` → `market_capital` |
| "宁德时代股息率" | `quote_detail('SZ300750')` → `dividend_yield` |
| "茅台52周高低" | `quote_detail('SH600519')` → `high52w`, `low52w` |
| "宁德时代K线带PE曲线" | `kline('SZ300750', period='day')` → `pe`, `close` 列 |
| "比亚迪年初至今涨幅" | `quotec('SZ002594')` → `current_year_percent` |
| "宁德时代换手率如何" | `quotec('SZ300750')` → `turnover_rate`, `amplitude` |

### 2.2 财务数据类

| 问题 | 调用路径 |
|------|---------|
| "宁德时代2025年营收" | `income('SZ300750', is_annals=1)` → `total_revenue` |
| "宁德时代净利润增速" | `income('SZ300750', is_annals=1)` → `net_profit[1]`（同比） |
| "宁德时代ROE多少" | `indicator('SZ300750')` → `avg_roe` |
| "宁德时代毛利率" | `indicator('SZ300750')` → `gross_selling_rate` |
| "宁德时代资产负债率" | `balance('SZ300750')` → `asset_liab_ratio` |
| "宁德时代每股收益" | `indicator('SZ300750')` → `basic_eps` |
| "宁德时代每股现金流" | `indicator('SZ300750')` → `operate_cash_flow_ps` |
| "宁德时代经营现金流" | `cash_flow('SZ300750')` → `ncf_from_oa` |

### 2.3 资金流向类

| 问题 | 调用路径 |
|------|---------|
| "宁德时代今日资金流向" | `capital_flow('SZ300750')` → 逐分钟 |
| "宁德时代近5日资金" | `capital_history('SZ300750', 5)` → `sum5` |
| "宁德时代大单净买入" | `capital_assort('SZ300750')` → buy_large - sell_large |
| "宁德时代融资余额" | `margin('SZ300750')` → `margin_trading_balance` |
| "宁德时代大宗交易" | `blocktrans('SZ300750')` → 折溢价/交易量 |

### 2.4 股东类

| 问题 | 调用路径 |
|------|---------|
| "宁德时代前十大股东" | `top_holders('SZ300750')` → `items` |
| "宁德时代北向资金持股" | `top_holders('SZ300750')` → 找"香港中央结算" |
| "宁德时代机构持仓变化" | `org_holding_change('SZ300750')` |
| "宁德时代分红方案" | `bonus('SZ300750')` → `plan_explain` |

### 2.5 行业类

| 问题 | 调用路径 |
|------|---------|
| "宁德时代属于什么行业" | `industry('SZ300750')` → `.industry` |
| "宁德时代有哪些概念标签" | `industry('SZ300750')` → `.concept`（★ 股票→概念反向映射） |
| "宁德时代和比亚迪共同概念" | `industry('SZ300750')`.concept ∩ `industry('SZ002594')`.concept |
| "电池行业平均PE" | `industry_compare('SZ300750')` → `avg.pe_ttm` |
| "电池行业估值对比" | `industry_compare('SZ300750')` → `items`（各公司数据） |

### 2.6 搜索

| 问题 | 调用路径 |
|------|---------|
| "搜索宁德时代股票代码" | `suggest_stock('宁德时代')` → `data[0].code` |
| "搜索新能源概念板块代码" | `suggest_stock('新能源')` → 过滤 `type=35` |

---

## 三、数据源优先级矩阵

| 查询类型 | 雪球(pysnowball) | 当前第一选择 | 结论 |
|---------|:--------------:|:----------:|:----:|
| 股价/涨跌幅 | ✅ quotec | ✅ 腾讯财经 | 对等，选哪个都行 |
| 总市值/流通市值 | ✅ quotec | ✅ 腾讯财经 | 对等 |
| PE/PB/股息率 | ✅ **quote_detail** | ✅ 腾讯财经 | PE/PB雪球更稳定 |
| K线 | ✅ **kline(含PE/PB曲线)** | ✅ akshare | 雪球优势在于估值历史 |
| 换手率/振幅 | ✅ quotec | ❌ 各源都有 | — |
| 利润表 | ✅ **income(JSON)** | 🔲 新浪(HTML) | ✅ 雪球更好，免解析 |
| 资产负债表 | ✅ **balance(JSON)** | 🔲 新浪(HTML) | ✅ 雪球更好 |
| 现金流量表 | ✅ **cash_flow(JSON)** | 🔲 新浪(HTML) | ✅ 雪球更好 |
| 财务指标 | ✅ indicator(JSON) | ✅ akshare | 对等 |
| 资金流向细分(大单/中单/小单) | ✅ **capital_assort** | ✅ akshare | 雪球数据更细 |
| 十大股东 | ✅ **top_holders** | ✅ akshare | 雪球格式更好 |
| **行业估值对比** | ✅ **industry_compare** | ❌ 无 | ★ 独有 |
| **机构持仓变动** | ✅ **org_holding_change** | ❌ 无 | ★ 独有 |
| **大宗交易** | ✅ **blocktrans** | ❌ 无 | ★ 独有 |
| **融资融券余额** | ✅ **margin** | ❌ 无 | ★ 独有 |
| 北向资金持股 | ✅ northbound | ✅ akshare | 对等 |

---

## 四、雪球独有优势

以下数据 **只有雪球能免费提供**（其他源没有或需要付费）：

1. **行业估值对比** — 同行业公司PE/PB/ROE/毛利率对比 + 行业均值/最大/最小
2. **机构持仓变动历史** — 每期机构数、持仓比例变化、平均持仓成本
3. **大宗交易明细** — 交易量、折溢价率、买卖营业部
4. **融资融券余额** — 每日融资余额、融券余额、净买入
5. **资金流向细分（大单/中单/小单）** — akshare也有但字段格式不同，互为补充
6. **K线 + 估值历史曲线** — K线同步返回PE/PB/PS/PCF/市值历史，单次请求即可
7. **★ 股票→概念板块反向聚类** — `industry(code)` 一次调用返回个股所有概念标签。akshare只有正向（概念→成分股），批量调用industry()后交叉取交集即可完成多只股票的聚类

---

## 五、集成状态

```
web_search_base/sources/
  └── xueqiu.py     🔲 待创建
      ├── fetch_quote(code)              🔲 — quotec
      ├── fetch_quote_detail(code)       🔲 — quote_detail
      ├── fetch_kline(code)              🔲 — kline
      ├── fetch_income(code)             🔲 — income
      ├── fetch_balance(code)            🔲 — balance
      ├── fetch_cash_flow(code)          🔲 — cash_flow
      ├── fetch_indicator(code)          🔲 — indicator
      ├── fetch_capital_assort(code)     🔲 — capital_assort
      ├── fetch_top_holders(code)        🔲 — top_holders
      ├── fetch_industry_compare(code)   🔲 — industry_compare
      └── fetch_margin(code)             🔲 — margin
```
