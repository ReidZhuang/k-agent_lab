# DS_SINA_FINANCE 字段分析

## 数据来源
新浪财经财务报表页面（HTML 解析）
- 利润表: `vFD_ProfitStatement`
- 资产负债表: `vFD_BalanceSheet`
- 现金流量表: `vFD_CashFlow`

## 字段统计

| 报表 | 总科目数 | 精选数 | 标记有用 |
|:----|:--------:|:------:|:--------:|
| 利润表 | 29 | 22 | 15 |
| 资产负债表 | 88 | 44 | 18 |
| 现金流量表 | 69 | 30 | 14 |
| **合计** | **186** | **96** | **54** |

## 核心可用指标（建议入库）

### 利润表
| 字段 | 英文名 | 说明 |
|:-----|:-------|:-----|
| 营业收入 | revenue | 主营业务收入 |
| 营业成本 | cost | 主营业务成本 |
| 销售费用 | sales_exp | 销售费用 |
| 管理费用 | admin_exp | 管理费用 |
| 财务费用 | fin_exp | 财务费用 |
| 研发费用 | rd_exp | 研发费用 |
| 投资收益 | inv_income | 投资收益 |
| 营业利润 | operating_profit | 营业利润 |
| 利润总额 | total_profit | 利润总额 |
| 净利润 | net_profit | 净利润 |
| 归母净利润 | net_profit_parent | 归属于母公司净利润 |
| 基本每股收益 | eps_basic | EPS |
| 营业成本 | cost | 营业成本 |

### 资产负债表
| 字段 | 英文名 | 说明 |
|:-----|:-------|:-----|
| 货币资金 | cash | 现金及等价物 |
| 交易性金融资产 | trading_assets | 短期投资 |
| 应收账款 | accounts_receivable | 应收款 |
| 存货 | inventory | 存货 |
| 流动资产合计 | current_assets | 流动资产 |
| 固定资产 | fixed_assets | 固定资产 |
| 无形资产 | intangible_assets | 无形资产 |
| 商誉 | goodwill | 商誉 |
| 资产总计 | total_assets | 总资产 |
| 短期借款 | short_term_loans | 短期借款 |
| 应付账款 | accounts_payable | 应付款 |
| 长期借款 | long_term_loans | 长期借款 |
| 负债合计 | total_liabilities | 总负债 |
| 股本 | share_capital | 实收资本 |
| 未分配利润 | retained_earnings | 留存收益 |
| 归母股东权益 | equity_parent | 净资产 |
| 所有者权益合计 | total_equity | 总权益 |

### 现金流量表
| 字段 | 英文名 | 说明 |
|:-----|:-------|:-----|
| 经营活动现金流净额 | op_cash_flow | 经营现金流 |
| 资本支出 | capex | 购建固定资产支付的现金 |
| 投资活动现金流净额 | inv_cash_flow | 投资现金流 |
| 筹资活动现金流净额 | fin_cash_flow | 筹资现金流 |
| 自由现金流 | free_cash_flow | op_cash_flow - capex |
| 期末现金 | cash_end | 期末现金余额 |

## 建议
- 利润表和现金流量表的关键字段可以直接入库
- 资产负债表的 44 个精选字段中选出 18 个核心的入库
- 对于新浪数据（15 分钟延迟），标记 refresh_time = daily（日级更新）
- 后续可以通过 Tushare 的同字段覆盖高频需求
