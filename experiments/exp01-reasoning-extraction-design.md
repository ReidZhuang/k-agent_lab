# 实验一：基于 tool_call arguments 的推理过程提取

> 设计日期：2026-06-23
> 实验状态：待实施
> 关联研究：`research/proposals/agent-tool-optimization-research.md`
> 实验目录：`research/experiments/exp01/`

---

## 1. 实验概述

### 1.1 核心问题

当 LLM 在多轮 tool loop 中连续调用工具时，我们能否**通过 tool_call.arguments 的结构化字段，获取 LLM 对上一轮返回内容的关注重点**？这些 reasoning 信息是否准确、一致、可用？

### 1.2 商业价值

如果这个方向成立，我们可以：

- 从 `arguments` 中提取 LLM 明确引用的数据点 → 对应的 tool result 片段**必须保留全文**
- 找出 LLM 从未提及的数据 → 对应的 tool result 片段**可以压缩或删除**
- 实现**选择性上下文剪裁**——每轮只保留 LLM 实际在用的部分，节省 30-70% 的 tool result tokens

### 1.3 实验假设

> **H0（原假设）**：LLM 在 tool_call.arguments 中输出的 reasoning 是敷衍的、不准确的、无法可靠反映其实际关注重点。
>
> **H1（备择假设）**：LLM 能在 tool_call.arguments 中输出准确、一致的 reasoning，可用于指导上下文剪裁。

---

## 2. 实验设计

### 2.1 调用路径选择

| 决策 | 理由 |
|------|------|
| **OpenAI 兼容路径**（非 Anthropic 路径） | 需要自定义 function tool 的 parameters 结构，在 parameters 中嵌入 `reasoning` 字段。Anthropic 路径的 `web_search_20250305` 是内置工具类型，无法扩展参数。 |
| **搜索后端：DuckDuckGo** | 免费、无需 API Key、结果长度适中（~3-8KB/次），适合实验验证。拟用 `duckduckgo_search` 库。 |

### 2.2 测试场景

选择**多轮深度研究**场景，天然需要连续搜索：

> **用户查询**："分析宁德时代2024年的财务表现，重点关注动力电池和储能业务的增长差异，然后与比亚迪的电池业务进行对比。"

**预期 tool loop 流程**（轮次可增减）：

| 轮次 | 预期搜索内容 | 预期引用的上一轮数据 |
|------|-------------|---------------------|
| 1️⃣ | `宁德时代 2024 年报 营收 净利润` | —（初始搜索，无上轮数据） |
| 2️⃣ | `宁德时代 2024 动力电池 储能 营收占比 增速` | 上轮中的营收总额、净利润数字 |
| 3️⃣ | `比亚迪 2024 动力电池 储能 营收 装机量` | 上轮中的储能增速、动力电池增速 |
| 4️⃣ | `宁德时代 比亚迪 电池 对比 2024` | 前面所有轮次的关键对比数据 |

每一轮返回的内容应在 **3KB 以上**，确保有足够的数据量供 LLM 选择关注点。

### 2.3 工具定义（核心实验变量）

```python
web_search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": """搜索互联网获取最新信息。

在你每次调用此工具前，你**必须**在 reasoning_analysis 中做三件事：
1. 回顾上一轮搜索结果中的关键发现
2. 指出哪些信息还缺失或不清晰
3. 说明本次搜索想验证什么

注意：如果这是第一轮搜索（没有上轮结果），在 key_findings_used 中写 "initial_search"。""",
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning_analysis": {
                    "type": "object",
                    "description": "你对上一轮搜索结果的分析和本次搜索策略",
                    "properties": {
                        "key_findings_used": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "你从上一轮搜索结果中提取并准备用在本轮的关键数据点或发现。必须包含具体数字或事实引用，不能是笼统描述。示例：['宁德时代2024年营收3600亿元']"
                        },
                        "gaps_identified": {
                            "type": "string",
                            "description": "上一轮结果中缺失的、或者你还想进一步深挖的信息缺口"
                        },
                        "search_strategy": {
                            "type": "string",
                            "description": "基于 key_findings_used 和 gaps_identified，你希望通过这次搜索达到什么目的"
                        }
                    },
                    "required": ["key_findings_used", "gaps_identified", "search_strategy"]
                },
                "query": {
                    "type": "string",
                    "description": "完整的搜索查询语句"
                }
            },
            "required": ["reasoning_analysis", "query"]
        }
    }
}
```

**关键设计点**：

