# TuShare Pro 知识图谱

> 查询入口: 根据用户问题，按"实体 → 关系 → API"路径查找
> 所有 API 通过 `pro.函数名()` 调用，返回 pandas.DataFrame
> 格式参考: `API名称(参数: 类型) → 返回值`

---

## 一、实体关系图

### 1.1 核心金融实体链

```
公司/股票 (ts_code)
    ├── 行情数据
    │   ├── 日线 → pro.daily(ts_code='000001.SZ')
    │   ├── 周线 → pro.weekly(ts_code='000001.SZ')
    │   ├── 月线 → pro.monthly(ts_code='000001.SZ')
    │   ├── 复权 → pro.pro_bar(ts_code='000001.SZ', adj='qfq')
    │   ├── 每日指标 → pro.daily_basic(ts_code='000001.SZ', trade_date='')
    │   ├── 涨跌停 → pro.stk_limit(ts_code='000001.SZ')
    │   ├── 停复牌 → pro.suspend_d(ts_code='000001.SZ')
    │   └── 实时 → pro.rt_k(ts_code='000001.SZ') / pro.rt_min(ts_code='', freq='1MIN')
    │
    ├── 财务数据
    │   ├── 利润表 → pro.income(ts_code='000001.SZ')
    │   ├── 资产负债表 → pro.balancesheet(ts_code='000001.SZ')
    │   ├── 现金流量表 → pro.cashflow(ts_code='000001.SZ')
    │   ├── 财务指标 → pro.fina_indicator(ts_code='000001.SZ')
    │   ├── 业绩预告 → pro.forecast(ts_code='000001.SZ')
    │   ├── 业绩快报 → pro.express(ts_code='000001.SZ')
    │   ├── 分红送股 → pro.dividend(ts_code='000001.SZ')
    │   ├── 主营业务 → pro.fina_mainbz(ts_code='000001.SZ')
    │   └── 审计意见 → pro.fina_audit(ts_code='000001.SZ')
    │
    ├── 资金流向
    │   ├── 个股资金 → pro.moneyflow(ts_code='000001.SZ')
    │   ├── 大盘资金 → pro.moneyflow_mkt_dc()
    │   └── 北向资金 → pro.moneyflow_hsgt(start_date='', end_date='')
    │
    ├── 股东/持仓
    │   ├── 前十大股东 → pro.top10_holders(ts_code='000001.SZ')
    │   ├── 前十大流通股东 → pro.top10_floatholders(ts_code='000001.SZ')
    │   ├── 股东人数 → pro.stk_holdernumber(ts_code='000001.SZ')
    │   └── 股东增减持 → pro.stk_holdertrade(ts_code='000001.SZ')
    │
    ├── 融资/质押/大宗
    │   ├── 融资融券 → pro.margin(trade_date='') / pro.margin_detail(ts_code='')
    │   ├── 股权质押 → pro.pledge_stat(ts_code='') / pro.pledge_detail(ts_code='')
    │   ├── 大宗交易 → pro.block_trade(ts_code='')
    │   ├── 限售解禁 → pro.share_float(ts_code='')
    │   └── 股票回购 → pro.repurchase(ts_code='')
    │
    └── 基础信息
        ├── 股票列表 → pro.stock_basic(list_status='L')
        ├── 公司信息 → pro.stock_company(ts_code='000001.SZ')
        ├── 管理层 → pro.stk_managers(ts_code='')
        ├── 曾用名 → pro.namechange(ts_code='')
        └── IPO新股 → pro.new_share(start_date='', end_date='')
```

### 1.2 行业板块 → 成分股关系

```
申万行业分类 (index_classify)
    ├── L1 一级行业（31个）→ pro.index_classify(level='L1')
    ├── L2 二级行业（134个）→ pro.index_classify(level='L2')
    ├── L3 三级行业 → pro.index_classify(level='L3')
    │
    └── 行业成分股 → pro.index_member_all(index_code='801010.SI')
        └── 行业日行情 → pro.sw_daily(ts_code='801010.SI')
```

### 1.3 指数关系

