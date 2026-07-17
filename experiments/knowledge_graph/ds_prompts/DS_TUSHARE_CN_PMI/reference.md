# cn_pmi — PMI数据（CN PMI）

## 数据源名称
- **中文名称**：PMI数据
- **英文名称**：CN PMI
- **数据源ID**：DS_TUSHARE_CN_PMI

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.cn_pmi(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
中国采购经理人指数（PMI）

## 数据内容覆盖业务描述
制造业景气度分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，cn_pmi 接口提供 PMI数据 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_pmi(参数1=值1, 参数2=值2)
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
| PMI020401 | float | PMI020401 | ? |
| PMI010702 | float | PMI010702 | ? |
| PMI010503 | float | PMI010503 | ? |
| PMI011600 | float | PMI011600 | ? |
| PMI010500 | float | PMI010500 | ? |
| PMI010200 | float | PMI010200 | ? |
| PMI020502 | float | PMI020502 | ? |
| PMI020202 | float | PMI020202 | ? |
| PMI020200 | float | PMI020200 | ? |
| PMI010603 | float | PMI010603 | ? |
| PMI010601 | float | PMI010601 | ? |
| PMI010000 | float | PMI010000 | ? |
| UPDATE_BY | float | UPDATE_BY | ? |
| UPDATE_TIME | float | UPDATE_TIME | ? |
| PMI020600 | float | PMI020600 | ? |
| PMI010802 | float | PMI010802 | ? |
| PMI011400 | float | PMI011400 | ? |
| PMI020500 | float | PMI020500 | ? |
| PMI020501 | float | PMI020501 | ? |
| PMI010602 | float | PMI010602 | ? |
| PMI010800 | float | PMI010800 | ? |
| PMI011100 | float | PMI011100 | ? |
| PMI011200 | float | PMI011200 | ? |
| PMI010100 | float | PMI010100 | ? |
| PMI010400 | float | PMI010400 | ? |
| PMI010403 | float | PMI010403 | ? |
| PMI010801 | float | PMI010801 | ? |
| PMI020602 | float | PMI020602 | ? |
| PMI021000 | float | PMI021000 | ? |
| PMI010703 | float | PMI010703 | ? |
| PMI011800 | float | PMI011800 | ? |
| PMI010501 | float | PMI010501 | ? |
| PMI010900 | float | PMI010900 | ? |
| PMI011300 | float | PMI011300 | ? |
| PMI011700 | float | PMI011700 | ? |
| PMI010700 | float | PMI010700 | ? |
| PMI010803 | float | PMI010803 | ? |
| PMI011500 | float | PMI011500 | ? |
| PMI020100 | float | PMI020100 | ? |
| CREATE_BY | float | CREATE_BY | ? |
| MONTH | float | MONTH | ? |
| PMI020201 | float | PMI020201 | ? |
| PMI020402 | float | PMI020402 | ? |
| PMI020700 | float | PMI020700 | ? |
| PMI020800 | float | PMI020800 | ? |
| PMI010402 | float | PMI010402 | ? |
| PMI020101 | float | PMI020101 | ? |
| PMI020301 | float | PMI020301 | ? |
| PMI020302 | float | PMI020302 | ? |
| PMI020601 | float | PMI020601 | ? |
| PMI010502 | float | PMI010502 | ? |
| PMI012000 | float | PMI012000 | ? |
| PMI010701 | float | PMI010701 | ? |
| PMI020102 | float | PMI020102 | ? |
| PMI020300 | float | PMI020300 | ? |
| PMI030000 | float | PMI030000 | ? |
| CREATE_TIME | float | CREATE_TIME | ? |
| PMI010401 | float | PMI010401 | ? |
| PMI010600 | float | PMI010600 | ? |
| PMI011900 | float | PMI011900 | ? |
| PMI020400 | float | PMI020400 | ? |
| PMI020900 | float | PMI020900 | ? |
| ID | float | ID | ? |
| PMI010300 | float | PMI010300 | ? |
| PMI011000 | float | PMI011000 | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_pmi(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.cn_pmi(...) 返回的 DataFrame
# 示例：columns = ['PMI020401', 'PMI010702', 'PMI010503', 'PMI011600', 'PMI010500'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
