# DS_LEVISTOCK_SECTOR API 调用规则
```python
import levistock as lk
sectors = lk.sector_em('industry')  # 注意：传字符串，不是关键字参数
for s in sectors:
    print(s['sector_name'], s['change_pct'])
```
