| 字段名 | 类型 | 索引 | 说明 | 数据示例 |
|--------|:----:|:----:|:----:|:--------:|
| name | str | 1 | 股票名称 | 宁德时代 |
| code | str | 2 | 股票代码 | 300750 |
| price | float | 3 | 当前价 | 359.06 |
| pre_close | float | 4 | 昨收价 | 348.76 |
| open | float | 5 | 开盘价 | 349.00 |
| volume | float | 6 | 成交量(手) | 462907 |
| change | float | 31 | 涨跌额 | 10.30 |
| pct_chg | float | 32 | 涨跌幅% | 2.95 |
| high | float | 33 | 最高价 | ≥349.00 |
| low | float | 34 | 最低价 | ≤349.00 |
| amount | float | ? | 成交额(万元) | 索引未知，返回数据中按顺序查找 |
| turnover_rate | float | ? | 换手率% | 索引未知，返回数据中按顺序查找 |
