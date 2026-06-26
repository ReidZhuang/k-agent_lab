# akshare 财经数据接口参考手册

> 版本: 1.18.64 | 安装: `pip install akshare` | GitHub: https://github.com/akfamily/akshare
> 文档: https://akshare-hh.readthedocs.io | 主页: https://akshare.akfamily.xyz

---

## 总览

akshare 是基于 Python 的开源财经数据接口库，共 **1133 个公开 API 函数**，覆盖：

- **A股**（406 个接口）— 最核心模块
- **巨潮资讯**（30 个接口）— 官方披露/公司治理/股东/公告/互动易 ★
- **宏观经济**（226 个接口）— 中国宏观 + 全球八大经济体
- **指数**（80 个接口）— A股指数 + 全球指数
- **基金**（75 个接口）— ETF、开放式基金、货币基金
- **期货**（68 个接口）— 国内期货 + 外盘 + 期现价差
- **债券/可转债**（45 个接口）— 含中美利率对比 + 巨潮债券发行
- **期权**（47 个接口）— ETF期权 + 商品期权 + 波动率
- **外汇/汇率**（18 个接口）— 即期、历史、互换
- **能源/碳排放**（9 个接口）— 碳市场 + 原油
- **现货**（17 个接口）— SGE 黄金、白银、生猪
- **REITs**（4 个接口）
- **美股/港股** — 行情、财务、估值全系列

所有接口返回 `pandas.DataFrame`，统一格式。数据源由各函数后缀标识：
- `_em` = 东方财富
- `_sina` = 新浪财经
- `_ths` = 同花顺
- `_xq` = 雪球
- `_jsl` = 集思录
- `_baidu` = 百度
- `_cninfo` = 巨潮资讯

---

## 一、A股数据（stock_*）

### 1.1 个股财务数据

#### stock_financial_abstract（核心）
```
stock_financial_abstract(symbol: str = '600004') -> pd.DataFrame
```
- **来源**: 新浪财经-财务报表-关键指标
- **输出**: 80 个指标 × 42 个报告期（最近 10 年）
- **指标分类**:
  - 常用指标（17项）: 归母净利润、营业总收入、营业成本、净利润、扣非净利润、经营活动现金流净额、每股收益、每股净资产、ROE(加权)、总资产、净资产、毛利率、净利率、资产负债率、流动比率、速动比率等
  - 每股指标（15项）: EPS、BPS、每股公积金、每股未分配利润、每股经营现金流
  - 盈利能力（15项）: ROE(摊薄/平均/扣非)、ROA、净利率、毛利率
  - 成长能力（4项）: 营收增长率、净利增长率
  - 收益质量（7项）: 经营现金流/营业收入、期间费用率
  - 财务风险（6项）: 流动比率、速动比率、资产负债率
  - 营运能力（9项）: 存货周转率、总资产周转率
- **适用场景**: 多期财务趋势分析、快速财务体检
- **速度**: ~0.3s

#### stock_financial_analysis_indicator_em（深度财务分析）
```
stock_financial_analysis_indicator_em(symbol: str = '301389.SZ', indicator: str = '按报告期') -> pd.DataFrame
```
- **来源**: 东方财富
- **输出**: 40 期 × ~140 项深度财务指标
- **核心指标**: EPS(基本/稀释/扣非)、BPS、每股公积金、ROE(加权/扣非)、ROIC、毛利率、净利率、营业利润率、资产负债率、流动比率、速动比率、现金比率、利息保障倍数、经营现金流/营业收入、存货周转率、总资产周转率、应收账款周转率、营业周期
- **特色**: 含同比/环比增速（TOI_YOY、DPNP_YOY等）、杜邦分析相关指标
- **速度**: ~0.3s

#### 三大财务报表
```python
stock_profit_sheet_by_report_em(symbol='SZ300750')        # 利润表（按报告期, 203列）
stock_balance_sheet_by_report_em(symbol='SZ300750')        # 资产负债表（按报告期）
stock_cash_flow_sheet_by_report_em(symbol='SZ300750')      # 现金流量表（按报告期）
```
- 按季/半年/年报输出，全部 Excel 级科目
- 另有 `_by_yearly_em` 版本（按年）

#### 杜邦与成长能力对比
```python
stock_zh_dupont_comparison_em(symbol='SZ300750')           # 杜邦分析树（含历史对比）
stock_zh_growth_comparison_em(symbol='SZ300750')           # 成长能力对比（营收增速、利润增速）
stock_zh_scale_comparison_em(symbol='SZ300750')            # 规模对比（资产、营收规模）
stock_zh_valuation_comparison_em(symbol='SZ300750')        # 估值对比（PE/PB/PS 分位）
```

