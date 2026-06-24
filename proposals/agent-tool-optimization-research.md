# Agent Tool Loop Token 优化研究方向 —— 阶段性总结

> 起草日期：2026-06-23
> 状态：研究阶段 · 等待实验验证
> 关联：Agent-Work API 子需求（`子需求-Agent-Work_API_完整需求文档_v2.0_Claude.md`）

---

## 背景

Agent-Work API 的 21 个 Agent 需要以 DeepSeek SDK 直调方式运行，每个 Agent 在 tool loop 中可能经历多轮 `LLM → tool_call → 本地执行 → 结果回注 → LLM 再推理` 的循环。

当前存在的核心痛点：

1. **Tool result 全量重发**：每轮 loop 都将所有历史 tool result 重新发送给 LLM，无关内容反复往返，浪费 tokens
2. **Web search 数据粒度粗糙**：搜索工具一次性返回多个链接的全文，LLM 实际只用到其中一小部分
3. **无法区分 LLM 的"直接引用"和"隐性参与推理"**：压缩看似无关的内容可能悄无声息地降低推理质量

---

## 研究方向一：基于 tool_call arguments 的推理过程提取

### 核心思路

在 LLM 调用工具时（`finish_reason = "tool_calls"`），虽然 `content = null` 无法附带文本，但 **tool_call 的 `arguments` 字段是 LLM 可以输出结构化信息的唯一通道**。

我们可以通过设计 tool 的入参，强迫 LLM 在调用工具时输出"为什么要调用这个工具、上一轮结果的哪部分信息被采用"。

### 具体机制

传统 tool 定义：
```yaml
name: web_search
parameters:
  query: string    # LLM 只传 query，不暴露任何推理过程
```

带推理约束的 tool 定义（实验方案）：
```yaml
name: web_search
description: >
  搜索互联网。在调用前，你**必须**在 `reasoning` 字段中说明：
  上一轮工具结果中的哪部分信息促使你发起这次搜索。
parameters:
  reasoning:
    type: string
    description: >
      [必须] 回顾上一轮工具结果，说明：
      1. 你从中提取了什么关键线索
      2. 你期望通过这次搜索深入什么
      3. 你希望新搜索聚焦在哪个子维度
  search_focus:
    type: string
    description: 基于上一轮结果中的特定线索提炼的搜索焦点
  query:
    type: string
    description: 完整搜索 query
```

LLM 返回的 `arguments` 会包含：
```json
{
  "reasoning": "上一轮搜索显示宁德时代2024年营收增长22%，但未提及分业务板块增速。需要进一步搜索以判断增长质量。",
  "search_focus": "宁德时代分业务增速",
  "query": "宁德时代 2024 动力电池 储能 营收 占比"
}
```

### 利用方式

本地可以解析 `arguments.reasoning` 字段，提取 LLM 关注的关键词/来源，据此判断：

- 哪些历史 tool result 仍然需要保留全文
- 哪些可以压缩为摘要甚至删除
- 与直接存储完整 tool result 相比节省 tokens

### 成本收益估算

| 项目 | 消耗 | 说明 |
|------|------|------|
| 额外 tokens | ~30-80 tokens/次 | reasoning 字段占用的 completion tokens |
| 可能节省 | 几百-几千 tokens/轮 | 如果成功将无关 tool result 压缩掉 |
| 净收益条件 | 省掉的 tokens > 额外消耗 | 需要实验验证 |

### 风险与局限性

1. **LLM 的 reasoning 可能不可靠** —— 模型可能敷衍填入不准确的内容
2. **无法覆盖"隐性参与推理"** —— LLM 使用一段数据做推理判断但不显式引用，我们无法察觉
3. **增加 tool 调用的 cognitive load** —— 强迫 LLM 输出 reasoning 可能增加推理轮数

### 参考：OpenClaw 的工具设计模式

OpenClaw 的 Tavily 搜索插件使用了类似的分层思路，在 SKILL.md 中明确指导 LLM：

> *"Combine search + extract when you need to find pages first, then get their full content."*
> *"If tavily_search results already contain the snippets you need, skip the extract step."*

但 OpenClaw **没有**实现"从 tool_call arguments 提取推理过程"的机制——这属于新的设计。

---

## 研究方向二：分步搜索 + Token 计算器

### 核心思路

针对 web search 这类天然"先选择、后深入"的工具，将一次粗粒度的搜索拆成两步：

```
传统单步:
  web_search("茅台 2024 年报") → 10KB 全文 → 全部发给 LLM

分步:
  第1步: web_search_meta("茅台 2024 年报") → 只返回标题+摘要列表(500B)
  第2步: LLM 从中选择 → web_open(url) → 只返回选中链接的全文
```

同时引入 **Token 计算器**来判断"是否值得多交互一轮"。

### Tool 设计示例

```yaml
# 选择型工具：只返回元数据
name: web_search_meta
parameters:
  query: string
  max_results: 5
# 返回: [{title, snippet, url, source}]

# 理解型工具：获取选定内容的全文  
name: web_open
parameters:
  url: string
  reason: string    # 为什么选择这个 URL
# 返回: {content: "..."}
```

### Token 计算器逻辑

```python
def should_split_search(current_context_tokens, estimated_result_size):
    """
    判断当前是否需要分步搜索
    """
    # 如果上下文已经很重，多一轮交互的成本更高
    context_overhead_penalty = current_context_tokens / 100000 * 0.3
    
    # 分步的成本：多一轮 LLM 调用
    cost_of_split = 200 + 500 * (1 + context_overhead_penalty)
    #   ↑ 200: 第一轮 meta 的 completion tokens
    #     500: 第二轮 open 的平均 completion tokens
    
    # 不分割的成本：全量结果在后续 N 轮中重复发送
    estimated_useful_ratio = 0.3   # 预估只有 30% 内容对 LLM 有用
    expected_remaining_rounds = 2   # 预估剩余 loop 轮数
    waste_per_round = estimated_result_size * (1 - estimated_useful_ratio)
    cost_of_full = waste_per_round * expected_remaining_rounds
    
    return cost_of_split < cost_of_full
```

