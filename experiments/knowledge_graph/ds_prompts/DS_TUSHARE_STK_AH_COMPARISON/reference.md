# stk_ah_comparison — AH股比价（AH Comparison）

## 数据源名称
- **中文名称**：AH股比价
- **英文名称**：AH Comparison
- **数据源ID**：DS_TUSHARE_STK_AH_COMPARISON

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.stk_ah_comparison()`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
A+H股溢价率对比数据

## 数据内容覆盖业务描述
AH股套利分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，stk_ah_comparison 接口提供 AH股比价 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.stk_ah_comparison(参数1=值1, 参数2=值2)
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
| ah_premium | float | 溢价(A/H)% | ? |
| ah_comparison | float | 比价(A/H) | ? |
| pct_chg | float | A股股票涨跌幅 | ? |
| close | float | A股股票收盘价 | ? |
| name | str | A股股票名称 | ? |
| hk_close | float | 港股股票收盘价 | ? |
| hk_pct_chg | float | 港股股票涨跌幅 | ? |
| hk_name | str | 港股股票名称 | ? |
| hk_code | str | 港股股票代码 | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.stk_ah_comparison(ts_code='000001.SZ')
print(df.head(10))
```

## 调用返回值样例
```
# pro.stk_ah_comparison(...) 返回的 DataFrame
# 示例：columns = ['ah_premium', 'ah_comparison', 'pct_chg', 'close', 'name'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
7. **特别提醒**：无参数，直接调用即可。不要传日期参数。
