# DS_TUSHARE_DAILY API 调用规则

## 接口
pro.daily(ts_code, start_date, end_date)

## 必填参数
- ts_code: 股票代码（必须传）

## 标准调用模板
```python
import os, tushare as ts
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.daily(ts_code='000001.SZ', start_date='20260101', end_date='20260630')
print(df)
```

## 注意
- import os 必须写
- ts_code 必须传
