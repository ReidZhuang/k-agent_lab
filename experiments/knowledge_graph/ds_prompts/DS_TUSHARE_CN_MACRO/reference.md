# cn_macro/多表 — 宏观指标（CN Macro）

## 数据源名称
- **中文名称**：宏观指标
- **英文名称**：CN Macro
- **数据源ID**：DS_TUSHARE_CN_MACRO

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.cn_macro/多表(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
中国宏观经济指标数据，含多张子表

## 数据内容覆盖业务描述
宏观经济分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，cn_macro/多表 接口提供 宏观指标 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_macro/多表(参数1=值1, 参数2=值2)
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
| 综合PMI | float | 综合PMI产出指数 | ? |
| cnt_mom | float | CPI当月环比增速 | ? |
| cnt_val | float | 全国CPI当月值 | ? |
| cnt_yoy | float | CPI当月同比增速 | ? |
| gdp | float | 国内生产总值累计值 | ? |
| pi | float | 第一产业GDP累计值 | ? |
| si | float | 第二产业GDP累计值 | ? |
| ti | float | 第三产业GDP累计值 | ? |
| gdp_yoy | float | GDP当季同比增速 | ? |
| m0 | float | 流通中现金（亿元） | ? |
| m1 | float | 狭义货币供应量（亿元） | ? |
| m2 | float | 广义货币供应量（亿元） | ? |
| m2_yoy | float | M2同比增速 | ? |
| 非制造业PMI | float | 非制造业商务活动指数 | ? |
| PMI010000 | float | 制造业PMI指数 | ? |
| PMI020100 | float | 大型企业PMI | ? |
| PMI020200 | float | 中型企业PMI | ? |
| PMI010200 | float | PMI新订单指数 | ? |
| PMI010100 | float | PMI生产指数 | ? |
| PMI020300 | float | 小型企业PMI | ? |
| ppi_mom | float | PPI当月环比增速 | ? |
| ppi_yoy | float | PPI当月同比增速 | ? |
| quarter | string | 数据对应的季度 | ? |
| inc_cumval | float | 社融累计值（亿元） | ? |
| inc_month | float | 当月社融增量（亿元） | ? |
| stk_endval | float | 社融存量（万亿元） | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_macro/多表(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.cn_macro/多表(...) 返回的 DataFrame
# 示例：columns = ['综合PMI', 'cnt_mom', 'cnt_val', 'cnt_yoy', 'gdp'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