- `key_findings_used` 被设计为 **array 类型**，强制 LLM 逐条列出具体引用而非笼统概括
- 要求"必须包含具体数字或事实引用"——构建 prompt 压力迫使 LLM 认真回顾
- `gaps_identified` 和 `search_strategy` 分离：区分"识别到缺口"和"计划怎么填"两阶段思维

### 2.4 Agent Loop 设计

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": USER_QUERY}
]

tool_call_history = []  # 记录所有 tool_call 的 arguments
max_rounds = 6

for round in range(max_rounds):
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages,
        tools=[web_search_tool],
        tool_choice="auto"
    )

    if response.choices[0].finish_reason == "stop":
        final_answer = response.choices[0].message.content
        break

    if response.choices[0].finish_reason == "tool_calls":
        tc = response.choices[0].message.tool_calls[0]
        arguments = json.loads(tc.function.arguments)

        # ========== 实验数据采集点 ==========
        tool_call_history.append({
            "round": round + 1,
            "raw_arguments": arguments,
            "reasoning_analysis": arguments.get("reasoning_analysis", {}),
            "query": arguments.get("query", "")
        })
        # ====================================

        # 执行搜索（DuckDuckGo）
        search_result = execute_duckduckgo_search(arguments["query"])

        # 注入 tool result
        messages.append(response.choices[0].message)  # assistant message with tool_call
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": search_result
        })
```

### 2.5 System Prompt 设计

```yaml
system_prompt: >
  你是一个金融研究助手，擅长通过多轮搜索深入分析公司财务数据。

  工作方式：
  1. 你会分多步进行搜索，每一轮都基于之前的发现深入
  2. 每次搜索前，你必须仔细回顾上一轮搜索结果中的具体数据
  3. 在 web_search 工具的 reasoning_analysis 中，准确列出你实际在用的关键发现

  注意：
  - 不要重复搜索已经获得的信息
  - 如果你发现上一轮结果已经足够回答问题，可以直接给出最终答案
  - 在最终答案中，引用你搜索到的具体数据来源
```

### 2.6 对照实验（Control Group）

为了验证 reasoning 是否准确，需要对照组——使用**不加 reasoning 约束的传统 web_search**，比较两组的：

| 对比维度 | 实验组（有 reasoning） | 对照组（无 reasoning） |
|---------|----------------------|---------------------|
| tool 定义 | 含 reasoning_analysis 参数 | 仅 query 参数 |
| 搜索总轮数 | 记录 | 记录 |
| 最终回答质量 | 人工评分 1-5 | 人工评分 1-5 |
| 总 token 消耗 | 统计 | 统计 |

如果两组的搜索轮数和回答质量没有显著差异，则说明 forcing reasoning 不增加 cognitive load。

---

## 3. 评估体系

### 3.1 量化评估指标

| 指标 | 计算方式 | 评判标准 |
|------|---------|---------|
| **引用准确率** | `(准确引用的数据点数) / (key_findings_used 总条目数)` | ≥ 80% 为优秀 |
| **引用覆盖率** | `(被引用的上一轮内容片段数) / (上一轮返回的总内容片段数)` | 反映 LLM 实际用了多少 |
| **推理一致性** | 跨轮次的 reasoning 是否逻辑连贯——A 轮说"缺 X" → B 轮是否真在搜 X | 人工判断 |
| **幻觉条目率** | `(上一轮结果中不存在但被列在 key_findings_used 中的条目数) / (总条目数)` | < 10% 可接受 |

### 3.2 定性评估维度

- **reasoning 的粒度**：是"搜索到了相关数据"还是"宁德2024年营收3600亿，同比+22%"？
- **reasoning 是否真实参与搜索策略**：`gaps_identified` 和最终 `query` 之间有没有明确的关联？
- **tool loop 效率**：相比对照组，实验组是否多花了无谓的轮次？

### 3.3 热力图分析（后处理）

实验结束后，对每一轮的 tool result 做**段落拆分**，标记哪些段落被 LLM 在下一轮的 `key_findings_used` 中引用，生成热力图：

```
轮次1 搜索结果段落:
  ┌─────────────────────────────────────────┐
  │ 营收: 3600亿 ─████████████████████████─ │ ← 被引用
  │ 净利润: 500亿 ─████████████████─────── │ ← 被引用
  │ 业务结构 ─███────────────────────────── │ ← 部分引用
  │ 研发投入 ────────────────────────────── │ ← 未引用
  │ ESG评级 ────────────────────────────── │ ← 未引用
  └─────────────────────────────────────────┘
