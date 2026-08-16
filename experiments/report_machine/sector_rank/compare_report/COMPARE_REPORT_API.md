# 板块对比分析报告生成服务 — 接口文档

独立 FastAPI 服务，端口 **8326**。前端「板块分析」页提交选中股票 → 生成板块对比分析报告（个股简要分析 + 横向对比）。

代码位置：`experiments/report_machine/sector_rank/compare_report/`

> ⚠️ **当前为占位实现**：`_call_agent()` 不真实调用 openclaw agent，返回占位内容（每只股票模拟 1.5s 耗时）。报告内容标注"占位文件"，待 agent 生成功能开发完成后替换（见文末【后续替换点】）。

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
| `sector_name` | 是 | THS 板块名称（报告目录/文件名用） |
| `stocks` | 是 | 选中的股票名称列表（1~20 只） |
| `username` | 否 | 前端登录用户名，成功后报告复制到 `user/{username}/板块分析/{板块名}/` |

错误码：400（空/超 20 只）。

### 2. GET /api/compare/reports/{task_id}/events

SSE 实时进度（`event: <type>` + `data: json`，data 含 `type/ts/seq`；空闲 15s 心跳；终态后流结束；断线重连重放全部事件）。

| event | 附加字段 | 含义 |
|---|---|---|
| `task_queued` | `task_id, sector_name, stocks, position` | 已入队 |
| `generating` | `stock, index, total` | 开始生成第 index+1 只的简要分析 |
| `stock_done` | `stock, index, total` | 单只段落完成 |
| `stock_failed` | `stock, index, total, error` | 单只失败 |
| `task_done` | `task_id, files, failed, duration_s` | **终态**：整份报告已写盘 |
| `task_failed` | `task_id, error` | **终态**（整体失败） |

### 3. GET /api/compare/reports/{task_id}/status

兜底轮询：`{status, sector_name, stocks, files, failed, last_events(最近20条)}`。

### 4. GET /health

```json
{"status": "ok", "port": 8326, "user_base": "..."}
```

## 报告落地

- 服务端暂存：`sector_rank/compare_report/reports/`
- 用户空间（传了 `username` 时）：`user/{username}/板块分析/{板块名}/{YYYYMMDD}_{板块名}_对比分析报告.md`
  - explorer 中独立总文件夹「板块分析」（与「上市公司分析」平行），内按板块名分子目录
  - 命名与公司分析一致（`{日期}_{股票名}_公司分析报告.md`），公司名换板块名；**同日重复生成直接覆盖**
- 前端查看：切到「文档」标签页 / 侧栏文件树

## 后续替换点（agent 生成开发完成后）

替换 `compare_report_server.py` 中 `_call_agent()` 函数体（已标注 `TODO(替换点)`）：

```python
# 真实调用方式(参照 mx_company_reporter/company_report_api.py):
#   POST http://127.0.0.1:18789/v1/chat/completions
#   model: openclaw/mx-agent
#   query = f"生成{','.join(stocks)}的公司简要分析报告和对比分析报告"
#   需复用: _load_token() / _chat_once() / _extract_mcp_error() / _delete_session_safe()
```

替换后任务流程变为：整份报告一次生成（无需逐股段落拼接），事件流不变，前端无需改动。
