## 接口
ball.industry_compare(symbol)

## 参数
- symbol: 股票代码（如 SH600519）

## 返回格式
返回 dict，data 包含 avg（行业均值）、items（具体股票列表）
取行业均值用 result["data"]["avg"]["pe_ttm"]
取个股数据用 result["data"]["items"][0]["pe_ttm"]
