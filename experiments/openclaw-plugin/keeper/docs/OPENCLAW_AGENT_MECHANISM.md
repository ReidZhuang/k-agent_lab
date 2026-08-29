# OpenClaw Agent 运作机制详解（v2026.6.1，源码实证版）

> 版本：2026-08-26 落盘 · 基于本机 `/usr/lib/node_modules/openclaw/`（2026.6.1）dist 源码 + 官方 docs 实证
> 用途：为 keeper 档位2插件（`api.on("context")` 语义级语料压缩）设计提供"机制层"依据。
> 阅读约定：**【★ 与插件直接相关】** 标记为插件落地点；代码引用 `dist/xxx.js:行号` 可 `sed -n` 复核。

---

## 0. 一句话结论

OpenClaw 每次调用模型的路径是固定的：

```
runLoop → streamAssistantResponse
        → transformContext(内置 guard 链 + 你的 api.on("context") 插件)   ←★ 语义压缩在这里
        → convertToLlm(内部消息转 provider 格式)
        → provider
```

语义级语料压缩 = **用 `tool_result_persist` 保证取数格式契约 + 用 `before_tool_call` 清理顺带参数 + 用 `api.on("context")` 在每次提交前把旧 tool 结果替换成"被引用行+摘要"**，全程只改发给模型那份内存，不动盘上 transcript。这正是原生 `contextPruning` 的设计语义；本插件只是把"长度启发式"换成"LLM 语义级判断"。

---

## 1. 总体架构：一次 agent 运行的外壳

### 1.1 分层模型

| 层 | 例子 | 含义 |
|---|---|---|
| **Provider** | `opencode-go`、`anthropic` | 认证、模型目录、模型引用命名 |
| **Model** | `deepseek-v4-flash` | 某次 turn 实际选中的模型 |
| **Agent runtime** | `openclaw`（内嵌）、`codex`、`claude-cli` | 真正执行"准备好的模型循环"的低层环路 |
| **Channel** | Telegram、Discord、`/v1/chat/completions` | 消息进出 OpenClaw 的渠道 |

keeper 用**内嵌 openclaw runtime + opencode-go provider（OpenAI-completions 协议）**。runtime 选型只影响"谁拥有模型循环"；`context` 钩子完整程度以内嵌 openclaw runtime 为最高——这对 keeper 是利好。

### 1.2 会话状态归属

**Gateway 进程是会话状态唯一主人**（keeper 独立 profile = 独立 gateway/state）：

- **Session store**：`~/.openclaw-keeper/agents/<agentId>/sessions/sessions.json` —— `sessionKey → SessionEntry` 关系表（当前 sessionId、时间戳、toggles、token 计数器、`compactionCount` 等）
- **Transcript**：`~/.openclaw-keeper/agents/<agentId>/sessions/<sessionId>.jsonl` —— 追加式、树形（每条有 `id`+`parentId`）对话全文 + tool call/result + compaction 摘要

### 1.3 一次运行的入口（三种）

| 入口 | 说明 | keeper 用法 |
|---|---|---|
| `openclaw agent --agent keeper --message "..."` | CLI 单次运行 | run_report.sh 备选 |
| Gateway RPC `agent`/`agent.wait` | 程序化调用 | 同下 |
| `POST /v1/chat/completions`（`gateway.http.endpoints.chatCompletions.enabled`）| OpenAI 兼容端点，走**与 CLI 相同的 agent 运行代码路径** | `gen_report.py` 现用：同步、只拿最终 content+usage；中间轮在 agent 会话内部发生 |

HTTP 端点会话语义：**默认每请求无状态**（每次新 session key）；带 `user` 字符串按它派生稳定 session key；也可用 `x-openclaw-session-key` 头完全控制路由。反复调用同一 session-key 即形成持久会话——语义压缩发生的容器。

### 1.4 运行前置步骤（`agentCommand` → `runEmbeddedAgent`）

