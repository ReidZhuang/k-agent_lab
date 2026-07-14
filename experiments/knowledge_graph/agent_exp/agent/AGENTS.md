# AGENTS.md — 迭代式路由解析工作流

## 工作方式

初次用自然语言关键词调 route_query → 审查返回字段 → 若多个候选则根据 granularity 等属性判断歧义来源，推导 qualified 关键词再次路由 → 直到满足停止条件，输出 [FINAL_ANSWER]。

关键判断依据：`alias(qualified/simple)`、`granularity`、`refresh_time`。

**重要：所有工具调用必须通过 tool_calls 机制，不要在你的回复文字中写出工具调用的 JSON 参数。**

下面是 tool_calls 的内部格式参考（你只需决定调哪个工具和传什么参数，JSON 由系统自动生成）：
```
route_query(keywords=["涨跌幅"], entity_type="stock_code", entity_value="300750.SZ")
fetch_data(field_id="FIELD_QUOTE_PCT_CHG", entity_value="300750.SZ")
```

### 多指标拆分
用户 query 含多个指标（"和、与、、"等连接词）时，逐个路由。每轮只查一个指标，完成后用 [FINAL_ANSWER] 列出所有结果。
例：查"成交额和换手率"→ 先 route_query(["成交额"])，再 route_query(["换手率"])。

### 无匹配处理
fuzzy 结果明显错误（如"国家级别"不匹配"个股"）时，用 `strict=true` 重新路由确认是否真的不存在。若返回 0 字段，输出 [FINAL_ANSWER] 说明该指标知识图谱中不存在。

## 停止条件

任一满足则输出 [FINAL_ANSWER]：

- **A** 唯一匹配 + `alias=qualified` → 精确命中，确认
- **B** 唯一匹配 + `granularity` 范围粒度与实体一致（`stock_code`→`个股级别`，`index_code`→`指数级别`，`sector_name`→`板块级别`）
- **C** 唯一匹配 + `refresh_time` 符合时间限定（"今天/上午"→`realtime`，"昨天/历史"→`daily_*`，"季度"→`quarterly`）
- **D** 多字段但能利用属性排除到只剩一个
- **E** 连续多轮 top field 相同 → 收敛
