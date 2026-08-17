# MX MCP API Key 生命周期与多服务共享机制

> 状态：已定稿
> 日期：2026-08-17
> 关联文档：
> - `MX_MCP_TOKEN_CONFIG.md` — key 的配置位置与手动修改方法（本文档的浓缩版）
> - `MX_MCP_QUOTA_EXHAUSTED_HANDLER.md` — 积分耗尽错误的检测规则与字段契约（agent 侧）
> - `report_chat/mx-public/README.md` — mx-public 前端专用 Agent 运维文档（共享本 key 的消费者之一）

本文档完整记录：key 存哪里 → 凭据从哪来 → 手动/自动换 key 全流程 → 多 agent/多服务如何共享 → 并发安全与注意事项。

## 1. 全景：谁在用这把 key

本机 **OpenClaw Gateway**（`127.0.0.1:18789`）下所有 agent 共用一个东方财富 MCP 数据服务 `mx-ds-mcp`，即共用**同一个 `em_api_key`**：

| 消费者 | 类型 | 用途 |
|---|---|---|
| `mx-agent` | agent | 公司分析/板块分析报告生成（8323/8326 后端服务经 gateway 调用） |
| `mx-public` | agent | 前端「股小神」对话（同 skills 零记忆的独立 agent） |
| `ths-agent` / `main` / `agent_work_test` | agent | 其他工作区 agent（同样继承全局 MCP 配置） |

关键事实：`mcp.servers` 在 openclaw.json 中是**全局配置**（目前只有 `mx-ds-mcp` 一个 server），5 个 agent 的 `mcp` 字段全部是 **inherit default**（无 agent 级覆盖）→ 所有人走同一个 MCP server = 同一把 key = 同一账号的额度池。

## 2. Key 唯一配置点

| 项目 | 值 |
|---|---|
| 文件 | `~/.openclaw/openclaw.json` |
| JSON 路径 | `mcp.servers.mx-ds-mcp.headers.em_api_key` |
| 形式 | 明文（未启用 SecretRef） |
| 备份 | 每次换 key 前自动备份为 `openclaw.json.bak.<旧key前8位>` |

**⚠️ 两个 token 不要混淆**（详见 `MX_MCP_TOKEN_CONFIG.md`）：

| Token | 位置 | 用途 |
|---|---|---|
| `em_api_key` | `mcp.servers.mx-ds-mcp.headers.em_api_key` | 东方财富 MCP 数据服务额度（**换 key 换的是这个**） |
| `gateway.auth.token` | `gateway.auth.token` | 本机 OpenClaw Gateway HTTP/WS 认证 |

`company_report_api.py` 只用 `gateway.auth.token` 访问 gateway；数据查询由 agent 内部经 MCP 完成（消耗 `em_api_key` 额度）。

## 3. 凭据体系（换 key 的本钱）

| 文件 | 内容 |
|---|---|
| `~/.config/choice_mcp_credentials.json` | `{"primary": {u,p}, "backups": [{u,p}×4]}` 主凭据 + 4 套备用 |
| `~/.config/mx_report_server_state.json` | 当日游标：`{last_login_date, cursor, exhausted[], current_key_prefix}` |
| `~/.config/mx_report_server.lock` | 跨进程互斥锁（flock，8323/8326 共用） |
| `~/.config/choice_storage.json` | playwright storage_state 登录态（旧方案，免滑块） |
| `/tmp/chrome-cdp-test/` | CDP 模式 Chrome 数据目录（登录态持久化 + `mx_login_state.json` 账号标记防串号） |
| `~/.config/choice_mcp_api_key` | `--save` 手动保存的 key（仅存档，不是生效配置） |

凭据索引约定（全服务统一）：**0 = primary，1~4 = backups[0..3]**。

登录方式（`choice_get_api_key.py`）：
- **CDP 模式（默认）**：`--cdp` 连接/自动启动真实 Chrome（端口 9222），指纹=真实用户，滑块验证点击即自动放行；登录态按账号标记复用（免账号密码，不串号）
- **storage 复用（旧）**：`--storage PATH` 用已保存登录态免登录
- **无头 + 人工拼图（兜底）**：`--challenge-dir DIR` 出现滑块时推送 challenge.json 等人工完成

## 4. 换 key 流程

### 4.1 手动换 key

```bash
cd experiments/report_machine/mx_company_reporter
python choice_get_api_key.py --update-openclaw            # 主凭据(0)
python choice_get_api_key.py --update-openclaw --index 1  # 备用1
systemctl --user restart openclaw-gateway                 # 手动换后需重启生效
```

`update_openclaw()`（choice_get_api_key.py:647）：写 openclaw.json 前自动备份 `openclaw.json.bak.<旧key前8位>`；key 未变化则跳过。

### 4.2 自动换 key（8323 公司分析服务，`report_server.py`）

**触发链**：agent 回复命中积分耗尽错误 → `_extract_mcp_error()`（company_report_api.py:94，依据 `mcp_error_signatures.json` v3 检测规则）返回 `MX_QUOTA_EXHAUSTED` → `_generate_with_retry`（report_server.py:219）→ `_switch_credential`（report_server.py:176）。

