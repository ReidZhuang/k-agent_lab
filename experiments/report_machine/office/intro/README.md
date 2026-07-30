# Office 报告生成系统

## 概述

Office 是一个自动化的午间报告生成系统。它从多个数据源获取股票盘中数据和新闻资讯，通过 DeepSeek v4 Flash 大模型生成结构化的分析报告，同时输出 Markdown 和 Word (.docx) 格式。

## 架构

```
                    ┌──────────┐
                    │  Client  │
                    │ POST     │
                    │ /report  │
                    └────┬─────┘
                         │
              ┌──────────▼──────────┐
              │  Writer (8310)      │
              │  4 worker           │
              │  run_in_executor     │
              │  pool_maxsize=200    │
              └────┬────┬───────────┘
                   │    │
          ┌────────▼┐   │
          │ Fetcher │   │ (函数调用)
          │ (函数)   │   │
          └─────────┘   │
                        │
              ┌─────────▼───────────┐
              │  Sub Writer 池      │
              │  ThreadPool(64)     │
              │  每只股票:           │
              │  ├─ 解析 fetch 数据  │
              │  └─ POST Middleman   │
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │  Reporter (8312)    │
              │  4 worker           │
              │  64线程 run_in_exec │
              │  pool_maxsize=200   │
              │  Agent Loop (8轮)   │
              │  DeepSeek v4 Flash  │
              └────┬────┬───────────┘
                   │    │
         POST TypeB│    │
              ┌────▼┐  │
              │Middle│  │
              │man B │  │
              └──────┘  │
                        │
              ┌─────────▼───────────┐
              │  Middleman (8311)   │
              │  4 worker           │
              │  Type A: 24线程池   │
              │  Type B: 64线程池   │
              │  run_in_executor    │
              │  pool_maxsize=200   │
              └────┬───────────────┘
                   │
              ┌────▼────────────────┐
              │  mail_tower (8300)  │
              │  5 engines:         │
              │  sinafin / baidufin │
              │  thsfin / juchao    │
              │  / qnainfo          │
              └─────────────────────┘
```

## 组件

| 组件 | 端口 | 并发模型 | 说明 |
|:----|:----:|:---------|:-----|
| Writer | 8310 | 4 worker + `run_in_executor` | 入口 API，接收股票列表，管理 sub writer |
| Middleman | 8311 | 4 worker + 24(Type A) + 64(Type B) 线程池 | writer ↔ mail_tower 中间层 |
| Reporter | 8312 | 4 worker + 64 线程池 | 接收 context，运行 LLM agent loop |
| Fetcher | — | 函数调用 | 取数编排（非独立服务）|

## 数据流

1. 客户端 POST `/api/v1/report` 到 Writer，传入股票列表
2. Writer 调用 Fetcher（函数）获取盘中数据 + 午间消息
3. Writer 为每只股票启动 Sub Writer（ThreadPoolExecutor 64 线程）
4. 每个 Sub Writer 并发：解析 fetch 数据 + 调 Middleman Type A（聚合 5 engine 搜索）
5. Middleman Type A 内部 5 引擎并发调 mail_tower，每引擎独立 /search + /poll
6. Sub Writer 组装完整 context，POST 到 Reporter
7. Reporter 进入 Agent Loop（最多 8 轮），使用 DeepSeek v4 Flash
8. 如果 LLM 需要查看文章正文，调用 get_article_body tool → Middleman Type B
9. LLM 输出最终报告 → 保存到 `output/{stock_name}/{date}_{stock_name}_midday.md` + `.docx`

## 关键设计

### 非阻塞架构

所有 FastAPI 端点使用 `async def` + `run_in_executor` + 独立线程池，确保 event loop 永不阻塞，单个 worker 可同时处理大量并发请求。

### 连接池

所有组件使用 `requests.Session()` + `HTTPAdapter(pool_maxsize=200)` 共享连接池，防止高并发下连接耗尽。

### 重试与兜底

- **Sub Writer → Reporter**: 超时 180s/90s/60s × 3 次重试
- **响应丢失检查**: 所有重试失败后检查 output 目录是否已有报告文件（双保险）
- **Fallback**: 真失败时保存 context 到 `fallback/`，可通过 `retry_fallback.py` 重试

### 延迟初始化（fork-safe）

线程池使用延迟创建模式（double-checked locking），支持 uvicorn workers>1 的 fork 场景。

### 日志