1. 校验参数、解析 session、持久化元数据，立即返回 `{runId, acceptedAt}`
2. `agentCommand`：解析 model/thinking 默认值 → 加载 skills 快照 → 调 `runEmbeddedAgent`
3. `runEmbeddedAgent`：**按 session lane 串行化**（每 session 一把队列 + 可选全局 lane）→ 解析模型与 auth → 构建 session → 订阅运行时事件 → agent 运行事件桥接为 `agent` 流（`tool`/`assistant`/`lifecycle` 三路）→ 强制超时（默认 48h）
4. Transcript 写入受**会话写锁**保护（文件级、跨进程感知，等待超时默认 60s）

---

## 2. 核心循环：`runLoop`（agent 电机本体）

源码：`dist/proxy-C4ZsjXLz.js`。骨架（略错误分支）：

```
while (true) {
  while (有更多 tool calls 或 pendingMessages) {
    投递 steering/followup 消息进 context
    message = streamAssistantResponse(context, ...)     // ← 一次模型调用
    if (stopReason == error/aborted) → agent_end 返回
    toolCalls = message.content 中 type=="toolCall" 的块
    if (toolCalls.length > 0) {
      executed = executeToolCalls(context, message, ...)  // 顺序/并行
      for result: context.messages.push(result)           // ←★ tool 结果进入下一轮可见 context
    }
    turn_end 事件; 检查 shouldStopAfterTurn
  }
  取 followUpMessages 继续; 否则 break → agent_end
}
```

**这就是"tool call round"的本体**。exp02 优化窗口 = "结果进 context 后、下一轮调模型前"——旧 tool 结果滚雪球导致输入二次膨胀。

### 2.1 `streamAssistantResponse`：每次模型调用流水线

```
messages = context.messages
if (config.transformContext) messages = await config.transformContext(messages, signal)  // ←★ 插件
llmMessages = await config.convertToLlm(messages)        // 内部 AgentMessage[] → provider 格式
llmContext  = { systemPrompt, messages: llmMessages, tools }
response = streamFn(model, llmContext, ...)              // 真实 HTTP 调用
```

**每调一次模型，`transformContext` 必然执行一次。** `systemPrompt` 独立传给 provider，不在 messages 数组里。

---

## 3. Context 是什么、`transformContext` 链上都有谁

### 3.1 模型看到的全部内容（`docs/concepts/context.md`）

- **System prompt**（每次重建）：内置 base prompt + 工具列表与短描述 + skills 列表（仅元数据）+ 工作区路径 + 时间 + runtime 元数据 + 注入的工作区文件（`AGENTS.md`/`SOUL.md`/`TOOLS.md`/`IDENTITY.md`/`USER.md`/`HEARTBEAT.md`/`BOOTSTRAP.md`，按 `bootstrapMaxChars` 截断、总上限 `bootstrapTotalMaxChars`）+ 工具 JSON schema
- **会话历史**：user/assistant/toolResult 全量
- **附件/媒体块**

### 3.2 ★ `transformContext` 链成员与严格顺序（源码实证）

`config.transformContext` 是多个安装器**链式包裹**的复合函数。安装顺序（每轮 run 准备时）与最终调用顺序（最外层先跑）：

```
外层  installModelPromptTransform      （替换最后一条 user prompt 为 modelPrompt + prepend/appendContext）
  ↓  installHistoryImagePruneContextTransform（旧图片块 → 占位标记）
  ↓  installToolResultContextGuard     （★ 单条 tool 结果 > maxSingleToolResultChars 就地截断;
                                          整体超阈值抛 PREEMPTIVE_CONTEXT_OVERFLOW_MESSAGE;
                                          midTurnPrecheck.enabled 时再做超窗预检）
  ↓  installContextEngineLoopHook      （仅当插件 context engine 声明 ownsCompaction 时存在;
                                          每轮迭代跑 afterTurn + assemble）
  ↓  最内层 base transformContext = runner.emitContext(messages)
      =====> ★★ plugin api.on("context") 处理器链 跑在这里 ★★
```