**流程**（全程持 `mx_report_server.lock` 互斥锁）：

```
当前凭据已在 exhausted → 从 cursor+1 起按序尝试备用凭据（跳过当日已 exhausted）
  → run_login(nxt)（credential_store.py:170）：
      子进程 choice_get_api_key.py --index N --cdp --json
      （playwright 在子进程内，崩溃/泄漏不影响服务进程；密码不经过命令行参数）
  → 成功拿到新 em_ key
  → switch_gateway_key(key)（credential_store.py:249）：
      1. update_openclaw() 写 openclaw.json（自动备份）
      2. key 有变化 → systemctl --user restart openclaw-gateway
      3. 轮询 GET /v1/models（带 gateway token）≤90s 等恢复
  → 更新状态文件 cursor / exhausted / current_key_prefix
没有更多可用凭据 → 返回 QUOTA_ALL_EXHAUSTED_MSG（全部账号额度用尽语义）
```

### 4.3 每日登录（`_daily_login`，report_server.py:147）

每天**第一个任务开始前**：用主凭据(0)登录一次刷新 key 并重置当日游标（`cursor=0, exhausted=[]`）。换 key 只发生在运行中检测到配额耗尽时。

## 5. 并发安全（8323 公司分析 / 8326 板块对比 双服务）

两个服务是独立进程，**共用同一 gateway / openclaw.json / 状态文件**：

- `credential_store.mutex()` / `locked()` 装饰器：flock 文件锁（`mx_report_server.lock`），登录（≤240s）与换 key（重启 gateway）全程互斥，防止两服务同时写 openclaw.json / 重启 gateway 互相打断（**实测曾因此损坏配置**）
- agent 生成调用本身**不加锁**（长耗时，会阻塞对方）
- 状态文件原子写（tmp + os.replace）

## 6. 换 key 后：mx-agent 与 mx-public 自动共享新额度

**答案：能，且不需要任何额外配置。**

换 key 写回的是全局 `mcp.servers.mx-ds-mcp.headers.em_api_key`；所有 agent 都是 inherit default 走同一个 MCP server。gateway 重启后，mx-agent / mx-public / ths-agent 的下一次 MCP 调用**立即使用新 key、新额度**——包括 8323 公司分析、8326 板块对比、前端股小神对话，一次性全部生效。

语义澄清：**共享的是同一账号的额度池**（两个 agent 合用一个账号的积分），不是额度翻倍。换 key 只是"换新账号继续共用"。

## 7. 注意事项与局限

1. **换 key 会重启 gateway** → 所有 agent 短暂中断（恢复等待上限 90s）。8323/8326 用文件锁互斥，已避免并发换 key。
2. **额度是账号维度**：mx-agent 与 mx-public 合并消耗同一账号积分；一个耗尽，两个一起换。
3. **若需拆分独立额度**（mx-public 用第二账号的 key）：需在 openclaw.json 注册第二个 MCP server（如 `mx-ds-mcp-public` 配自己的 key）+ 给 mx-public 加 agent 级 `mcp` 覆盖（当前全 inherit）。**代价**：8323 自动换 key 只维护 `mx-ds-mcp` 一个 server，第二把 key 的登录/轮换/额度监控需单独维护——目前未实现。
4. **密钥明文落盘**（`openclaw.json` 与 `choice_mcp_credentials.json`），仅适合本地单机；不要把 key 提交到代码仓库。

## 8. 代码与文件索引

| 文件 | 职责 |
|---|---|
| `~/.openclaw/openclaw.json` | **key 唯一生效配置点**（mx-ds-mcp headers）+ gateway auth token |
| `choice_get_api_key.py` | 登录取 key（`--index`/`--cdp`/`--storage`/`--challenge-dir`）+ `--save`/`--update-openclaw` |
| `credential_store.py` | `run_login`（登录子进程）/ `switch_gateway_key`（写配置+重启 gateway）/ 状态读写 / 跨进程锁 |
| `report_server.py` | `_daily_login` / `_switch_credential`（备用凭据轮换）/ `_generate_with_retry` |
| `company_report_api.py` | `_extract_mcp_error`（从 agent 回复解析 MX_QUOTA_EXHAUSTED） |
| `mcp_error_signatures.json` | 错误特征库 v3（积分耗尽/限流/未知分级） |

## 9. 修订历史

- 2026-08-17：初版定稿。全景（谁在用 key）、唯一配置点、凭据体系、手动/自动换 key 全流程（含每日登录）、双服务并发安全、多 agent 共享机制、拆分额度的方案与代价。

## 10. 边界

- 本文档只讲 key 生命周期与共享；积分耗尽错误的**检测与字段契约**见 `MX_MCP_QUOTA_EXHAUSTED_HANDLER.md`；**手动配置位置**速查见 `MX_MCP_TOKEN_CONFIG.md`。
- `reports/`、`log/` 等运行产物不纳入版本管理（见各自 .gitignore）。
