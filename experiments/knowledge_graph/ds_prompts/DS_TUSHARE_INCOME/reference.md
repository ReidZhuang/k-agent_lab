# income — 利润表（Income Statement）

## 数据源名称
- **中文名称**：利润表
- **英文名称**：Income Statement
- **数据源ID**：DS_TUSHARE_INCOME

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.income(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
上市公司利润表数据，包括营业收入、营业成本、净利润等

## 数据内容覆盖业务描述
盈利能力分析、营收追踪

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，income 接口提供 利润表 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.income(参数1=值1, 参数2=值2)
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
| compens_payout_refu | float | compens_payout_refu | ? |
| continued_net_profit | float | continued_net_profit | ? |
| capit_comstock_div | float | capit_comstock_div | ? |
| comshare_payable_dvd | float | comshare_payable_dvd | ? |
| prfshare_payable_dvd | float | prfshare_payable_dvd | ? |
| distr_profit_shrhder | float | distr_profit_shrhder | ? |
| workers_welfare | float | workers_welfare | ? |
| withdra_oth_ersu | float | withdra_oth_ersu | ? |
| withdra_rese_fund | float | withdra_rese_fund | ? |
| withdra_biz_devfund | float | withdra_biz_devfund | ? |
| withdra_legal_pubfund | float | withdra_legal_pubfund | ? |
| withdra_legal_surplus | float | withdra_legal_surplus | ? |
| adj_lossgain | float | adj_lossgain | ? |
| transfer_oth | float | transfer_oth | ? |
| transfer_housing_imprest | float | transfer_housing_imprest | ? |
| transfer_surplus_rese | float | transfer_surplus_rese | ? |
| fin_exp_int_inc | float | fin_exp_int_inc | ? |
| fin_exp_int_exp | float | fin_exp_int_exp | ? |
| distable_profit | float | distable_profit | ? |
| undist_profit | float | undist_profit | ? |
| insurance_exp | float | insurance_exp | ? |
| ebitda | float | ebitda | ? |
| ebit | float | ebit | ? |
| compr_inc_attr_m_s | float | compr_inc_attr_m_s | ? |
| compr_inc_attr_p | float | compr_inc_attr_p | ? |
| t_compr_income | float | t_compr_income | ? |
| oth_compr_income | float | oth_compr_income | ? |
| income_tax | float | income_tax | ? |
| nca_disploss | float | nca_disploss | ? |
| non_oper_exp | float | non_oper_exp | ? |
| non_oper_income | float | non_oper_income | ? |
| other_bus_cost | float | other_bus_cost | ? |
| reins_cost_refund | float | reins_cost_refund | ? |
| insur_reser_refu | float | insur_reser_refu | ? |
| sell_exp | float | 销售费用 | ? |
| oper_cost | float | 营业成本 | ? |
| total_revenue | float | 营业总收入 | ? |
| basic_eps | float | 基本每股收益 | ? |
| n_income | float | 净利润 | ? |
| operate_profit | float | 营业利润 | ? |
| rd_exp | float | 研发费用 | ? |
| fin_exp | float | 财务费用 | ? |
| minority_gain | float | 少数股东损益 | ? |
| total_cogs | float | 营业总成本 | ? |
| end_date | date | 财务报表截止日期 | ? |
| revenue | float | 营业收入 | ? |
| total_profit | float | 利润总额 | ? |
| admin_exp | float | 管理费用 | ? |
| n_income_attr_p | float | 归属母公司股东净利润 | ? |
| dt_eps | float | 稀释每股收益 | ? |
| f_ann_date | float | f_ann_date | ? |
| report_type | float | report_type | ? |
| comp_type | float | comp_type | ? |
| end_type | float | end_type | ? |
| basic_eps | float | basic_eps | ? |
| diluted_eps | float | diluted_eps | ? |
| int_income | float | int_income | ? |
| prem_earned | float | prem_earned | ? |
| comm_income | float | comm_income | ? |
| n_commis_income | float | n_commis_income | ? |
| n_oth_income | float | n_oth_income | ? |
| n_oth_b_income | float | n_oth_b_income | ? |
| prem_income | float | prem_income | ? |
| out_prem | float | out_prem | ? |
| une_prem_reser | float | une_prem_reser | ? |
| reins_income | float | reins_income | ? |
| n_sec_tb_income | float | n_sec_tb_income | ? |
| n_sec_uw_income | float | n_sec_uw_income | ? |
| n_asset_mg_income | float | n_asset_mg_income | ? |
| oth_b_income | float | oth_b_income | ? |
| fv_value_chg_gain | float | fv_value_chg_gain | ? |
| invest_income | float | invest_income | ? |
| ass_invest_income | float | ass_invest_income | ? |
| forex_gain | float | forex_gain | ? |
| int_exp | float | int_exp | ? |
| comm_exp | float | comm_exp | ? |
| biz_tax_surchg | float | biz_tax_surchg | ? |
| assets_impair_loss | float | assets_impair_loss | ? |
| prem_refund | float | prem_refund | ? |
| compens_payout | float | compens_payout | ? |
| reser_insur_liab | float | reser_insur_liab | ? |
| div_payt | float | div_payt | ? |
| reins_exp | float | reins_exp | ? |
| oper_exp | float | oper_exp | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.income(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.income(...) 返回的 DataFrame
# 示例：columns = ['compens_payout_refu', 'continued_net_profit', 'capit_comstock_div', 'comshare_payable_dvd', 'prfshare_payable_dvd'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