参见详细文档 [LOGGING.md](LOGGING.md)。

系统包含三类日志：

| 类型 | 位置 | 说明 |
|:-----|:------|:------|
| DebugLogger（JSONL） | `test_drive/results/debug_logs/*.jsonl` | 调试用结构化日志，7 个组件共 26 个 step，可按需移除 |
| log_office_error | SQLite `error_log` 表 | 异常记录（15 处调用点），保留 |
| Commander 任务日志 | `office/log/task_*.log` / `summary_*.json` | 定时任务流水和摘要 |

> **移除调试日志**：见 [LOGGING.md](LOGGING.md)「移除指南」。

## 启动

```bash
# 1. 启动 mail_tower（依赖）
cd /home/stockagent/project_space/research/experiments/mail_tower
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300

# 2. 启动 middleman
cd /home/stockagent/project_space/research/experiments/report_machine/office
conda run -n stock_agent python middleman/server.py

# 3. 启动 reporter
conda run -n stock_agent python reporter/server.py

# 4. 启动 writer（入口）
conda run -n stock_agent python writer/server.py

# 5. 测试
curl -X POST http://localhost:8310/api/v1/report \
  -H "Content-Type: application/json" \
  -d '{"stock_names": ["淮北矿业", "博瑞医药"]}'
```

## 输出格式

每只股票生成两个文件：

```
output/{stock_name}/
├── {date}_{stock_name}_midday.md     # Markdown 格式（可读）
└── {date}_{stock_name}_midday.docx   # Word 格式（可打印/分发）
```

Word 格式转换通过 `python-docx` 实现，转换函数在 `output/md_to_docx.py`。

## 配置文件

`office/cfg/config.yaml` 包含所有组件配置（middleman/reporter/writer 地址、并发限制、DeepSeek 模型参数等）。

## 依赖

- Python 3.10+
- conda 环境 `stock_agent`
- DeepSeek API key（环境变量 `DEEPSEEK_API_KEY`）
- python-docx（Word 输出）

## 测试

详细测试报告见 `test_drive/TEST_REPORT.md`。

```bash
# 第1层：单元测试
conda run -n stock_agent python test_drive/unit/test_syntax.py
conda run -n stock_agent python test_drive/unit/test_models.py

# 端到端测试（需启动所有服务）
curl -X POST http://localhost:8310/api/v1/report \
  -H "Content-Type: application/json" \
  -d '{"stock_names":["淮北矿业","博瑞医药","凯莱英","广生堂"]}'
```

## 性能参考（2026-07-28 测试数据）

| 测试规模 | 耗时 | 成功率 | 总字数 |
|:--------|:----:|:------:|:------:|
| 30 只股票 | 4 min | 30/30 | ~221K |
| 50 只股票 | 5.6 min | 48/48 | ~347K |
| 78 只股票 | 7.8 min | 76/76 | ~573K |

瓶颈：baidufin 引擎（Playwright 启动 Chromium ~15s 中位数）。

## 错误处理

参见 `intro/error_codes.md`。所有组件通过 `database.log_office_error()` 写入数据库 `error_log` 表。

## 失败兜底

Sub writer 连续 3 次联系 Reporter 失败后，context 会被保存到 `fallback/` 目录下。可使用 `retry_fallback.py` 脚本手动重试：

```bash
conda run -n stock_agent python retry_fallback.py --list     # 查看失败列表
conda run -n stock_agent python retry_fallback.py --retry-all # 全部重试
```

## 更新日志

| 日期 | 变更 | 说明 |
|:----|:-----|:------|
| 2026-07-28 | 初始版本 | Office 系统全部功能开发完成 |
| 2026-07-28 | 非阻塞改造 | writer/middleman/reporter 全部使用 `run_in_executor` + 独立线程池 |
| 2026-07-28 | 大连接池 | 所有组件 `pool_maxsize=200`，消除连接耗尽 |
| 2026-07-28 | 双保险 | 响应丢失后检查报告文件是否存在 |
| 2026-07-28 | 78只压测通过 | 76/76 成功，零 fallback，7.8min |
| 2026-07-28 | 添加 Word 输出 | 自动生成 .docx 格式报告 |
| 2026-07-30 | 接入 Commander | 定时任务通过 commander/scheduled_task.py 调度 |
| 2026-07-30 | 文档完善 | [LOGGING.md](LOGGING.md) 详细记录所有日志点 |
