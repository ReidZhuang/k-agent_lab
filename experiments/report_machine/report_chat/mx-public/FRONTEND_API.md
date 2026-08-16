# mx-public 前端调用方式（给前端开发）

> 目标：让前端像 **ChatGPT / DeepSeek 网页版**一样与 mx-public 对话——流式打字机效果、多轮上下文、每用户会话隔离。全部通过 OpenClaw Gateway 的 OpenAI 兼容端点实现。

## 1. 一句话速览

```
POST http://127.0.0.1:18789/v1/chat/completions
Authorization: Bearer <gateway-token>
model = "openclaw/mx-public"
```

支持标准 OpenAI Chat Completions 协议：`messages` 数组、`stream: true` 流式 SSE（打字机效果）、多轮对话延续、每用户 session key 隔离。

## 2. 基础参数

| 参数 | 值 | 说明 |
|---|---|---|
| URL | `http://127.0.0.1:18789/v1/chat/completions` | gateway HTTP 端口（18789） |
| 认证 | `Authorization: Bearer <token>` | gateway token（`openclaw.json` 中 `gateway.auth.token`） |
| model | `openclaw/mx-public` | **必须是这个**，路由到 mx-public agent |
| 流式 | `"stream": true` | SSE 流式返回，打字机效果 |
| 会话隔离 | `x-openclaw-session-key` 请求头 | 每用户一个固定 key，见 §3 |

### 可用端点
- `GET /v1/models` — 列出可用 agent（会看到 `openclaw/mx-public`）
- `POST /v1/chat/completions` — 对话主端点
- `POST /v1/embeddings` — 嵌入（一般用不到）

## 3. 会话隔离（最重要！）

OpenClaw 默认**每次请求无状态**（每次生成新会话）。要像 ChatGPT 一样多轮延续，必须指定会话归属。两种方式：

### 方式 A：`x-openclaw-session-key`（推荐，精确控制）
```http
x-openclaw-session-key: agent:mx-public:<用户会话ID>
```
- **`agent:mx-public:` 前缀必须带**——决定路由到 mx-public 的 workspace/skills；不带前缀会落到 main agent、加载错误 skills
- `<用户会话ID>` 由你前端生成：**每个用户（或每个对话线程）一个唯一固定值**，如 `user-10086-conv-abc123`
- 同一会话 ID 多次调用 = 同一对话上下文延续
- 不同用户用不同 ID = 天然隔离，互不串台

### 方式 B：OpenAI 标准 `user` 字段
```json
{ "user": "conv:<会话ID>" }
```
Gateway 会从 `user` 派生稳定 session key。适合不想碰自定义头的场景，但隔离粒度不如方式 A 精确。**前端推荐用方式 A。**

### 会话 ID 生成建议
- **每用户每会话一个**：`<userId>-<convId>`（convId 前端生成 uuid）
- 新对话 = 新 convId；继续对话 = 复用原 convId
- 前端本地存 convId ↔ 会话映射（页面刷新后仍能恢复上下文）

## 4. 调用示例

### 4.1 非流式（简单场景/调试）
```bash
curl -sS http://127.0.0.1:18789/v1/chat/completions \
  -H 'Authorization: Bearer <gateway-token>' \
  -H 'Content-Type: application/json' \
  -H 'x-openclaw-session-key: agent:mx-public:user-10086-conv-abc123' \
  -d '{
    "model": "openclaw/mx-public",
    "messages": [{"role": "user", "content": "帮我分析一下电子化学品板块今天涨幅前列的公司"}]
  }'
```

### 4.2 流式（ChatGPT 网页版打字机效果）
```bash
curl -N http://127.0.0.1:18789/v1/chat/completions \
  -H 'Authorization: Bearer <gateway-token>' \
  -H 'Content-Type: application/json' \
  -H 'x-openclaw-session-key: agent:mx-public:user-10086-conv-abc123' \
  -d '{
    "model": "openclaw/mx-public",
    "stream": true,
    "messages": [{"role": "user", "content": "你好"}]
  }'
```
返回 `Content-Type: text/event-stream`，每行 `data: <json>`，最后 `data: [DONE]`。前端用 `EventSource` 或 `fetch` + ReadableStream 逐块渲染即可实现打字机效果。

### 4.3 前端 JS（fetch 流式示例）
```javascript
async function chat(messages, sessionKey, onDelta) {
  const resp = await fetch('http://127.0.0.1:18789/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + GATEWAY_TOKEN,   // 建议由后端转发，前端不直接持有
      'Content-Type': 'application/json',
      'x-openclaw-session-key': 'agent:mx-public:' + sessionKey,
    },
    body: JSON.stringify({ model: 'openclaw/mx-public', stream: true, messages }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop(); // 保留不完整行
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (data === '[DONE]') return;
      try {
        const json = JSON.parse(data);
        const delta = json.choices?.[0]?.delta?.content;
        if (delta) onDelta(delta);   // 逐字/逐块渲染到页面
      } catch {}
    }
  }
}

// 使用：
// await chat([{role:'user', content:'分析一下中石科技'}], 'user-10086-conv-abc123', (t) => appendText(t));
```

