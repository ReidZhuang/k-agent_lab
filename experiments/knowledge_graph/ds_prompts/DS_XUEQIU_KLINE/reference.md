# DS_XUEQIU_KLINE — 雪球K线（Xueqiu K-Line）

## 数据源名称
- **中文名称**：雪球K线
- **英文名称**：Xueqiu K-Line
- **数据源ID**：DS_XUEQIU_KLINE

## 接口
- **类型**：xueqiu SDK（D类）
- **函数签名**：`ball.kline(symbol, count=284)`

## 数据内容描述
雪球提供的个股K线数据，支持日/周/月

## 数据内容覆盖业务描述
个股技术分析

## 数据接口背景描述（若有）
雪球是中国知名的投资者交流平台，pysnowball 是雪球非官方 Python SDK。需登录雪球网页版获取 xq_a_token。token 配置在 `query_agent_api/config/xueqiu_token.json` 中。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import pysnowball as ball
# 需先设置 token
data = ball.kline(symbol, count=284)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| symbol: 股票代码（如 SH600519） |
| count: 返回K线数量 |

### 返回值
返回 dict，格式为 {"data": {"column": [...], "item": [[...]]}, "error_code": 0}
column 是列名列表，item 是数据列表

## 数据更新时效描述
雪球实时行情数据为实时更新，K线数据日频更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| current | — | 当前价 | — |
| high | — | 最高价 | — |
| low | — | 最低价 | — |
| volume | — | 成交量 | — |

## 接口调用示例
```python
import pysnowball as ball
# token 已在模板中自动配置
data = ball.kline(symbol='SZ300750', count=5)
if data.get('data'):
    print(data['data']['item'][0])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ball.kline(symbol, count=284) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **代码格式**：必须用 SH/SZ 前缀（如 `SZ300750`），`_xq_code()` 自动转换
2. **Token 配置**：需要在 `xueqiu_token.json` 中配置有效的 xq_a_token
3. **Token 过期**：雪球 token 有时效性，过期需要重新登录网页版获取
4. **count 参数**：控制返回 K 线数量，默认约 284 根
