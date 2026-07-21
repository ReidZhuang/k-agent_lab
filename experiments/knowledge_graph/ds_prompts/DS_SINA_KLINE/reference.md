# DS_SINA_KLINE — 新浪K线（Sina K-Line）

## 数据源名称
- **中文名称**：新浪K线
- **英文名称**：Sina K-Line
- **数据源ID**：DS_SINA_KLINE

## 接口
- **类型**：HTTP GET 请求
- **URL**：`http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData`

## 数据内容描述
新浪财经提供的个股K线数据，支持多种时间粒度

## 数据内容覆盖业务描述
免费K线数据备选

## 数据接口背景描述（若有）
新浪财经提供免费的历史行情和财务数据，通过 HTTP 请求直接获取。不需要 token 或认证，但有反爬措施（需带 User-Agent 和 Referer 头）。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import requests
url = 'http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData'
params = {...}  # 见下方参数说明
headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, params=params, headers=headers)
# 后续解析取决于返回格式...
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| 参数 | 必填 | 说明 | |
| :----:|:-----| |
| symbol | 是 | 股票代码（小写前缀 + 6位代码），如 sz300750、sh600519、bj835368 | |
| scale | 是 | 时间粒度：240=日线, 60=60分钟, 30=30分钟, 15=15分钟, 5=5分钟 | |
| ma | 否 | 固定传 no | |
| datalen | 是 | 返回K线数量，最大约1000 | |

### 返回值
JSONP，格式为 `var=([{...}, {...}]);`
去掉 `var=` 前缀和末尾的 `);`，中间是 JSON 数组。

## 数据更新时效描述
新浪实时行情数据为 3-5 秒刷新一次，盘中持续更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| date | — | 时间 | — |
| open | — | 开盘 | — |
| high | — | 最高 | — |
| low | — | 最低 | — |
| close | — | 收盘 | — |
| volume | — | 成交量 | — |

## 接口调用示例
```python
import requests, json, re
url = 'http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData'
resp = requests.get(url, params={'symbol':'sz300750','scale':240,'ma':'no','datalen':5},
    headers={'User-Agent':'Mozilla/5.0', 'Referer':'https://finance.sina.com.cn'})
match = re.search(r'\[.*\]', resp.text)
if match:
    data = json.loads(match.group())
    print(data[-1])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# HTTP 响应文本...
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **代码前缀**：前缀小写（`sz300750` 不是 `SZ300750`）
2. **JSONP 解析**：响应开头有 `<script>location.href='//sina.com';</script>` 重定向注解，用 `re.search(r'\[.*\]', txt)` 提取 JSON 数组
3. **Referer 头**：必须带 Referer: https://finance.sina.com.cn
4. **数据量限制**：datalen 最大约 1000