```
指数 (ts_code e.g. 000300.SH)
    ├── 日线行情 → pro.index_daily(ts_code='000300.SH')
    ├── 周线行情 → pro.index_weekly(ts_code='000300.SH')
    ├── 月线行情 → pro.index_monthly(ts_code='000300.SH')
    ├── 基本信息 → pro.index_basic(ts_code='000300.SH')
    ├── 成分股权重 → pro.index_weight(index_code='000300.SH')
    ├── 每日指标 → pro.index_dailybasic(trade_date='')
    ├── 国际指数 → pro.index_global()
    └── 实时 → pro.rt_idx_k(ts_code='000001.SH')
```

### 1.4 宏观经济 → 市场联动

```
中国宏观 → A股联动:
    ├── GDP增速 → pro.cn_gdp()
    ├── PMI → pro.cn_pmi()               → 制造业景气
    ├── CPI → pro.cn_cpi()               → 消费/通胀
    ├── PPI → pro.cn_ppi()               → 上游利润
    ├── M2 → pro.cn_m()                  → 流动性
    ├── 社融 → pro.sf_month()            → 信用扩张
    ├── LPR → pro.shibor_lpr()           → 利率/估值
    └── Shibor → pro.shibor()            → 银行间流动性

全球 → A股联动:
    ├── 美债收益率 → pro.us_tycr()      → 成长股估值
    └── Libor → pro.libor()              → 全球资金成本
```

### 1.5 多市场覆盖

```
A股 (000001.SZ, 600519.SH)
    ├── 行情: daily / weekly / monthly / pro_bar
    ├── 财务: income / balancesheet / cashflow
    └── 资金: moneyflow

港股 (00700.HK)
    ├── 行情: hk_daily / hk_daily_adj
    ├── 基础: hk_basic
    └── 交易日历: hk_tradecal

美股 (AAPL)
    ├── 行情: us_daily / us_daily_adj
    ├── 基础: us_basic
    └── 交易日历: us_tradecal

期货 (CU24.SHF)
    ├── 行情: fut_daily
    ├── 合约: fut_basic / fut_mapping
    ├── 持仓: fut_holding
    └── 仓单: fut_wsr

可转债 (123456.SZ)
    ├── 行情: cb_daily
    ├── 基础: cb_basic
    ├── 发行: cb_issue
    └── 转股: cb_share

ETF (510050.SH)
    ├── 行情: fund_daily / fund_adj
    ├── 规模: fund_share / etf_share_size
    ├── 持仓: fund_portfolio
    └── 篮子组合: etf_sz_cons / etf_sh_cons
```

---

## 二、查询路径索引

按自然语言问题类型，映射对应的 TuShare API。

### 2.1 公司财务类

```
"宁德时代最新营收利润" → pro.income(ts_code='300750.SZ')
"宁德时代2025年毛利率" → pro.fina_indicator(ts_code='300750.SZ') → gross_profit_margin
"宁德时代ROE" → pro.fina_indicator(ts_code='300750.SZ') → roe
"宁德时代资产负债表" → pro.balancesheet(ts_code='300750.SZ')
"宁德时代现金流" → pro.cashflow(ts_code='300750.SZ')
"宁德时代业绩预告" → pro.forecast(ts_code='300750.SZ')
"宁德时代主营业务构成" → pro.fina_mainbz(ts_code='300750.SZ')
"宁德时代审计意见" → pro.fina_audit(ts_code='300750.SZ')
"贵州茅台分红记录" → pro.dividend(ts_code='600519.SH')
"宁德时代财报什么时候出" → pro.disclosure_date(ts_code='300750.SZ')
```

### 2.2 行情类

```
"贵州茅台今日股价" → pro.daily(ts_code='600519.SH') → 最新日期
"贵州茅台K线" → pro.daily(ts_code='600519.SH', start_date='20260101')
"贵州茅台月K线" → pro.monthly(ts_code='600519.SH')
"贵州茅台复权价格" → pro.pro_bar(ts_code='600519.SH', adj='qfq')
"全市场今日行情" → pro.daily(trade_date='20260709') → 需循环或指定日期
"贵州茅台涨跌停价" → pro.stk_limit(ts_code='600519.SH')
"贵州茅台换手率" → pro.daily_basic(ts_code='600519.SH')
"贵州茅台PE/PB" → pro.daily_basic(ts_code='600519.SH') → pe/pb列
"今日停复牌股票" → pro.suspend_d(trade_date='20260709')
"贵州茅台实时行情" → pro.rt_k(ts_code='600519.SH')
```

