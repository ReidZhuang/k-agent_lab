# DS_TUSHARE_FINA_IND API 调用规则

## 接口
pro.fina_indicator(ts_code, start_date, end_date, period='')

## 必填参数
- ts_code: 股票代码（必须传）

## 标准调用模板
```python
import os, tushare as ts
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fina_indicator(ts_code='300750.SZ', start_date='20240101', end_date='20240630')
print(df[['end_date','grossprofit_margin','netprofit_margin']])
```

## 注意
- import os 必须写
- ts_code 必须传
