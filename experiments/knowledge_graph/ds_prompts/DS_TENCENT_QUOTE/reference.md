# DS_TENCENT_QUOTE — 腾讯实时行情（Tencent Quote）

## 数据源名称
- **中文名称**：腾讯实时行情
- **英文名称**：Tencent Quote
- **数据源ID**：DS_TENCENT_QUOTE

## 接口
- **类型**：HTTP GET 请求
- **URL**：`https://web.sqt.gtimg.cn/q={code}`

## 数据内容描述
腾讯财经个股实时行情数据

## 数据内容覆盖业务描述
免费实时行情

## 数据接口背景描述（若有）
腾讯财经提供免费的实时行情数据，通过 HTTP GET 请求获取。返回 ~ 分隔的字段格式。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import requests
url = 'https://web.sqt.gtimg.cn/q={code}'
params = {...}  # 见下方参数说明
headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, params=params, headers=headers)
# 后续解析取决于返回格式...
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| code: sh600519 或 sz300750（sh=上海, sz=深圳） |
| 批量: 逗号分隔多个代码 |
| 请求需带 User-Agent 头 |
| **必须跟随 302 重定向**（加 allow_redirects=True） |

## 数据更新时效描述
腾讯实时行情数据为 3 秒刷新一次，盘中持续更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| name | str | 股票名称 | 宁德时代 |
| code | str | 股票代码 | 300750 |
| price | float | 当前价 | 359.06 |
| pre_close | float | 昨收价 | 348.76 |
| open | float | 开盘价 | 349.00 |
| volume | float | 成交量(手) | 462907 |
| change | float | 涨跌额 | 10.30 |
| pct_chg | float | 涨跌幅% | 2.95 |
| high | float | 最高价 | ≥349.00 |
| low | float | 最低价 | ≤349.00 |
| amount | float | 成交额(万元) | 索引未知，返回数据中按顺序查找 |
| turnover_rate | float | 换手率% | 索引未知，返回数据中按顺序查找 |

## 接口调用示例
```python
import requests
resp = requests.get('https://web.sqt.gtimg.cn/q=sz300750',
    headers={'User-Agent':'Mozilla/5.0'}, allow_redirects=True)
txt = resp.text
print(txt[:200])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# HTTP 响应文本...
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **~ 分隔**：返回数据以 `~` 分隔约 88 个字段，用 `.split('~')` 解析
2. **302 重定向**：必须跟随重定向（`allow_redirects=True`）
3. **字段索引**：各字段按固定索引位置取值（如 name=1, price=3 等）
4. **批量查询**：逗号分隔多个代码可批量查询
5. **代码格式**：❗这是最常出错的点。Tencent 接口的 code 格式是 `sz300750`（小写交易所前缀 + 纯数字代码），**不是** Tushare 的 `300750.SZ` 格式。同样 `sh600519` 对应 Tushare 的 `600519.SH`。使用前必须将 entity_value 从 Tushare 格式转换为腾讯格式（前置小写 sh/sz + 去掉点和后缀）。
