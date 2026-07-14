# Agent 路由解析实验报告

- **模型**: qwen2.5:7b
- **日期**: 2026-07-13
- **System prompt**: ~2587 字符

---

## q001 — 宁德时代今天上午的涨跌幅如何？

**路由调用**: 1 轮 | **停止原因**: final_answer_tag

### Round 1
- **keywords**: `["涨跌幅"]`
- **entity**: stock_code / 300750.SZ
- **结果**: 7 个字段（跨 domain）

### 最终决策
LLM 直接根据 `granularity="实时,个股级别"` 选中 `FIELD_QUOTE_PCT_CHG`。

> 从返回字段中，`FIELD_QUOTE_PCT_CHG` 的 `granularity` 是 "实时,个股级别"，这与您的查询需求匹配。
>
> **✅ FIELD_QUOTE_PCT_CHG**

---

## q006 — 宁德时代今日成交额和换手率

**路由调用**: 1 轮 | **停止原因**: final_answer_tag

### Round 1
- **keywords**: `["成交额", "换手率"]`
- **strict**: false
- **结果**: 14 个字段

### 最终决策
LLM 自动将 14 个字段拆分为两个指标：

- **成交额** → `FIELD_QUOTE_AMOUNT`（实时,个股级别）
- **换手率** → `FIELD_TURNOVER_RATE`（实时,个股级别）

> 为了更精确地匹配您的需求，我们选择以下两个字段：
> - 成交额：`FIELD_QUOTE_AMOUNT`
> - 换手率：`FIELD_TURNOVER_RATE`

---

## q007 — 宁德时代所属板块今日涨跌幅

**路由调用**: 2 轮 | **停止原因**: final_answer_tag

### Round 1
- **keywords**: `["涨跌幅"]`
- **entity**: sector_name / 新能源汽车（LLM 自动推理）
- **结果**: 7 个字段

### Round 2
- **keywords**: `["宁德时代新能源汽车板块今日涨跌幅"]`（尝试更精确表达）
- **结果**: 5 个字段（fuzzy），`FIELD_SECTOR_PCT_CHG` 排第一

### 最终决策
LLM 用 granularity 验证后确认：

> `FIELD_SECTOR_PCT_CHG` 的 `granularity` 是 "日频,板块级别"，完全符合宁德时代所属新能源汽车板块今日涨跌幅的要求。
>
> **✅ FIELD_SECTOR_PCT_CHG**

---

## q008 — 宁德时代今天中午的MA10是多少

**路由调用**: 3 轮 | **停止原因**: final_answer_tag

### Round 1
- **keywords**: `["MA10"]`
- **结果**: 5 个字段（全部 fuzzy，宏观经济数据）

### Round 2
- **keywords**: `["宁德时代 个股涨跌幅"]`
- **结果**: 5 个字段（历史 K 线数据，仍无 MA10）

### Round 3
- **keywords**: `["MA10"]`
- **结果**: 5 个字段（宏观经济，同上）

### 最终决策
LLM 穷举后正确判断不存在：

> 考虑到我们已经尝试了多次精确查询，并且没有得到满意的结果，我们可以得出结论：当前的知识图谱中并没有包含宁德时代今天中午的MA10这一具体指标。
>
> **✅ 知识图谱中暂无宁德时代今天中午的MA10数据。**

---

## 汇总

| 查询 | 轮次 | 结果 | 亮点 |
|------|------|------|------|
| 上午涨跌幅 | 1 | ✅ FIELD_QUOTE_PCT_CHG | granularity 直接命中 |
| 成交额和换手率 | 1 | ✅ 双字段 | 自动拆分多指标 |
| 所属板块涨跌幅 | 2 | ✅ FIELD_SECTOR_PCT_CHG | 自动切换 sector 实体 |
| MA10 | 3 | ✅ 知识图谱中不存在 | 穷举后正确判断"无" |
