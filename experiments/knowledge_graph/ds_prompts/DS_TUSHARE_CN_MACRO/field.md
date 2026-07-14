## 字段映射
| 字段名 | 类型 | 说明 | 数据示例 |
|--------|:----:|:-----|:--------:|
| quarter | str | 季度 | — |
| gdp | float | GDP 累计值 | — |
| pi | float | 第一产业累计值 | — |
| si | float | 第二产业累计值 | — |
| ti | float | 第三产业累计值 | — |
| gdp_yoy | float | GDP 当季同比 | — |
| cnt_val | float | CPI 当月值 | — |
| cnt_yoy | float | CPI 同比 | — |
| cnt_mom | float | CPI 环比 | — |
| ppi_yoy | float | PPI 同比 | — |
| ppi_mom | float | PPI 环比 | — |
| m0 | float | M0 | — |
| m1 | float | M1 | — |
| m2 | float | M2 | — |
| m2_yoy | float | M2 同比 | — |
| inc_month | float | 社融增量 | — |
| inc_cumval | float | 社融累计值 | — |
| stk_endval | float | 社融存量 | — |

## 子表
| 函数 | 参数 | 说明 |
|:----|:-----|:------|
| pro.cn_gdp | quarter | GDP |
| pro.cn_cpi | month | CPI |
| pro.cn_ppi | month | PPI |
| pro.cn_pmi | month | PMI |
| pro.cn_m | month | M0/M1/M2 |
