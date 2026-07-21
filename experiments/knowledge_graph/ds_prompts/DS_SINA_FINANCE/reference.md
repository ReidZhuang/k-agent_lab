# DS_SINA_FINANCE — 新浪财务数据（Sina Finance）

## 数据源名称
- **中文名称**：新浪财务数据
- **英文名称**：Sina Finance
- **数据源ID**：DS_SINA_FINANCE

## 接口
- **类型**：HTML 页面解析
- **URL**：按字段选择 URL（详见下方 URL 选择规则）

## 数据内容描述
新浪财经基础财务数据（利润表/资产负债表/现金流量表核心指标）

## 数据内容覆盖业务描述
免费财务数据

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
从新浪财经页面解析 HTML 表格。**字段与 URL 的对应关系见下方表格。**

### URL 选择规则
| 字段名 | 说明 | 所属报表 | URL |
|:------|:-----|:--------|:----|
| total_revenue / oper_cost / n_income / n_income_attr_p | 利润表科目 | 利润表 | vFD_ProfitStatement |
| total_assets / total_liab | 资产负债表科目 | 资产负债表 | vFD_BalanceSheet |
| cashflow_op / end_bal_cash | 现金流量表科目 | 现金流量表 | vFD_CashFlow |

## 数据更新时效描述
新浪财报数据按季度更新，通常在财报发布后 1-3 天更新。每张表含最近 4-5 个报告期。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| total_revenue | float | 营业总收入 | ? |
| oper_cost | float | 营业成本 | ? |
| n_income | float | 净利润 | ? |
| n_income_attr_p | float | 归母净利润 | ? |
| total_assets | float | 资产总计 | ? |
| total_liab | float | 负债合计 | ? |
| cashflow_op | float | 经营活动现金流净额 | ? |
| end_bal_cash | float | 期末现金及现金等价物 | ? |

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
编码: GB2312（必须 resp.encoding = "gb2312"）
含最近 4~5 个报告期的财务数据
**行标签有中文序号前缀**（如"一、营业总收入"），匹配时用 `in` 操作符

