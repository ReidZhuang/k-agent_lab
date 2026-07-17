# DataField 重复检测报告

**检测日期**: 2026-07-15
**检测方法**: 按 `api_column + 数据源` 分组，count > 1 即为疑似重复
**审核建议**: 人工逐条判断是否为真重复，决策后通知我执行删除

---

## 一、可转债（DS_TUSHARE_CB_DAILY）— 3 组

这 3 组中同一张表 `cb_daily` 的不同字段的 api_column 巧合相同（宽表结构），**不是重复**。

### 1.1 pct_chg（3 个字段）
| 字段 | 标准名 | 描述 | 别名关键词 |
|------|--------|------|-----------|
| FIELD_CB_CB_OVER_RATE | 转股溢价率 | 转股溢价率 | 转股溢价、转换溢价、股性溢价 |
| FIELD_CB_BOND_OVER_RATE | 纯债溢价率 | 纯债溢价率 | 纯债溢价、债底溢价、债券溢价 |
| FIELD_CB_PCT_CHG | 涨跌幅 | 当日涨跌幅 | 涨跌幅、转债涨跌、涨幅 |

**判断**: 三个不同语义的字段（转股溢价率 vs 纯债溢价率 vs 涨跌幅），只是恰好在同一张表里都叫 pct_chg 列。**不是重复** ✅

### 1.2 close（3 个字段）
| 字段 | 标准名 | 描述 |
|------|--------|------|
| FIELD_CB_BOND_VALUE | 纯债价值 | 纯债价值（元）|
| FIELD_CB_CLOSE | 收盘价 | 当日收盘价（元）|
| FIELD_CB_CB_VALUE | 转股价值 | 转股价值（元）|

同 1.1，**不是重复** ✅

### 1.3 rate_clause（3 个字段）
| 字段 | 标准名 | 描述 |
|------|--------|------|
| FIELD_CB_RATING | 信用评级 | 最新信用评级（string）|
| FIELD_CB_CALL_CLAUSE | 强赎条款 | 赎回条款（string）|
| FIELD_CB_PUT_CLAUSE | 回售条款 | 回售条款（string）|

不同条款文本，**不是重复** ✅

---

## 二、行业分类（DS_TUSHARE_INDEX_CLASSIFY）— 2 组

同一 API `index_classify` 返回的三种级别数据，**不是重复**。

### 2.1 industry_name（3 个字段）
| 字段 | 标准名 | 描述 |
|------|--------|------|
| FIELD_INDUSTRY_L1_NAME | 一级行业名称 | 申万一级行业名称 |
| FIELD_INDUSTRY_L2_NAME | 二级行业名称 | 申万二级行业名称 |
| FIELD_INDUSTRY_L3_NAME | 三级行业名称 | 申万三级行业名称 |

三级分类独立，**不是重复** ✅

### 2.2 industry_code（3 个字段同理）

---

## 三、涨跌停（DS_TUSHARE_STK_LIMIT）— 1 组

| 字段 | 标准名 | 描述 | 别名关键词 | 所属概念 |
|------|--------|------|-----------|---------|
| FIELD_LIMIT_DOWN_PRICE | 跌停价 | 当日跌停价格 | 跌停价、跌停板价格 | CONCEPT_LIMIT_UP_DOWN |
| FIELD_LIMIT_DOWN | 跌停价 | 当日跌停价格 | 个股跌停价、当日跌停 | CONCEPT_REALTIME_QUOTE |

**完全重复**：同数据源、同表、同 api_column、同名、同描述、同类型。仅概念归属不同。
**建议**: 删一个 ✅

---

## 四、PE_TTM（DS_TUSHARE_DAILY_BASIC）— 1 组

| 字段 | 标准名 | 描述 | 别名关键词 | 所属概念 |
|------|--------|------|-----------|---------|
| FIELD_PE_TTM | 市盈率TTM | 滚动市盈率 | 市盈率、滚动市盈率、PE_TTM | 实时行情与估值 |
| FIELD_VAL_PE_TTM | PE_TTM | 滚动市盈率 | 市盈率、PE_TTM、滚动市盈率 | 估值对比分析 |

**疑似重复**：同数据源、同表（daily_basic）、同 api_column（pe_ttm）。区别只在于所属概念不同。
**建议**: 确认是否需要两个概念下的同一字段 → 如需则保留，否则删一个 🔍

---

## 五、ROE（DS_TUSHARE_FINA_IND）— 1 组

| 字段 | 标准名 | 描述 | 别名关键词 |
|------|--------|------|-----------|
| FIELD_FIN_ROE_DILUTED | ROE(摊薄) | 摊薄净资产收益率 | 摊薄ROE、稀释ROE |
| FIELD_FIN_ROE_DT | ROE(扣非) | 扣除非经常损益后ROE | 扣非ROE、核心ROE |

