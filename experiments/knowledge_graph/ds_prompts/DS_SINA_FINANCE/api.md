## 数据获取
从新浪财经页面解析 HTML 表格。**字段与 URL 的对应关系见下方表格。**

## URL 选择规则
| 字段名 | 说明 | 所属报表 | URL |
|:------|:-----|:--------|:----|
| total_revenue / oper_cost / n_income / n_income_attr_p | 利润表科目 | 利润表 | vFD_ProfitStatement |
| total_assets / total_liab | 资产负债表科目 | 资产负债表 | vFD_BalanceSheet |
| cashflow_op / end_bal_cash | 现金流量表科目 | 现金流量表 | vFD_CashFlow |

## URL 模板
- 利润表: `https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml`
- 资产负债表: `https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/part/displaytype/4.phtml`
- 现金流量表: `https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{code}/ctrl/part/displaytype/4.phtml`

## 参数
code: 股票代码（必填），6位数字，如 300750，**必须用纯数字，不加 sh/sz 前缀**

## 说明
- 免 Token
- 编码: GB2312（必须 resp.encoding = "gb2312"）
- 含最近 4~5 个报告期的财务数据
- **行标签有中文序号前缀**（如"一、营业总收入"），匹配时用 `in` 操作符

## 提取方法
```python
import requests
from bs4 import BeautifulSoup

code = "300750"  # ⚠️ 纯数字，不加 sh/sz 前缀！
# 根据查询字段选择正确的 URL（利润表/资产负债表/现金流量表）
url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
resp.encoding = "gb2312"
soup = BeautifulSoup(resp.text, "html.parser")  # ⚠️ 用 html.parser，不用 lxml

target_label = "营业总收入"  # ← 从查询条件的"行标签"获取

for table in soup.find_all("table"):
    if "报表日期" in str(table.get_text()):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if cells:
                label = cells[0].get_text(strip=True)
                if target_label in label:  # 用 in 操作符（因有"一、"前缀）
                    _result = [float(cells[1].get_text().replace(",", ""))]
                    break
        break  # 找到第一个表格后退出
```

## 字段与行标签对应关系
| 字段名 | 行标签 | 所属报表 |
|:------|:-------|:--------|
| total_revenue | 营业总收入 | 利润表 |
| oper_cost | 营业成本 | 利润表 |
| n_income | 净利润 | 利润表 |
| n_income_attr_p | 归属于母公司所有者的净利润 | 利润表 |
| total_assets | 资产总计 | 资产负债表 |
| total_liab | 负债合计 | 资产负债表 |
| cashflow_op | 经营活动产生的现金流量净额 | 现金流量表 |
| end_bal_cash | 期末现金及现金等价物余额 | 现金流量表 |
