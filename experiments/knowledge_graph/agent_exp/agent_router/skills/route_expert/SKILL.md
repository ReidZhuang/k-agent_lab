---
name: route_expert
description: 知识图谱路由工具的使用技巧
---

## 关键词 & 匹配级别（重要）

每个 DataField 有 4 级别名，keywords 按优先级逐级匹配：

```
FIELD_QUOTE_PCT_CHG
  qualified     → ['个股涨跌幅', '实时涨跌幅']      ← 带域限定的精确名
  simple        → ['涨跌幅']                         ← 最简中文名
  business_tag  → ['个股波动', '股价涨幅', '日内波动'] ← 业务场景标签
  synonyms      → ['涨幅', '跌幅', '涨跌百分比', ...]  ← 近义词变体
```

| 级别 | LLM 的作用 |
|------|-----------|
| **qualified** | **核心武器**。从 entity 推导 domain → 拼出 qualified 关键词 → 唯一命中 |
| **simple** | **探路工具**。先查一次，发现歧义后收窄 |
| **business_tag** | 语义兜底 |
| **synonyms** | 最末兜底 |

**工作流：** simple 发现歧义 → qualified 收窄到唯一。

返回字段的 `alias` 说明命中级别：
- `qualified` ✅ → 精确命中，可确认
- `simple` ⚠️ → 可能有歧义，需配合 granularity 等验证
- `synonym` ❓ → 近义词兜底

## 返回字段的属性说明

- `id` — 字段唯一代号
- `data_type` — 数据类型：`float`（数值）、`string`（文本）、`int`（整数）
- `unit` — 计量单位：`%`、`点`、`元`。确认返回值单位是否匹配 query 预期
- `granularity` — **关键属性**。格式 `{时间粒度},{范围粒度}`。时间粒度：`实时`（适合"今天/现在"）| `日频`（适合"昨天/历史"）| `季频`。范围粒度：`个股级别` | `指数级别` | `板块级别` | `市场级别`。选字段时范围粒度匹配实体类型，时间粒度匹配查询时效
- `refresh_time` — 数据更新时机：`realtime`（实时）| `daily_*`（收盘后）| `quarterly`（季频）。

## 从 entity 推导 qualified 关键词
- `stock_code` → 加"个股"、"实时"，如 `涨跌幅` → `个股涨跌幅`
- `index_code` → 加"指数"，如 `涨跌幅` → `指数涨跌幅`
- `sector_name` → 加"板块"，如 `涨跌幅` → `板块涨跌幅`
