## 函数
pro.daily(ts_code, start_date, end_date)
返回指定股票在时间范围内的日线行情数据（open, close, high, low, vol, pct_chg 等），
结果是一个 pandas DataFrame，每行一个交易日。

## 参数说明
|:----|:----:|:----:|:-----|:----:|
| ts_code | str | 是 | 股票代码，带市场后缀 | 000001.SZ |
| start_date | str | 否 | 起始日期 YYYYMMDD | 20260701 |
| end_date | str | 否 | 结束日期 YYYYMMDD | 20260714 |