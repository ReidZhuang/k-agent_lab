# 股小神 — 智能对话标签页

## 功能概述

主界面标签页「🤖 股小神」提供类似 DeepSeek 网页版的股票问答：

- **首页式入口** — 空态时展示大标题 + 居中大输入框 + 示例问题提示（点提示词直接填入）
- **流式打字机** — 与 mx-public agent 对话，逐块渲染回复
- **多会话管理** — 顶部会话选择条：最左大加号新建聊天；标签横向可拖动/滚动选择；点击切换历史会话继续聊；标签 hover 出现 × 删除
- **历史永存** — 会话与消息存后端数据库（按登录用户隔离），换浏览器/设备不丢
- **停止生成** — 生成中可点「■ 停止」，已生成部分保留

## 架构

```
[浏览器 ChatPanel.vue] ──(登录态 /api/chat/*)──> [8320 后端代理] ──(Bearer gateway-token)──> [OpenClaw Gateway 127.0.0.1:18789]
```

- 前端**永不接触** gateway token（安全边界，见 mx-public `FRONTEND_API.md` §5）
- 8320 后端持有 token（`chat_api.py` 每次请求现读 `~/.openclaw/openclaw.json`，管理员轮换 token 无需重启）
- 每个登录用户通过独立 session key 与 gateway 隔离

## 数据流（一次问答）

1. 前端 `chatStream()` 把**完整历史** POST 到 `/api/chat/completions`（AbortController 可中断）
2. 后端校验登录 → 会话不存在则自动创建 → 落库最后一条 user 消息（首条自动生成标题）→ 组装 session key → httpx 流式转发 gateway
3. gateway 的 SSE 增量（`data: {json}` 行）逐字节透传
4. 前端逐块渲染（打字机效果），流结束后 POST 回存 assistant 完整回复
5. 前端刷新会话列表（标题、更新时间已由后端更新）

## API 端点（均在 `/api` 下，需 `Authorization: <token>`）

| 方法 | URL | 说明 |
|---|---|---|
| POST | `/chat/completions` | 流式对话（SSE 透传），body `{conv_id, messages: [{role, content}]}` |
| GET | `/chat/sessions` | 会话列表（按最近更新倒序，含 message_count） |
| POST | `/chat/sessions` | 创建会话（幂等），body `{conv_id, title?}` |
| DELETE | `/chat/sessions/{conv_id}` | 删除会话及其全部消息 |
| GET | `/chat/sessions/{conv_id}/messages` | 消息历史（正序，用于恢复现场） |
| POST | `/chat/sessions/{conv_id}/messages` | 回存一条消息，body `{role: user\|assistant, content}` |

## 会话模型

| 项 | 规则 |
|---|---|
| conv_id | 前端生成（`c` + 时间戳36进制 + 随机串，非安全上下文无 crypto.randomUUID） |
| 标题 | 首条 user 消息前 20 字自动生成（后端 `append_chat_message` 内处理） |
| session key | `agent:mx-public:<userId>-<convId>`，userId 来自后端登录态，用户间天然隔离 |
| 停止生成 | 前端 abort fetch；已生成部分由前端回存，历史与展示一致 |
| 删除 | 会话 + 消息级联删除（`delete_chat_session` 事务内完成） |

## 前端实现要点（ChatPanel.vue）

- **会话条**：`overflow-x: auto` 横向滚动 + mousedown 拖拽滚动（点击标签/删除按钮不触发）；最左「＋」新建
- **hero 首页态**：`!currentConvId || messages.length === 0` 时展示，发送首条时自动建会话
- **消息渲染**：`marked`（gfm+breaks，与 DocPreview 一致），气泡内 markdown 样式 scoped 定义
- **流式收尾防污染**：`finally` 中仅当 `currentConvId` 仍是发起会话时才把回复 push 进消息列表（切换会话后 abort 的收尾不会串台）
- **输入框**：自适应高度（scrollHeight，上限 200px），Enter 发送 / Shift+Enter 换行

## 数据库（database.py）

```
chat_session(id, user_id, conv_id, title, created_at, updated_at)   UNIQUE(user_id, conv_id)
chat_message(id, session_id, role, content, created_at)
```

`CREATE TABLE IF NOT EXISTS` 幂等建表，旧库升级无需迁移。

## 排障

| 现象 | 原因 | 处理 |
|---|---|---|
| 对话报「Unknown model: disabled/disabled」 | mx-public token 超限被禁用 | `guardian.py unlock` + 重启 gateway |
| 对话报「Gateway 配置不可用」 | openclaw.json 缺失或 token 字段被改 | 检查 `~/.openclaw/openclaw.json` 的 `gateway.auth.token` |
| 流中断无报错 | 前端 abort（停止/切会话） | 预期行为，已生成部分自动回存 |
| 两个用户看到同一会话 | 不应发生 | 会话按 `user_id` 过滤 + session key 带 userId |

---

*配套文档：mx-public 侧接入记录见 `report_machine/report_chat/mx-public/INTEGRATION_FRONT.md`；gateway 调用规范见 `FRONTEND_API.md`*