#### 财务分析指标（新浪版）
```python
stock_financial_analysis_indicator(symbol='600004', start_year='1900') -> pd.DataFrame
```
- 新浪财经版，参数简单的长跨度历史财务指标

#### 沪深港通财务
```python
stock_hk_financial_indicator_em(symbol='03900')            # 港股财务指标
stock_financial_us_report_em(stock='TSLA', symbol='资产负债表', indicator='年报')  # 美股财务报表
```

### 1.2 个股行情与K线

```python
stock_zh_a_hist(symbol='000001', period='daily', start_date='19700101', end_date='20500101', adjust='') -> pd.DataFrame
```
- **period**: daily/weekly/monthly
- **adjust**: ''(不复权)/'qfq'(前复权)/'hfq'(后复权)
- 返回: 日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、换手率

```python
stock_zh_a_hist_min_em(symbol='300750', period='5', start_date='2025-01-01', end_date='2025-12-31')  # 分钟K线
stock_zh_a_hist_tx(symbol='300750', start_date='2025-01-01', end_date='2025-12-31')                 # 腾讯日K
```

#### 实时行情
```python
stock_zh_a_spot_em()    # 全市场A股实时行情（所有股票）
stock_sh_a_spot_em()    # 沪A
stock_sz_a_spot_em()    # 深A
stock_bj_a_spot_em()    # 北交所
stock_kc_a_spot_em()    # 科创板
stock_cy_a_spot_em()    # 创业板
```

### 1.3 个股基本面信息

```python
stock_individual_info_em(symbol='300750')                   # 基本信息（行业/注册地/员工数/发行价/上市日期等）
stock_profile_cninfo(symbol='600030')                       # 公司概况（巨潮资讯，含公司简介）
stock_fhps_em(date='20231231')                              # 分红送配
stock_yjbb_em(date='20200331')                              # 业绩报表
stock_yjkb_em(date='20211231')                              # 业绩快报
stock_yjyg_em()                                              # 业绩预告（最新）
stock_zh_a_gdhs()                                            # 股东户数变化
stock_zh_a_gbjg_em()                                         # 个股公告
```

#### 股东与高管
```python
stock_gdfx_top_10_em(symbol='300750')                        # 前10大股东
stock_hold_control_cninfo(symbol='300750')                   # 实际控制人
stock_hold_management_detail_em(symbol='300750')              # 高管信息
stock_shareholder_change_ths(symbol='300750.SZ')             # 股东变动
stock_gpzy_profile_em(symbol='300750')                       # 股权质押概况
```

### 1.4 资金流向

```python
stock_individual_fund_flow(stock='300750', market='sz')      # 个股资金流向（主力/超大单/大单/中单/小单）
stock_main_fund_flow(symbol='全部股票')                       # 全市场主力资金流向
stock_market_fund_flow()                                      # 市场资金流向全景
stock_sector_fund_flow_hist(symbol='汽车服务')                # 板块资金流向历史
stock_sector_fund_flow_rank()                                 # 板块资金流向排名
stock_fund_flow_individual(symbol='即时')                     # 个股资金流排名（即时/近3日/近5日/近10日）
stock_fund_flow_industry(symbol='即时')                       # 行业资金流排名
stock_fund_flow_concept(symbol='即时')                        # 概念资金流排名
```

### 1.5 沪深港通（北向/南向）

```python
stock_hsgt_hist_em(symbol='北向资金')                         # 北向资金历史（南向同理）
stock_hsgt_fund_flow_summary_em()                             # 沪深港通资金流向汇总
stock_hsgt_hold_stock_em(market='沪股通', indicator='沪股通持股')  # 北向资金持股明细
stock_hsgt_individual_em(stock='300750')                      # 沪深港通个股资金流向
stock_hsgt_board_rank_em()                                    # 沪深港通板块排行
```

### 1.6 龙虎榜与大宗交易

```python
stock_lhb_detail_em()                                         # 龙虎榜详情
stock_lhb_jgstatistic_em()                                    # 龙虎榜机构统计
stock_lhb_yybph_em()                                          # 营业部排行
stock_lhb_stock_statistic_em()                                # 个股上榜统计
stock_dzjy_mrtj()                                             # 大宗交易每日统计
stock_dzjy_yybph()                                            # 大宗交易营业部排行
```

### 1.7 机构持仓/评级