关键推论：

1. **插件 `context` 处理器跑在"内置 tool-result 兜底截断"和"溢出预检报错"之前**——语义压缩省下的字节能**直接避免**内置 `PREEMPTIVE_CONTEXT_OVERFLOW_MESSAGE` 硬报错。
2. 插件看到的是**换好当前 prompt 后、未转 provider 格式**的内部 `AgentMessage[]`；`toolResult.details` 此时仍在（`convertToLlm` 之后才剥离）。
3. `context` 处理器之间**无 priority 排序**，顺序=扩展加载顺序——**原生 contextPruning 与你的插件在同一条链上竞争**，谁先谁后实验期必须实测（或显式关闭 contextPruning）。

### 3.3 ★ 消息内部格式（`dist/types-DAMKpKGt.d.ts`，插件要解析的就是它）

```
UserMessage        { role:"user";      content: string | (Text|Image)[]; timestamp }
AssistantMessage   { role:"assistant"; content: (Text|Thinking|ToolCall)[];
                     api; provider; model; usage; stopReason; errorMessage?; timestamp }
ToolResultMessage  { role:"toolResult"; toolCallId; toolName;
                     content: (TextContent|ImageContent)[];   // ← 模型可见正文
                     details?: TDetails;                      // ← runtime 元数据, 进 provider 前剥离
                     isError; timestamp }
ToolCall block     { id; name; arguments: Record<string,unknown>; executionMode? }
TextContent        { type:"text"; text }
```

两个事实直接决定插件设计：

- **`discard_lines`(v2) 的载体 = AssistantMessage 中某 ToolCall.arguments 的键**；在 transcript/context 中位置稳定，插件可直接扫。
- **`toolResult.content` 必须是模型可见的部分，`details` 不是**——JSON 行集、行号标记全都要落在 `content` 的 text blocks 里。

---

## 4. 工具执行机制：一次 tool call 完整路径

### 4.1 工具注册

- 插件 `api.registerTool({name, description, parameters: TypeBox schema, execute(id, params) → {content:[{type:"text",text}], details?, terminate?}})`；manifest `contracts.tools` 声明归属；可选工具需 `tools.allow` 白名单
- **参数 schema（TypeBox）会被完整发给模型**——这给了"在工具 schema 里声明 `discard_lines` 可选参数、逼模型结构化输出"的空间（★ 见 PLUGIN_DESIGN_V2.md）

### 4.2 一次执行流水线（`executeToolCalls`/`finalizeExecutedToolCall`）

```
assistant 中取 toolCall blocks
prepareToolCall:
  找工具; validateToolArguments(schema 校验)
  config.beforeToolCall(...)          ←★ before_tool_call 插件钩子的宿主(可改 params/block/requireApproval)
executePreparedToolCall → 真正调用工具 execute(id, args)
finalizeExecutedToolCall:
  config.afterToolCall(...)           ←★ tool_result_persist 插件钩子的宿主
  (可返回 {content, details, isError} 覆盖工具结果)
createToolResultMessage → { role:"toolResult", toolCallId, toolName, content, details, isError, timestamp }
push 进 context.messages + newMessages（随后写进 transcript 的也是它）
```

### 4.3 ★ 与你直接相关的两个工具钩子

- **`before_tool_call`**：`event.{toolName, params, toolCallId, runId, toolKind}`；可返回 `{block:true,blockReason}`（终端语义阻断）、`{params:{...}}`（改写参数）、`{requireApproval}`。**示范用途**：把模型塞进查询里但不想让真工具看到的 `discard_lines` 在此从 `params` 剥离。
- **`tool_result_persist`**（实现为 extension runner 的 `tool_result` 事件）：`event.{toolName, toolCallId, input, content, details, isError}`，返回 `{content, details, isError}` 覆盖最终结果。**跑在"结果入 context + 写盘 transcript"之前**。**示范用途**：对取数工具返回统一注入 JSON 行集格式（v2 契约）。

