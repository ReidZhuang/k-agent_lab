## 数据获取
从新浪财经页面解析 HTML 表格

## URL
https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml

## 参数
code: 股票代码（必填），如 300750

## 说明
- 免 Token
- 编码: GB2312
- 含最近 4~5 个报告期的利润表数据

## 提取方法
1. 找到页面中包含"报表日期"的表格（利润表数据所在表格）
2. 遍历该表格的所有行
3. 按行标签（如"营业收入"、"营业利润"）匹配目标行
4. 取 cells[1] 作为最新一期数据
