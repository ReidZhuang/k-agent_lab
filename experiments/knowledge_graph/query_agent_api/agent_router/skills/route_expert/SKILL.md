---
name: route_expert
description: 字段筛选专业知识
---

## 从 id 前缀读含义

id 命名规则：`FIELD_{类别}_{具体指标}`

| 前缀 | 含义 |
|------|------|
| FIELD_QUOTE_ | 实时行情（涨跌幅、最高价、成交量等） |
| FIELD_INDEX_ | 指数相关 |
| FIELD_SECTOR_ | 板块相关 |
| FIELD_KLINE_ | K线数据 |
| FIELD_FIN_ | 财务数据 |
| FIELD_PE_ | 市盈率 |
| FIELD_LHB_ | 龙虎榜 |
| FIELD_TURNOVER_ | 换手率 |
| FIELD_VAL_ | 估值 |
| FIELD_NORTH_ | 北向资金 |
| FIELD_CF_ | 现金流 |
| FIELD_MONEY_ | 资金流向 |
| FIELD_MACRO_ | 宏观 |
| FIELD_CB_ | 可转债 |

## 常见 obj 类型判断

- 带"指数" → index_code
- 带"板块"、"概念"、"行业" → sector_name
- 带.SZ/.SH/.BJ 或纯数字代码 → stock_code
- 其余 → 默认为 stock_code