### 2.3 资金流向类

```
"宁德时代主力资金" → pro.moneyflow(ts_code='300750.SZ')
"今天北向资金流入" → pro.moneyflow_hsgt()
"行业资金流向排名" → pro.moneyflow_ind_ths()
"概念板块资金流向" → pro.moneyflow_cnt_ths()
"大盘资金流向" → pro.moneyflow_mkt_dc()
"沪深港通十大成交" → pro.hsgt_top10(trade_date='')
"港股通成交统计" → pro.ggt_daily(trade_date='')
"港股通十大成交" → pro.ggt_top10(trade_date='')
```

### 2.4 宏观/政策类

```
"中国最新GDP" → pro.cn_gdp()
"中国CPI数据" → pro.cn_cpi()
"中国PPI" → pro.cn_ppi()
"中国PMI" → pro.cn_pmi()
"最新LPR利率" → pro.shibor_lpr()
"M2货币供应" → pro.cn_m()
"社会融资规模" → pro.sf_month()
"Shibor利率" → pro.shibor()
"美债收益率" → pro.us_tycr()
"美国国债利率" → pro.us_tltr()
```

### 2.5 股东/机构类

```
"贵州茅台前十大股东" → pro.top10_holders(ts_code='600519.SH')
"贵州茅台前十大流通股东" → pro.top10_floatholders(ts_code='600519.SH')
"贵州茅台股东人数变化" → pro.stk_holdernumber(ts_code='600519.SH')
"贵州茅台股东增减持" → pro.stk_holdertrade(ts_code='600519.SH')
"贵州茅台管理层信息" → pro.stk_managers(ts_code='600519.SH')
"贵州茅台管理层薪酬" → pro.stk_rewards(ts_code='600519.SH')
```

### 2.6 融资/质押/大宗

```
"全市场融资融券余额" → pro.margin(trade_date='20260708')
"贵州茅台融资融券明细" → pro.margin_detail(ts_code='600519.SH')
"融资融券标的名单" → pro.margin_secs()
"贵州茅台股权质押" → pro.pledge_stat(ts_code='600519.SH')
"贵州茅台大宗交易" → pro.block_trade(ts_code='600519.SH')
"限售股解禁" → pro.share_float(ts_code='600519.SH')
"贵州茅台股票回购" → pro.repurchase(ts_code='600519.SH')
```

### 2.7 行业/板块类

```
"申万一级行业有哪些" → pro.index_classify(level='L1')
"申万二级行业有哪些" → pro.index_classify(level='L2')
"银行板块成分股" → pro.index_member_all(index_code='801780.SI')
"银行板块行情" → pro.sw_daily(ts_code='801780.SI')
"今日申万行业表现" → pro.sw_daily(trade_date='')
"贵州茅台行业归属" → pro.stock_basic(ts_code='600519.SH') → industry列
```

### 2.8 指数类

```
"上证指数走势" → pro.index_daily(ts_code='000001.SH')
"沪深300成分股权重" → pro.index_weight(index_code='000300.SH')
"沪深300行情" → pro.index_daily(ts_code='000300.SH')
"美股指数行情" → pro.index_global()
"指数基本信息" → pro.index_basic(ts_code='000300.SH')
```

### 2.9 期货/商品类

```
"沪铜期货行情" → pro.fut_daily(ts_code='CU24.SHF')
"沪铜主力合约" → pro.fut_mapping(ts_code='CU24.SHF')
"螺纹钢持仓排名" → pro.fut_holding(ts_code='RB24.SHF')
"天然橡胶仓单" → pro.fut_wsr(ts_code='RU24.SHF')
"期货结算参数" → pro.fut_settle(ts_code='CU24.SHF')
"南华商品指数" → pro.fut_index_daily(ts_code='NH0100.NHF')
"黄金现货行情" → pro.sge_daily(ts_code='AU99.99')
```

### 2.10 基金/ETF类

```
"科创50ETF净值" → pro.fund_daily(ts_code='588000.SH')
"ETF列表" → pro.fund_basic(ts_code='', market='E')
"ETF规模变化" → pro.etf_share_size(ts_code='510050.SH')
"ETF持仓" → pro.fund_portfolio(ts_code='510050.SH')
"基金分红" → pro.fund_div(ts_code='510050.SH')
"基金经理" → pro.fund_manager(ts_code='510050.SH')
"基金公司列表" → pro.fund_company()
"ETF篮子成分（沪）" → pro.etf_sh_cons(ts_code='510050.SH')
"ETF篮子成分（深）" → pro.etf_sz_cons(ts_code='159915.SZ')
```

