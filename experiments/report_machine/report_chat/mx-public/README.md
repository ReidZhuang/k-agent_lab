# mx-public — 前端专用 Agent（开发与运维文档）

> 本文档是 mx-public 的全部开发文件与运维说明。**开发文件统一存放于此目录**，运行时数据（会话 transcript、记忆、workspace）仍留在 `~/.openclaw` 下（OpenClaw 运行机制要求，不可迁移）。

## 1. 是什么

`mx-public` 是与 `mx-agent` **同 skills、零记忆**的独立 Agent，专供前端页面调用：

- 拥有 6 个相同的 skills（company-analysis / sector-multi-stock-analysis / rd-leaders-brief / rd-leaders-research / tushare-data / mx-mcp-quota-exhausted-handler）
- **不带 mx-agent 的任何记忆与使用痕迹**（独立 workspace，memory 为空，不认识 mx-agent）
- 5 项硬性限制全部通过 **policy.json 一个配置文件**驱动（见 §3）

## 2. 目录与文件布局

### 本目录（开发文件，全部在此）
```
report_chat/mx-public/
├── README.md             ← 本文档（总览 + 运维）
├── FRONTEND_API.md       ← 前端调用方式（重点，给前端开发看这份）
├── INTEGRATION_FRONT.md  ← 前端接入记录（股小神：8320 代理落地情况）
├── policy.json           ← 唯一策略配置（5 项限制全由此驱动）
├── guardian.py           ← 守护脚本（status/apply/monitor/unlock/archive/flush-memory）
└── logs/                 ← 运维日志（如需要，可建）
```

### 运行时数据（OpenClaw 运行机制要求，不可迁移）
| 路径 | 内容 |
|---|---|
| `~/.openclaw/agents/mx-public/agent/` | agent 运行时目录（models.json、plugins） |
| `~/.openclaw/agents/mx-public/sessions/` | 会话 transcript（token 统计与归档的对象） |
| `~/.openclaw/workspace-mx-public/` | 独立 workspace（AGENTS/SOUL/IDENTITY/USER + memory/ + skills/） |

> ⚠️ 迁移注意事项：guardian.py 与 policy.json 迁移后，`guardian.py` 内 `POLICY_PATH` 已指向本目录；4 个 cron 任务的工作目录也已同步更新（见 §5）。

## 3. 5 项限制的实现（policy.json 一键配置）

```json5
{
  "agent": { "id": "mx-public", "model": "deepseek/deepseek-v4-flash", "workspace": "…", "agentDir": "…" },
  "compaction": {           // 需求1：context 超固定值自动 compact
    "enabled": true,
    "reserveTokens": 20000,          // 保留的压缩预算
    "keepRecentTokens": 20000,       // 保留最近 token 数
    "maxActiveTranscriptBytes": "10mb", // 超过 10MB 触发压缩
    "truncateAfterCompaction": true,
    "midTurnPrecheck": true,         // 长任务中途也检查
    "memoryFlush": true,             // 压缩前自动冲刷记忆
    "notifyUser": false              // 用户无感知
  },
  "sessionArchive": {       // 需求2：定时归档清理会话且用户无感知
    "enabled": true,
    "intervalMinutes": 1440,         // 每天检查
    "archiveAfterMinutes": 720,      // 空闲 12 小时以上
    "keepArchivedDays": 7            // 保留 7 天
  },
  "memoryFlush": {          // 需求3：定时冲刷记忆；达上限强制冲刷
    "enabled": true,
    "scheduleCron": "0 2 * * *",     // 每天 2:00
    "maxMemoryFileBytes": 16384      // 16KB 上限，超限强制冲刷
  },
  "tokenBudget": {          // 需求4：总 token 上限，超限强制停止
    "enabled": true,
    "maxTotalTokens": 2000000,       // 200 万 token
    "checkIntervalMinutes": 30,      // 每 30 分钟检查
    "onExceed": "disable",           // 超限 → model 改为 disabled/disabled
    "disabledModel": "disabled/disabled"
  }
}
```

### 各项的执行机制
| 需求 | 机制 | 说明 |
|---|---|---|
| 1. 自动 compact | OpenClaw 原生默认 | ⚠️ **不显式写入 `agents.defaults.compaction`**：policy.json 中的 compaction 字段仅作配置文档。该格式（`"10mb"`、midTurnPrecheck/memoryFlush 嵌套）被 openclaw gateway 强校验拒绝（8/11、8/16 两次事故：gateway 反复崩溃、systemd 限流停止，前端对话全挂）。guardian.py `apply` 会跳过 compaction 写入并告警；会话超阈值压缩由 openclaw 内置默认处理 |
| 2. 归档清理 | `guardian.py archive` + cron | 只清理 mx-public 的 transcript，**不动 mx-agent**；前端页面上下文（前端自己存的会话记录）不受影响 |
| 3. 记忆冲刷 | `guardian.py flush-memory` + cron | 每天 2:00 定时 + 每 2 小时检查超 16KB 强制冲刷；调用 `openclaw agent --agent mx-public` 蒸馏当天对话 |
| 4. token 上限 | `guardian.py monitor` + cron | 每 30 分钟累加所有 transcript 的 `usage.totalTokens`；超限自动把 model 改成 `disabled/disabled` → 前端调用报 `Unknown model`，服务强制停止；管理员 `guardian.py unlock` 解封 |
| 5. 一个配置文件 | `policy.json` | guardian.py 所有命令都从这里读配置 |

