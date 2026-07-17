# DS_XUEQIU_IND_COMPARE — 雪球行业对比（Xueqiu Industry Compare）

## 数据源名称
- **中文名称**：雪球行业对比
- **英文名称**：Xueqiu Industry Compare
- **数据源ID**：DS_XUEQIU_IND_COMPARE

## 接口
- **类型**：xueqiu SDK（D类）
- **函数签名**：`ball.industry_compare(symbol)`

## 数据内容描述
个股与所在行业均值的对比数据

## 数据内容覆盖业务描述
行业内对比、估值分位

## 数据接口背景描述（若有）
雪球是中国知名的投资者交流平台，pysnowball 是雪球非官方 Python SDK。需登录雪球网页版获取 xq_a_token。token 配置在 `query_agent_api/config/xueqiu_token.json` 中。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import pysnowball as ball
# 需先设置 token
data = ball.industry_compare(symbol)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| symbol: 股票代码（如 SH600519） |

### 返回值
返回 dict，data 包含 avg（行业均值）、items（具体股票列表）
取行业均值用 result["data"]["avg"]["pe_ttm"]
取个股数据用 result["data"]["items"][0]["pe_ttm"]

## 数据更新时效描述
雪球实时行情数据为实时更新，K线数据日频更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| pe_ttm | float | 同行业公司PE中位数 | ? |
| pb | float | 同行业公司PB中位数 | ? |
| avg_roe | float | 同行业公司ROE中位数 | ? |

## 接口调用示例
```python
import pysnowball as ball
data = ball.industry_compare(symbol='SZ300750')
avg_pe = data['data']['avg']['pe_ttm']
print(avg_pe)
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ball.industry_compare(symbol) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **代码格式**：必须用 SH/SZ 前缀（如 `SZ300750`），`_xq_code()` 自动转换
2. **Token 配置**：需要在 `xueqiu_token.json` 中配置有效的 xq_a_token
3. **Token 过期**：雪球 token 有时效性，过期需要重新登录网页版获取
