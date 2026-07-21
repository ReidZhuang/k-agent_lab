# balancesheet — 资产负债表（Balance Sheet）

## 数据源名称
- **中文名称**：资产负债表
- **英文名称**：Balance Sheet
- **数据源ID**：DS_TUSHARE_BALANCE

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.balancesheet(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
上市公司资产负债表数据，包括资产、负债、所有者权益各科目

## 数据内容覆盖业务描述
财务分析、偿债能力评估

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，balancesheet 接口提供 资产负债表 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.balancesheet(参数1=值1, 参数2=值2)
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
| r_and_d | float | r_and_d | ? |
| oth_debt_invest | float | oth_debt_invest | ? |
| debt_invest | float | debt_invest | ? |
| long_pay_total | float | long_pay_total | ? |
| oth_pay_total | float | oth_pay_total | ? |
| cip_total | float | cip_total | ? |
| fix_assets_total | float | fix_assets_total | ? |
| oth_rcv_total | float | oth_rcv_total | ? |
| accounts_pay | float | accounts_pay | ? |
| accounts_receiv_bill | float | accounts_receiv_bill | ? |
| contract_liab | float | contract_liab | ? |
| contract_assets | float | contract_assets | ? |
| fair_value_fin_assets | float | fair_value_fin_assets | ? |
| cost_fin_assets | float | cost_fin_assets | ? |
| hfs_sales | float | hfs_sales | ? |
| hfs_assets | float | hfs_assets | ? |
| payables | float | payables | ? |
| st_fin_payable | float | st_fin_payable | ? |
| acc_receivable | float | acc_receivable | ? |
| lending_funds | float | lending_funds | ? |
| oth_eqt_tools_p_shr | float | oth_eqt_tools_p_shr | ? |
| oth_eqt_tools | float | oth_eqt_tools | ? |
| oth_comp_income | float | oth_comp_income | ? |
| lt_payroll_payable | float | lt_payroll_payable | ? |
| total_liab_hldr_eqy | float | total_liab_hldr_eqy | ? |
| total_hldr_eqy_inc_min_int | float | total_hldr_eqy_inc_min_int | ? |
| total_hldr_eqy_exc_min_int | float | total_hldr_eqy_exc_min_int | ? |
| minority_int | float | minority_int | ? |
| invest_loss_unconf | float | invest_loss_unconf | ? |
| forex_differ | float | forex_differ | ? |
| ordin_risk_reser | float | ordin_risk_reser | ? |
| treasury_share | float | treasury_share | ? |
| policy_div_payable | float | policy_div_payable | ? |
| indem_payable | float | indem_payable | ? |
| pledge_borr | float | pledge_borr | ? |
| indept_acc_liab | float | indept_acc_liab | ? |
| reser_lthins_liab | float | reser_lthins_liab | ? |
| reser_lins_liab | float | reser_lins_liab | ? |
| reser_outstd_claims | float | reser_outstd_claims | ? |
| reser_une_prem | float | reser_une_prem | ? |
| ph_invest | float | ph_invest | ? |
| depos_received | float | depos_received | ? |
| prem_receiv_adva | float | prem_receiv_adva | ? |
| oth_liab | float | oth_liab | ? |
| agency_bus_liab | float | agency_bus_liab | ? |
| depos | float | depos | ? |
| deriv_liab | float | deriv_liab | ? |
| depos_oth_bfi | float | depos_oth_bfi | ? |
| total_ncl | float | total_ncl | ? |
| oth_ncl | float | oth_ncl | ? |
| defer_inc_non_cur_liab | float | defer_inc_non_cur_liab | ? |
| defer_tax_liab | float | defer_tax_liab | ? |
| estimated_liab | float | estimated_liab | ? |
| specific_payables | float | specific_payables | ? |
| lt_payable | float | lt_payable | ? |
| bond_payable | float | bond_payable | ? |
| total_cur_liab | float | total_cur_liab | ? |
| oth_cur_liab | float | oth_cur_liab | ? |
| non_cur_liab_due_1y | float | non_cur_liab_due_1y | ? |
| acting_uw_sec | float | acting_uw_sec | ? |
| acting_trading_sec | float | acting_trading_sec | ? |
| rsrv_insur_cont | float | rsrv_insur_cont | ? |
| payable_to_reinsurer | float | payable_to_reinsurer | ? |
| st_bonds_payable | float | st_bonds_payable | ? |
| deferred_inc | float | deferred_inc | ? |
| acc_exp | float | acc_exp | ? |
| oth_payable | float | oth_payable | ? |
| div_payable | float | div_payable | ? |
| int_payable | float | int_payable | ? |
| taxes_payable | float | taxes_payable | ? |
| payroll_payable | float | payroll_payable | ? |
| comm_payable | float | comm_payable | ? |
| sold_for_repur_fa | float | sold_for_repur_fa | ? |
| adv_receipts | float | adv_receipts | ? |
| acct_payable | float | acct_payable | ? |
| notes_payable | float | notes_payable | ? |
| trading_fl | float | trading_fl | ? |
| loan_oth_bank | float | loan_oth_bank | ? |
| depos_ib_deposits | float | depos_ib_deposits | ? |
| cb_borr | float | cb_borr | ? |
| invest_as_receiv | float | invest_as_receiv | ? |
| transac_seat_fee | float | transac_seat_fee | ? |
| client_prov | float | client_prov | ? |
| client_depos | float | client_depos | ? |
| indep_acct_assets | float | indep_acct_assets | ? |
| refund_cap_depos | float | refund_cap_depos | ? |
| ph_pledge_loans | float | ph_pledge_loans | ? |
| refund_depos | float | refund_depos | ? |
| rr_reins_lthins_liab | float | rr_reins_lthins_liab | ? |
| rr_reins_lins_liab | float | rr_reins_lins_liab | ? |
| rr_reins_outstd_cla | float | rr_reins_outstd_cla | ? |
| rr_reins_une_prem | float | rr_reins_une_prem | ? |
| deriv_assets | float | deriv_assets | ? |
| prec_metals | float | prec_metals | ? |
| depos_in_oth_bfi | float | depos_in_oth_bfi | ? |
| cash_reser_cb | float | cash_reser_cb | ? |
| total_nca | float | total_nca | ? |
| oth_nca | float | oth_nca | ? |
| decr_in_disbur | float | decr_in_disbur | ? |
| defer_tax_assets | float | defer_tax_assets | ? |
| lt_amor_exp | float | lt_amor_exp | ? |
| st_borr | float | 短期借款 | ? |
| total_hldr_eqy_exc_min_int | float | 所有者权益合计 | ? |
| fix_assets | float | 固定资产 | ? |
| total_liab | float | 负债总计 | ? |
| goodwill | float | 商誉 | ? |
| accts_pay | float | 应付账款 | ? |
| cip | float | 在建工程 | ? |
| money_cap | float | 货币资金 | ? |
| intan_assets | float | 无形资产 | ? |
| inventories | float | 存货 | ? |
| total_assets | float | 资产总计 | ? |
| lt_borr | float | 长期借款 | ? |
| accts_receiv | float | 应收账款 | ? |
| f_ann_date | float | f_ann_date | ? |
| report_type | float | report_type | ? |
| comp_type | float | comp_type | ? |
| end_type | float | end_type | ? |
| total_share | float | total_share | ? |
| cap_rese | float | cap_rese | ? |
| undistr_porfit | float | undistr_porfit | ? |
| surplus_rese | float | surplus_rese | ? |
| special_rese | float | special_rese | ? |
| trad_asset | float | trad_asset | ? |
| notes_receiv | float | notes_receiv | ? |
| accounts_receiv | float | accounts_receiv | ? |
| oth_receiv | float | oth_receiv | ? |
| prepayment | float | prepayment | ? |
| div_receiv | float | div_receiv | ? |
| int_receiv | float | int_receiv | ? |
| amor_exp | float | amor_exp | ? |
| nca_within_1y | float | nca_within_1y | ? |
| sett_rsrv | float | sett_rsrv | ? |
| loanto_oth_bank_fi | float | loanto_oth_bank_fi | ? |
| premium_receiv | float | premium_receiv | ? |
| reinsur_receiv | float | reinsur_receiv | ? |
| reinsur_res_receiv | float | reinsur_res_receiv | ? |
| pur_resale_fa | float | pur_resale_fa | ? |
| oth_cur_assets | float | oth_cur_assets | ? |
| total_cur_assets | float | total_cur_assets | ? |
| fa_avail_for_sale | float | fa_avail_for_sale | ? |
| htm_invest | float | htm_invest | ? |
| lt_eqt_invest | float | lt_eqt_invest | ? |
| invest_real_estate | float | invest_real_estate | ? |
| time_deposits | float | time_deposits | ? |
| oth_assets | float | oth_assets | ? |
| lt_rec | float | lt_rec | ? |
| const_materials | float | const_materials | ? |
| fixed_assets_disp | float | fixed_assets_disp | ? |
| produc_bio_assets | float | produc_bio_assets | ? |
| oil_and_gas_assets | float | oil_and_gas_assets | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.balancesheet(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.balancesheet(...) 返回的 DataFrame
# 示例：columns = ['r_and_d', 'oth_debt_invest', 'debt_invest', 'long_pay_total', 'oth_pay_total'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