### 2.11 可转债/债券类

```
"可转债行情" → pro.cb_daily(ts_code='123456.SZ')
"可转债基础信息" → pro.cb_basic(ts_code='123456.SZ')
"可转债发行" → pro.cb_issue(ts_code='123456.SZ')
"可转债评级" → pro.cb_rating(ts_code='123456.SZ')
"可转债转股结果" → pro.cb_share(ts_code='123456.SZ')
"债券回购行情" → pro.repo_daily(ts_code='204001.SH')
"债券报价" → pro.bc_otcqt()
```

### 2.12 港股/美股/外汇

```
"腾讯控股行情" → pro.hk_daily(ts_code='00700.HK')
"腾讯控股复权" → pro.hk_daily_adj(ts_code='00700.HK')
"腾讯控股基础信息" → pro.hk_basic(ts_code='00700.HK')
"港股交易日历" → pro.hk_tradecal(start_date='', end_date='')
"苹果行情" → pro.us_daily(ts_code='AAPL')
"美元人民币汇率" → pro.fx_daily(ts_code='USDCNY')
```

### 2.13 龙虎榜/打板

```
"今日龙虎榜" → pro.top_list(trade_date='20260708')
"龙虎榜机构交易" → pro.top_inst(trade_date='20260708')
```

### 2.14 股票列表/基础数据

```
"A股全部股票列表" → pro.stock_basic(list_status='L')
"上市公司信息" → pro.stock_company(ts_code='000001.SZ')
"交易日历" → pro.trade_cal(exchange='SSE', start_date='', end_date='')
"IPO新股" → pro.new_share(start_date='', end_date='')
"ST股票列表" → pro.st(ts_code='')
"股票曾用名" → pro.namechange(ts_code='600519.SH')
```

### 2.15 特色数据（有限）

```
"沪深股通持股明细" → pro.hk_hold(ts_code='600519.SH')
"股票技术面因子" → pro.stk_factor(ts_code='000001.SZ')
"券商月度金股" → pro.broker_recommend(month='202506')
"券商盈利预测" → pro.report_rc(ts_code='000001.SZ')
```

---

## 三、数据源优先级矩阵

按查询类型选择最优 API:

| 查询类型 | 第一选择 | 第二选择 | 说明 |
|---------|---------|---------|------|
| 日线行情 | pro.daily | pro.pro_bar | bar 可同时获取复权 |
| 周月线 | pro.weekly / pro.monthly | pro.stk_weekly_monthly | 后者每日更新 |
| 每日指标(PE/PB) | pro.daily_basic | — | — |
| 复权价格 | pro.pro_bar(adj='qfq') | pro.adj_factor | 自行计算复权 |
| 涨跌停价 | pro.stk_limit | — | — |
| 财务指标(ROE/EPS) | pro.fina_indicator | — | 核心指标首选 |
| 三大报表 | pro.income/balancesheet/cashflow | — | 全科目级 |
| 业绩预告 | pro.forecast | pro.express | 预告优先更新 |
| 个股资金流向 | pro.moneyflow | pro.moneyflow_dc/ths | 多数据源对比 |
| 北向资金 | pro.moneyflow_hsgt | pro.hsgt_top10 | — |
| 申万行业分类 | pro.index_classify | — | L1/L2/L3 |
| 行业行情 | pro.sw_daily | pro.ci_daily | 申万/中信 |
| 指数行情 | pro.index_daily | pro.index_weekly/monthly | — |
| 指数成分 | pro.index_member_all | pro.index_weight | 先分类后查成分 |
| 宏观经济 | pro.cn_gdp/cpi/ppi/pmi | — | 各接口独立 |
| Shibor/LPR | pro.shibor / pro.shibor_lpr | — | — |
| 股东数据 | pro.top10_holders | pro.stk_holdernumber | — |
| 融资融券 | pro.margin | pro.margin_detail | — |
| 大宗交易 | pro.block_trade | — | — |
| 龙虎榜 | pro.top_list | pro.top_inst | — |
| 期货行情 | pro.fut_daily | pro.fut_mapping | — |
| ETF行情 | pro.fund_daily | pro.fund_adj | — |
| 港股行情 | pro.hk_daily | pro.hk_daily_adj | — |
| 美股行情 | pro.us_daily | pro.us_daily_adj | — |

