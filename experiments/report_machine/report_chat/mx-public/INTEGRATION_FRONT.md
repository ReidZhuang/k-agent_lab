# mx-public 前端接入记录（股神的秘密 · 股小神）

> 本文件记录 mx-public 的首个前端消费方 ——「股神的秘密」8320 后端的对接落地情况。
> 调用规范见 [FRONTEND_API.md](FRONTEND_API.md)；前端侧功能文档见 `experiments/front/intro/chat.md`。

## 1. 接入架构（已落地）

```
[浏览器 ChatPanel.vue] ──登录态──> [8320 后端 chat_api.py] ──Bearer token──> [OpenClaw Gateway 18789]
```

- **token 安全边界（FRONTEND_API.md §5）**：gateway token 只存在 8320 后端，浏览器永不接触
- 8320 代理端点：`POST /api/chat/completions`，SSE 逐字节透传（`httpx.AsyncClient.stream`，timeout=None）
- token 每次请求现读 `~/.openclaw/openclaw.json` 的 `gateway.auth.token`——管理员轮换后无需重启 8320

## 2. 会话隔离落地

- session key：`agent:mx-public:<userId>-<convId>`
  - `<userId>` = 8320 登录用户 ID（`_get_user` 依赖），用户间天然隔离
  - `<convId>` = 前端生成的会话 ID（每会话一个）
- 前缀 `agent:mx-public:` 保证路由到 mx-public 的 workspace/skills（FRONTEND_API.md §3）

## 3. 会话持久化（两层保障的落地分工）

| 层 | 实现 | 保留期 |
|---|---|---|
| Gateway 侧 transcript | 同 key 再调用 agent 记得对话 | 7 天（guardian 每天 3:05 归档） |
| 前端侧 DB（**主依赖**） | 8320 SQLite `chat_session` / `chat_message` 表，前端每次请求带全量历史 + 回放恢复 | 永久 |

消息落库时序（保证历史与展示一致）：
1. `/api/chat/completions` 后端在转发前落库最后一条 user 消息（首条自动生成标题：前 20 字）
2. 流式结束后前端 POST `/api/chat/sessions/{conv_id}/messages` 回存 assistant 完整回复
3. 用户停止生成 / 切换会话（前端 abort）时，已生成的部分同样回存

## 4. 错误透传

- gateway 非 200（含 `Unknown model: disabled/disabled` 配额超限）→ 后端收集错误体，以 SSE `data: {error: {message}}` 帧透传 → 前端提示
- gateway 配置缺失 → 502「Gateway 配置不可用」

## 5. 排障速查（叠加 README §7）

| 现象 | 检查 |
|---|---|
| 前端所有对话报「Unknown model: disabled/disabled」 | token 超限 → `guardian.py unlock` + 重启 gateway |
| 两个用户对话串台 | session key 是否带上了 userId（`agent:mx-public:<userId>-<convId>`） |
| 对话不记得上一句 | 前端 messages 历史是否全量带上；同 convId 是否复用 |
| 历史会话消失 | 会话在 8320 DB（永久）；gateway transcript 7 天归档只影响 agent 侧记忆，不影响前端回放 |

---

*最近更新：2026-08-16（股小神上线）*