**不是重复**：摊薄 ROE 和扣非 ROE 是不同的财务口径，语义不同。只是 API 返回的列名都叫 `roe_dt`。**不是重复** ✅

---

## 六、营业收入（DS_TUSHARE_INCOME）— 1 组

| 字段 | 标准名 | 描述 |
|------|--------|------|
| FIELD_FS_REVENUE | 营业收入 | 营业收入（亿元）|
| FIELD_FS_TOTAL_REVENUE | 营业总收入 | 营业总收入（亿元）|

**不是重复**："营业收入"和"营业总收入"在财报中是不同的行项目（总收入=营业收入+其他收益）。**不是重复** ✅

---

## 七、上涨家数/下跌家数（DS_AKSHARE_SECTOR_SPOT）— 2 组

所有字段都指向同一张表 `stock_board_industry_spot_em`。

### 7.1 上涨家数
| 字段 | 标准名 | 所属概念 |
|------|--------|---------|
| FIELD_SECTOR_UP_COUNT | 上涨家数 | 板块实时行情 |
| FIELD_UP_COUNT | 上涨家数 | 市场情绪与快讯 |

### 7.2 下跌家数
| 字段 | 标准名 | 所属概念 |
|------|--------|---------|
| FIELD_SECTOR_DOWN_COUNT | 下跌家数 | 板块实时行情 |
| FIELD_DOWN_COUNT | 下跌家数 | 市场情绪与快讯 |

**完全重复**（同数据源、同表、同列、同名）。但已有 has_backup=True，说明已配主备关系。
**建议**: 已配主备，保留。如想精简可删掉备用的那两个 🔍

---

## 八、新浪财务（DS_SINA_*）— 8 组

全部是同一份数据在导入时对同一字段创建了两套命名：中文完整名（如 `FIELD_CF_经营活动产生的现金流量净额`）和英文缩写名（如 `FIELD_CF_OPER_FLOW`）。

全部符合：
- 同数据源 ✅
- 同表 ✅
- 同 api_column ✅
- 同描述（表述略有差异但指向同一行）✅
- 同类型/单位/粒度 ✅

| 字段1（英文缩写） | 字段2（中文全名） | api_column | 数据源 |
|------------------|------------------|-----------|--------|
| FIELD_INC_COMPR_PARENT | FIELD_INC_归属于母公司所有者的综合收益总额 | compr_income_parent | 利润表 |
| FIELD_INC_NET_PROFIT_PARENT | FIELD_INC_归属于母公司所有者的净利润 | net_profit_parent | 利润表 |
| FIELD_BS_EQUITY_PARENT | FIELD_BS_归属于母公司股东权益合计 | equity_parent | 资产负债表 |
| FIELD_BS_FIXED_ASSETS | FIELD_BS_FIXED_ASSETS_NET | fixed_assets | 资产负债表 |
| FIELD_CF_OPER_FLOW | FIELD_CF_经营活动产生的现金流量净额 | op_cash_flow | 现金流量表 |
| FIELD_CF_INV_FLOW | FIELD_CF_投资活动产生的现金流量净额 | inv_cash_flow | 现金流量表 |
| FIELD_CF_FIN_FLOW | FIELD_CF_筹资活动产生的现金流量净额 | fin_cash_flow | 现金流量表 |
| FIELD_CF_NET_INCREASE | FIELD_CF_现金及现金等价物的净增加额 | cash_net_increase | 现金流量表 |
| FIELD_CF_CASH_END | FIELD_CF_现金的期末余额 | cash_end | 现金流量表 |
| FIELD_CF_CASH_BEGIN | FIELD_CF_期初现金及现金等价物余额 | cash_begin | 现金流量表 |

**建议**: 删掉中文全名那套，保留英文缩写名。前者 ID 携带中文（如 `FIELD_INC_归属于母公司所有者的净利润`），在 API 交互中不便使用 🔍

---

## 汇总

| 组号 | api_column | 数据源 | 建议 | 优先级 |
|------|-----------|--------|------|:------:|
| 1-3 | CB 可转债 | DS_TUSHARE_CB_DAILY | ✅ 不是重复 | — |
| 4-5 | industry | DS_TUSHARE_INDEX_CLASSIFY | ✅ 不是重复 | — |
| **3** | **down_limit** | **DS_TUSHARE_STK_LIMIT** | **⛔ 删一个** | 🔴 |
| **4** | **pe_ttm** | **DS_TUSHARE_DAILY_BASIC** | **需确认** | 🟡 |
| 5 | roe_dt | DS_TUSHARE_FINA_IND | ✅ 不是重复 | — |
| 6 | revenue | DS_TUSHARE_INCOME | ✅ 不是重复 | — |
| **7** | **上涨/下跌家数** | **DS_AKSHARE_SECTOR_SPOT** | **已配主备，精简可选** | 🟢 |
| **8** | **Sina Finance ×8** | **DS_SINA_*** | **删中文名保留缩写名** | 🟡 |