```python
stock_institute_hold(symbol='300750')                         # 机构持仓汇总
stock_institute_hold_detail(year='2025', quarter='4')         # 机构持仓明细（年度/季度）
stock_institute_recommend(symbol='投资评级选股')               # 机构评级
stock_institute_recommend_detail(symbol='300750')              # 个股机构评级明细
stock_research_report_em(symbol='300750')                     # 个股研报
```

### 1.8 打新/IPO

```python
stock_ipo_info(symbol='300750')                               # IPO基本信息
stock_ipo_declare_em()                                        # 新股申购
stock_ipo_review_em()                                         # 新股上会
stock_new_ipo_cninfo()                                        # 新股（巨潮）
stock_new_a_spot_em()                                         # 次新股
```

### 1.9 科创/ST/停复牌

```python
stock_zh_kcb_spot()                                           # 科创板行情
stock_zh_kcb_daily()                                          # 科创板日K
stock_zh_kcb_report_em(symbol='300750')                       # 科创板报告
stock_zh_a_st_em()                                            # ST股票列表
stock_zh_a_stop_em()                                          # 停复牌
```

### 1.10 涨跌停/异动

```python
stock_zt_pool_em(date='20241008')                             # 涨停股池
stock_zt_pool_strong_em(date='20241008')                      # 强势股池
stock_zt_pool_dtgc_em(date='20241008')                        # 跌停股池
stock_zt_pool_sub_new_em(date='20241008')                     # 次新股池
stock_zt_pool_previous_em(date='20241008')                    # 昨日涨停
stock_hot_rank_em()                                           # 热搜股票
stock_hot_rank_detail_em()                                    # 热搜股票详情
stock_hot_keyword_em()                                        # 热搜关键词
```

### 1.11 行业/概念板块

**东方财富数据源（`_em`）**:

```python
stock_board_industry_spot_em(symbol='小金属')                  # 行业板块实时行情
stock_board_industry_cons_em(symbol='小金属')                  # 行业板块成分股
stock_board_industry_hist_em(symbol='小金属')                  # 行业板块日K线
stock_board_industry_hist_min_em(symbol='小金属')              # 行业板块分钟K线
stock_board_industry_name_em()                                 # 行业板块名称列表
stock_board_concept_spot_em(symbol='可燃冰')                   # 概念板块实时行情
stock_board_concept_cons_em(symbol='可燃冰')                   # 概念板块成分股
stock_board_concept_hist_em(symbol='可燃冰')                   # 概念板块日K线
stock_board_concept_hist_min_em(symbol='可燃冰')               # 概念板块分钟K线
stock_board_concept_name_em()                                  # 概念板块名称列表
stock_board_change_em()                                        # 板块涨跌排行
```

**同花顺数据源（`_ths`）**:

```python
stock_board_industry_summary_ths()                             # 行业板块行情汇总（含涨跌幅/资金流）
stock_board_industry_index_ths(symbol='小金属')                # 行业板块指数
stock_board_industry_info_ths(symbol='小金属')                 # 行业板块基本信息
stock_board_industry_name_ths()                                # 行业板块名称列表
stock_board_concept_summary_ths()                              # 概念板块行情汇总
stock_board_concept_index_ths(symbol='可燃冰')                 # 概念板块指数
stock_board_concept_info_ths(symbol='可燃冰')                  # 概念板块基本信息
stock_board_concept_name_ths()                                 # 概念板块名称列表
```

**板块资金流向**:

```python
stock_sector_fund_flow_hist(symbol='汽车服务')                 # 板块资金流向历史
stock_sector_fund_flow_rank()                                  # 板块资金流向排名
stock_fund_flow_industry(symbol='即时')                        # 行业资金流排名
stock_fund_flow_concept(symbol='即时')                         # 概念资金流排名
stock_hsgt_board_rank_em()                                     # 沪深港通板块排行
```

### 1.12 证券代码/名称转换

```python
stock_info_a_code_name()                                      # A股全部代码名称映射表
stock_info_sh_name_code()                                     # 沪市
stock_info_sz_name_code()                                     # 深市
stock_info_bj_name_code()                                     # 北交所
stock_individual_info_em(symbol='300750')                     # 含行业归属
stock_a_code_to_symbol(symbol='300750')                       # 代码转交易所格式
```

---

## 二、宏观经济（macro_*）

总计 **226 个函数**，产品最丰富的模块之一。

### 2.1 中国宏观（85个函数）

