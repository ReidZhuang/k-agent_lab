# DS_SINA_INCOME — 新浪利润表（Sina Income Statement）

## 数据源名称
- **中文名称**：新浪利润表
- **英文名称**：Sina Income Statement
- **数据源ID**：DS_SINA_INCOME

## 接口
- **类型**：HTTP GET（HTML 页面解析）
- **URL 模板**：`https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml`

## 数据内容描述
新浪财经利润表完整数据

## 数据内容覆盖业务描述
免费利润表分析

## 数据接口背景描述（若有）
新浪财经提供免费的历史行情和财务数据，通过 HTTP 请求直接获取。不需要 token 或认证，但有反爬措施（需带 User-Agent 和 Referer 头）。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import requests
from bs4 import BeautifulSoup
url = '...'  # 见 api.md
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(resp.text, 'html.parser')
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

### 数据获取方式
从新浪财经页面解析 HTML 表格

## 数据更新时效描述
新浪财报数据按季度更新，通常在财报发布后 1-3 天更新。每张表含最近 4-5 个报告期。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| revenue | float | 营业收入 | 12913104.10 |
| cost | float | 营业成本 | 9708637.00 |
| sales_exp | float | 销售费用 | 92408.60 |
| admin_exp | float | 管理费用 | 307994.30 |
| fin_exp | float | 财务费用 | 6226.80 |
| rd_exp | float | 研发费用 | 531377.20 |
| inv_income | float | 投资收益 | 268832.80 |
| operating_profit | float | 营业利润 | 2665129.10 |
| total_profit | float | 利润总额 | 2674160.30 |
| tax_exp | float | 所得税费用 | 306718.40 |
| net_profit | float | 净利润 | 2367441.90 |
| net_profit_parent | float | 归母净利润 | 2147034.20 |
| eps_basic | float | 基本每股收益(元/股) | 0.87 |
| eps_diluted | float | 稀释每股收益(元/股) | 0.87 |

## 接口调用示例
```python
import requests
from bs4 import BeautifulSoup
# URL 见 api.md 中的 URL 选择规则
print('详见 api.md')
```

## 调用返回值样例（head(5)）
```
# 返回值格式
#  的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **编码**：必须设置 `resp.encoding = 'gb2312'`，否则中文乱码
2. **纯数字代码**：URL 中的 code 是纯数字（如 300750），不加 sh/sz 前缀
3. **行标签匹配**：HTML 行标签有中文序号前缀（如 '一、营业总收入'），用 `in` 操作符匹配
4. **单元格取值**：始终取 `cells[1]` 作为最新一期数据
5. **`--` 占位符**：无数据的单元格值为 `'--'`，取值时需判断 `val and val != '--'`
6. **银行股差异**：银行股科目不同（如 '现金及存放中央银行款项' 而非 '货币资金'）
7. **报告期数量**：每张表含最近 4-5 个报告期
### 额外说明
免 Token
编码: GB2312
含最近 4~5 个报告期的利润表数据

