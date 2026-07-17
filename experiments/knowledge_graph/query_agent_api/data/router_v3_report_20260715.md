# agent_router v3 双检索测试报告

**模型**: qwen2.5:7b
**日期**: 2026-07-15
**结果**: 32 用例, 全部通过

| # | ID | Var | Obj | 匹配字段 | 中文名 | scope | alias级别 | 协议 |
|---|-----|-----|-----|---------|--------|-------|----------|------|
| 1 | RR-01 | 涨跌幅 | 宁德时代 | FIELD_QUOTE_PCT_CHG | 涨跌幅 | 实时,个股级别 | --- | --- |
| 2 | RR-02 | 成交量 | 贵州茅台 | FIELD_QUOTE_VOL | 成交量 | 实时,个股级别 | --- | --- |
| 3 | RR-03 | 涨跌幅 | 上证指数 | FIELD_INDEX_PCT_CHG | 涨跌幅 | 日频,指数级别 | --- | --- |
| 4 | RR-04 | 板块涨跌幅 | 电池板块 | FIELD_SECTOR_PCT_CHG | 板块涨跌幅 | 日频,板块级别 | --- | --- |
| 5 | RR-05 | 最高价 | 宁德时代 | FIELD_QUOTE_HIGH | 最高价 | 实时,个股级别 | --- | --- |
| 6 | RR-06 | 换手率 | 宁德时代 | FIELD_TURNOVER_RATE | 换手率 | 实时,个股级别 | --- | --- |
| 7 | RR-07 | 市盈率 | 中国平安 | FIELD_PE_TTM | 市盈率TTM | 日频,个股级别 | --- | --- |
| 8 | RR-08 | 板块 | 宁德时代 | FIELD_SECTOR_NAME | 板块名称 | 日频,板块级别 | --- | --- |
| 9 | RR-09 | 涨跌幅 | 宁德时代 | FIELD_QUOTE_PCT_CHG | 涨跌幅 | 实时,个股级别 | --- | --- |
| 10 | RR-10 | 资金流向 | 北向资金 | FIELD_NORTH_NET | 北向资金净流入 | 日频,市场级别 | --- | --- |
| 11 | RR-11 | 收盘价 | 恒生指数 | FIELD_INDEX_PRICE | 当前点位 | 日频,指数级别 | --- | --- |
| 12 | RR-12 | 股价 | 宁德时代 | FIELD_QUOTE_CHG | 涨跌额 | 实时,个股级别 | --- | --- |
| 13 | RR-13 | 最低价 | 万科A | FIELD_QUOTE_LOW | 最低价 | 实时,个股级别 | --- | --- |
| 14 | RR-14 | 开盘价 | 格力电器 | FIELD_QUOTE_OPEN | 开盘价 | 实时,个股级别 | --- | --- |
| 15 | RR-15 | 成交额 | 东方财富 | FIELD_QUOTE_AMOUNT | 成交额 | 实时,个股级别 | --- | --- |
| 16 | RR-16 | 涨跌额 | 中国平安 | FIELD_QUOTE_CHG | 涨跌额 | 实时,个股级别 | --- | --- |
| 17 | RR-17 | 每股净资产 | 招商银行 | FIELD_FIN_BPS | 每股净资产 | 季频,个股级别 | --- | --- |
| 18 | RR-18 | 市净率 | 海康威视 | FIELD_PB | 市净率 | 实时,个股级别 | --- | --- |
| 19 | RR-19 | 股息率 | 大秦铁路 | FIELD_DIVIDEND_YIELD | 股息率 | 日频,个股级别 | --- | --- |
| 20 | RR-20 | 板块成交额 | 半导体板块 | FIELD_SECTOR_AMOUNT | 板块成交额 | 日频,板块级别 | --- | --- |
| 21 | RR-21 | 板块振幅 | 银行板块 | FIELD_SECTOR_AMPLITUDE | 板块振幅 | 日频,板块级别 | --- | --- |
| 22 | RR-22 | 行业平均PE | 银行板块 | FIELD_VAL_IND_PE | 行业平均PE | 季频,行业级别 | --- | --- |
| 23 | RR-23 | 行业平均ROE | 白酒板块 | FIELD_VAL_IND_ROE | 行业平均ROE | 季频,行业级别 | --- | --- |
| 24 | RR-24 | 综合PMI | 中国 | FIELD_MACRO_COMPOSITE_PMI | 综合PMI | 月频,国家级别 | --- | --- |
| 25 | RR-25 | CPI环比 | 中国 | FIELD_MACRO_CPI_MOM | CPI环比 | 月频,国家级别 | --- | --- |
| 26 | RR-26 | 北向资金净流入 | 贵州茅台 | FIELD_NORTH_NET | 北向资金净流入 | 日频,市场级别 | --- | --- |
| 27 | RR-27 | 指数成交量 | 创业板指 | FIELD_INDEX_VOL | 成交量 | 日频,指数级别 | --- | --- |
| 28 | RR-28 | 指数涨跌幅 | 科创50 | FIELD_INDEX_PCT_CHG | 涨跌幅 | 日频,指数级别 | --- | --- |
| 29 | RR-29 | K线收盘价 | 五粮液 | FIELD_KLINE_CLOSE | 收盘价 | 日频,个股级别 | --- | --- |
| 30 | RR-30 | 应收账款周转率 | 海康威视 | FIELD_FIN_AR_TURN | 应收账款周转率 | 季频,个股级别 | --- | --- |
| 31 | RR-31 | 涨跌额 | 比亚迪 | FIELD_QUOTE_CHG | 涨跌额 | 实时,个股级别 | --- | --- |
| 32 | RR-32 | 每股收益 | 交通银行 | FIELD_FS_BASIC_EPS | 基本每股收益 | 季频,个股级别 | --- | --- |

