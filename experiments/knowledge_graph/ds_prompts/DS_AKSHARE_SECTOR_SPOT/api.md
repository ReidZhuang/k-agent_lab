## 接口
ak.stock_board_industry_spot_em(symbol='板块名称')

## 参数
- symbol: 板块名称（如 '小金属'、'半导体'），必填参数

## 返回格式
当 symbol 指定具体板块时，返回 item-value 两列格式：
| item | value |
|------|-------|
| 最新 | 1314.10 |
| 涨跌幅 | -0.18 |
| 换手率 | 0.82 |

从返回的 DataFrame 中提取目标字段：按 item 列匹配，取 value 列的值。

## 提取示例
```python
df = ak.stock_board_industry_spot_em(symbol="电池")
result_row = df[df["item"] == "涨跌幅"]
value = float(result_row["value"].iloc[0])
```
