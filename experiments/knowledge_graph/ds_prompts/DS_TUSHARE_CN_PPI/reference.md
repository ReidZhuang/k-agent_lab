# cn_ppi — PPI数据（CN PPI）

## 数据源名称
- **中文名称**：PPI数据
- **英文名称**：CN PPI
- **数据源ID**：DS_TUSHARE_CN_PPI

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.cn_ppi(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
中国工业生产者出厂价格指数（PPI）

## 数据内容覆盖业务描述
工业品价格分析

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，cn_ppi 接口提供 PPI数据 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_ppi(参数1=值1, 参数2=值2)
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
| ppi_cg_dcg_accu | float | PPI：生活资料：耐用消费品类：累计同比 | ? |
| ppi_cg_adu_accu | float | PPI：生活资料：一般日用品类：累计同比 | ? |
| ppi_cg_c_accu | float | PPI：生活资料：衣着类：累计同比 | ? |
| ppi_cg_f_accu | float | PPI：生活资料：食品类：累计同比 | ? |
| ppi_cg_accu | float | PPI：生活资料：累计同比 | ? |
| ppi_mp_p_accu | float | PPI：生产资料：加工业：累计同比 | ? |
| ppi_mp_rm_accu | float | PPI：生产资料：原料业：累计同比 | ? |
| ppi_mp_qm_accu | float | PPI：生产资料：采掘业：累计同比 | ? |
| ppi_mp_accu | float | PPI：生产资料：累计同比 | ? |
| ppi_accu | float | PPI：全部工业品：累计同比 | ? |
| ppi_cg_dcg_mom | float | PPI：生活资料：耐用消费品类：环比 | ? |
| ppi_cg_adu_mom | float | PPI：生活资料：一般日用品类：环比 | ? |
| ppi_cg_c_mom | float | PPI：生活资料：衣着类：环比 | ? |
| ppi_cg_f_mom | float | PPI：生活资料：食品类：环比 | ? |
| ppi_cg_mom | float | PPI：生活资料：环比 | ? |
| ppi_mp_p_mom | float | PPI：生产资料：加工业：环比 | ? |
| ppi_mp_rm_mom | float | PPI：生产资料：原料业：环比 | ? |
| ppi_mp_qm_mom | float | PPI：生产资料：采掘业：环比 | ? |
| ppi_mp_mom | float | PPI：生产资料：环比 | ? |
| ppi_mom | float | PPI：全部工业品：环比 | ? |
| ppi_cg_dcg_yoy | float | PPI：生活资料：耐用消费品类：当月同比 | ? |
| ppi_cg_adu_yoy | float | PPI：生活资料：一般日用品类：当月同比 | ? |
| ppi_cg_c_yoy | float | PPI：生活资料：衣着类：当月同比 | ? |
| ppi_cg_f_yoy | float | PPI：生活资料：食品类：当月同比 | ? |
| ppi_cg_yoy | float | PPI：生活资料：当月同比 | ? |
| ppi_mp_p_yoy | float | PPI：生产资料：加工业：当月同比 | ? |
| ppi_mp_rm_yoy | float | PPI：生产资料：原料业：当月同比 | ? |
| ppi_mp_qm_yoy | float | PPI：生产资料：采掘业：当月同比 | ? |
| ppi_mp_yoy | float | PPI：生产资料：当月同比 | ? |
| ppi_yoy | float | PPI：全部工业品：当月同比 | ? |
| month | str | 月份YYYYMM | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.cn_ppi(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.cn_ppi(...) 返回的 DataFrame
# 示例：columns = ['ppi_cg_dcg_accu', 'ppi_cg_adu_accu', 'ppi_cg_c_accu', 'ppi_cg_f_accu', 'ppi_cg_accu'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