## 详细输出

### RR-01: var=涨跌幅, obj=['宁德时代']

- **匹配字段**: FIELD_QUOTE_PCT_CHG
- **中文名**: 涨跌幅
- **description**: 当日涨跌幅百分比
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["涨跌幅"], "qualified": ["个股涨跌幅", "实时涨跌幅"], "business_tag": ["个股波动", "股价涨幅", "日内波动"], "synonyms": ["涨幅", "跌幅", "涨跌百分比", "股价涨跌", "涨跌幅度"]}
- **选择用时**: 3.8s
- **候选数**: 8

### RR-02: var=成交量, obj=['贵州茅台']

- **匹配字段**: FIELD_QUOTE_VOL
- **中文名**: 成交量
- **description**: 当日成交量（手）
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["成交量"], "qualified": ["个股成交量", "实时成交量"], "business_tag": ["成交活跃度", "量能", "换手规模"], "synonyms": ["成交股数", "交易量", "成交手数", "量"]}
- **选择用时**: 1.5s
- **候选数**: 7

### RR-03: var=涨跌幅, obj=['上证指数']

- **匹配字段**: FIELD_INDEX_PCT_CHG
- **中文名**: 涨跌幅
- **description**: 指数涨跌幅百分比
- **granularity**: 日频,指数级别
- **alias**: {"simple": ["涨跌幅"], "qualified": ["指数涨跌幅", "指数涨幅"], "business_tag": ["大盘晴雨表", "市场温度计", "指数波动率"], "synonyms": ["涨幅", "跌幅", "涨跌百分比", "指数涨跌", "涨跌幅度"]}
- **选择用时**: 1.7s
- **候选数**: 8

### RR-04: var=板块涨跌幅, obj=['电池板块']

- **匹配字段**: FIELD_SECTOR_PCT_CHG
- **中文名**: 板块涨跌幅
- **description**: 板块指数涨跌幅
- **granularity**: 日频,板块级别
- **alias**: {"simple": ["涨跌幅"], "qualified": ["板块涨跌幅", "行业板块涨幅"], "business_tag": ["行业晴雨表", "板块热度", "概念波动"], "synonyms": ["板块涨幅", "行业涨幅", "概念涨幅", "板块涨跌"]}
- **选择用时**: 0.8s
- **候选数**: 3

### RR-05: var=最高价, obj=['宁德时代']

- **匹配字段**: FIELD_QUOTE_HIGH
- **中文名**: 最高价
- **description**: 当日最高价
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["最高价"], "qualified": ["个股最高价", "实时高点"], "business_tag": ["日内高点", "当日最高", "峰值价格"], "synonyms": ["最高", "日内最高", "今日高点", "盘面高点"]}
- **选择用时**: 1.0s
- **候选数**: 6

### RR-06: var=换手率, obj=['宁德时代']

- **匹配字段**: FIELD_TURNOVER_RATE
- **中文名**: 换手率
- **description**: 流通股本换手率
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["换手率"], "qualified": ["个股换手率", "流通换手"], "business_tag": ["交易活跃度", "换手水平", "流动性指标"], "synonyms": ["换手", "流通换手", "换手比率", "交易换手"]}
- **选择用时**: 1.0s
- **候选数**: 4

### RR-07: var=市盈率, obj=['中国平安']

