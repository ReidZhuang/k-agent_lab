## 接口
lk.sector_em(sector_type='industry')

## 参数
- sector_type: 板块类型（默认 'industry'），可选值：'industry', 'concept', 'region'

## 返回格式
返回 list[dict]，每个 dict 包含板块行情数据

## 提取示例
按 sector_name 字段匹配特定板块：
```python
data_list = lk.sector_em(sector_type='industry')
if data_list:
    target_sector = "电池"  # 从查询条件获取
    for item in data_list:
        if item.get("sector_name") == target_sector:
            _result = [item.get("change_pct", 0)]
            break
```