## 4. 常用运维命令（guardian.py）

```bash
cd /home/stockagent/project_space/research/experiments/report_machine/report_chat/mx-public

python3 guardian.py status          # 查看用量、开关状态、归档/冲刷策略
python3 guardian.py monitor         # 手动执行一次 token 用量检查（超限即禁用）
python3 guardian.py unlock          # 管理员解封（恢复 model；仍超限时会二次确认）
python3 guardian.py archive         # 手动归档清理 7 天前的会话 transcript
python3 guardian.py flush-memory    # 手动触发记忆冲刷
python3 guardian.py flush-memory --force-if-over   # 强制模式：超 16KB 才触发（cron 用）
python3 guardian.py apply           # 把 policy.json 应用到 openclaw.json（agent 注册 + compaction 配置）
```

> 修改 policy.json 后：compaction 相关需重启 gateway 生效；model 字段可热更新但有缓存，改后建议重启。

## 4.1 ⚠️ 配置写入正确姿势（踩坑记录，8/16 两次崩溃）

**核心结论：改 openclaw.json 一律用 `openclaw config patch --stdin`，不要直接编辑文件。**

| 方式 | 结果 |
|---|---|
| ❌ 直接编辑 openclaw.json 写 compaction | gateway 校验失败崩溃（`Invalid input`）或重启后被内存配置覆盖丢失 |
| ✅ `openclaw config patch --stdin`（CLI） | schema 校验 + 磁盘/内存同步，重启后保留 |
| ❌ gateway config.patch / config.apply（API） | compaction 路径被保护（protected paths），直接拒绝 |

**compaction 合法格式（schema 严格，顶层无 `enabled` 字段！）**：
```json5
{
  "agents": {
    "defaults": {
      "compaction": {
        "reserveTokens": 20000,          // 上下文接近上限时的预留余量
        "keepRecentTokens": 20000,       // 压缩后保留最近 token 数
        "maxActiveTranscriptBytes": "10mb", // 转录文件达 10MB 提前压缩（需 truncateAfterCompaction）
        "truncateAfterCompaction": true,  // 压缩后轮转精简文件
        "notifyUser": false,              // 用户无感知
        "midTurnPrecheck": { "enabled": true },  // 工具循环中途预检
        "memoryFlush": { "enabled": true }       // 压缩前先冲刷记忆
      }
    }
  }
}
```

命令：
```bash
# dry-run 校验：
echo '{"agents":{"defaults":{"compaction":{...}}}}' | openclaw config patch --stdin --dry-run --json
# 正式写入：
echo '{"agents":{"defaults":{"compaction":{...}}}}' | openclaw config patch --stdin
# 生效：gateway restart
```

**崩溃历史（为什么有这条）**：
1. 8/11 与 8/16：直接改 openclaw.json 写 compaction，带非法顶层 `enabled` 字段 → `agents.defaults.compaction: Invalid input` → gateway startup_failed 反复崩溃
2. 8/16 二次：格式改对（无 enabled）后直接编辑文件 → gateway 重启时用内存配置覆盖磁盘 → compaction 静默丢失
3. 最终解法：guardian.py apply 已改为内部调用 `openclaw config patch --stdin`（见 `apply_compaction_cli`），schema 校验 + 同步写入，一次成功

## 5. cron 任务（4 个，全部由 mx-agent 会话托管）

| 任务名 | 频率 | 动作 | delivery |
|---|---|---|---|
| mx-public-token-monitor | 每 30 分钟 | `guardian.py monitor`（超限禁用） | none（事件落盘，管理员用 status 查看） |
| mx-public-memory-size-guard | 每 2 小时 | `guardian.py flush-memory --force-if-over` | none |
| mx-public-memory-flush | 每天 2:00 | `guardian.py flush-memory` | none |
| mx-public-session-archive | 每天 3:05 | `guardian.py archive` | none |

> 本环境无 channel，cron delivery 全部为 `none`：任务照跑、结果落盘，管理员手动 `guardian.py status` 查看，不推送消息。

## 6. 安全边界（重要）

- `/v1/chat/completions` 端点 = **完整操作员权限面**：持有 gateway token 即视为 owner 级凭据，可调用敏感工具
- **只允许内网/本机访问**（loopback / tailnet / 私网），严禁直接暴露公网
- 前端用户隔离通过 **session key** 实现（每用户一个 key），但**不是**权限隔离——前端后端必须先做用户认证，再以服务端身份转发到 gateway
- 建议前端后端作为唯一持有 gateway token 的一方，前端页面不直接接触 token

## 7. 快速排障

| 现象 | 原因 | 处理 |
|---|---|---|
| 调用报 `Unknown model: disabled/disabled` | token 超限被禁用 | `guardian.py unlock` + 重启 gateway |
| 前端对话互相串台 | session key 未按用户区分 | 每用户固定唯一 key（见 FRONTEND_API.md §3） |
| 对话不记得上一句 | 每次调用没带同一 session key / user | 同一会话复用同一 key |
| guardian 报找不到 policy.json | 路径被改 | 检查 POLICY_PATH 是否指向本目录 |

---

*最近更新：2026-08-16 23:15（文件从 ~/.openclaw/agents/mx-public/ 迁移至本目录，cron 与 guardian 路径已同步）*