- **匹配字段**: FIELD_PE_TTM
- **中文名**: 市盈率TTM
- **description**: 滚动市盈率
- **granularity**: 日频,个股级别
- **alias**: {"simple": ["市盈率"], "qualified": ["滚动市盈率", "PE_TTM"], "business_tag": ["估值指标", "盈利估值", "TTM估值"], "synonyms": ["TTM市盈率", "PE_TTM", "滚动PE", "市盈率TTM"]}
- **选择用时**: 1.3s
- **候选数**: 5

### RR-08: var=板块, obj=['宁德时代']

- **匹配字段**: FIELD_SECTOR_NAME
- **中文名**: 板块名称
- **description**: 行业/概念板块名称
- **granularity**: 日频,板块级别
- **alias**: {"simple": ["板块名称"], "qualified": ["行业板块名称", "概念板块名称"], "business_tag": ["板块标识", "行业标签", "概念标签"], "synonyms": ["板块名", "行业名", "概念名", "板块简称"]}
- **选择用时**: 1.9s
- **候选数**: 5

### RR-09: var=涨跌幅, obj=['宁德时代', '比亚迪']

- **匹配字段**: FIELD_QUOTE_PCT_CHG
- **中文名**: 涨跌幅
- **description**: 当日涨跌幅百分比
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["涨跌幅"], "qualified": ["个股涨跌幅", "实时涨跌幅"], "business_tag": ["个股波动", "股价涨幅", "日内波动"], "synonyms": ["涨幅", "跌幅", "涨跌百分比", "股价涨跌", "涨跌幅度"]}
- **选择用时**: 1.3s
- **候选数**: 8

### RR-10: var=资金流向, obj=['北向资金']

- **匹配字段**: FIELD_NORTH_NET
- **中文名**: 北向资金净流入
- **description**: 北向资金净流入（百万元）
- **granularity**: 日频,市场级别
- **alias**: {"simple": ["北向净流入"], "qualified": ["北向资金净流入", "陆股通净流入"], "business_tag": ["外资净流入", "北水", "陆股通"], "synonyms": ["北向资金", "外资净买", "陆股通净流入", "北向净买"]}
- **选择用时**: 1.2s
- **候选数**: 5

### RR-11: var=收盘价, obj=['恒生指数']

- **匹配字段**: FIELD_INDEX_PRICE
- **中文名**: 当前点位
- **description**: 指数收盘点位
- **granularity**: 日频,指数级别
- **alias**: {"simple": ["收盘价"], "qualified": ["指数收盘点位", "指数当前点位"], "business_tag": ["大盘水位", "指数报价", "市场点位"], "synonyms": ["指数价格", "指数值", "指数点位", "指数现价"]}
- **选择用时**: 1.0s
- **候选数**: 6

### RR-12: var=股价, obj=['宁德时代']

- **匹配字段**: FIELD_QUOTE_CHG
- **中文名**: 涨跌额
- **description**: 当日涨跌金额
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["涨跌额"], "qualified": ["个股涨跌额", "实时涨跌"], "business_tag": ["股价变动", "日内涨跌", "涨跌幅度"], "synonyms": ["涨跌金额", "股价涨跌", "日内变动", "涨跌数值"]}
- **选择用时**: 1.0s
- **候选数**: 5

### RR-13: var=最低价, obj=['万科A']

- **匹配字段**: FIELD_QUOTE_LOW
- **中文名**: 最低价
- **description**: 当日最低价
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["最低价"], "qualified": ["个股最低价", "实时低点"], "business_tag": ["日内低点", "当日最低", "谷底价格"], "synonyms": ["最低", "日内最低", "今日低点", "盘面低点"]}
- **选择用时**: 1.6s
- **候选数**: 6

### RR-14: var=开盘价, obj=['格力电器']

- **匹配字段**: FIELD_QUOTE_OPEN
- **中文名**: 开盘价
- **description**: 当日开盘价
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["开盘价"], "qualified": ["个股开盘价", "今日开盘"], "business_tag": ["开盘价格", "开盘定位", "开盘基准"], "synonyms": ["开盘", "今日开盘", "开盘点位", "开盘值"]}
- **选择用时**: 0.9s
- **候选数**: 6

### RR-15: var=成交额, obj=['东方财富']

- **匹配字段**: FIELD_QUOTE_AMOUNT
- **中文名**: 成交额
- **description**: 当日成交额
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["成交额"], "qualified": ["个股成交额", "实时成交额"], "business_tag": ["成交资金", "交易额", "资金规模"], "synonyms": ["成交金额", "交易金额", "资金量"]}
- **选择用时**: 1.0s
- **候选数**: 8

