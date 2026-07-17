## 接口
lk.market_index_all_em()

## 说明
- 无参数，返回所有主要指数的实时行情
- 返回 list[dict]，每个 dict 包含一个指数数据
- **要从列表中找出特定指数，遍历 data_list 按 name 字段匹配**

## 提取示例
```python
data_list = lk.market_index_all_em()
if data_list:
    target_name = "上证指数"  # 从查询条件获取
    for item in data_list:
        if item.get("name") == target_name:
            _result = [item.get("price", 0)]
            break
```