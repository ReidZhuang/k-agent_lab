## 接口
HTTP GET: http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData

## 参数
| 参数 | 必填 | 说明 |
|------|:----:|:-----|
| symbol | 是 | 股票代码（小写前缀 + 6位代码），如 sz300750、sh600519、bj835368 |
| scale | 是 | 时间粒度：240=日线, 60=60分钟, 30=30分钟, 15=15分钟, 5=5分钟 |
| ma | 否 | 固定传 no |
| datalen | 是 | 返回K线数量，最大约1000 |

代码前缀：6→sh, 0/3→sz, 8→bj

## 返回格式
JSONP，格式为 `var=([{...}, {...}]);`
去掉 `var=` 前缀和末尾的 `);`，中间是 JSON 数组。

## 提取方法
⚠️ 响应开头可能包含 `<script>location.href='//sina.com';</script>` 重定向注解，需要用 `find('var=')` 定位 JSONP 起点。

```python
import requests, json, re
url = 'http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData'
code = "sz300750"  # 小写前缀 + 代码
resp = requests.get(url, params={"symbol": code, "scale": 240, "ma": "no", "datalen": 5},
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}, timeout=10)
txt = resp.text.strip()
# ⚠️ 不直接用 strip/startswith！用 re 或 find 取 JSON 数组
match = re.search(r'\[.*\]', txt)  # 找到第一个 JSON 数组
if match:
    data = json.loads(match.group())
    if data:
        row = data[-1]  # 最新一期
        _result = [float(row["close"])]
```
