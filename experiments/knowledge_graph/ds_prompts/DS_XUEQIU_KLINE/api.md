## 接口
ball.kline(symbol, count=284)

## 参数
- symbol: 股票代码（如 SH600519）
- count: 返回K线数量

## 返回格式
返回 dict，格式为 {"data": {"column": [...], "item": [[...]]}, "error_code": 0}
column 是列名列表，item 是数据列表
