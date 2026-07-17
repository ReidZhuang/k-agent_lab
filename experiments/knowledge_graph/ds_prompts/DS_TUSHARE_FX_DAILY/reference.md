# fx_daily — 外汇日线行情（FX Daily）

## 数据源名称
- **中文名称**：外汇日线行情
- **英文名称**：FX Daily
- **数据源ID**：DS_TUSHARE_FX_DAILY

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.fx_daily()  # 无参数，无需传任何内容`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
人民币外汇每日行情数据

## 数据内容覆盖业务描述
汇率分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，fx_daily 接口提供 外汇日线行情 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fx_daily(参数1=值1, 参数2=值2)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

**注意**：只传查询条件中有提供值的参数，绝对不要编造参数值。

### 返回值
函数返回 `pandas.DataFrame`，列名见下方输出数据描述。取最新一行用 `df.iloc[-1]`，按列名取值用 `row['列名']`。

## 数据更新时效描述
Tushare 数据更新频率因接口而异：日线行情通常T+1更新，实时数据盘中更新。具体取决于 Tushare 官方数据发布策略。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| trade_date | date | 交易日期（GMT） | ? |
| bid_open | float | 买入价开盘 | ? |
| ask_high | float | 卖出价最高 | ? |
| ts_code | string | 外汇货币对代码 | ? |
| ask_low | float | 卖出价最低 | ? |
| bid_high | float | 买入价最高 | ? |
| bid_close | float | 买入价收盘 | ? |
| ask_close | float | 卖出价收盘 | ? |
| ask_open | float | 卖出价开盘 | ? |
| bid_low | float | 买入价最低 | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fx_daily(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.fx_daily(...) 返回的 DataFrame
# 示例：columns = ['trade_date', 'bid_open', 'ask_high', 'ts_code', 'ask_low'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
7. **特别提醒**：直接调用 pro.fx_daily() 即可返回全量外汇日线数据
