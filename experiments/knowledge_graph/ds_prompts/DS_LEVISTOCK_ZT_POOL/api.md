## 接口
lk.stock_zt_pool_em(date)

## 参数
date: 日期 YYYYMMDD，从查询条件中的时间范围获取

## 返回格式
返回 list[dict]，每个 dict 包含涨停股票信息

## 提取示例
```python
data = lk.stock_zt_pool_em(date="20260715")
if data:
    item = data[0]
    _result = [item.get("continuous", 0)]  # 字段名从字段映射表获取
```
