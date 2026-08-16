# 板块对比分析报告生成服务 — 接口文档

独立 FastAPI 服务，端口 **8326**。前端「板块分析」页提交选中股票 → 生成板块对比分析报告（整份合并分析，非逐股拼接）。

代码位置：`experiments/report_machine/sector_rank/compare_report/`

> 已接入真实 agent 调用（2026-08-16）：复用 mx_company_reporter 管线（登录/换 key/会话清理/积分耗尽守卫），query 触发 mx-agent 的 `sector-multi-stock-analysis` 技能（形态 B 名单型）。

## 启停

```bash
./compare_report_server.sh start|stop|restart|status
# 日志: log/compare_report_server.log
```

## 接口

### 1. POST /api/compare/reports

创建生成任务（单 worker 串行处理）。

```bash
curl -X POST http://127.0.0.1:8326/api/compare/reports \
  -H "Content-Type: application/json" \
  -d '{"sector_name": "白酒概念", "stocks": ["会稽山", "泸州老窖", "贵州茅台"], "username": "zgx"}'
```

```json
{"task_id": "a1b2c3d4e5f6", "status": "queued"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `sector_name` | 是 | THS 板块名称（报告目录/文件名用，也拼进 agent query） |
| `stocks` | 是 | 选中的股票名称列表（1~20 只） |
| `username` | 否 | 前端登录用户名，成功后报告复制到 `user/{username}/板块分析/{板块名}/` |

错误码：
- 400：板块名为空 / 股票列表为空 / 超 20 只
- 503：凭据配置缺失或非法（`credential_store.credentials_error()` 原因）
- 409：今日全部凭据已耗尽（`cursor == -1`，与公司分析 8323 同语义）

### 2. GET /api/compare/reports/{task_id}/events

SSE 实时进度（`event: <type>` + `data: json`，data 含 `type/ts/seq`；空闲 15s 心跳；终态后流结束；断线重连重放全部事件）。

| event | 附加字段 | 含义 |
|---|---|---|
| `task_queued` | `task_id, sector_name, stocks, position` | 已入队 |
| `login_started` | `credential, reason: daily_first\|quota_switch` | 开始登录（每日首次 / 换备用凭据） |
| `login_ok` | `credential, key_prefix` | 登录成功（key 前 8 位） |
| `login_failed` | `credential, reason` | 登录/切换失败 |
| `generating` | `sector_name, count, index:0, total:1` | 整份报告开始生成（一次调用，非逐股） |
| `quota_switching` | `from_credential, to_credential` | 检测到积分耗尽，切换备用凭据 |
| `retrying` | `stock`（板块名+只数）, `credential, attempt` | 换 key 后重试生成 |
| `all_quota_exhausted` | `used_credentials` | 今日全部凭据耗尽（终态前） |
| `task_done` | `task_id, files, failed, duration_s` | **终态**：整份报告已写盘 |
| `task_failed` | `task_id, error` | **终态**（整体失败） |

### 3. GET /api/compare/reports/{task_id}/status

兜底轮询：`{status, sector_name, stocks, files, failed, last_events(最近20条)}`。

### 4. GET /health

```json
{"status": "ok", "port": 8326, "credentials_available": true, "today": "2026-08-16", "state": {...}}
```

## 生成流程（真实 agent 调用）

1. **每日登录检查**（与公司分析 8323 一致，共用状态文件 `~/.config/mx_report_server_state.json`）：任务开始前若今日未登录 → 主凭据登录妙想（CDP 模式）→ 更新 openclaw.json 的 `em_api_key` → 必要时重启 gateway 并验证 `/v1/models`
2. **整份报告一次 agent 调用**（非逐股）：query 组装触发 `sector-multi-stock-analysis` 技能（形态 B 名单型）：
   ```
   {sector_name}板块涨幅排名前列的{股票1},{股票2},...，合并分析这些上市公司
   ```
   板块名与股票名单来自前端，末句写死。报告即 agent 返回原文（含固定骨架：板块背景/梯队总览/分梯队公司介绍/资金动向/机构成本/总结策略/数据缺口）。
3. **积分耗尽换 key**：agent 返回 `MX_QUOTA_EXHAUSTED` 错误块 → 当前凭据标记 exhausted → 按序登录下一备用凭据 → 更新 gateway → 重试整份报告
4. **全部耗尽**：`all_quota_exhausted` 事件 + `task_failed`（"今日用户积分已用尽,报告无法生成,请明日再试"），不落盘

## 报告落地

- 服务端暂存：`sector_rank/compare_report/reports/`
- 用户空间（传了 `username` 时）：`user/{username}/板块分析/{板块名}/{YYYYMMDD}_{板块名}_对比分析报告.md`
  - explorer 中独立总文件夹「板块分析」（与「上市公司分析」平行），内按板块名分子目录
  - 命名与公司分析一致（`{日期}_{股票名}_公司分析报告.md`），公司名换板块名；**同日重复生成直接覆盖**
- 前端查看：切到「文档」标签页 / 侧栏文件树

## 实现说明

- **复用 mx_company_reporter 管线**（`sys.path` 引入）：`credential_store`（凭据/游标状态/run_login/switch_gateway_key）+ `company_report_api`（`SESSION_AGENT_PREFIX` / `_chat_once` / `_extract_mcp_error` / `_delete_session_safe`）
  - ★ session key 必须带 `agent:mx-agent:` 前缀（裸 key fallback 到默认 agent，加载旧 skills，`sector-multi-stock-analysis` 不在场）
  - 每次调用唯一 session key，`finally` 中 `_delete_session_safe` 删除（幂等）
  - 积分耗尽守卫：`_extract_mcp_error()` 五级检测，命中返回 `ok:false` 不落盘；错误契约详见 `mx_company_reporter/MX_MCP_QUOTA_EXHAUSTED_HANDLER.md`
- 常量：`MAX_STOCKS = 20`（前端排名表上限）；`GEN_TIMEOUT = 1800`（整份报告一次生成，agent 逐只取数，给足 30 分钟）
- 环境变量 `MX_COMPARE_FAKE_EXHAUST=1`：测试模式，首次生成伪造配额耗尽，演练换 key 全流程不耗真实积分（勿在生产开启）
- 任务粒度说明：公司分析 8323 是逐股串行（N 次调用）；本服务是**整份报告一次调用**（1 次调用），前端事件流中 `generating` 只出现一次（`total: 1`），无 `stock_done`/`stock_failed` 事件
