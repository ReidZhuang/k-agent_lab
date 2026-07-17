# DS_XUEQIU_QUOTE — 雪球实时行情（Xueqiu Quote）

## 数据源名称
- **中文名称**：雪球实时行情
- **英文名称**：Xueqiu Quote
- **数据源ID**：DS_XUEQIU_QUOTE

## 接口
- **类型**：xueqiu SDK（D类）
- **函数签名**：`ball.quotec(symbols)`

## 数据内容描述
雪球个股实时行情，含涨跌、振幅等

## 数据内容覆盖业务描述
个股实时行情

## 数据接口背景描述（若有）
雪球是中国知名的投资者交流平台，pysnowball 是雪球非官方 Python SDK。需登录雪球网页版获取 xq_a_token。token 配置在 `query_agent_api/config/xueqiu_token.json` 中。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import pysnowball as ball
# 需先设置 token
data = ball.quotec(symbols)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| symbols: 股票代码（如 SH600519），必填 |

### 返回值
返回 dict，data是list，每项含 current, percent, high, low 等字段

## 数据更新时效描述
雪球实时行情数据为实时更新，K线数据日频更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| current | float | 雪球实时价 | ? |

## 接口调用示例
```python
import pysnowball as ball
data = ball.quotec(symbols='SZ300750')
print(data['data'][0]['current'])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ball.quotec(symbols) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **代码格式**：必须用 SH/SZ 前缀（如 `SZ300750`），`_xq_code()` 自动转换
2. **Token 配置**：需要在 `xueqiu_token.json` 中配置有效的 xq_a_token
3. **Token 过期**：雪球 token 有时效性，过期需要重新登录网页版获取