### RR-16: var=涨跌额, obj=['中国平安']

- **匹配字段**: FIELD_QUOTE_CHG
- **中文名**: 涨跌额
- **description**: 当日涨跌金额
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["涨跌额"], "qualified": ["个股涨跌额", "实时涨跌"], "business_tag": ["股价变动", "日内涨跌", "涨跌幅度"], "synonyms": ["涨跌金额", "股价涨跌", "日内变动", "涨跌数值"]}
- **选择用时**: 0.9s
- **候选数**: 3

### RR-17: var=每股净资产, obj=['招商银行']

- **匹配字段**: FIELD_FIN_BPS
- **中文名**: 每股净资产
- **description**: 每股净资产
- **granularity**: 季频,个股级别
- **alias**: {"simple": ["每股净资产"], "qualified": ["每股净资产", "BPS"], "business_tag": ["估值指标", "每股账面价值", "净资产"], "synonyms": ["BPS", "每股账面价值", "每股净资", "净资产每股"]}
- **选择用时**: 0.8s
- **候选数**: 3

### RR-18: var=市净率, obj=['海康威视']

- **匹配字段**: FIELD_PB
- **中文名**: 市净率
- **description**: 市净率
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["市净率"], "qualified": ["市净率", "PB"], "business_tag": ["估值指标", "净资产估值", "PB估值"], "synonyms": ["PB", "市净", "净资产倍数"]}
- **选择用时**: 1.1s
- **候选数**: 3

### RR-19: var=股息率, obj=['大秦铁路']