边界：`details` 在 provider replay 与 compaction 输入之前剥离；transcript 只保留有界 `details`，过大替换为 `persistedDetailsTruncated:true`。**模型必读的文本放 `content`，别放 `details`**。

---

## 5. 消息持久化：transcript 与 session 生命周期

- Transcript：JSONL，首行 `type:"session"` 头（id/cwd/timestamp/parentSession）；之后 `message`（user/assistant/toolResult）、`custom_message`（进模型 context）、`custom`（不进 context 的扩展状态）、`compaction`（`firstKeptEntryId`+`tokensBefore`）、`branch_summary`、`model_change`、`thinking_level_change`
- sessionId 生命周期：每 sessionKey 一个当前 sessionId；`/new`/`/reset`、每日 4:00 本地重置（默认）、`session.reset.idleMinutes` 可选空闲重置；`sessions.json` 里 `sessionStartedAt`（日重置基准）/`lastInteractionAt`（空闲基准）/`updatedAt`
- **★ 插件语义压缩不改 transcript** —— 无论压缩多少次，jsonl 里永远保留原始全文，随时可回看/复盘。

---

## 6. 上下文管理机制（原生三件套 + 插件引擎）

### 6.1 原生 `contextPruning`（启发式裁剪 tool 结果）

- **★ 本身就是一个 `api.on("context")` 处理器**（`dist/compaction-successor-transcript-CUmEvaGX.js:3031`）——"`context` 事件可用"的官方先例
- **内存语义**：只改内存，不改盘上 transcript
- 机制（`pruneContextMessages`）：`mode:"cache-ttl"`（默认 ttl 300s，配合 Anthropic prompt cache）；**soft-trim**（超 `softTrimRatio`，保头尾 `softTrim.headChars/tailChars` 各 1500 中间 `...`）；**hard-clear**（比例再超 `hardClearRatio` 且可剪字节 ≥ `minPrunableToolChars` 5e4，整条换占位符 `[Old tool result content cleared]`）；`keepLastAssistants:3`
- 默认：**非 Anthropic provider 关闭**（keeper 用 opencode-go → 默认 off）
- 局限：只看长度/位置，看不到语义——正是插件要补的

### 6.2 compaction（摘要压缩，持久写盘）

- 触发#1 **溢出恢复**：模型返回溢出类错误签名 → 本地压缩 → 重试
- 触发#2 **阈值维护**：turn 成功后 `contextTokens > contextWindow - reserveTokens` → 压缩
- 行为：较老轮次摘要成 `compaction` entry 写回 transcript，最近消息原样保留；**压缩前先跑一个静默（NO_REPLY）"写 memory"turn**（memory flush）；切分保证 **assistant 的 tool call 与其 toolResult 配对不拆散**；`truncateAfterCompaction:true` 时压缩后轮换 successor transcript
- keeper 现状配置：reserveTokens 20000 / keepRecentTokens 20000 / midTurnPrecheck.enabled=false / memoryFlush.enabled=true / truncateAfterCompaction=true / maxActiveTranscriptBytes="10mb" / notifyUser=false
- `maxActiveTranscriptBytes`：turn 开跑前活跃 jsonl 达字节数 → 先本地压缩；`midTurnPrecheck` 是轮中 tool 结果追加后、下次模型提交前的预算预检（keeper 保持 disabled）
- 定位：compaction=整段对话摘要且**持久写盘**；pruning=tool 结果修剪且**每次请求内存态**

### 6.3 可插拔 `contextEngine`（插件级，较高路线）