### 决策流程

```
LLM 发起搜索请求
        │
        ▼
  Token 计算器评估
        │
  ┌─────┴─────┐
  │           │
  划算        不划算
  │           │
  ▼           ▼
分步搜索     传统全量搜索
(选择型)     (直接返回全文)
```

### 关键遗留问题

1. **如何判断 tool call 是"选择型"还是"理解型"？**
   - 可能的方案：在 tool 元数据中标注 `interaction_mode: selection | comprehension`  
   - 选择型（`selection`）：搜索结果、链接列表、候选人列表——LLM 只需要选
   - 理解型（`comprehension`）：财报全文、技术文档、政策原文——LLM 需要完整阅读

2. **Token 计算的单位边界是什么？**
   - 按"次 API 调用"计算？还是按"一个请求的完整生命周期"计算？
   - 初步方案：**单次 agent run 为边界**，不跨请求累计

3. **分步搜索的风险**
   - 如果第一轮 meta 信息不足以让 LLM 做出正确选择，LLM 回过头要求全量 → 3 轮做了 1 轮的活
   - 参考 Tavily 的解决思路：在搜索工具中加入 `include_answer` 参数，让 AI 在搜索时一并生成摘要，降低误选概率

---

## 参考设计：OpenClaw 的 Web Search 架构

### OpenClaw 支持的搜索插件

| 插件 | 类型 | 关键特性 |
|------|------|---------|
| Tavily | 商业 API | 3 层工具（search / search_advanced / extract），支持 query-focused chunking |
| DuckDuckGo | 免费搜索 | 标准 `web-search-provider` 接口，无需 API Key |
| SearXNG | 自托管 | 元搜索引擎，支持配置多个后端 |
| Firecrawl | 爬虫 | JS 渲染页面内容提取 |
| Browser | 浏览器自动化 | 可编程浏览器操作 |

### Tavily 的工具分层模型（最值得参考）

```
web_search              → 简单搜索 (query + count)
tavily_search           → 高级搜索 (depth/topic/time_range/domain_filter/include_answer)
tavily_extract          → URL 内容提取 (支持 query + chunks_per_source 定向提取)
```

关键的优化点：`tavily_extract` 的 `query` 参数——LLM 可以在提取时指定"我只想看这部分"，返回的是片段而不是全文。这本质上是 **在服务端侧做了渐进式披露**。

### 与此研究的关系

OpenClaw 的搜索工具设计确认了 **分步搜索是一种成熟的、已被已有的 Agent 框架采用** 的模式。但 OpenClaw 没有解决"什么时候该分步、什么时候该全量"的决策问题——这正是 Token 计算器的切入点。

---

## 下一步计划

### 阶段一：实验验证方向一（推理过程提取）

**目标**：确认 LLM 是否能在 tool_call 的 `arguments` 中输出可靠的 reasoning

- [ ] 设计实验 prompt + tool 定义
- [ ] 使用 DeepSeek-V4-Flash 调用测试
- [ ] 验证 reasoning 的质量（一致性、准确性、有用性）
- [ ] 测试不同 tool 类型（选择型 vs 理解型）的效果差异

### 阶段二：实验验证方向二（分步搜索）

**目标**：验证分步搜索在 token 消耗上是否有净收益

- [ ] 设计 `web_search_meta` 和 `web_open` 的 tool 定义
- [ ] 实现 Token 计算器原型
- [ ] 与"一步到位全量搜索"做对比测试
- [ ] 测试不同场景（简单查询、多维度分析、深度研究）

### 阶段三：设计决策

- [ ] 根据实验结果决定：哪个方向进入工程化
- [ ] 将确认的模式写入 `web_search_tool.yaml` 和 `url_fetcher_tool.yaml`
- [ ] 更新 Agent-Work API 的 Tool 设计章节
- [ ] 设计实验记录文档：`research/experiments/`

---

## 脚注

### 技术背景：tool_call 协议细节

```
LLM 返回 tool_call 时:
  - content = null（无法附带文本）
  - tool_calls[].function.arguments = string（JSON 字符串，LLM 可在此输出结构化信息）
  - finish_reason = "tool_calls"（loop 继续的信号）

LLM 返回最终结果时:
  - content = "最终回答"（LLM 才正式输出文本）
  - finish_reason = "stop"（loop 终止的信号）

Agent loop 的核心：
  while True:
      response = api.chat.completions.create(messages=messages, tools=tools)
      if response.finish_reason == "stop": break
      if response.finish_reason == "tool_calls":
          result = execute_tool(tool_call)
          messages.append({"role": "tool", ...})
          continue
```

### 关键术语

| 术语 | 说明 |
|------|------|
| oneshot | Agent 用完即销毁，不保留上下文（但内部可以有多次 tool loop） |
| tool loop | Agent 内部的多轮 tool_call 循环，对调用方透明 |
| 选择型工具 | LLM 从 N 个候选中选 M 个执行（如搜索结果 → 选链接打开） |
| 理解型工具 | LLM 需要完整阅读后做判断（如打开财报全文 → 提取数据） |
| 隐性参与推理 | LLM 读了某段内容后调整了判断方式，但最终输出中无法看出引用来源 |
| progressive disclosure | 渐进式披露：先给摘要，需要时再取细节 |