| 类别 | 函数 | 内容 |
|------|------|------|
| GDP | `macro_china_gdp`, `macro_china_gdp_yearly` | GDP总量、同比增速 |
| CPI | `macro_china_cpi`, `macro_china_cpi_monthly`, `macro_china_cpi_yearly` | 消费者物价指数 |
| PPI | `macro_china_ppi`, `macro_china_ppi_yearly` | 生产者物价指数 |
| PMI | `macro_china_pmi`, `macro_china_non_man_pmi`, `macro_china_cx_pmi_yearly`, `macro_china_cx_services_pmi_yearly` | 制造业/非制造业/财新PMI |
| 货币供给 | `macro_china_money_supply`, `macro_china_m2_yearly`, `macro_china_supply_of_money` | M2/M1/M0 |
| 利率 | `macro_china_shibor_all`, `macro_china_lpr`, `macro_china_swap_rate`, `macro_china_reserve_requirement_ratio` | SHIBOR/LPR/准备金率 |
| 外汇/黄金 | `macro_china_foreign_exchange_gold`, `macro_china_fx_gold`, `macro_china_rmb`, `macro_china_fx_reserves_yearly` | 外储/黄金/人民币汇率 |
| 外贸 | `macro_china_exports_yoy`, `macro_china_imports_yoy`, `macro_china_trade_balance` | 进出口同比/贸易差额 |
| 工业 | `macro_china_industrial_production_yoy`, `macro_china_energy_index`, `macro_china_daily_energy` | 工业增加值/能源 |
| 房地产 | `macro_china_real_estate`, `macro_china_new_house_price` | 房地产投资/新房价格 |
| 消费 | `macro_china_consumer_goods_retail`, `macro_china_retail_price_index` | 社零/零售价格 |
| 金融 | `macro_china_stock_market_cap`, `macro_china_central_bank_balance`, `macro_china_new_financial_credit`, `macro_china_bank_financing` | 股市市值/央行资产负债表/社融 |
| 贷款 | `macro_china_market_margin_sh`, `macro_china_market_margin_sz`, `macro_china_shrzgm` | 融资融券余额/社会融资规模 |
| 就业 | `macro_china_urban_unemployment` | 城镇失业率 |
| 投资 | `macro_china_gdzctz`, `macro_china_fdi` | 固定资产投资/外资 |
| 财政 | `macro_china_national_tax_receipts`, `macro_china_czsr` | 税收/财政收入 |
| 保险 | `macro_china_insurance`, `macro_china_insurance_income` | 保险业/保费收入 |
| 其他 | `macro_china_au_report`（黄金报告）, `macro_china_agricultural_product`（农产品） | |

### 2.2 美国宏观

```python
macro_usa_gdp_monthly             # GDP
macro_usa_cpi_monthly             # CPI
macro_usa_cpi_yoy                 # CPI 同比
macro_usa_core_cpi_monthly        # 核心CPI
macro_usa_non_farm                # 非农就业
macro_usa_unemployment_rate       # 失业率
macro_usa_initial_jobless         # 初请失业金
macro_usa_ism_pmi                 # ISM制造业PMI
macro_usa_ism_non_pmi             # ISM非制造业PMI
macro_usa_retail_sales            # 零售销售
macro_usa_industrial_production   # 工业产出
macro_usa_trade_balance           # 贸易差额
macro_usa_house_starts            # 新屋开工
macro_usa_exist_home_sales        # 成屋销售
macro_usa_new_home_sales          # 新房销售
macro_usa_house_price_index       # 房价指数
macro_usa_eia_crude_rate          # EIA原油库存
macro_usa_api_crude_stock         # API原油库存
macro_usa_building_permits        # 营建许可
macro_usa_factory_orders          # 工厂订单
macro_usa_durable_goods_orders    # 耐用品订单
macro_usa_michigan_consumer_sentiment  # 密歇根消费者信心
macro_usa_cb_consumer_confidence  # Conference Board消费者信心
macro_usa_personal_spending       # 个人支出
macro_usa_pce_price               # PCE物价
macro_usa_adp_employment          # ADP就业
macro_usa_rig_count               # 钻井数
macro_usa_cftc_c_holding          # CFTC持仓
```

### 2.3 欧元区/德国/日本/英国/瑞士/加拿大/澳大利亚

每个经济体覆盖 GDP、CPI、PMI、失业率、贸易、零售、工业产出等核心指标。
例如：`macro_euro_gdp_yoy`, `macro_japan_bank_rate`, `macro_germany_ifo`, `macro_uk_bank_rate`

### 2.4 航运指数

