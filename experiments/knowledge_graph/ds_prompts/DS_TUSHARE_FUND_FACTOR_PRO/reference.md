# fund_factor_pro — 基金因子（Fund Factor Pro）

## 数据源名称
- **中文名称**：基金因子
- **英文名称**：Fund Factor Pro
- **数据源ID**：DS_TUSHARE_FUND_FACTOR_PRO

## 接口
- **类型**：Tushare Pro API（A类）
- **函数签名**：`pro.fund_factor_pro(ts_code, start_date, end_date)`
- **SDK**：`import tushare as ts; pro = ts.pro_api()`
- **认证方式**：需设置 `TUSHARE_TOKEN` 环境变量（`ts.set_token(os.getenv('TUSHARE_TOKEN'))`）

## 数据内容描述
基金多维因子数据

## 数据内容覆盖业务描述
基金量化评估

## 数据接口背景描述（若有）
Tushare 是国内主流的金融数据平台之一，fund_factor_pro 接口提供 基金因子 数据。Tushare 的 Pro API 基于 pandas DataFrame 返回，使用简单。需在 [tushare.pro](https://tushare.pro) 注册获取 token。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import os, tushare as ts
import pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fund_factor_pro(参数1=值1, 参数2=值2)
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
| ktn_upper_bfq | float | ktn_upper_bfq | ? |
| xsii_td4_bfq | float | xsii_td4_bfq | ? |
| xsii_td3_bfq | float | xsii_td3_bfq | ? |
| xsii_td2_bfq | float | xsii_td2_bfq | ? |
| xsii_td1_bfq | float | xsii_td1_bfq | ? |
| wr1_bfq | float | wr1_bfq | ? |
| wr_bfq | float | wr_bfq | ? |
| vr_bfq | float | vr_bfq | ? |
| trma_bfq | float | trma_bfq | ? |
| trix_bfq | float | trix_bfq | ? |
| taq_up_bfq | float | taq_up_bfq | ? |
| taq_mid_bfq | float | taq_mid_bfq | ? |
| taq_down_bfq | float | taq_down_bfq | ? |
| rsi_bfq_6 | float | rsi_bfq_6 | ? |
| rsi_bfq_24 | float | rsi_bfq_24 | ? |
| rsi_bfq_12 | float | rsi_bfq_12 | ? |
| maroc_bfq | float | maroc_bfq | ? |
| roc_bfq | float | roc_bfq | ? |
| psyma_bfq | float | psyma_bfq | ? |
| psy_bfq | float | psy_bfq | ? |
| obv_bfq | float | obv_bfq | ? |
| mtmma_bfq | float | mtmma_bfq | ? |
| mtm_bfq | float | mtm_bfq | ? |
| mfi_bfq | float | mfi_bfq | ? |
| ma_mass_bfq | float | ma_mass_bfq | ? |
| mass_bfq | float | mass_bfq | ? |
| macd_dif_bfq | float | macd_dif_bfq | ? |
| macd_dea_bfq | float | macd_dea_bfq | ? |
| macd_bfq | float | macd_bfq | ? |
| ma_bfq_90 | float | ma_bfq_90 | ? |
| ma_bfq_60 | float | ma_bfq_60 | ? |
| ma_bfq_5 | float | ma_bfq_5 | ? |
| ma_bfq_30 | float | ma_bfq_30 | ? |
| ma_bfq_250 | float | ma_bfq_250 | ? |
| ma_bfq_20 | float | ma_bfq_20 | ? |
| ma_bfq_10 | float | ma_bfq_10 | ? |
| topdays | float | topdays | ? |
| lowdays | float | lowdays | ? |
| trade_date_doris | float | trade_date_doris | ? |
| open | float | open | ? |
| high | float | high | ? |
| low | float | low | ? |
| close | float | close | ? |
| pre_close | float | pre_close | ? |
| change | float | change | ? |
| pct_change | float | pct_change | ? |
| vol | float | vol | ? |
| amount | float | amount | ? |
| asi_bfq | float | asi_bfq | ? |
| asit_bfq | float | asit_bfq | ? |
| atr_bfq | float | atr_bfq | ? |
| bbi_bfq | float | bbi_bfq | ? |
| bias1_bfq | float | bias1_bfq | ? |
| bias2_bfq | float | bias2_bfq | ? |
| bias3_bfq | float | bias3_bfq | ? |
| boll_lower_bfq | float | boll_lower_bfq | ? |
| boll_mid_bfq | float | boll_mid_bfq | ? |
| boll_upper_bfq | float | boll_upper_bfq | ? |
| brar_ar_bfq | float | brar_ar_bfq | ? |
| brar_br_bfq | float | brar_br_bfq | ? |
| cci_bfq | float | cci_bfq | ? |
| cr_bfq | float | cr_bfq | ? |
| dfma_dif_bfq | float | dfma_dif_bfq | ? |
| dfma_difma_bfq | float | dfma_difma_bfq | ? |
| dmi_adx_bfq | float | dmi_adx_bfq | ? |
| dmi_adxr_bfq | float | dmi_adxr_bfq | ? |
| dmi_mdi_bfq | float | dmi_mdi_bfq | ? |
| dmi_pdi_bfq | float | dmi_pdi_bfq | ? |
| downdays | float | downdays | ? |
| updays | float | updays | ? |
| dpo_bfq | float | dpo_bfq | ? |
| madpo_bfq | float | madpo_bfq | ? |
| ema_bfq_10 | float | ema_bfq_10 | ? |
| ema_bfq_20 | float | ema_bfq_20 | ? |
| ema_bfq_250 | float | ema_bfq_250 | ? |
| ema_bfq_30 | float | ema_bfq_30 | ? |
| ema_bfq_5 | float | ema_bfq_5 | ? |
| ema_bfq_60 | float | ema_bfq_60 | ? |
| ema_bfq_90 | float | ema_bfq_90 | ? |
| emv_bfq | float | emv_bfq | ? |
| maemv_bfq | float | maemv_bfq | ? |
| expma_12_bfq | float | expma_12_bfq | ? |
| expma_50_bfq | float | expma_50_bfq | ? |
| kdj_bfq | float | kdj_bfq | ? |
| kdj_d_bfq | float | kdj_d_bfq | ? |
| kdj_k_bfq | float | kdj_k_bfq | ? |
| ktn_down_bfq | float | ktn_down_bfq | ? |
| ktn_mid_bfq | float | ktn_mid_bfq | ? |

## 接口调用示例
```python
import os, tushare as ts, pandas as pd
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
df = pro.fund_factor_pro(ts_code='000001.SZ', start_date='20260701', end_date='20260715')
print(df.head(10))
```

## 调用返回值样例
```
# pro.fund_factor_pro(...) 返回的 DataFrame
# 示例：columns = ['ktn_upper_bfq', 'xsii_td4_bfq', 'xsii_td3_bfq', 'xsii_td2_bfq', 'xsii_td1_bfq'] (前5列)
# 实际数据取决于调用参数和当前日期
```

## 取数时容易出现的坑
1. **Token超限**：Tushare 有积分和调用频率限制，高频调用会被限流
2. **参数不传空**：不需要的参数不要传，不要编造默认值
3. **代码格式**：股票代码必须带交易所后缀（如 `000001.SZ`、`600519.SH`）
4. **DataFrame格式**：返回直接是 DataFrame（不是 `.data` 属性），直接用列名取值
5. **日期格式**：一律用 `YYYYMMDD` 格式，不要用带分隔符的格式
6. **空数据**：非交易日或未来日期返回空 DataFrame，需要做判空处理