---

## 四、数据类型转换图

```
用户查询 → {关键词分类} → 对应的 TuShare API:

营收/净利/毛利率/ROE          → pro.fina_indicator / pro.income
股价/行情/K线/涨跌            → pro.daily / pro.pro_bar
复权价格                      → pro.pro_bar(adj='qfq')
PE/PB/换手率/市值             → pro.daily_basic
涨跌停                        → pro.stk_limit
资金流向/主力/大单            → pro.moneyflow
北向资金/沪深港通             → pro.moneyflow_hsgt / pro.hsgt_top10
GDP/CPI/PMI/通胀              → pro.cn_gdp / pro.cn_cpi / pro.cn_pmi
LPR/Shibor/利率               → pro.shibor_lpr / pro.shibor
股东/持股/实控人              → pro.top10_holders / pro.stk_holdernumber
融资融券/质押/大宗            → pro.margin / pro.pledge_stat / pro.block_trade
申万行业分类                  → pro.index_classify
行业成分股/行业行情           → pro.index_member_all / pro.sw_daily
指数的                        → pro.index_daily / pro.index_weight
港股                          → pro.hk_daily
美股                          → pro.us_daily
期货/大宗/商品                → pro.fut_daily / pro.fut_mapping
可转债/债券                   → pro.cb_daily / pro.cb_basic
基金/ETF                      → pro.fund_daily
外汇/汇率                     → pro.fx_daily
龙虎榜                        → pro.top_list / pro.top_inst
财报披露日期                  → pro.disclosure_date
主营业务构成                  → pro.fina_mainbz
限售解禁                      → pro.share_float
股票回购                      → pro.repurchase
交易日历                      → pro.trade_cal
股票列表/代码映射             → pro.stock_basic
```

---

## 五、web_search_base 扩展指南

### 5.1 当前项目已集成

```python
# 已在 etl_incremental.py 中使用
pro.daily()        → stg_daily
pro.daily_basic()  → stg_daily_basic
pro.stk_limit()    → stg_stk_limit
pro.sw_daily()     → stg_sw_daily
pro.moneyflow()    → stg_moneyflow

# 已在 etl_feature.py 中使用
pro.fina_indicator()  → 财务指标匹配
pro.income()          → 营收数据
pro.index_classify()  → 申万行业分类（L1+L2）
```

### 5.2 建议优先扩展

| 优先级 | API | 用途 | 复杂度 |
|:------:|-----|------|:------:|
| ⭐⭐⭐ | top10_holders | 前十大股东追踪 | 低 |
| ⭐⭐⭐ | stk_holdernumber | 股东户数（筹码集中度） | 低 |
| ⭐⭐ | forecast | 业绩预告 | 低 |
| ⭐⭐ | dividend | 分红记录 | 低 |
| ⭐⭐ | margin | 融资融券余额 | 低 |
| ⭐ | block_trade | 大宗交易折溢价 | 中 |
| ⭐ | share_float | 限售解禁 | 低 |
| ⭐ | stk_holdertrade | 股东增减持 | 低 |

### 5.3 代码调用模式

```python
import tushare as ts
ts.set_token('your_token_here')
pro = ts.pro_api()

def fetch_financial(symbol: str) -> str:
    """财务指标查询"""
    df = pro.fina_indicator(ts_code=symbol)
    # DataFrame 处理 → 格式化文本
    return df.to_string()
```

---

## 六、注意事项

1. **代码格式**: A 股统一用 `000001.SZ` / `600519.SH`；港股用 `00700.HK`；美股用 `AAPL`
2. **积分限制**: 本手册基于 2124 分账户，共 160 个可用接口；打板/特色数据需 5000-8000 分
3. **频率限制**: 2000 分约 60 次/分钟，建议调用间隔 ≥ 0.5s
4. **数据延迟**: 日线行情收盘后约 2 小时完成更新
5. **Token**: 需在 `ts.set_token()` 中设置，可从 TuShare Pro 官网获取
6. **分页**: 各接口有 limit 限制（5000 行），大数据量需按日期循环