```python
macro_shipping_bdi                # 波罗的海干散货指数
macro_shipping_bpi                # 巴拿马型运费指数
macro_shipping_bci                # 海岬型运费指数
macro_shipping_bcti               # 波罗的海原油油轮指数
```

### 2.5 全球利率/其他

```python
rate_interbank                    # 银行间利率
repo_rate_hist                    # 回购利率历史
macro_global_sox_index            # 全球半导体指数
macro_info_ws                     # 华尔街资讯
macro_cons_gold                   # 黄金消费
macro_cons_silver                 # 白银消费
```

---

## 三、指数数据（index_*）

### 3.1 A股指数

```python
index_zh_a_hist(symbol='000001', period='daily')             # 指数历史K线
index_zh_a_hist_min_em(symbol='000001')                      # 指数分钟K线
index_realtime_sw(symbol='801010', index_type='SW')          # 申万行业指数实时（已废弃）
index_analysis_daily_sw                                       # 申万行业指数日度分析
index_stock_cons(symbol='000300')                             # 指数成分股
index_stock_cons_weight_csindex(symbol='000300')              # 指数成分股权重（中证）
index_stock_info()                                            # 所有指数信息
index_code_id_map_em()                                        # 指数代码映射
```

### 3.2 全球指数

```python
index_global_spot_em()                                        # 全球指数实时行情
index_global_hist_em(symbol='GDAXI')                          # 全球指数历史K线
index_global_name_table()                                     # 全球指数名称表
index_us_stock_sina()                                         # 美股指数
```

### 3.3 特色指数

```python
index_hog_spot_price(symbol='四川')                           # 生猪现货价格
index_news_sentiment_scope(symbol='新能源汽车')               # 新闻情绪指数
index_option_50etf_qvix                                       # 50ETF波动率指数
index_option_300etf_qvix                                      # 300ETF波动率指数
```

---

## 四、基金（fund_*）

### 4.1 ETF

```python
fund_etf_spot_em()                                            # ETF实时行情（全市场）
fund_etf_hist_em(symbol='510050')                             # ETF历史净值
fund_etf_hist_min_em(symbol='510050')                         # ETF分钟K线
fund_etf_hist_sina(symbol='510050')                           # ETF日K（新浪）
fund_etf_fund_info_em(symbol='510050')                        # ETF基金信息
fund_etf_scale_sse()                                          # ETF规模（上交所）
fund_etf_scale_szse()                                         # ETF规模（深交所）
fund_etf_category_sina()                                      # ETF分类
```

### 4.2 开放式基金

```python
fund_open_fund_daily_em(symbol='000001')                      # 开放式基金日K
fund_open_fund_info_em(symbol='000001')                       # 基金基本信息
fund_open_fund_rank_em()                                      # 开放式基金排行
fund_fee_em(symbol='000001')                                  # 基金费率
fund_manager_em()                                             # 基金经理
fund_hold_structure_em(symbol='000001')                       # 基金持仓结构
fund_rating_all()                                             # 全部基金评级
```

### 4.3 基金持仓分析

```python
fund_portfolio_hold_em(symbol='000001')                       # 基金持仓明细
fund_portfolio_industry_allocation_em(symbol='000001')        # 基金行业配置
fund_portfolio_bond_hold_em(symbol='000001')                  # 基金债券持仓
fund_portfolio_change_em(symbol='000001')                     # 基金持仓变动
```

### 4.4 货币基金/理财

```python
fund_money_fund_daily_em()                                    # 货币基金日K
fund_money_rank_em()                                          # 货币基金排行
fund_lcx_rank_em()                                            # 理财产品排行
```

### 4.5 LOF/分级基金

```python
fund_lof_spot_em()                                            # LOF实时行情
fund_lof_hist_em(symbol='166000')                             # LOF历史净值
fund_graded_fund_daily_em(symbol='150000')                    # 分级基金
```

### 4.6 雪球基金分析（7个接口）

```python
fund_individual_basic_info_xq(symbol='000001')               # 雪球基金基本信息
fund_individual_analysis_xq(symbol='000001')                  # 雪球基金分析
fund_individual_detail_hold_xq(symbol='000001')               # 雪球持仓详情
fund_individual_detail_info_xq(symbol='000001')               # 雪球详细信息
fund_individual_achievement_xq(symbol='000001')               # 雪球业绩
fund_individual_profit_probability_xq(symbol='000001')        # 雪球盈利概率
```

---

## 五、期货（futures_*）

### 5.1 国内期货行情

