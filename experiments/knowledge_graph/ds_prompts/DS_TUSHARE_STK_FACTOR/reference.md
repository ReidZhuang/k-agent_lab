# stk_factor — 个股技术因子（Stock Factor）

## 数据源名称
- **中文名称**：个股技术因子
- **英文名称**：Stock Factor
- **数据源ID**：DS_TUSHARE_STK_FACTOR

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.stk_factor(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
个股技术分析因子数据

## 数据内容覆盖业务描述
量化因子计算

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，stk_factor 接口提供 个股技术因子 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.stk_factor(参数1=值1, 参数2=值2)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| ts_code | 视情况 | str | 股票代码（如 000001.SZ、600519.SH），见路由条件 |
| start_date | 视情况 | str | 起始日期 YYYYMMDD，见路由条件中的时间范围 |
| end_date | 视情况 | str | 结束日期 YYYYMMDD，见路由条件中的时间范围 |

**注意**：只传查询条件中有提供值的参数，绝对不要编造参数值。

### 返回值
函数返回 `pandas.DataFrame`，列名见下方输出数据描述。取最新一行用 `df.iloc[-1]`，按列名取值用 `row['列名']`。

## 数据更新时效描述
Tushare 数据更新频率因接口而异：日线行情通常T+1更新，实时数据盘中更新。具体取决于 Tushare 官方数据发布策略。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| pre_close_qfq | float | pre_close_qfq | ? |
| pre_close_hfq | float | pre_close_hfq | ? |
| low_qfq | float | low_qfq | ? |
| low_hfq | float | low_hfq | ? |
| high_qfq | float | high_qfq | ? |
| high_hfq | float | high_hfq | ? |
| close_qfq | float | close_qfq | ? |
| close_hfq | float | close_hfq | ? |
| open_qfq | float | open_qfq | ? |
| open_hfq | float | open_hfq | ? |
| adj_factor | float | adj_factor | ? |
| amount | float | amount | ? |
| vol | float | vol | ? |
| pct_change | float | pct_change | ? |
| change | float | change | ? |
| pre_close | float | pre_close | ? |
| low | float | low | ? |
| high | float | high | ? |
| open | float | open | ? |
| close | float | close | ? |
| boll_upper | float | 布林线上轨 | ? |
| cci | float | 顺势指标 | ? |
| macd_dea | float | MACD指标DEA线 | ? |
| rsi_12 | float | 12日相对强弱指标 | ? |
| macd | float | MACD柱状线 | ? |
| boll_lower | float | 布林线下轨 | ? |
| kdj_k | float | KDJ指标K值 | ? |
| boll_mid | float | 布林线中轨 | ? |
| macd_dif | float | MACD指标DIF线 | ? |
| rsi_24 | float | 24日相对强弱指标 | ? |
| rsi_6 | float | 6日相对强弱指标 | ? |
| kdj_d | float | KDJ指标D值 | ? |
| kdj_j | float | KDJ指标J值 | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.stk_factor(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.stk_factor(...) 返回的 DataFrame
# 示例：columns = ['pre_close_qfq', 'pre_close_hfq', 'low_qfq', 'low_hfq', 'high_qfq'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
