# DS_TENCENT_QUOTE 表结构

API 返回 ~ 分隔的 88 个字段（URL 不带后缀拼接，用 requests.text.split("~") 分割）。

已验证的字段索引（字段[0] 是前缀 "v_szXXXX"="，字段从索引 1 开始）：

|索引|字段名|说明|验证方法|
|:---:|:---|:---|:---|
|1|name|股票名称|实测 `宁德时代`|
|2|code|股票代码|实测 `300750`|
|3|price|当前价|实测 `359.06`|
|4|pre_close|昨收价|实测 `348.76`|
|5|open|开盘价|实测 `349.00`|
|6|volume|成交量(手)|实测 `462907`|
|31|change|涨跌额|`price - pre_close` 验证|
|32|pct_chg|涨跌幅%|`change / pre_close * 100` 验证|
|33|high|最高价|`>= price` 验证|
|34|low|最低价|`<= price` 验证|

**注意**：其他字段（总市值、市盈率、成交额等）索引未经实测验证，不在此列出。
取数时通过字段名在 DataFrame 或 dict 中按 key 获取，不要按索引。

提取示例（已验证字段）：
```python
fields = requests.get(url, ...).text.split("~")
price = float(fields[3])       # 当前价
change = float(fields[31])     # 涨跌额
pct_chg = float(fields[32])    # 涨跌幅%
```