```python
futures_zh_daily_sina(symbol='RB0')                           # 期货日K
futures_zh_realtime()                                          # 期货实时行情（全品种）
futures_zh_minute_sina(symbol='RB0', period='5')              # 期货分钟K线
futures_zh_spot()                                             # 期货现货行情
futures_main_sina()                                           # 主力合约
futures_display_main_sina()                                   # 主力合约展示
```

### 5.2 外盘期货

```python
futures_foreign_hist(symbol='LC', period='daily')             # 外盘期货历史K线
futures_foreign_commodity_realtime(symbol='LC')                # 外盘期货实时行情
futures_foreign_detail(symbol='LC')                            # 外盘期货详情
```

### 5.3 期货持仓/库存

```python
futures_dce_position_rank(symbol='m')                          # 大商所持仓排名
futures_shfe_warehouse_receipt(symbol='cu')                    # 上期所仓单
futures_czce_warehouse_receipt(symbol='SR')                    # 郑商所仓单
futures_inventory_em(symbol='大豆')                            # 期货库存
futures_hold_pos_sina(symbol='RB9999')                         # 持仓分析
```

### 5.4 期现价差

```python
futures_spot_price(symbol='RB')                               # 期现价差（历史）
futures_spot_price_daily(symbol='RB')                          # 期现价差（每日）
futures_to_spot_shfe(symbol='cu')                              # 上期所期转现
```

### 5.5 国外期现

```python
futures_comex_inventory(symbol='黄金')                         # COMEX库存
futures_hog_core()                                             # 生猪核心数据
futures_hog_cost()                                             # 生猪养殖成本
futures_hog_supply()                                           # 生猪供给
```

### 5.6 合约信息

```python
futures_contract_info_shfe()                                  # 上期所合约
futures_contract_info_czce()                                  # 郑商所合约
futures_contract_info_dce()                                   # 大商所合约
futures_contract_info_cffex()                                 # 中金所合约
futures_contract_info_gfex()                                  # 广期所合约
futures_contract_info_ine()                                   # 上海能源中心
```

### 5.7 全球行情

```python
futures_global_hist_em(symbol='NQ')                           # 全球期货历史
futures_global_spot_em()                                      # 全球期货实时行情
```

---

## 六、可转债/债券（bond_*）

### 6.1 可转债

```python
bond_zh_cov(symbol='123456')                                  # 可转债行情
bond_zh_cov_info(symbol='123456', delisted='False')           # 可转债基本信息
bond_zh_cov_spot(symbol='123456')                              # 可转债实时行情
bond_zh_cov_daily(symbol='123456')                             # 可转债日K
bond_zh_cov_min(symbol='123456')                               # 可转债分钟K
bond_cb_jsl()                                                  # 集思录可转债数据
bond_cb_index_jsl()                                            # 集思录可转债指数
bond_zh_cov_value_analysis(symbol='123456')                    # 可转债价值分析
bond_cb_adj_logs_jsl()                                        # 可转债转股价调整日志
bond_cb_redeem_jsl()                                          # 可转债强赎
```

### 6.2 国债/金融债

```python
bond_china_yield(symbol='国债')                                # 中国国债收益率
bond_zh_us_rate()                                              # 中美利率对比（关键数据）
bond_treasury_index_cbond()                                    # 中证国债指数
bond_composite_index_cbond()                                   # 综合债券指数
bond_local_government_issue_cninfo()                           # 地方债发行
bond_treasure_issue_cninfo()                                   # 国债发行
```

### 6.3 债券交易

```python
bond_deal_summary_sse()                                        # 上交所债券成交概况
bond_cash_summary_sse()                                        # 上交所债券现券
bond_spot_deal()                                               # 债券现券成交
bond_spot_quote()                                              # 债券报价
```

---

## 七、外汇/汇率（currency_*, forex_*）

```python
currency_boc_sina()                                            # 中行外汇牌价（全部货币）
currency_hist(from_symbol='USD', to_symbol='CNY')              # 汇率历史
currency_time_series(from_symbol='USD', to_symbol='CNY')       # 汇率时间序列
currency_latest()                                              # 最新汇率
currency_convert(from_symbol='USD', to_symbol='CNY')           # 汇率换算

forex_spot_em()                                                # 外汇实时行情
forex_hist_em(symbol='USDCNY', period='daily')                 # 外汇历史K线

fx_spot_quote()                                                # 外汇即期报价
fx_swap_quote()                                                # 外汇掉期报价
fx_pair_quote(symbol='USDCNY')                                 # 货币对报价
```

---

## 八、期权（option_*）

