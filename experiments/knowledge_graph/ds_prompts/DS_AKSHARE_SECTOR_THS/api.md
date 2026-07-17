## 接口
ak.stock_board_industry_summary_ths()

## 参数
**无参数！** 此函数不接受任何参数。不要传 symbol 或其他参数。

## 说明
- 无参数，返回所有同花顺行业板块的实时行情
- 返回 DataFrame，每行一个板块

## 提取示例
要获取特定板块的数据，在返回的 DataFrame 中按板块名过滤：
```python
df = ak.stock_board_industry_summary_ths()   # 注意：不要传参数！
row = df[df["板块"] == "电池"].iloc[0]
value = row["涨跌幅"]
```
