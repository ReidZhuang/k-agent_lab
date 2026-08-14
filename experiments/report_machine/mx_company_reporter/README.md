# mx_company_reporter

通过 OpenClaw mx-agent 生成上市公司深度分析报告的 Python API。
每次调用自动完成：生成报告 → 保存 Markdown → **立即删除临时会话**（上下文零残留、token 零累积）。

## 依赖

- Python 3.8+（纯标准库，无第三方依赖）
- OpenClaw Gateway 运行于 `127.0.0.1:18789`（token 认证），已启用 OpenAI 兼容端点
  （`gateway.http.endpoints.chatCompletions.enabled: true`）

## 使用

```python
from company_report_api import generate_company_report

r = generate_company_report("淮北矿业")
print(r["md_path"])          # reports/淮北矿业_2026-08-13.md
print(r["session_deleted"])  # True
```

命令行：

```bash
python3 company_report_api.py 淮北矿业
```

## 返回结构

成功：

```json
{
  "ok": true,
  "stock": "淮北矿业",
  "report": "完整 Markdown 报告文本",
  "md_path": "reports/淮北矿业_2026-08-13.md",
  "session_key": "report-<时间戳>-<随机>",
  "session_deleted": true
}
```

取数失败 / 积分耗尽（进入兜底）：

```json
{
  "ok": false,
  "stock": "淮北矿业",
  "report": "agent 返回的原始文本（含积分耗尽错误块）",
  "error": {
    "code": "MX_QUOTA_EXHAUSTED",   // 或 MCP_ERROR（其他服务错误）
    "stage": "mid-run",
    "detail": "你的积分已用完~请前往 https://ai.eastmoney.com/skills 购买套餐补充积分，即可继续使用",
    "type": "quota_exhausted",
    "tool": "mx_ashare_finance_data",
    "request": "原始查询语句（充值后可回放重试）"
  },
  "session_key": "report-<时间戳>-<随机>",
  "session_deleted": true
}
```

调用方只需判断 `ok` 字段：`ok: false` 时读取 `error.code` 进入兜底机制（如切换备用数据源、跳过该股票、等待次日重试）。

## 积分耗尽守卫（quota guard）

- 原理：不做事前探测（积分可能在取数过程中耗尽，探测无意义）；由 `mx-mcp-quota-exhausted-handler` 技能控制 agent，**取数循环中一旦看到积分耗尽类错误返回，立即停止、不重试、不编造数据、不切换数据源**，按规范格式输出错误块（错误码 `MX_QUOTA_EXHAUSTED`）
- API 检测该错误块（优先级：机器可读 JSON → 错误码纯文本 → 官方文案启发式）→ 命中即返回 `ok: false` + 结构化错误
- 会话清理不受影响（finally 中仍会删除临时会话）
- 检测规则与字段契约详见 `MX_MCP_QUOTA_EXHAUSTED_HANDLER.md`；`error.request` 字段保留原始请求，充值后可直接回放重试

> 历史：v2 旧契约（`##MCP_ERROR##` 标记 / `QUOTA_EXHAUSTED` 错误码 / `mx-mcp-quota-guard` 技能）未经实测、系编造，已于 2026-08-14 废弃，全面替换为本规约。

## 文件说明

| 文件 | 说明 |
|---|---|
| `company_report_api.py` | 主 API（生成报告 + MD 落盘 + finally 删会话） |
| `openclaw_rpc.py` | 极简 WebSocket RPC 客户端（调 Gateway `sessions.delete`，纯标准库） |
| `test_delete_session.py` | 端到端测试脚本（创建→删除→验证） |
| `MX_MCP_QUOTA_EXHAUSTED_HANDLER.md` | 积分耗尽错误处理规约：检测规则、规范错误格式（`MX_QUOTA_EXHAUSTED`）、字段契约、与分析管线衔接（对应 `mx-mcp-quota-exhausted-handler` 技能，开发兜底/重试策略前必读） |
| `reports/` | 报告输出目录（自动创建） |

## 工作原理

1. 每次调用生成唯一 `x-openclaw-session-key` → 无状态，上下文不累积
2. `POST /v1/chat/completions`，`model: openclaw/mx-agent` → 自动使用 company-analysis
   技能 + 东方财富 MCP 数据工具
3. `finally` 块中通过 WS RPC `sessions.delete` 删除临时会话（幂等，可恢复归档）