```python
option_cffex_hs300_daily_sina()                                # 沪深300指数期权日K
option_cffex_sz50_daily_sina()                                 # 上证50指数期权日K
option_cffex_zz1000_daily_sina()                               # 中证1000指数期权日K
option_current_em(symbol='159915')                             # ETF期权当前行情
option_minute_em(symbol='10008000')                            # 期权分钟行情
option_premium_analysis_em(symbol='10008000')                  # 期权溢价分析
option_risk_analysis_em(symbol='10008000')                     # 期权风险分析
option_value_analysis_em(symbol='10008000')                    # 期权价值分析
option_sse_greeks_sina(symbol='510050')                        # 期权希腊字母
option_vol_shfe(symbol='cu')                                   # 上期所波动率
option_vol_gfex(symbol='l')                                    # 广期所波动率
```

---

## 九、能源/碳交易（energy_*）

```python
energy_carbon_domestic()                                       # 全国碳市场
energy_carbon_bj()                                             # 北京碳市场
energy_carbon_sh()                                             # 上海碳市场
energy_carbon_sz()                                             # 深圳碳市场
energy_carbon_gz()                                             # 广州碳市场
energy_carbon_hb()                                             # 湖北碳市场
energy_carbon_eu()                                             # 欧盟碳市场（EUA）
energy_oil_hist()                                              # 原油历史数据
energy_oil_detail()                                            # 原油详情
```

---

## 十、其他实用模块

### 10.1 现货/贵金属

```python
spot_golden_benchmark_sge()                                    # 上海金交所黄金基准价
spot_silver_benchmark_sge()                                    # 上海金交所白银基准价
spot_hist_sge(symbol='AU99.99')                                # SGE历史行情
spot_price_qh(symbol='铜')                                     # 现货报价
spot_hog_soozhu()                                              # 搜猪网生猪价格
```

### 10.2 REITs

```python
reits_hist_em(symbol='508888')                                 # REITs历史净值
reits_realtime_em()                                            # REITs实时行情
reits_hist_min_em(symbol='508888')                             # REITs分钟K线
```

### 10.3 空气质量

```python
air_quality_hist()                                             # 空气质量历史
air_quality_rank()                                             # 空气质量排名
air_city_table()                                               # 城市表
```

### 10.4 电影票房

```python
movie_boxoffice_realtime()                                     # 实时票房
movie_boxoffice_daily()                                        # 日度票房
movie_boxoffice_weekly()                                       # 周度票房
movie_boxoffice_monthly()                                      # 月度票房
```

### 10.5 汽车销量

```python
car_market_total_cpca()                                       # 汽车市场总销量
car_market_man_rank_cpca()                                    # 厂商排名
car_market_segment_cpca()                                     # 细分市场
car_sale_rank_gasgoo()                                        # 车型销量排名（盖世）
```

### 10.6 新闻/舆情

```python
news_economic_baidu(date='20250301')                          # 百度经济新闻
news_trade_notify_dividend_baidu()                             # 分红公告
news_trade_notify_suspend_baidu()                              # 停牌公告
news_report_time_baidu()                                       # 公告时间
news_cctv(date='20250301')                                    # 央视新闻联播
```

---

## 十一、巨潮资讯网数据（\*_cninfo）

> 来源: 巨潮资讯网 (cninfo.com.cn) — 证监会指定的上市公司信息披露网站
> 特点: 最权威的官方数据，覆盖公司治理/公告/股东/IPO/分红等沪深交易所披露信息

### 11.1 个股基本面

```python
stock_profile_cninfo(symbol='300750')                     # 公司概况（法人/注册资金/成立上市日期/主营业务）
stock_ipo_summary_cninfo(symbol='300750')                  # IPO上市信息（发行价/发行数量/市盈率/中签率/承销商）
stock_dividend_cninfo(symbol='300750')                     # 历史分红（10派X元/送转/除权日）
stock_allotment_cninfo(symbol='600030')                    # 配股实施方案
stock_share_change_cninfo(symbol='300750')                 # 公司股本变动明细（总股本/流通股/限售股/变动原因）
```

### 11.2 股东股本

```python
stock_hold_control_cninfo(symbol='全部')                   # 实际控制人持股变动
stock_hold_change_cninfo(symbol='全部')                    # 股本变动
stock_hold_num_cninfo(date='20210630')                     # 股东人数及持股集中度
stock_hold_management_detail_cninfo(symbol='增持')         # 高管持股变动明细
```

### 11.3 公司治理

```python
stock_cg_equity_mortgage_cninfo(date='20210930')           # 股权质押
stock_cg_guarantee_cninfo(symbol='全部')                   # 对外担保
stock_cg_lawsuit_cninfo(symbol='全部')                     # 公司诉讼
```

