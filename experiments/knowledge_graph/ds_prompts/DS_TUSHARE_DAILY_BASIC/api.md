# DS_TUSHARE_DAILY_BASIC API 调用规则

## 接口
pro.daily_basic(ts_code, start_date, end_date, fields='')

## 必填参数
- ts_code: 股票代码（必须传，不可省略）

## 标准调用模板
```python
import os, tushare as ts
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.daily_basic(ts_code='600519.SH', start_date='20260101', fields='ts_code,trade_date,pe_ttm,pb')
print(df)
```

## 注意
- import os 必须写，否则 os.getenv 会报错
- ts_code 必须传，不可省略