- 默认 `legacy` 引擎（assemble 直通、内置 compaction）
- 插件引擎：`api.registerContextEngine(id, factory)`，实现 `info/ingest/assemble/compact`（可选 afterTurn/bootstrap 等）；`plugins.slots.contextEngine` 选定（唯一激活）——`assemble` 返回 `{messages, estimatedTokens, systemPromptAddition?}`，能**完全接管发给模型的消息列表**
- `ownsCompaction:true` → 禁用内置自动压缩、引擎自管；引擎抛错被隔离并降级回 legacy
- ⚠️ 这是"另起炉灶"路线，代价大；v2 设计走轻量 `context` 事件路线，两者可共存（`context` 事件始终运行）

---

## 7. 插件系统全景

### 7.1 形态与加载

- 原生插件 = `openclaw.plugin.json` manifest + 进程内运行时模块；发现路径：`plugins.load.paths`、workspace、全局插件目录、bundled
- manifest 关键字段：`id/name/description/contracts(tools)/activation(onStartup)/configSchema/toolMetadata`
- 入口：`definePluginEntry({id, name, description, register(api){...}})`（`openclaw/plugin-sdk/plugin-entry`）
- 配置：`plugins.entries.<id>.config/.enabled`、`plugins.allow/deny`、`plugins.slots.*`；本地开发 `openclaw plugins install ./plugin --link`，改代码重启 gateway
- 信任边界：原生插件与核心同进程同权限

### 7.2 `api` 对象（`docs/plugins/sdk-overview.md`）

注册类：`registerTool/registerCommand/registerProvider/registerContextEngine/registerCompactionProvider/registerHook/registerHttpRoute/registerGatewayMethod/registerCli/registerService`
hooks/工作流：`api.on(...)`（typed hook）、`enqueueNextTurnInjection`、`registerSessionExtension`（持久 JSON 会话状态）、`registerAgentEventSubscription`、`runContext`
字段：`api.id/name/version/config/pluginConfig/runtime/logger/registrationMode/resolvePath`

### 7.3 `api.on(...)` typed hooks 目录（`docs/plugins/hooks.md`）

- **Agent turn**：`before_model_resolve`、`agent_turn_prepare`、`before_prompt_build`（prependContext/systemPrompt 注入）、`before_agent_start`、`before_agent_run`（可 block）、`before_agent_reply`（可短路合成回复）、`before_agent_finalize`、`agent_end`、`heartbeat_prompt_contribution`
- **观察**：`model_call_started/ended`、`llm_input`、`llm_output`（★ token 实测来源）
- **工具**：`before_tool_call`（block/改写参数/审批）、`after_tool_call`（观察）、`resolve_exec_env`、`tool_result_persist`（★ 改写 tool 结果）、`before_message_write`
- **消息**：`inbound_claim`、`message_received`、`message_sending`（cancel/改写）、`reply_payload_sending`、`message_sent`、`before_dispatch`
- **会话/压缩**：`session_start/end`、`before_compaction/after_compaction`、`before_reset`
- **子 agent**：`subagent_spawned/ended`、`subagent_delivery_target`
- **生命周期**：`gateway_start/stop`、`cron_changed`、`before_install`

优先级：同事件按 `priority` 高→低；同 priority 保持注册序；`block:true`/`cancel:true` 为终端语义（跳过更低优先级）。
配置门槛：`plugins.entries.<id>.hooks.{timeoutMs,timeouts.<hookName>}`；对话访问类事件（`before_model_resolve`/`before_agent_reply`/`llm_input`/`llm_output`/`before_agent_finalize`/`agent_end`/`before_agent_run`）需要 `hooks.allowConversationAccess:true`。

### 7.4 ★ `context` 事件精确语义（你要用的那个，`dist/sessions-CHf3LZvU.js` emitContext）

```
emitContext(messages):
  currentMessages = structuredClone(messages)          // 深拷贝一次
  for ext in extensions:
    for handler in ext.handlers.get("context"):
      r = await handler({ type:"context", messages: currentMessages }, ctx)
      if (r && r.messages) currentMessages = r.messages  // 后处理看前处理成果
  return currentMessages                                  // 即 transformContext 返回值
```

