# pledge_detail — 股权质押明细（Pledge Detail）

## 数据源名称
- **中文名称**：股权质押明细
- **英文名称**：Pledge Detail
- **数据源ID**：DS_TUSHARE_PLEDGE

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.pledge_detail(ts_code)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
上市公司股权质押明细数据

## 数据内容覆盖业务描述
质押风险排查

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，pledge_detail 接口提供 股权质押明细 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.pledge_detail(参数1=值1, 参数2=值2)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| ts_code | 视情况 | str | 股票代码（如 000001.SZ、600519.SH），见路由条件 |

**注意**：只传查询条件中有提供值的参数，绝对不要编造参数值。

### 返回值
函数返回 `pandas.DataFrame`，列名见下方输出数据描述。取最新一行用 `df.iloc[-1]`，按列名取值用 `row['列名']`。

## 数据更新时效描述
Tushare 数据更新频率因接口而异：日线行情通常T+1更新，实时数据盘中更新。具体取决于 Tushare 官方数据发布策略。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| is_buyback | float | is_buyback | ? |
| h_total_ratio | float | h_total_ratio | ? |
| p_total_ratio | float | p_total_ratio | ? |
| pledged_amount | float | pledged_amount | ? |
| holding_amount | float | holding_amount | ? |
| release_date | float | release_date | ? |
| pledge_amount | float | 质押股票数量（万股） (列名:pledge_amount) | ? |
| end_date | date | 质押结束日期 (列名:end_date) | ? |
| holder_name | string | 质押股东名称 (列名:holder_name) | ? |
| is_release | string | 是否已解押（Y/N） (列名:is_release) | ? |
| pledgor | string | 质押接受方机构 (列名:pledgor) | ? |
| start_date | date | 质押开始日期 (列名:start_date) | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.pledge_detail(ts_code='000001.SZ')
print(df.head(10))
```

## 调用返回值样例
```
# pro.pledge_detail(...) 返回的 DataFrame
# 示例：columns = ['is_buyback', 'h_total_ratio', 'p_total_ratio', 'pledged_amount', 'holding_amount'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
