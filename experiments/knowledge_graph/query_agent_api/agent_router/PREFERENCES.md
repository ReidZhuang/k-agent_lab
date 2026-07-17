# PREFERENCES.md — 筛选优先级

## 优先级硬排序

1. **scope（范围粒度）** — 不匹配直接淘汰，没有商量余地
2. **match（匹配级别）** — qualified > simple > fuzzy
3. **time_gran（时间粒度）** — 同级别下，与 condition 最匹配的优先
4. **protocol（协议）** — 同样条件下，优先选 tushare（数据最全）

## 特殊情况

- 如果 scope 过滤后只剩 1 个 → 就是它
- 如果 scope 过滤后剩 0 个 → 选 match 级别最高的那个（可能 KG 缺少精准字段）
- 如果 obj 不能明确判断类型 → 只看 match 级别和语义最接近的
