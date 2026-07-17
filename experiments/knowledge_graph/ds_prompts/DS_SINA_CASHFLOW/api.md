## 数据获取
从新浪财经页面解析 HTML 表格

## URL
https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{code}/ctrl/part/displaytype/4.phtml

## 参数
code: 股票代码（必填），如 300750

## 说明
- 免 Token
- 编码: GB2312
- 含最近 4~5 个报告期的现金流量表数据

## 页面结构
数据表格位于页面中唯一包含"报表日期"的表。
该表的行结构为：
- row[0]: 空行
- row[1]: 表头（"报表日期", 日期1, 日期2, ...）
- row[3]起：数据行，每行第一个td是行标签

## 提取方法
1. 找到包含"报表日期"的表格
2. 遍历该表格的所有行
3. 按行标签（如"经营活动产生的现金流量净额"）匹配目标行
4. 取 cells[1] 作为最新一期数据（去掉逗号后转 float）