- **匹配字段**: FIELD_DIVIDEND_YIELD
- **中文名**: 股息率
- **description**: 滚动股息率
- **granularity**: 日频,个股级别
- **alias**: {"simple": ["股息率"], "qualified": ["股息率", "分红收益率"], "business_tag": ["分红回报", "股利收益", "现金回报"], "synonyms": ["股息收益率", "分红率", "股利回报", "现金分红率"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-20: var=板块成交额, obj=['半导体板块']

- **匹配字段**: FIELD_SECTOR_AMOUNT
- **中文名**: 板块成交额
- **description**: 板块当日成交额
- **granularity**: 日频,板块级别
- **alias**: {"simple": ["成交额"], "qualified": ["板块成交额", "行业成交额"], "business_tag": ["板块资金量", "行业流动性", "概念成交"], "synonyms": ["行业成交", "概念成交", "板块资金", "成交金额"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-21: var=板块振幅, obj=['银行板块']

- **匹配字段**: FIELD_SECTOR_AMPLITUDE
- **中文名**: 板块振幅
- **description**: 板块指数振幅
- **granularity**: 日频,板块级别
- **alias**: {"simple": ["振幅"], "qualified": ["板块振幅", "行业波动幅度"], "business_tag": ["板块波动", "行业震荡", "概念震幅"], "synonyms": ["行业振幅", "概念振幅", "板块波动率"]}
- **选择用时**: 0.9s
- **候选数**: 3

### RR-22: var=行业平均PE, obj=['银行板块']

- **匹配字段**: FIELD_VAL_IND_PE
- **中文名**: 行业平均PE
- **description**: 同行业公司PE中位数
- **granularity**: 季频,行业级别
- **alias**: {"simple": ["行业平均PE"], "qualified": ["行业平均市盈率", "行业PE"], "business_tag": ["行业估值", "PE对比基准", "同行业PE"], "synonyms": ["行业PE", "行业估值", "同业PE", "行业市盈率"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-23: var=行业平均ROE, obj=['白酒板块']

- **匹配字段**: FIELD_VAL_IND_ROE
- **中文名**: 行业平均ROE
- **description**: 同行业公司ROE中位数
- **granularity**: 季频,行业级别
- **alias**: {"simple": ["行业平均ROE"], "qualified": ["行业平均净资产收益率", "行业ROE"], "business_tag": ["行业盈利", "ROE对比基准", "同行业ROE"], "synonyms": ["行业ROE", "同业ROE", "行业盈利水平", "ROE基准"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-24: var=综合PMI, obj=['中国']

- **匹配字段**: FIELD_MACRO_COMPOSITE_PMI
- **中文名**: 综合PMI
- **description**: 综合PMI产出指数
- **granularity**: 月频,国家级别
- **alias**: {"simple": ["综合PMI"], "qualified": ["综合PMI", "综合产出指数"], "business_tag": ["经济景气", "综合PMI", "总产出"], "synonyms": ["经济景气", "总产出", "综合产出"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-25: var=CPI环比, obj=['中国']

- **匹配字段**: FIELD_MACRO_CPI_MOM
- **中文名**: CPI环比
- **description**: CPI当月环比增速
- **granularity**: 月频,国家级别
- **alias**: {"simple": ["CPI环比"], "qualified": ["CPI环比", "居民消费价格环比"], "business_tag": ["通胀环比", "CPI月增", "月度通胀"], "synonyms": ["CPI环比增速", "通胀环比", "CPI月度变化", "CPI月增"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-26: var=北向资金净流入, obj=['贵州茅台']

- **匹配字段**: FIELD_NORTH_NET
- **中文名**: 北向资金净流入
- **description**: 北向资金净流入（百万元）
- **granularity**: 日频,市场级别
- **alias**: {"simple": ["北向净流入"], "qualified": ["北向资金净流入", "陆股通净流入"], "business_tag": ["外资净流入", "北水", "陆股通"], "synonyms": ["北向资金", "外资净买", "陆股通净流入", "北向净买"]}
- **选择用时**: 1.1s
- **候选数**: 3

### RR-27: var=指数成交量, obj=['创业板指']

- **匹配字段**: FIELD_INDEX_VOL
- **中文名**: 成交量
- **description**: 指数成交量（手）
- **granularity**: 日频,指数级别
- **alias**: {"simple": ["成交量"], "qualified": ["指数成交量", "市场成交量"], "business_tag": ["大盘量能", "市场流动性", "指数成交规模"], "synonyms": ["成交股数", "指数成交", "量", "成交手数"]}
- **选择用时**: 0.9s
- **候选数**: 3

### RR-28: var=指数涨跌幅, obj=['科创50']

- **匹配字段**: FIELD_INDEX_PCT_CHG
- **中文名**: 涨跌幅
- **description**: 指数涨跌幅百分比
- **granularity**: 日频,指数级别
- **alias**: {"simple": ["涨跌幅"], "qualified": ["指数涨跌幅", "指数涨幅"], "business_tag": ["大盘晴雨表", "市场温度计", "指数波动率"], "synonyms": ["涨幅", "跌幅", "涨跌百分比", "指数涨跌", "涨跌幅度"]}
- **选择用时**: 1.1s
- **候选数**: 3

### RR-29: var=K线收盘价, obj=['五粮液']

- **匹配字段**: FIELD_KLINE_CLOSE
- **中文名**: 收盘价
- **description**: 当日收盘价
- **granularity**: 日频,个股级别
- **alias**: {"simple": ["收盘价"], "qualified": ["K线收盘价", "历史收盘"], "business_tag": ["历史收盘", "K线收盘", "当日结算"], "synonyms": ["收盘", "K线收盘", "历史收盘价"]}
- **选择用时**: 0.9s
- **候选数**: 3

### RR-30: var=应收账款周转率, obj=['海康威视']

- **匹配字段**: FIELD_FIN_AR_TURN
- **中文名**: 应收账款周转率
- **description**: 营业收入/平均应收账款
- **granularity**: 季频,个股级别
- **alias**: {"simple": ["应收账款周转率"], "qualified": ["应收账款周转率", "应收周转"], "business_tag": ["营运能力", "回款效率", "周转指标"], "synonyms": ["应收周转率", "应收账款周转", "回款速度", "周转率"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-31: var=涨跌额, obj=['比亚迪']

- **匹配字段**: FIELD_QUOTE_CHG
- **中文名**: 涨跌额
- **description**: 当日涨跌金额
- **granularity**: 实时,个股级别
- **alias**: {"simple": ["涨跌额"], "qualified": ["个股涨跌额", "实时涨跌"], "business_tag": ["股价变动", "日内涨跌", "涨跌幅度"], "synonyms": ["涨跌金额", "股价涨跌", "日内变动", "涨跌数值"]}
- **选择用时**: 1.0s
- **候选数**: 3

### RR-32: var=每股收益, obj=['交通银行']

- **匹配字段**: FIELD_FS_BASIC_EPS
- **中文名**: 基本每股收益
- **description**: 基本每股收益
- **granularity**: 季频,个股级别
- **alias**: {"simple": ["基本每股收益"], "qualified": ["基本每股收益", "基本EPS"], "business_tag": ["每股盈利", "每股收益", "基本EPS"], "synonyms": ["EPS", "每股收益", "基本EPS", "每股盈利"]}
- **选择用时**: 0.9s
- **候选数**: 4
