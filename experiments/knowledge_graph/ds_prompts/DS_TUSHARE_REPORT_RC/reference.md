# report_rc — 研报数据（Report RC）

## 数据源名称
- **中文名称**：研报数据
- **英文名称**：Report RC
- **数据源ID**：DS_TUSHARE_REPORT_RC

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.report_rc(ts_code)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
券商研究报告覆盖及评级数据

## 数据内容覆盖业务描述
研报舆情、分析师评级追踪

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，report_rc 接口提供 研报数据 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.report_rc(参数1=值1, 参数2=值2)
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
| ev_ebitda | float | ev_ebitda | ? |
| rd | float | rd | ? |
| pe | float | pe | ? |
| np | float | np | ? |
| tp | float | tp | ? |
| op_pr | float | op_pr | ? |
| op_rt | float | op_rt | ? |
| quarter | float | quarter | ? |
| author_name | float | author_name | ? |
| classify | float | classify | ? |
| report_type | float | report_type | ? |
| name | float | name | ? |
| report_title | string | 研报标题 (列名:report_title) | ? |
| org_name | string | 研究机构名称 (列名:org_name) | ? |
| eps | float | 券商预测每股收益 (列名:eps) | ? |
| min_price | float | 券商预测最低目标价 (列名:min_price) | ? |
| max_price | float | 券商预测最高目标价 (列名:max_price) | ? |
| roe | float | 券商预测净资产收益率 (列名:roe) | ? |
| report_date | date | 研报发布日期 (列名:report_date) | ? |
| rating | string | 券商评级（买入/增持/中性等） (列名:rating) | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.report_rc(ts_code='000001.SZ')
print(df.head(10))
```

## 调用返回值样例
```
# pro.report_rc(...) 返回的 DataFrame
# 示例：columns = ['ev_ebitda', 'rd', 'pe', 'np', 'tp'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
7. **特别提醒**：只传 ts_code，不要传日期参数
