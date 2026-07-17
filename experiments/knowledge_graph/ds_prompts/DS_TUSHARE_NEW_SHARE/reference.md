# new_share — 新股数据（New Share）

## 数据源名称
- **中文名称**：新股数据
- **英文名称**：New Share
- **数据源ID**：DS_TUSHARE_NEW_SHARE

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.new_share(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
新股发行上市数据，包括发行价、中签率等

## 数据内容覆盖业务描述
新股申购分析、打新策略

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，new_share 接口提供 新股数据 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.new_share(参数1=值1, 参数2=值2)
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
| sub_code | float | sub_code | ? |
| ballot | float | 网上发行中签率 | ? |
| name | string | 新股名称 | ? |
| issue_date | date | 正式上市日期 | ? |
| price | float | 首次公开发行价格 | ? |
| ipo_date | date | 网上发行日期 | ? |
| amount | float | 发行总量（万股） | ? |
| pe | float | 发行市盈率 | ? |
| ts_code | string | 新股上市代码 | ? |
| limit_amount | float | 个人申购上限（万股） | ? |
| market_amount | float | 网上发行量（万股） | ? |
| funds | float | 募集资金总额（亿元） | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.new_share(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.new_share(...) 返回的 DataFrame
# 示例：columns = ['sub_code', 'ballot', 'name', 'issue_date', 'price'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
