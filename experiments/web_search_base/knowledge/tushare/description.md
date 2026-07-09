# TuShare Pro 财经数据接口参考手册

> 版本: Pro | 安装: `pip install tushare` | GitHub: https://github.com/waditu/tushare
> 文档: https://tushare.pro/document | 主页: https://tushare.pro
> 类型: REST API + Python SDK（需 Token 鉴权）

---

## 总览

TuShare Pro 是基于 Python 的财经数据接口库，共 **160 个可访问 API 函数**（2124 分账户级别），覆盖：

- **A股行情**（17 个接口）— 日线/周线/月线/分钟/复权/涨跌停/停复牌
- **A股财务**（10 个接口）— 三大报表/财务指标/业绩预告/分红
- **基础数据**（10 个接口）— 股票列表/交易日历/公司信息/IPO
- **资金流向**（8 个接口）— 个股资金流/沪深港通/板块资金流
- **参考数据**（14 个接口）— 十大股东/股东增减持/大宗交易/股权质押/限售解禁
- **指数专题**（18 个接口）— 申万行业/指数成分/全球指数/日周月线
- **宏观经济**（19 个接口）— GDP/CPI/PPI/PMI/利率/社融/货币供应/美国利率
- **ETF/基金**（9 个接口）— ETF篮子/基金列表/净值/分红/持仓
- **期货**（12 个接口）— 日线/合约/持仓/仓单/结算参数
- **债券/可转债**（12 个接口）— 可转债行情/发行/评级/债券回购
- **港股**（5 个接口）— 日线/基础信息/交易日历/实时
- **美股**（4 个接口）— 日线/复权/交易日历/基础信息
- **期权**（2 个接口）— 合约信息/日线行情
- **两融/转融通**（7 个接口）— 融资融券汇总明细/转融通
- **外汇**（2 个接口）— 外汇基础信息/日线
- **自选组合**（4 个接口）— 组合管理

所有接口通过 `pro.api_name()` 调用，返回 `pandas.DataFrame`，需先设置 Token。

### 快速鉴权

```python
import tushare as ts
ts.set_token('your_token_here')
pro = ts.pro_api()
# 然后调用: pro.daily(ts_code='000001.SZ', start_date='20260101')
```

---

## 一、A股行情数据（股票数据_行情数据）

### daily — 历史日线
```
pro.daily(ts_code='000001.SZ', trade_date='', start_date='', end_date='', limit=5000)
```
- **返回**: 17 个字段
- **核心字段**: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
- **权限**: 2000 积分起
- **更新频率**: 每个交易日收盘后（约 15:00-17:00 更新）
- **应用**: 基础日线行情分析、技术指标计算

### weekly — 周线行情
```
pro.weekly(ts_code='000001.SZ', trade_date='', start_date='', end_date='')
```
- **返回**: 周 K 线（基于日线聚合）
- **适用**: 中期趋势分析

### monthly — 月线行情
```
pro.monthly(ts_code='000001.SZ', trade_date='', start_date='', end_date='')
```
- **返回**: 月 K 线（基于日线聚合）
- **适用**: 长期趋势分析

### pro_bar — 复权行情（通用接口）
```
pro.pro_bar(ts_code='000001.SZ', adj='qfq', start_date='', end_date='')
```
- **参数**: adj='qfq'(前复权)/'hfq'(后复权)/''(不复权)
- **适用**: 需要复权价格的场景（量化回测、趋势跟踪）
- **注意**: 此接口为通用复权行情，可替代 daily 获取复权数据

### daily_basic — 每日指标
```
pro.daily_basic(ts_code='000001.SZ', trade_date='', start_date='', end_date='')
```
- **核心字段**: turnover_rate(换手率), volume_ratio(量比), pe(市盈率), pb(市净率), total_mv(总市值), circ_mv(流通市值)
- **适用**: 基本面选股、每日市场概况
- **更新**: T+1 完成

### stk_limit — 每日涨跌停价格
```
pro.stk_limit(ts_code='000001.SZ', trade_date='', start_date='', end_date='')
```
- **核心字段**: pre_close, up_limit(涨停价), down_limit(跌停价)
- **适用**: 涨停板监测、价格区间计算

### adj_factor — 复权因子
```
pro.adj_factor(ts_code='000001.SZ', trade_date='')
```
- **适用**: 自行计算复权价格或验证 pro_bar 结果

