# DS_LEVISTOCK_MARKET_INDEX API 调用规则
```python
import levistock as lk
indices = lk.market_index_em()
for i in indices:
    print(i['name'], i['price'], i['change_pct'])
```