- **返回契约**：`{ messages: next }` 即替换待发消息；不返回/`{messages:undefined}` 保持原样。多插件串行。
- **handler 的 `ctx`（extension runner createContext）**：`cwd/sessionManager/modelRegistry/model/signal/abort/compact(options)/getContextUsage()/getSystemPrompt()/isIdle/hasPendingMessages/shutdown/ui/hasUI`；typed hooks 另注入 `pluginConfig/agentId/sessionKey/sessionId/runId/trace`。
- **内置先例**：`contextPruningExtension` 正是 `api.on("context")` 返回 `{messages: pruneContextMessages(...)}`。
- ⚠️ **无 priority**：顺序=扩展加载顺序；内置 pruning 与插件同链竞争。
- ⚠️ `structuredClone` 保证 handler 收到的 `event.messages` 是深拷贝（改它安全）；返回后，内置 guard 在你返回的那份上继续做截断/溢出检查。

---

## 8. Skills 机制

- 加载位置（高→低優先）：workspace `<ws>/skills` → `<ws>/.agents/skills` → `~/.agents/skills` → `~/.openclaw/skills` → bundled → **`skills.load.extraDirs`**（keeper 已含 `keeper/skills` + `stock_research_agent/skills`）
- **注入方式**：system prompt 只放**元数据列表**（name+description+位置）；SKILL.md 全文不默认注入，模型需要时用 `read` 按需读取 → skill 开销小，规则可写得很细

---

## 9. 模型/Provider 层与 prompt 缓存

- 模型引用 `provider/model`（按第一个 `/` 切分）；keeper 用 `opencode-go/deepseek-v4-flash`
- runtime 选型：model 级 `agentRuntime` → provider 级 → `auto` → 默认 `openclaw`
- `convertToLlm` 转 provider 格式：Anthropic 兼容层 `toolResult` → `role:"user"` 的 `tool_result` 块（`tool_use_id`、`is_error`），`toolCall` → `tool_use`，thinking 独立；**`details` 不进转换**；相邻多个 toolResult 并进同一 user 消息
- prompt cache：Anthropic 系有分级缓存；`contextPruning` 的 cache-ttl 正是配合它。opencode-go（openai-completions，无 cache 分级）主要受益的是**上下文窗口压力下降**，而非缓存成本

---

## 10. 插件落地的钩子接缝汇总（★ v2 设计依据）

| 钩子 | 时机 | v2 插件职责 |
|---|---|---|
| `tool_result_persist` | 工具返回后、写盘前 | 取数返回 → JSON 行集（含行号 n）+ 引用元数据 |
| `before_tool_call` | 工具执行前 | 剥离 `discard_lines` 等辅助参数；留日志 |
| `api.on("context")` | 每次调模型前 | 按上轮 `discard_lines` 压缩旧 tool 结果（只删内存那份）|

另：`llm_input`/`llm_output`/`model_call_ended`（token 实测）、`before_agent_finalize`/`agent_end`（汇总）、`before_prompt_build`（systemPrompt/上下文注入，可选）。

---

## 11. 相关文件索引

- 官方插件开发：`/usr/lib/node_modules/openclaw/docs/tools/plugin.md`、`docs/plugins/building-plugins.md`、`docs/plugins/hooks.md`、`docs/plugins/sdk-overview.md`
- 官方 session pruning：`docs/concepts/session-pruning.md`；官方 compaction：`docs/reference/session-management-compaction.md`
- dist 关键实现：`compaction-successor-transcript-CUmEvaGX.js`（contextPruning）、`sessions-CHf3LZvU.js`（emitContext/createContext）、`proxy-C4ZsjXLz.js`（runLoop/streamAssistantResponse/finalizeExecutedToolCall/convertToLlm）、`selection-DrXxngyT.js`（transformContext 链安装）、`types-DAMKpKGt.d.ts`（Message 类型）
- 实验环境：`keeper/README.md`、`keeper/docs/PLUGIN_DESIGN_V2.md`（插件设计 v2）、`keeper/docs/LOGGING.md`