```

热力图可以直接回答：**LLM 实际只用了返回内容的多少比例？** ——这是 Token 优化潜力的直接证据。

---

## 4. 实验脚本架构

```
exp01/
├── README.md              ← 本设计文档
├── agent_loop.py          ← 主实验脚本（含 agent loop + 数据采集）
├── search_backend.py      ← DuckDuckGo 搜索封装
├── analyzer.py            ← 实验后数据分析（热力图 + 指标计算）
├── prompts.py             ← system_prompt + tool 定义常量
├── requirements.txt       ← 依赖：openai, duckduckgo_search, ...
└── results/
    ├── experiment_group/  ← 实验组结果（含 reasoning）
    │   ├── round_1.json
    │   ├── round_2.json
    │   └── summary.json
    └── control_group/     ← 对照组结果（不含 reasoning）
        ├── round_1.json
        └── summary.json
```

### 4.1 核心数据采集格式

每轮 tool_call 捕获以下数据保存到 JSON：

```json
{
    "round": 1,
    "query": "宁德时代 2024 营收 净利润",
    "reasoning_analysis": {
        "key_findings_used": ["initial_search"],
        "gaps_identified": "需要知道分业务板块数据",
        "search_strategy": "获取营收构成明细"
    },
    "tool_result_snippet": "宁德时代(300750.SZ)2024年营收3600亿元...",
    "tool_result_length": 5842,
    "next_round_references": null
}
```

第二轮：

```json
{
    "round": 2,
    "query": "宁德时代 2024 动力电池 储能 营收占比",
    "reasoning_analysis": {
        "key_findings_used": [
            "2024年总营收3600亿元，同比增长22%",
            "净利润500亿元"
        ],
        "gaps_identified": "",
        "search_strategy": ""
    }
}
```

### 4.2 数据分析流程

```
实验完成
    │
    ▼
提取所有 tool_call_history
    │
    ├── 对每轮: 解析 key_findings_used
    │   └── 与上一轮 tool_result 逐段匹配（模糊匹配 + 关键词匹配）
    │       ├── 匹配成功 → 标记为"已引用"，记录准确率
    │       └── 匹配失败 → 标记为"疑似幻觉"或"推理性引用"
    │
    ├── 跨轮次一致性检查
    │   ├── gaps_identified(N轮) → 是否在 N+1 轮被查询
    │   └── search_strategy(N轮) → 是否与 N+1 轮 query 一致
    │
    └── 生成热力图 + 指标报告
```

---

## 5. 实验风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| LLM 在 reasoning 中敷衍填入通用描述 | 中 | 高 | 工具描述中强调"必须包含具体数字"，system prompt 施压 |
| DuckDuckGo 搜索质量不稳定 | 中 | 中 | 如果 DDG 结果太差，备选方案为 Tavily API（需 Key） |
| 中文搜索效果不如英文 | 低 | 中 | 测试场景为中文公司，DDG 对中文搜索支持尚可 |
| LLM 一次性返回所有搜索而不用逐步推理 | 低 | 低 | 可在 system prompt 约束"分多步深入" |
| reasoning 字段增加的 tokens 超过收益 | 低 | 低 | 实验本身会测量额外开销，作为评估指标的一部分 |

---

## 6. 成功标准

- **基线条件**：LLM 在 ≥80% 的 tool_call 中按要求填写了 reasoning_analysis，且非空
- **通过条件**：引用准确率 ≥ 70%（即 key_findings_used 中的条目确实能在上一轮结果中找到对应）
- **优秀条件**：引用准确率 ≥ 85% + 推理一致性 ≥ 80% + 实验组和对照组的搜索轮数无显著差异

---

## 7. 待决策问题

1. **搜索后端选哪个？**
   - A）DuckDuckGo（免费，无需 Key，但中文结果可能不理想）
   - B）Tavily（需 Key，但 search + extract 分层可控）
   - C）先在实验中使用 DDG，失败时 Fallback 到 Tavily

2. **实验组和对照组在同一个脚本中运行，还是分成两个独立脚本？**
   - 同一脚本更便于对比但逻辑更复杂
   - 两个独立脚本更清晰但需要人工对照

3. **搜索范围**——是否限定搜索的 time_range 或 domain？
   - 限定：`site:eastmoney.com OR site:finance.sina.com.cn` → 结果更精准但信息覆盖面窄
   - 不限定：结果更泛但可能包含更多无用信息，测试 reasoning 更严苛