### suspend_d — 每日停复牌信息
```
pro.suspend_d(ts_code='000001.SZ', trade_date='')
```
- **适用**: 停复牌监测

### stk_weekly_monthly — 周月线行情（每日更新）
```
pro.stk_weekly_monthly(ts_code='000001.SZ')
```
- **适用**: 获取最新周月线数据

### stk_week_month_adj — 周月线复权行情（每日更新）

### bak_daily — 备用行情
```
pro.bak_daily(ts_code='', trade_date='')
```

### rt_k — 实时日线
```
pro.rt_k(ts_code='000001.SZ')
```

### rt_min — 实时分钟
```
pro.rt_min(ts_code='000001.SZ', freq='1MIN')
```
- **freq**: 1MIN/5MIN/15MIN/30MIN/60MIN
- **适用**: 盘中实时监控

### hsgt_top10 — 沪深股通十大成交股
```
pro.hsgt_top10(ts_code='', trade_date='')
```
- **适用**: 北向资金重点交易个股追踪

### ggt_daily — 港股通每日成交统计
```
pro.ggt_daily(trade_date='')
```
- **适用**: 南下资金每日流动监测

### ggt_top10 — 港股通十大成交股
```
pro.ggt_top10(ts_code='', trade_date='')
```

---

## 二、A股财务数据（股票数据_财务数据）

### income — 利润表
```
pro.income(ts_code='000001.SZ', start_date='', end_date='', period='')
```
- **核心字段**: revenue(营业收入), total_profit(利润总额), n_income(净利润), basic_eps(基本每股收益)
- **更新**: 按季发布（一季报4月30日前，中报8月31日前，三季报10月31日前，年报次年4月30日前）

### balancesheet — 资产负债表
```
pro.balancesheet(ts_code='000001.SZ', start_date='', end_date='')
```
- **核心字段**: total_assets(总资产), total_liab(总负债), total_hldr_eqy(股东权益合计)

### cashflow — 现金流量表
```
pro.cashflow(ts_code='000001.SZ', start_date='', end_date='')
```
- **核心字段**: cashflow_op(经营活动现金流净额), cashflow_inv(投资活动现金流净额), cashflow_fin(筹资活动现金流净额)

### fina_indicator — 财务指标
```
pro.fina_indicator(ts_code='000001.SZ', start_date='', end_date='')
```
- **核心字段**: roe(ROE), roe_diluted(ROE摊薄), gross_profit_margin(毛利率), net_profit_margin(净利润率), eps(EPS)
- **适用**: 上市公司财务健康度快速评估

### forecast — 业绩预告
```
pro.forecast(ts_code='000001.SZ', start_date='', end_date='')
```
- **适用**: 业绩超预期/低于预期检测

### express — 业绩快报
```
pro.express(ts_code='000001.SZ', start_date='', end_date='')
```
- **适用**: 正式财报前的业绩概览

### dividend — 分红送股
```
pro.dividend(ts_code='000001.SZ')
```
- **适用**: 红利策略投资

### fina_audit — 财务审计意见
```
pro.fina_audit(ts_code='000001.SZ')
```
- **适用**: 财务风险排查（非标审计意见预警）

### fina_mainbz — 主营业务构成
```
pro.fina_mainbz(ts_code='000001.SZ', type='', source='', start_date='', end_date='')
```
- **type**: P(产品)/D(地区)
- **适用**: 业务结构分析、收入拆分

### disclosure_date — 财报披露日期
```
pro.disclosure_date(ts_code='000001.SZ')
```
- **适用**: 提前预知财报发布时间

---

## 三、基础数据（股票数据_基础数据）

### stock_basic — 股票列表
```
pro.stock_basic(ts_code='', name='', market='', list_status='L', is_hs='')
```
- **核心字段**: ts_code, symbol, name, area, industry, fullname, list_date
- **适用**: 获取全市场股票代码/名称映射
- **更新**: 每日盘前更新（新股上市时）

### trade_cal — 交易日历
```
pro.trade_cal(exchange='SSE', start_date='', end_date='')
```
- **核心字段**: cal_date, is_open, pretrade_date
- **适用**: 判断交易日/非交易日

### stock_company — 上市公司基本信息
```
pro.stock_company(ts_code='000001.SZ')
```
- **核心字段**: chairman, managers, reg_capital, employees, main_business

