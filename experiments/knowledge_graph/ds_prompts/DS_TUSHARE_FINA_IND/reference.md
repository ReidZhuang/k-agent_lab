# fina_indicator — 财务指标（Financial Indicator）

## 数据源名称
- **中文名称**：财务指标
- **英文名称**：Financial Indicator
- **数据源ID**：DS_TUSHARE_FINA_IND

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.fina_indicator(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
上市公司各项财务指标，如ROE、ROA、毛利率等

## 数据内容覆盖业务描述
财务健康度综合评估

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，fina_indicator 接口提供 财务指标 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fina_indicator(参数1=值1, 参数2=值2)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| ts_code | 视情况 | str | 股票代码（如 000001.SZ、600519.SH），见路由条件 |
| start_date | 视情况 | str | 起始日期 YYYYMMDD，见路由条件中的时间范围 |
| end_date | 视情况 | str | 结束日期 YYYYMMDD，见路由条件中的时间范围 |

**注意**：只传查询条件中有提供值的参数，绝对不要编造参数值。

### 返回值
函数返回 `pandas.DataFrame`，列名见下方输出数据描述。取最新一行用 `df.iloc[-1]`，按列名取值用 `row['列名']`。

## 数据更新时效描述
Tushare 数据更新频率因接口而异：日线行情通常T+1更新，实时数据盘中更新。具体取决于 Tushare 官方数据发布策略。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| interestdebt | float | interestdebt | ? |
| equity_yoy | float | equity_yoy | ? |
| q_op_qoq | float | q_op_qoq | ? |
| q_sales_yoy | float | q_sales_yoy | ? |
| tr_yoy | float | tr_yoy | ? |
| eqt_yoy | float | eqt_yoy | ? |
| assets_yoy | float | assets_yoy | ? |
| bps_yoy | float | bps_yoy | ? |
| roe_yoy | float | roe_yoy | ? |
| ocf_yoy | float | ocf_yoy | ? |
| dt_netprofit_yoy | float | dt_netprofit_yoy | ? |
| ebt_yoy | float | ebt_yoy | ? |
| op_yoy | float | op_yoy | ? |
| cfps_yoy | float | cfps_yoy | ? |
| dt_eps_yoy | float | dt_eps_yoy | ? |
| basic_eps_yoy | float | basic_eps_yoy | ? |
| q_ocf_to_sales | float | q_ocf_to_sales | ? |
| q_npta | float | q_npta | ? |
| q_dt_roe | float | q_dt_roe | ? |
| q_gc_to_gr | float | q_gc_to_gr | ? |
| q_saleexp_to_gr | float | q_saleexp_to_gr | ? |
| profit_to_op | float | profit_to_op | ? |
| fixed_assets | float | fixed_assets | ? |
| roa_dp | float | roa_dp | ? |
| roa_yearly | float | roa_yearly | ? |
| turn_days | float | turn_days | ? |
| ocf_to_debt | float | ocf_to_debt | ? |
| tangibleasset_to_netdebt | float | tangibleasset_to_netdebt | ? |
| tangasset_to_intdebt | float | tangasset_to_intdebt | ? |
| tangibleasset_to_debt | float | tangibleasset_to_debt | ? |
| eqt_to_interestdebt | float | eqt_to_interestdebt | ? |
| eqt_to_debt | float | eqt_to_debt | ? |
| debt_to_eqt | float | debt_to_eqt | ? |
| ocf_to_shortdebt | float | ocf_to_shortdebt | ? |
| longdeb_to_debt | float | longdeb_to_debt | ? |
| currentdebt_to_debt | float | currentdebt_to_debt | ? |
| eqt_to_talcapital | float | eqt_to_talcapital | ? |
| tbassets_to_totalassets | float | tbassets_to_totalassets | ? |
| nca_to_assets | float | nca_to_assets | ? |
| ca_to_assets | float | ca_to_assets | ? |
| dp_assets_to_eqt | float | dp_assets_to_eqt | ? |
| roa2_yearly | float | roa2_yearly | ? |
| roe_yearly | float | roe_yearly | ? |
| npta | float | npta | ? |
| roa | float | roa | ? |
| roe_waa | float | roe_waa | ? |
| gc_of_gr | float | gc_of_gr | ? |
| impai_ttm | float | impai_ttm | ? |
| finaexp_of_gr | float | finaexp_of_gr | ? |
| adminexp_of_gr | float | adminexp_of_gr | ? |
| saleexp_to_gr | float | saleexp_to_gr | ? |
| profit_to_gr | float | profit_to_gr | ? |
| expense_of_sales | float | expense_of_sales | ? |
| cogs_of_sales | float | cogs_of_sales | ? |
| fcfe_ps | float | fcfe_ps | ? |
| fcff_ps | float | fcff_ps | ? |
| ebit_ps | float | ebit_ps | ? |
| cfps | float | cfps | ? |
| retainedps | float | retainedps | ? |
| diluted2_eps | float | diluted2_eps | ? |
| retained_earnings | float | retained_earnings | ? |
| invest_capital | float | invest_capital | ? |
| networking_capital | float | networking_capital | ? |
| working_capital | float | working_capital | ? |
| tangible_asset | float | tangible_asset | ? |
| netdebt | float | netdebt | ? |
| roe | float | 加权平均净资产收益率 | ? |
| dt_eps | float | 稀释每股收益 | ? |
| assets_turn | float | 营业收入/总资产 | ? |
| ebit | float | EBIT/利息费用 | ? |
| netprofit_yoy | float | 净利润同比增长率 | ? |
| netprofit_margin | float | 单季度净利率 | ? |
| fa_turn | float | 营业收入/平均固定资产 | ? |
| netprofit_yoy | float | 单季度净利润同比增长率 | ? |
| grossprofit_margin | float | 单季度毛利率 | ? |
| 资产减值损失/营收 | float | 资产减值损失占营收比例 | ? |
| ebit | float | 息税前利润 | ? |
| end_date | date | 财务报告截止日期 | ? |
| ocf_to_or | float | 经营现金流/营业收入 | ? |
| int_to_talcap | float | 带息债务/全部投入资本 | ? |
| rd_exp | float | 研发费用/营业收入 | ? |
| bps | float | 每股净资产 | ? |
| op_of_gr | float | 营业利润/营业总收入 | ? |
| fcff | float | 企业自由现金流 | ? |
| roic | float | 投入资本回报率 | ? |
| fcfe | float | 股权自由现金流 | ? |
| debt_to_assets | float | 总负债/总资产 | ? |
| eps | float | 基本每股收益 | ? |
| inv_turn | float | 营业成本/平均存货 | ? |
| netprofit_margin | float | 销售净利率 | ? |
| 价值变动净收益/利润总额 | float | 价值变动净收益占利润总额比例 | ? |
| undist_profit_ps | float | 每股未分配利润 | ? |
| ebitda | float | 息税折旧摊销前利润 | ? |
| or_yoy | float | 营业收入同比增长率 | ? |
| assets_to_eqt | float | 总资产/股东权益 | ? |
| q_sale_yoy | float | 单季度营收同比增长率 | ? |
| roe_dt | float | 摊薄净资产收益率 | ? |
| ar_turn | float | 营业收入/平均应收账款 | ? |
| ca_turn | float | 营业收入/平均流动资产 | ? |
| capital_rese_ps | float | 每股资本公积金 | ? |
| grossprofit_margin | float | 销售毛利率 | ? |
| ocfps | float | 每股经营活动现金流 | ? |
| ebit_of_gr | float | EBIT占营业总收入比例 | ? |
| q_roe | float | 单季度净资产收益率 | ? |
| total_revenue_ps | float | total_revenue_ps | ? |
| revenue_ps | float | revenue_ps | ? |
| surplus_rese_ps | float | surplus_rese_ps | ? |
| extra_item | float | extra_item | ? |
| profit_dedt | float | profit_dedt | ? |
| gross_margin | float | gross_margin | ? |
| current_ratio | float | current_ratio | ? |
| quick_ratio | float | quick_ratio | ? |
| cash_ratio | float | cash_ratio | ? |
| op_income | float | op_income | ? |
| current_exint | float | current_exint | ? |
| noncurrent_exint | float | noncurrent_exint | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fina_indicator(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.fina_indicator(...) 返回的 DataFrame
# 示例：columns = ['interestdebt', 'equity_yoy', 'q_op_qoq', 'q_sales_yoy', 'tr_yoy'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
