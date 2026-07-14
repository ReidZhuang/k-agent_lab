# DS_TUSHARE_STK_MANAGERS API 调用规则

## 接口
pro.stk_managers(ts_code='')

## 参数
- ts_code: 股票代码

## 示例
```python
import os
import tushare as ts
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.stk_managers(ts_code='000001.SZ')
```

## 注意
- Token 通过 os.getenv('TUSHARE_TOKEN') 读取