### 4.4 多轮对话（延续上下文）
前端把历史消息累积在 `messages` 数组里，每次请求带上全部历史 + 新消息：
```json
{
  "model": "openclaw/mx-public",
  "stream": true,
  "messages": [
    {"role": "user", "content": "中石科技今天为什么涨停？"},
    {"role": "assistant", "content": "中际旭创拟 17.47 亿受让 10.47% 股份……"},
    {"role": "user", "content": "那它估值贵吗？"}
  ]
}
```
> 注意：会话隔离 key 相同 + 历史消息带上 = 上下文连续。即使只依赖 gateway 侧会话记忆（不带历史），同一 key 也会让 agent 记得之前的对话，但**建议前端同时维护 messages 数组**，体验最稳。

## 5. 前端接入架构建议（安全）

```
[浏览器前端页面]  --(HTTPS, 用户登录)-->  [你的后端服务]  --(内网 HTTP+token)-->  OpenClaw Gateway (127.0.0.1:18789)
```

- **gateway token 只放在你的后端**，浏览器永远不接触
- 后端做：用户认证 → 校验权限 → 生成/复用 session key → 转发到 gateway → 把 SSE 流透传给前端
- 每用户唯一 session key（§3 方式 A），后端在用户登录时建立映射
- 流式透传：后端用 `fetch` 流式读 gateway，再以 `text/event-stream` 转发给前端（或用 WebSocket 包装）

## 6. 与 ChatGPT/DeepSeek 网页版的体验对照

| 能力 | 实现方式 |
|---|---|
| 打字机效果 | `stream: true` + SSE 逐块渲染（§4.3 的 onDelta） |
| 多轮上下文 | 同一 session key + messages 历史（§4.4） |
| 每用户独立会话 | session key 按用户隔离（§3） |
| 新建对话 | 换一个新 convId 的 session key |
| 历史会话恢复 | 前端本地保存 convId 映射，恢复时复用 key + 加载历史 messages |
| 停止生成 | 前端 abort fetch（AbortController）；agent 侧以任务隔离 + 超时兜底 |

## 7. 多会话管理（DeepSeek 式左侧会话列表）

支持：**新开聊天 = 新 session key，旧聊天不丢失、可并行、可恢复**。

### 7.1 核心机制
- 每个会话对应唯一 key：`agent:mx-public:<userId>-<convId>`（convId 前端生成 uuid）
- **新开聊天**：生成新 convId → 新 key → 全新上下文，与旧会话完全隔离
- **继续旧聊天**：复用旧 convId → 同一 key → 上下文延续
- 多会话可同时并存、互不干扰（gateway 按 key 隔离）

### 7.2 旧聊天不丢失 = 两层保障
| 层 | 机制 | 保留期 |
|---|---|---|
| Gateway 侧 | 旧 key 的 transcript 存在 `~/.openclaw/agents/mx-public/sessions/`，同 key 再调用时 agent 记得之前对话 | 7 天（guardian 每天 3:05 自动归档清理，防无限膨胀） |
| 前端侧（推荐） | 前端/后端数据库存每个会话的 `{convId, title, messages[]}`；恢复时用旧 key + 全量回放 messages | 永久（由前端存储决定） |

> **要像 DeepSeek 那样聊天记录永在，前端必须自己存消息历史并回放**；只依赖 gateway 记忆的"可续聊"窗口是 7 天。

### 7.3 前端左侧栏实现要点
1. 存会话数组：`[{convId, title, updatedAt, messages[]}]`（localStorage 或后端 DB）
2. 新建聊天 → 生成 uuid convId → 空 messages → 显示为空对话
3. 点历史会话 → 用其 convId 组 key + 回放 messages（恢复现场）
4. 标题自动生成：截取首条用户消息前 ~20 字（或让 agent 生成一句话）
5. 删除会话 = 前端删记录即可（可选：再删 gateway transcript，一般不必）
6. 并发提示：同一会话同时开两个页面可能上下文竞争，建议前端对同 convId 做互斥（或每轮后刷新本地 messages）

## 8. 已知限制与提示

- **agent 思考/工具调用需要时间**：股票分析类请求（走 mx 数据源 + 多技能）可能耗时 30s~数分钟，流式下前端需展示"正在分析"状态；若使用 mx 数据，受 mx 积分配额限制（配额耗尽会返回标准错误块）
- **`/v1/chat/completions` = 操作员权限面**：安全边界见 README §6，token 严禁进浏览器
- 若 agent 中途调用工具，流式可能先出工具过程再出最终答案——前端建议把 `delta.content` 之外的工具事件忽略或折叠展示（简单起见：只渲染 content 增量即可）
- 如需控制后端模型（默认 deepseek-v4-flash），可加请求头 `x-openclaw-model: <provider/model>` 覆盖（一般不需要）

## 9. 快速自检

```bash
# 1. 能列出模型吗？
curl -sS http://127.0.0.1:18789/v1/models -H 'Authorization: Bearer <token>'

# 2. 非流式对话通吗？（会看到 mx-public 自我介绍，且不认识 mx-agent = 记忆隔离生效）
curl -sS http://127.0.0.1:18789/v1/chat/completions \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -H 'x-openclaw-session-key: agent:mx-public:test-1' \
  -d '{"model":"openclaw/mx-public","messages":[{"role":"user","content":"你是谁？"}]}'
```

---

*配套文档：README.md（运维与策略）。文件位置：`/home/stockagent/project_space/research/experiments/report_machine/report_chat/mx-public/`*