### namechange — 股票曾用名
```
pro.namechange(ts_code='000001.SZ', start_date='', end_date='')
```
- **适用**: 股票更名历史查询

### new_share — IPO新股上市
```
pro.new_share(start_date='', end_date='')
```
- **核心字段**: 发行价、发行量、中签率、冻结资金
- **适用**: 新股申购分析

### st — ST股票信息
```
pro.st(ts_code='')
```
- **适用**: ST/*ST 股票监测

### stk_managers — 上市公司管理层
```
pro.stk_managers(ts_code='000001.SZ')
```

### stk_rewards — 管理层薪酬和持股

### bak_basic — 股票历史列表
```
pro.bak_basic(trade_date='')
```
- **适用**: 获取历史某个日期的股票列表（含已退市股票）

### bse_mapping — 北交所新旧代码对照

---

## 四、资金流向（股票数据_资金流向数据）

### moneyflow — 个股资金流向
```
pro.moneyflow(ts_code='000001.SZ', trade_date='', start_date='', end_date='')
```
- **核心字段**: buy_sm_vol(小单买入), sell_sm_vol(小单卖出), buy_md_vol(中单), sell_md_vol, buy_lg_vol(大单), sell_lg_vol, buy_elg_vol(超大单), sell_elg_vol, net_mf_vol(净流入量)
- **适用**: 主力资金动向监控
- **更新**: 每个交易日盘后更新

### moneyflow_hsgt — 沪深港通资金流向
```
pro.moneyflow_hsgt(start_date='', end_date='')
```
- **核心字段**: north_net(北向净流入), south_net(南向净流入)
- **适用**: 北向资金每日流向监控

### moneyflow_dc — 个股资金流向（DC 数据源）
### moneyflow_ths — 个股资金流向（THS 数据源）
### moneyflow_ind_dc — 板块资金流向（DC）
### moneyflow_ind_ths — 行业资金流向（THS）
### moneyflow_mkt_dc — 大盘资金流向（DC）
### moneyflow_cnt_ths — 板块资金流向（THS）

---

## 五、参考数据（股票数据_参考数据）

### top10_holders — 前十大股东
```
pro.top10_holders(ts_code='000001.SZ', start_date='', end_date='')
```
- **适用**: 大股东持仓分析

### top10_floatholders — 前十大流通股东
```
pro.top10_floatholders(ts_code='000001.SZ', start_date='', end_date='')
```
- **适用**: 流通股东变动的机构动向分析

### stk_holdernumber — 股东人数
```
pro.stk_holdernumber(ts_code='000001.SZ')
```
- **适用**: 股东户数变化（筹码集中度指标）
- **更新**: 按季度更新

### stk_holdertrade — 股东增减持
```
pro.stk_holdertrade(ts_code='000001.SZ')
```
- **适用**: 高管/大股东增减持行为监控

### share_float — 限售股解禁
```
pro.share_float(ts_code='000001.SZ')
```
- **适用**: 解禁压力评估

### pledge_stat — 股权质押统计
### pledge_detail — 股权质押明细
- **适用**: 质押平仓风险监控

### block_trade — 大宗交易
```
pro.block_trade(ts_code='', trade_date='', start_date='', end_date='')
```
- **适用**: 大宗交易折溢价分析、机构买卖追踪

### repurchase — 股票回购
```
pro.repurchase(ts_code='')
```
- **适用**: 公司回购行为分析

---

## 六、指数专题

### index_daily — 指数日线行情
```
pro.index_daily(ts_code='000001.SH', trade_date='', start_date='', end_date='')
```
- **核心字段**: open, high, low, close, pre_close, change, pct_chg, vol, amount
- **适用**: 大盘指数走势分析

### index_basic — 指数基本信息
```
pro.index_basic(ts_code='000001.SH', market='', publisher='', category='')
```
- **适用**: 指数代码-名称映射

### index_classify — 申万行业分类
```
pro.index_classify(level='L1', src='SW2021')
```
- **level**: L1(一级行业 31 个), L2(二级行业 134 个), L3(三级行业)
- **src**: SW2021(2021版申万), SW2014(2014版申万)
- **适用**: 行业分类归属查询
- **特色**: 本系统龙头评分模型的核心维度，用于行业板块聚合

### index_member_all — 申万行业成分（分级）
```
pro.index_member_all(index_code='801010.SI')
```
- **适用**: 查询某行业包含的所有股票

### sw_daily — 申万日线行情
```
pro.sw_daily(ts_code='801010.SI', start_date='', end_date='')
```
- **适用**: 行业指数走势分析

### index_weight — 指数成分和权重
```
pro.index_weight(index_code='000300.SH', start_date='', end_date='')
```
- **适用**: 指数成分股及权重查询

### index_global — 国际主要指数

### index_weekly — 指数周线行情
### index_monthly — 指数月线行情

### ci_daily — 中信行业指数日行情
### daily_info — 沪深市场每日交易统计
### sz_daily_info — 深圳市场每日交易情况
### index_dailybasic — 大盘指数每日指标

---

## 七、宏观经济

### 7.1 国内宏观

#### cn_gdp — 国内生产总值（GDP）
```
pro.cn_gdp(q='', start_date='', end_date='')
```
- **更新**: 季度数据，滞后约1个月

#### cn_cpi — 居民消费价格指数（CPI）
#### cn_ppi — 工业生产者出厂价格指数（PPI）
- **更新**: 月度，约每月中旬公布上月

#### cn_pmi — 采购经理指数（PMI）
```
pro.cn_pmi(limit=200)
```
- **更新**: 月度，当月最后一天发布

#### shibor — Shibor 利率
#### shibor_lpr — LPR 贷款基础利率
#### libor — Libor 利率
#### hibor — Hibor 利率

#### cn_m — 货币供应量（月度）
#### sf_month — 社融增量（月度）
- **更新**: 约每月10-15日

### 7.2 美国利率
- **us_tycr** — 国债收益率曲线利率
- **us_trltr** — 国债长期利率平均值
- **us_trycr** — 国债实际收益率曲线利率
- **us_tbr** — 短期国债利率
- **us_tltr** — 国债长期利率

---

## 八、ETF/基金

### fund_daily — ETF日线行情
```
pro.fund_daily(ts_code='510050.SH', trade_date='', start_date='', end_date='')
```
- **适用**: ETF 净值走势分析

### fund_adj — ETF复权因子
### fund_basic — 基金列表
### fund_share — 基金规模
### fund_nav — 基金净值
### fund_portfolio — 基金持仓
### fund_div — 基金分红
### fund_manager — 基金经理
### fund_company — 基金管理人
### etf_share_size — ETF份额规模
### etf_sz_cons — 每日篮子组合(深市PCF)
### etf_sh_cons — 每日篮子组合(沪市PCF)

---

## 九、期货数据

### fut_daily — 日线行情
```
pro.fut_daily(ts_code='CU24.SHF', trade_date='', start_date='', end_date='')
```
- **适用**: 期货价格走势分析

### fut_basic — 合约信息
### fut_mapping — 期货主力与连续合约
### fut_holding — 每日持仓排名
### fut_wsr — 仓单日报
### fut_settle — 每日结算参数
### fut_trade_cal — 期货交易日历
### fut_index_daily — 南华期货指数日线行情
### fut_weekly_detail — 期货主要品种交易周报
### fut_weekly_monthly — 期货周月线行情
### ft_limit — 期货合约涨跌停价格

---

## 十、债券/可转债

### cb_daily — 可转债行情
### cb_basic — 可转债基础信息
### cb_issue — 可转债发行
### cb_share — 可转债转股结果
### cb_rating — 可转债债券评级
### repo_daily — 债券回购日行情
### bc_otcqt — 柜台流通式债券报价
### bc_bestotcqt — 柜台流通式债券最优报价
### eco_cal — 全球财经事件

---

## 十一、港股/美股/外汇/期权

### 港股
- **hk_daily** — 港股日线行情
- **hk_daily_adj** — 港股复权行情
- **hk_basic** — 港股基础信息
- **hk_tradecal** — 港股交易日历
- **rt_hk_k** — 港股实时日线

### 美股
- **us_daily** — 美股日线行情
- **us_daily_adj** — 美股复权行情
- **us_basic** — 美股基础信息
- **us_tradecal** — 美股交易日历

### 外汇
- **fx_obasic** — 外汇基础信息
- **fx_daily** — 外汇日线行情

### 期权
- **opt_basic** — 期权合约信息
- **opt_daily** — 期权日线行情

---

## 十二、两融及转融通

- **margin** — 融资融券交易汇总
- **margin_detail** — 融资融券交易明细
- **margin_secs** — 融资融券标的
- **slb_len** — 转融资交易汇总
- **slb_len_mm** — 做市借券交易汇总(停)
- **slb_sec** — 转融券交易汇总(停)
- **slb_sec_detail** — 转融券交易明细(停)

---

## 十三、特色数据/打板专题（部分可访问）

### 可访问
- **top_list** — 龙虎榜每日明细
- **top_inst** — 龙虎榜机构交易明细
- **stk_factor** — 股票技术面因子
- **hk_hold** — 沪深股通持股明细
- **broker_recommend** — 券商月度金股
- **report_rc** — 券商盈利预测数据

### 不可访问（需5000-8000分）
- ST股票列表、沪深港通股票列表（需3000分）
- THS/DC/TDX概念板块行情、东财热度、开盘啦榜单、游资名录、筹码分布等（需5000-8000分）

---

## 十四、自选组合

- **p_save** — 组合保存
- **p_list** — 组合列表
- **p_delete** — 组合删除
- **p_get** — 成分查询

---

## 十五、数据质量与时效性

### 更新节奏

| 数据类型 | 更新频率 | 更新时间 |
|---------|:--------:|---------|
| 日线行情 | 每个交易日 | 15:00-17:00 |
| 周/月线 | 每周/每月末 | 对应周期结束后 |
| 实时行情 | 盘中连续 | 近实时 |
| 复权因子 | 事件驱动 | 分红/送股后更新 |
| 涨跌停价格 | 每个交易日 | 盘前计算 |
| 财务数据 | 按季度 | 季报/中报/年报披露 |
| 业绩预告 | 不定期 | 公司发布后 |
| 资金流向 | 每个交易日 | 盘后更新（约17:00） |
| 融资融券 | 每个交易日 | 盘后更新 |
| 股东数据 | 按季度 | 季报披露后 |
| 宏观经济 | 月度/季度 | 按国家统计局日程 |
| 龙虎榜 | 每个交易日 | 17:30-18:00 |

### 响应与限流

| 指标 | 说明 |
|------|:----:|
| 2000分频次 | 约 60 次/分钟 |
| 5000分频次 | 约 200 次/分钟 |
| 8000分频次 | 约 500 次/分钟 |
| 单次最大行数 | 5000 行（部分接口 1000-4000 行） |
| 超时设置 | 建议设置 30s |
| 重试建议 | 网络异常重试 3 次, 间隔 5 分钟 |

---

## 十六、与 web_search_base 的集成现状

### 当前项目已集成至 ETL 管道
- 已在 `tushare/test/scripts/etl_incremental.py` 中使用的接口:
  - `daily` → 日线行情入库 stg_daily
  - `daily_basic` → 每日指标入库 stg_daily_basic
  - `stk_limit` → 涨跌停价格入库 stg_stk_limit
  - `sw_daily` → 申万行业日行情入库 stg_sw_daily
  - `moneyflow` → 资金流向入库 stg_moneyflow

### 特征层已集成的接口
- `fina_indicator` → 财务指标匹配
- `income` → 营收数据
- `index_classify` → 行业分类（申万 L1 + L2）

### web_search_base 可扩展候选
| 优先级 | API | 用途 | 当前状态 |
|:------:|-----|------|:--------:|
| ⭐⭐⭐ | `daily` | 日线行情 | ✅ 已入库 |
| ⭐⭐⭐ | `daily_basic` | 每日指标(pe/pb) | ✅ 已入库 |
| ⭐⭐⭐ | `fina_indicator` | 财务指标(ROE/EPS) | ✅ 已入库 |
| ⭐⭐⭐ | `income` | 利润表 | ✅ 已入库 |
| ⭐⭐ | `moneyflow` | 资金流向 | ✅ 已入库 |
| ⭐⭐ | `top10_holders` | 十大股东 | ⬜ 待集成 |
| ⭐⭐ | `stk_holdernumber` | 股东户数 | ⬜ 待集成 |
| ⭐⭐ | `stock_basic` | 股票列表 | ⬜ 待集成 |
| ⭐ | `forecast` | 业绩预告 | ⬜ 待集成 |
| ⭐ | `dividend` | 分红送股 | ⬜ 待集成 |
| ⭐ | `margin` | 融资融券 | ⬜ 待集成 |
