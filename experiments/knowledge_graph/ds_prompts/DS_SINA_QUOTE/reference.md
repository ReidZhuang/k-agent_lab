# DS_SINA_QUOTE — 新浪实时行情（Sina Quote）

## 数据源名称
- **中文名称**：新浪实时行情
- **英文名称**：Sina Quote
- **数据源ID**：DS_SINA_QUOTE

## 接口
- **类型**：HTTP GET 请求
- **URL**：`http://hq.sinajs.cn/list={prefix}{code}`

## 数据内容描述
新浪财经个股实时行情（五档盘口）

## 数据内容覆盖业务描述
免费实时行情备选

## 数据接口背景描述（若有）
新浪财经提供免费的历史行情和财务数据，通过 HTTP 请求直接获取。不需要 token 或认证，但有反爬措施（需带 User-Agent 和 Referer 头）。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import requests
url = 'http://hq.sinajs.cn/list={prefix}{code}'
params = {...}  # 见下方参数说明
headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, params=params, headers=headers)
# 后续解析取决于返回格式...
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| code: sh600519 或 sz300750 |
| **必须带 Referer 和 User-Agent 头** |
| 编码: GBK，需要 r.encoding = 'gbk' |

### 返回值
数据以逗号分割：
```
var hq_str_sh600519="股票名,开盘价,昨收,当前价,最高,最低,买一,卖一,成交量,成交额..."
```
1. 去掉前缀 `var hq_str_xxx="` 和末尾的 `";`
2. 按逗号 `,` split
3. 按字段映射表中的索引取值（注意：Tencent 用 ~ 分割，Sina 用逗号分割）

## 数据更新时效描述
新浪实时行情数据为 3-5 秒刷新一次，盘中持续更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| name | str | 股票名称 | 宁德时代 |
| open | float | 开盘价 | 352.600 |
| pre_close | float | 昨收价 | 359.060 |
| price | float | 当前价 | 364.010 |
| high | float | 最高价 | 364.630 |
| low | float | 最低价 | 352.490 |
| buy1 | float | 买一价 | 364.000 |
| sell1 | float | 卖一价 | 364.010 |
| volume | int | 成交量(股) | 43631637 |
| amount | float | 成交额(元) | 15701875681.92 |
| b1_v | int | 买一量 | 9100 |
| b2_v | int | 买二量 | 700 |
| buy2 | float | 买二价 | 363.980 |
| b3_v | int | 买三量 | 1000 |
| buy3 | float | 买三价 | 363.970 |
| b4_v | int | 买四量 | 400 |
| buy4 | float | 买四价 | 363.960 |
| b5_v | int | 买五量 | 1000 |
| buy5 | float | 买五价 | 363.950 |
| s1_v | int | 卖一量 | 15387 |
| s2_v | int | 卖二量 | 1500 |
| sell2 | float | 卖二价 | 364.020 |
| s3_v | int | 卖三量 | 26990 |
| sell3 | float | 卖三价 | 364.030 |
| s4_v | int | 卖四量 | 900 |
| sell4 | float | 卖四价 | 364.040 |
| s5_v | int | 卖五量 | 400 |
| sell5 | float | 卖五价 | 364.050 |
| date | str | 日期 | 2026-07-14 |
| time | str | 时间 | 15:35:30 |

## 接口调用示例
```python
import requests
resp = requests.get('http://hq.sinajs.cn/list=sz300750',
    headers={'User-Agent':'Mozilla/5.0', 'Referer':'https://finance.sina.com.cn'})
resp.encoding = 'gbk'
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
1. **GBK 编码**：必须设置 `resp.encoding = 'gbk'`
2. **逗号分隔**：与腾讯的 ~ 分隔不同，新浪是逗号 `,` 分割
3. **Referer 头**：必须带 Referer
4. **代码格式**：❗Sina 接口的 code 格式是 `sz300750`（小写交易所前缀 + 纯数字代码），**不是** Tushare 的 `300750.SZ` 格式。使用前必须将 entity_value 从 Tushare 格式转换为新浪格式（前置小写 sh/sz + 去掉点和后缀）。
