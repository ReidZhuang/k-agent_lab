# DS_TUSHARE_CB_CALL 字段映射

| 字段名 | 类型 | 说明 |
|--------|:----:|:-----|
| call_reg_date | str | 赎回登记日 |
| payment_date | str | 行权后款项到账日 |
| call_amount | float | 赎回金额(万元) |
| call_vol | float | 赎回债券数量(张) |
| call_price_tax | float | 赎回价格(扣税，元/张) |
| call_price | float | 赎回价格(含税，元/张) |
| call_date | str | 赎回日期 |
| is_call | str | 是否赎回：已满足强赎条件、公告提示强赎、公告实施强赎、公告到期赎回、公告不强赎 |
| call_type | str | 赎回类型：到赎、强赎 |
