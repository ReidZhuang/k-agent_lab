# 文档：东方财富 MCP 积分耗尽错误处理规约

> 状态：已定稿（skill 提案 `mx-mcp-quota-exhausted-handler` 为 pending，审批应用后本规约随 skill 生效）
> 日期：2026-08-14
> 关联：`skills/company-analysis`（分析管线遇本错误须立即中止）

## 1. 背景

`mx-ds-mcp`（东方财富金融数据 MCP，工具前缀 `mx-ds-mcp__mx_*`）按积分计费。积分耗尽时工具返回如下错误：

> 你的积分已用完~请前往 https://ai.eastmoney.com/skills 购买套餐补充积分，即可继续使用

**处理原则：一旦识别为该错误，立即终止任务并返回统一规范格式的错误提示；禁止用其他数据源替代、禁止编造数据、禁止产出（部分）报告。**

兜底/重试策略（重试时机、备用数据源、积分监控告警）由用户侧另行设计，本规约只提供稳定字段契约。

## 2. 检测规则

对工具返回文本做**子串匹配**（忽略大小写与首尾空白）。

**一级命中（任一即判定）：**

- `积分已用完` / `积分用尽` / `积分不足`
- `补充积分` / `购买套餐`
- `ai.eastmoney.com/skills`

**二级确认（一级未命中时，同时满足）：**

- 包含 `积分` 或 `套餐`
- 且包含 `用完` / `用尽` / `不足` / `不够` / `耗尽` / `余额` 之一

不满足 → 非积分耗尽类错误，走普通错误流程（超时 / 429 / 网络 / 参数等不在本规约范围）。

## 3. 处置动作（命中后必须遵守）

1. 立即停止：不再调用任何 `mx-ds-mcp` 工具（含同批次其他查询）。
2. 禁止替代：不得改用其他数据源/工具/知识库；不得凭记忆或常识编造数据。
3. 禁止产出报告：不输出本次查询的分析报告或部分结论；批次内已有部分数据也按"任务未完成"处理。
4. 返回规范错误提示（见第 4 节），如实填写工具名与原始请求。
5. 记录到 `memory/YYYY-MM-DD.md`：`MCP配额耗尽 tool=<工具> query=<原始请求> time=<时间>`。

## 4. 规范格式错误提示

### 4.1 人类可读版（默认输出）

```
⛔ 数据服务不可用：东方财富 MCP 积分已耗尽
──────────────────────────────
错误码    : MX_QUOTA_EXHAUSTED
服务      : mx-ds-mcp（东方财富金融数据）
工具      : <受影响工具名，如 mx_ashare_finance_data>
原始请求  : <触发本次报错的用户请求/查询语句>
官方提示  : 你的积分已用完~请前往 https://ai.eastmoney.com/skills 购买套餐补充积分，即可继续使用
处置      : 已终止本次查询；未使用替代数据源；未生成报告
恢复      : 请在 https://ai.eastmoney.com/skills 购买套餐补充积分后，重新发起请求
```

### 4.2 机器可读版（供兜底/重试策略解析）

```json
{
  "error": {
    "code": "MX_QUOTA_EXHAUSTED",
    "type": "quota_exhausted",
    "service": "mx-ds-mcp",
    "tool": "<受影响工具名>",
    "request": "<原始请求>",
    "message": "你的积分已用完~请前往 https://ai.eastmoney.com/skills 购买套餐补充积分，即可继续使用",
    "action": "abort",
    "fallback_allowed": false,
    "retryable": true,
    "retry_condition": "after_recharge"
  }
}
```

## 5. 字段契约（稳定，勿改动）

| 字段 | 类型 | 固定值/含义 |
|---|---|---|
| error.code | string | 固定 `MX_QUOTA_EXHAUSTED`，策略匹配入口 |
| error.type | string | 固定 `quota_exhausted` |
| error.service | string | 固定 `mx-ds-mcp` |
| error.tool | string | 实际返回该错误的 MCP 工具名（如实填写） |
| error.request | string | 触发错误的原始查询（供重试回放） |
| error.message | string | 官方错误原文 |
| error.action | string | 固定 `abort`（本次任务已终止） |
| error.fallback_allowed | boolean | 固定 `false`（禁止替代数据源） |
| error.retryable | boolean | `true`（充值后重试有效） |
| error.retry_condition | string | `after_recharge` |

## 6. 与分析框架的衔接

- company-analysis 等分析管线中任一 `mx-ds-mcp` 调用命中检测规则 → **立即中止整个管线**，只返回错误块，不输出任何分析结论。
- `request` 字段保留原始分析请求，充值后可直接原样重放。

## 7. 交付物与提案状态

| 交付物 | 位置 | 状态 |
|---|---|---|
| Skill 提案 | `mx-mcp-quota-exhausted-handler`（proposal id: `mx-mcp-quota-exhausted-handler-20260814-a41c9e09f8`） | ⏳ pending，待审批 apply 后生效 |
| 本文档 | `docs/mx-mcp-quota-exhausted-handler.md` | ✅ 已写入 |
| 当日记录 | `memory/2026-08-14.md` | ✅ 已追加 |

**审批方式**：在 Control UI / WebChat 中对 pending 提案执行 apply（或对 agent 说"应用该提案"），审批后 skill 生效，本规约随 skill 自动可用。

## 8. 兜底/重试策略对接契约（供用户侧开发）

- 匹配入口：`error.code == "MX_QUOTA_EXHAUSTED"`（恒定不变）
- `retryable: true` + `retry_condition: "after_recharge"` → 充值后重试有效
- `fallback_allowed: false` → 策略禁止静默切换其他数据源，只能提示充值或等待
- `request` 字段可回放原查询
- 新增字段需与本规约版本同步

## 9. 修订历史

- 2026-08-14：初版定稿。检测规则（一级/二级命中）、处置铁律、规范错误格式（人类可读版+机器可读版）、字段契约、与分析框架衔接、对接契约。

## 10. 边界

- 只覆盖"积分耗尽"类错误；超时 / 429 / 网络 / 参数错误走其他流程。
- 同批次部分成功部分报错：整批视为未完成，返回错误块（可注明已成功部分，但不输出其分析结论）。
- `tool` / `request` 如实填写，禁止占位符（查询为空时注明"请求为空"）。
- 兜底/重试策略入口：`error.code == "MX_QUOTA_EXHAUSTED"`；扩展字段需与本规约版本同步。