### 11.4 行业分类

```python
stock_industry_category_cninfo(symbol='巨潮行业分类标准')  # 行业分类数据
stock_industry_change_cninfo(symbol='300750')              # 行业归属变动历史（含申万/巨潮/中证）
stock_industry_pe_ratio_cninfo(symbol='证监会行业分类')    # 行业市盈率
```

### 11.5 信息披露

```python
stock_zh_a_disclosure_report_cninfo(symbol='300750')       # 公告查询（标题/时间/公告链接）
stock_zh_a_disclosure_relation_cninfo(symbol='300750')     # 预约披露调研
stock_irm_cninfo(symbol='300750')                          # 互动易提问（投资者提问列表）
stock_irm_ans_cninfo(symbol='1513586704097333248')         # 互动易回答（公司回复详情）
```

### 11.6 新股数据

```python
stock_new_ipo_cninfo()                                     # 新股发行
stock_new_gh_cninfo()                                      # 新股过会
stock_rank_forecast_cninfo(date='20230817')                # 投资评级
```

### 11.7 基金持仓（巨潮版）

```python
fund_report_stock_cninfo(date='20210630')                  # 基金重仓股
fund_report_asset_allocation_cninfo()                      # 基金资产配置
fund_report_industry_allocation_cninfo(date='20210630')    # 基金行业配置
```

### 11.8 债券发行（巨潮版）

```python
bond_treasure_issue_cninfo(start_date='20210910')          # 国债发行
bond_corporate_issue_cninfo(start_date='20210911')         # 企业债发行
bond_local_government_issue_cninfo(start_date='20210911')  # 地方债发行
bond_cov_issue_cninfo(start_date='20210913')               # 可转债发行
bond_cov_stock_issue_cninfo()                              # 可转债转股
```

---

## 十二、来源规范

所有接口后缀标识数据来源:

| 后缀 | 来源 | 特点 |
|------|------|------|
| `_em` | 东方财富 | 字段最全，速度快，适合结构化数据 |
| `_sina` | 新浪财经 | 稳定，覆盖全面，有15分钟延迟 |
| `_ths` | 同花顺 | 补充数据源 |
| `_xq` | 雪球 | 用户行为、讨论、社区数据 |
| `_jsl` | 集思录 | 可转债专业数据 |
| `_baidu` | 百度 | 新闻、舆情 |
| `_cninfo` | 巨潮资讯 | 上市公司公告 |
| `_sse` | 上交所 | 官方数据 |
| `_szse` | 深交所 | 官方数据 |
| `_soozhu` | 搜猪网 | 生猪数据 |
| `_cpca` | 乘联会 | 汽车销量 |
| `_cflp` | 中国物流与采购联合会 | 物流指数 |

---

## 十三、速度与可靠性

| 数据源 | 响应时间 | 并发限制 | 稳定性 |
|--------|---------|---------|--------|
| 东方财富 (`_em`) | 0.2-1.0s | 一般 | ⭐⭐⭐⭐⭐ |
| 新浪 (`_sina`) | 0.1-0.5s | 一般 | ⭐⭐⭐⭐ |
| 腾讯 | 0.1-0.3s | 一般 | ⭐⭐⭐⭐ |
| 同花顺 (`_ths`) | 0.3-1.0s | 有频率限制 | ⭐⭐⭐ |
| 雪球 (`_xq`) | 0.3-0.8s | 一般 | ⭐⭐⭐⭐ |
| 集思录 (`_jsl`) | 0.2-0.5s | 一般 | ⭐⭐⭐⭐ |

---

## 十四、与 web_search_base 的集成现状

目前已在 `web_search_base/sources/akshare_em.py` 中使用的接口:
- `stock_financial_abstract` → `format_abstract()` 和 `format_multi_period_comparison()`

可扩展的候选接口:
- `stock_financial_analysis_indicator_em` → 深度财务指标（140项）
- `stock_individual_fund_flow` → 资金流向
- `stock_board_industry_spot_em` → 行业板块表现
- `stock_hsgt_hold_stock_em` → 北向资金持股
- `stock_institute_recommend` → 机构评级一致预期
- `stock_zh_dupont_comparison_em` → 杜邦分析
- `stock_zh_growth_comparison_em` → 成长能力对比
- `index_global_spot_em` → 全球指数行情
- `fund_etf_spot_em` → ETF行情
- `bond_zh_cov` → 可转债行情
- `bond_zh_us_rate` → 中美利率对比
