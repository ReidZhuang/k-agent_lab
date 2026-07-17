# cb_issue — 可转债发行（CB Issue）

## 数据源名称
- **中文名称**：可转债发行
- **英文名称**：CB Issue
- **数据源ID**：DS_TUSHARE_CB_ISSUE

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.cb_issue()`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
可转债发行申购信息

## 数据内容覆盖业务描述
打新债分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，cb_issue 接口提供 可转债发行 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cb_issue(参数1=值1, 参数2=值2)
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
| offl_size | float | 网下发行总额（张） (列名:offl_size) | ? |
| shd_ration_size | float | 老股东配售数量（张） (列名:shd_ration_size) | ? |
| shd_ration_ratio | float | 老股东配售比例 (列名:shd_ration_ratio) | ? |
| shd_ration_price | float | 老股东配售价格 (列名:shd_ration_price) | ? |
| shd_ration_pay_date | str | 老股东配售缴款日 (列名:shd_ration_pay_date) | ? |
| shd_ration_record_date | str | 老股东配售股权登记日 (列名:shd_ration_record_date) | ? |
| shd_ration_date | str | 老股东配售日 (列名:shd_ration_date) | ? |
| shd_ration_name | str | 老股东配售简称 (列名:shd_ration_name) | ? |
| shd_ration_code | str | 老股东配售代码 (列名:shd_ration_code) | ? |
| onl_pch_excess | float | 网上发行超额认购倍数 (列名:onl_pch_excess) | ? |
| onl_pch_num | int | 网上发行有效申购户数 (列名:onl_pch_num) | ? |
| onl_pch_vol | float | 网上发行有效申购数量（张） (列名:onl_pch_vol) | ? |
| onl_size | float | 网上发行总额（张） (列名:onl_size) | ? |
| onl_date | str | 网上发行日期 (列名:onl_date) | ? |
| onl_name | str | 网上申购简称 (列名:onl_name) | ? |
| onl_code | str | 网上申购代码 (列名:onl_code) | ? |
| issue_type | str | 发行方式 (列名:issue_type) | ? |
| issue_price | float | 发行价格 (列名:issue_price) | ? |
| issue_size | float | 发行总额（元） (列名:issue_size) | ? |
| plan_issue_size | float | 计划发行总额（元） (列名:plan_issue_size) | ? |
| res_ann_date | str | 发行结果公告日 (列名:res_ann_date) | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cb_issue(ts_code='000001.SZ')
print(df.head(10))
```

## 调用返回值样例
```
# pro.cb_issue(...) 返回的 DataFrame
# 示例：columns = ['offl_size', 'shd_ration_size', 'shd_ration_ratio', 'shd_ration_price', 'shd_ration_pay_date'] (前5列)
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
