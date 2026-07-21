# cashflow — 现金流量表（Cash Flow）

## 数据源名称
- **中文名称**：现金流量表
- **英文名称**：Cash Flow
- **数据源ID**：DS_TUSHARE_CASHFLOW

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.cashflow(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
上市公司现金流量表数据，包括经营/投资/筹资现金流

## 数据内容覆盖业务描述
现金流分析、财务健康度评估

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，cashflow 接口提供 现金流量表 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cashflow(参数1=值1, 参数2=值2)
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
| c_recp_borrow | float | c_recp_borrow | ? |
| beg_bal_cash_equ | float | beg_bal_cash_equ | ? |
| end_bal_cash_equ | float | end_bal_cash_equ | ? |
| beg_bal_cash | float | beg_bal_cash | ? |
| oth_loss_asset | float | oth_loss_asset | ? |
| use_right_asset_dep | float | use_right_asset_dep | ? |
| credit_impa_loss | float | credit_impa_loss | ? |
| net_cash_rece_sec | float | net_cash_rece_sec | ? |
| net_dism_capital_add | float | net_dism_capital_add | ? |
| im_n_incr_cash_equ | float | im_n_incr_cash_equ | ? |
| fa_fnc_leases | float | fa_fnc_leases | ? |
| conv_copbonds_due_within_1y | float | conv_copbonds_due_within_1y | ? |
| conv_debt_into_cap | float | conv_debt_into_cap | ? |
| im_net_cashflow_oper_act | float | im_net_cashflow_oper_act | ? |
| others | float | others | ? |
| incr_oper_payable | float | incr_oper_payable | ? |
| decr_oper_payable | float | decr_oper_payable | ? |
| decr_inventories | float | decr_inventories | ? |
| incr_def_inc_tax_liab | float | incr_def_inc_tax_liab | ? |
| decr_def_inc_tax_assets | float | decr_def_inc_tax_assets | ? |
| invest_loss | float | invest_loss | ? |
| loss_fv_chg | float | loss_fv_chg | ? |
| loss_scr_fa | float | loss_scr_fa | ? |
| loss_disp_fiolta | float | loss_disp_fiolta | ? |
| incr_acc_exp | float | incr_acc_exp | ? |
| decr_deferred_exp | float | decr_deferred_exp | ? |
| lt_amort_deferred_exp | float | lt_amort_deferred_exp | ? |
| amort_intang_assets | float | amort_intang_assets | ? |
| depr_fa_coga_dpba | float | depr_fa_coga_dpba | ? |
| prov_depr_assets | float | prov_depr_assets | ? |
| uncon_invest_loss | float | uncon_invest_loss | ? |
| incl_cash_rec_saims | float | incl_cash_rec_saims | ? |
| c_recp_cap_contrib | float | c_recp_cap_contrib | ? |
| c_cash_equ_end_period | float | c_cash_equ_end_period | ? |
| c_cash_equ_beg_period | float | c_cash_equ_beg_period | ? |
| n_incr_cash_cash_equ | float | n_incr_cash_cash_equ | ? |
| eff_fx_flu_cash | float | eff_fx_flu_cash | ? |
| n_cash_flows_fnc_act | float | n_cash_flows_fnc_act | ? |
| stot_cashout_fnc_act | float | stot_cashout_fnc_act | ? |
| oth_cashpay_ral_fnc_act | float | oth_cashpay_ral_fnc_act | ? |
| incl_dvd_profit_paid_sc_ms | float | incl_dvd_profit_paid_sc_ms | ? |
| c_pay_dist_dpcp_int_exp | float | c_pay_dist_dpcp_int_exp | ? |
| c_prepay_amt_borr | float | c_prepay_amt_borr | ? |
| stot_cash_in_fnc_act | float | stot_cash_in_fnc_act | ? |
| oth_cash_recp_ral_fnc_act | float | oth_cash_recp_ral_fnc_act | ? |
| proc_issue_bonds | float | proc_issue_bonds | ? |
| n_cashflow_inv_act | float | 投资活动现金流净额 | ? |
| cashflow_fin | float | 筹资活动现金流净额 | ? |
| im_net_cashflow_oper_act | float | 经营活动现金流净额 | ? |
| end_bal_cash | float | 期末现金及等价物余额 | ? |
| free_cashflow | float | 自由现金流 | ? |
| f_ann_date | float | f_ann_date | ? |
| comp_type | float | comp_type | ? |
| report_type | float | report_type | ? |
| end_type | float | end_type | ? |
| net_profit | float | net_profit | ? |
| finan_exp | float | finan_exp | ? |
| c_fr_sale_sg | float | c_fr_sale_sg | ? |
| recp_tax_rends | float | recp_tax_rends | ? |
| n_depos_incr_fi | float | n_depos_incr_fi | ? |
| n_incr_loans_cb | float | n_incr_loans_cb | ? |
| n_inc_borr_oth_fi | float | n_inc_borr_oth_fi | ? |
| prem_fr_orig_contr | float | prem_fr_orig_contr | ? |
| n_incr_insured_dep | float | n_incr_insured_dep | ? |
| n_reinsur_prem | float | n_reinsur_prem | ? |
| n_incr_disp_tfa | float | n_incr_disp_tfa | ? |
| ifc_cash_incr | float | ifc_cash_incr | ? |
| n_incr_disp_faas | float | n_incr_disp_faas | ? |
| n_incr_loans_oth_bank | float | n_incr_loans_oth_bank | ? |
| n_cap_incr_repur | float | n_cap_incr_repur | ? |
| c_fr_oth_operate_a | float | c_fr_oth_operate_a | ? |
| c_inf_fr_operate_a | float | c_inf_fr_operate_a | ? |
| c_paid_goods_s | float | c_paid_goods_s | ? |
| c_paid_to_for_empl | float | c_paid_to_for_empl | ? |
| c_paid_for_taxes | float | c_paid_for_taxes | ? |
| n_incr_clt_loan_adv | float | n_incr_clt_loan_adv | ? |
| n_incr_dep_cbob | float | n_incr_dep_cbob | ? |
| c_pay_claims_orig_inco | float | c_pay_claims_orig_inco | ? |
| pay_handling_chrg | float | pay_handling_chrg | ? |
| pay_comm_insur_plcy | float | pay_comm_insur_plcy | ? |
| oth_cash_pay_oper_act | float | oth_cash_pay_oper_act | ? |
| st_cash_out_act | float | st_cash_out_act | ? |
| n_cashflow_act | float | n_cashflow_act | ? |
| oth_recp_ral_inv_act | float | oth_recp_ral_inv_act | ? |
| c_disp_withdrwl_invest | float | c_disp_withdrwl_invest | ? |
| c_recp_return_invest | float | c_recp_return_invest | ? |
| n_recp_disp_fiolta | float | n_recp_disp_fiolta | ? |
| n_recp_disp_sobu | float | n_recp_disp_sobu | ? |
| stot_inflows_inv_act | float | stot_inflows_inv_act | ? |
| c_pay_acq_const_fiolta | float | c_pay_acq_const_fiolta | ? |
| c_paid_invest | float | c_paid_invest | ? |
| n_disp_subs_oth_biz | float | n_disp_subs_oth_biz | ? |
| oth_pay_ral_inv_act | float | oth_pay_ral_inv_act | ? |
| n_incr_pledge_loan | float | n_incr_pledge_loan | ? |
| stot_out_inv_act | float | stot_out_inv_act | ? |
| n_cashflow_inv_act | float | n_cashflow_inv_act | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cashflow(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.cashflow(...) 返回的 DataFrame
# 示例：columns = ['c_recp_borrow', 'beg_bal_cash_equ', 'end_bal_cash_equ', 'beg_bal_cash', 'oth_loss_asset'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
