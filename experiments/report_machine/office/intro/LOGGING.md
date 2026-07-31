# Office 日志记录 — 完整清单

> **用途**：本文档全面记录 Office 系统中所有的日志输出点、格式、位置和用途。
> 设计目标：如需整体移除调试日志（DebugLogger），可依据本文逐一清理，不影响核心功能。

---

## 目录

1. [日志系统分类](#1-日志系统分类)
2. [DebugLogger — 结构化调试日志（JSONL）](#2-debuglogger--结构化调试日志jsonl)
3. [log_office_error — 数据库错误日志（SQLite error_log）](#3-log_office_error--数据库错误日志sqlite-error_log)
4. [各组件日志清单](#4-各组件日志清单)
5. [Mail Tower 日志系统](#5-mail-tower-日志系统)
6. [Commander 日志系统](#6-commander-日志系统)
7. [移除指南](#7-移除指南)

---

## 1. 日志系统分类

Office 系统包含 **三类** 日志，职责互不重叠：

| 类别 | 位置 | 格式 | 用途 | 能否移除 |
|:-----|:-----|:-----|:-----|:---------|
| **DebugLogger** | `test_drive/results/debug_logs/*.jsonl` | JSONL | 性能追踪、调试 | ✅ 可移除 |
| **log_office_error** | SQLite `error_log` 表 | 结构化行 | 异常记录、运维 | ❌ 保留 |
| **Commander 任务日志** | `office/log/task_*.log` | 文本 | 定时任务流水 | ❌ 保留 |

---

## 2. DebugLogger — 结构化调试日志（JSONL）

### 实现文件

`office/dlog/debug_logger.py`

### 配置入口

```python
_ENABLED = True  # 全局开关，模块级常量
```

提供 `set_enabled(bool)` 函数，但当前**没有任何代码调用它**——日志始终开启。

### 输出位置

```
office/test_drive/results/debug_logs/{component}_{YYYYMMDD}.jsonl
```

每个组件独立文件，每日自动轮转。

### 行格式

```jsonl
{"t":"2026-07-30 11:31:02.123", "ts":1722312662, "component":"writer_sub",
 "step":"type_a_done", "elapsed_ms":1234.5, "stock_name":"茅台", ...}
```

| 字段 | 说明 |
|:-----|:------|
| `t` | 时间戳 `YYYY-MM-DD HH:mm:ss.SSS` |
| `ts` | Unix 秒数（`time.time()`）|
| `component` | 组件名 |
| `step` | 步骤标识 |
| `elapsed_ms` | 耗时（毫秒），可选 |
| 其他 | 步骤相关数据 |

### 组件列表

所有注册的 DebugLogger 组件：

| 组件名 | 所属文件 |
|:-------|:---------|
| `writer_sub` | writer/server.py |
| `writer_api` | writer/server.py |
| `middleman_type_a` | middleman/server.py |
| `middleman_type_b` | middleman/server.py |
| `reporter` | reporter/server.py |
| `reporter_type_b` | reporter/agent.py |
| `reporter_round` | reporter/agent.py |

### 所有 DebugLogger 输出点

#### writer/server.py — writer_sub 组件

```python
log = get_logger("writer_sub")

# [line 146] Type A 搜索完成
log("type_a_done",
    stock_name=name,
    engines=len(results),
    _elapsed=t_elapsed)

# [line 180] 开始 POST Reporter
log("post_reporter_start",
    stock_name=name,
    context_size=context_size)

# [line 191] POST Reporter 成功
log("post_reporter_success",
    stock_name=name,
    output=output_path,
    _elapsed=t1)

# [line 222] POST Reporter 超时后恢复（双保险）
log("post_reporter_recovered",
    stock_name=name,
    output=expected_path,
    _elapsed=t1)
```

#### writer/server.py — writer_api 组件

```python
log = get_logger("writer_api")

# [line 271] 报告请求开始
log("report_start",
    report_id=report_id,
    stocks=stock_names)

# [line 312] 报告请求完成
log("report_done",
    report_id=report_id,
    total=total,
    success=success_count,
    failed=failed_names,
    _elapsed=t_elapsed)
```

#### middleman/server.py — middleman_type_a 组件

```python
log = get_logger("middleman_type_a")

# Type A — 单个引擎搜索完成
# [line 505]
log("engine_done",
    engine=engine_name,
    stock_code=stock_code,
    has_error=has_error,
    empty=empty,
    _elapsed=elapsed)

# Type A — 聚合完成
# [line 519]
log("search_aggregate_done",
    writer_id=writer_id,
    stock_code=stock_code,
    engines_ok=ok_count,
    engines_err=err_count,
    _elapsed=t1)
```

#### middleman/server.py — middleman_type_b 组件

```python
log = get_logger("middleman_type_b")

# Type B — 文章正文获取完成
# [line 557]
log("article_body_done",
    report_id=report_id,
    engine=engine_name,
    session_id=session_id[:20],
    requested=article_count,
    returned=returned_count,
    status=status,
    http_status=http_status,
    _elapsed=t1)
```

#### reporter/server.py — reporter 组件

```python
_log = get_logger("reporter")

# [line 62] 进入处理 handler
_log("handler_enter", report_id=rid, stock_name=name, ts_code=ts_code)

# [line 67] 获取线程池前
_log("before_get_pool", report_id=rid, stock_name=name)

# [line 69] 获取线程池后
_log("after_get_pool", report_id=rid, stock_name=name)

# [line 72] run_in_executor 前
_log("before_run_in_executor", report_id=rid, stock_name=name)

# [line 76] run_in_executor 后
_log("after_run_in_executor",
     report_id=rid, stock_name=name,
     rounds=rounds, output=output_path, _elapsed=elapsed)
```

#### reporter/agent.py — reporter_type_b 组件

```python
_dl = get_logger("reporter_type_b")

# [line 301] Type B 成功返回
_dl("type_b_result",
    engine=engine, requested=len(ids),
    returned=len(results), status="ok",
    _elapsed=t1)

# [line 307] Type B HTTP 错误
_dl("type_b_result",
    engine=engine, requested=len(ids),
    http=resp.status_code,
    _elapsed=t1)

# [line 312] Type B 异常
_dl("type_b_result",
    engine=engine, requested=len(ids),
    error=str(e)[:60],
    _elapsed=t1)
```

#### reporter/agent.py — reporter_round 组件

```python
_dl = get_logger("reporter_round")

# [line 409] Agent 循环开始
_dl("agent_start",
    stock_name=stock_name, ts_code=ts_code,
    has_articles=bool(articles_content),
    num_engines=len(article_engines),
    user_context_len=len(user_context))

# [line 415] LLM 调用
_dl("round_llm_call",
    stock_name=stock_name, round=round_i,
    messages_count=len(messages),
    last_role=messages[-1].get("role",""),
    last_content_len=len(str(messages[-1].get("content",""))),
    tool_choice=tool_choice)

# [line 433] LLM 调用异常
_dl("round_llm_error",
    stock_name=stock_name, round=round_i,
    error=str(e)[:200], _elapsed=t1)

# [line 454] LLM 响应
_dl("round_llm_response",
    stock_name=stock_name, round=round_i,
    finish_reason=msg.stop_reason,
    content_len=len(content),
    content_preview=content[:150],
    tool_calls_count=len(tool_calls),
    _elapsed=t1)

# [line 463] LLM 输出最终报告
_dl("round_finish",
    stock_name=stock_name, round=round_i,
    output_len=len(output),
    output_preview=output[:200])

# [line 477] Tool calls
_dl("round_tool_calls",
    stock_name=stock_name, round=round_i,
    tool_names=[t.name for t in tool_calls],
    tool_args=[t.input for t in tool_calls],
    assistant_content=content[:200])

# [line 549] Tool 返回结果
_dl("round_tool_result",
    stock_name=stock_name, round=round_i,
    article_ids=[a[2] for a in article_results],
    engines_with_data=list(set(a[0] for a in article_results)),
    warnings=warnings,
    result_len=total_len)

# [line 565] 内容过长截断
_dl("round_length",
    stock_name=stock_name, round=round_i,
    content_len=content_length,
    content_preview=content[:200])

# [line 578] 达到最大轮次
_dl("agent_max_rounds",
    stock_name=stock_name, rounds=round_i,
    messages_count=len(messages),
    last_assistant_content=last_content[:200])
```

---

## 3. log_office_error — 数据库错误日志（SQLite error_log）

### 实现文件

`office/database.py`

### 输出位置

SQLite `report_market.db` → `error_log` 表（`service_name='office'`）

### 函数签名

```python
log_office_error(
    module="office",
    function="",
    level="ERROR",
    stock_name="",
    ts_code="",
    error_msg="",
    detail="",           # 未传则自动填 traceback.format_exc()
    error_code="",
    data_snapshot="",
    engine_name="",
)
```

### 所有错误点（15 处）

#### writer/server.py（4 处）

| 行号 | 级别 | function | error_msg | error_code |
|:-----|:-----|:---------|:-----------|:-----------|
| 117 | WARNING | `_run_sub_writer._call_type_a` | `"middleman Type A 返回 {status_code}"` | — |
| 126 | WARNING | `_run_sub_writer._call_type_a` | `"middleman Type A 异常: {e}"` | — |
| 207 | ERROR | `_run_sub_writer` | `"POST reporter 超时（3 次）: {e}"` | `WRITER_REPORTER_TIMEOUT` |
| 236 | ERROR | `_run_sub_writer` | `"sub writer 失败，context 已保存到 {fallback_path}"` | `WRITER_SUB_WORKER_FAILED` |

#### middleman/server.py（4 处）

| 行号 | 级别 | function | error_msg | error_code |
|:-----|:-----|:---------|:-----------|:-----------|
| 284 | WARNING | `_call_mail_tower_article` | `"{engine} /article {resp.status_code}"` | `MIDDLEMAN_ENGINE_ERROR` |
| 390 | WARNING | `_call_mail_tower_article` | `"{engine} /article timeout or error after polling"` | `MIDDLEMAN_ENGINE_TIMEOUT` |
| 460 | WARNING | `_retry_http.{label}` | `"连接失败: {e}"` | `MIDDLEMAN_ENGINE_TIMEOUT` |
| 472 | ERROR | `_retry_http.{label}` | `"意外异常: {e}"` | — |

#### reporter/server.py（1 处）

| 行号 | 级别 | function | error_msg | error_code |
|:-----|:-----|:---------|:-----------|:-----------|
| 79 | ERROR | `generate_report` | `"agent.run 异常: {e}"` | `REPORTER_AGENT_ERROR` |

#### reporter/agent.py（2 处）

| 行号 | 级别 | function | error_msg | error_code |
|:-----|:-----|:---------|:-----------|:-----------|
| 435 | ERROR | `agent.run` | `"LLM API 调用异常: {e}"` | `REPORTER_LLM_ERROR` |
| 586 | WARNING | `agent.run` | `"达到最大轮次 {MAX_ROUNDS}，未生成最终报告"` | `REPORTER_LOOP_TIMEOUT` |

#### office/fetcher.py（4 处）

| 行号 | 级别 | function | error_msg | error_code |
|:-----|:-----|:---------|:-----------|:-----------|
| 68 | ERROR | `fetch_all.fetch_data` | `"fetch_midday_data 执行失败: {e}"` | `FETCH_SCRIPT_FAILED` |
| 94 | WARNING | `fetch_all.fetch_message` | `"fetch_midday_message 执行失败: {e}"` | `FETCH_SCRIPT_FAILED` |
| 109 | ERROR | `fetch_all` | `"所有股票取数失败: {missing}"` | `FETCH_ALL_FAILED` |
| 118 | WARNING | `fetch_all` | `"股票取数部分失败"` | `FETCH_PARTIAL_DATA` |

### 错误代码一览

完整列表见 `intro/error_codes.md`。

---

## 4. 各组件日志清单

### writer/server.py

```
日志类型      | 数量
DebugLogger   | 6 个 step（writer_sub ×4 + writer_api ×2）
log_office_error | 4 处调用
标准 logging   | 少量 print/info（启动信息）
```

### middleman/server.py

```
日志类型      | 数量
DebugLogger   | 3 个 step（type_a ×2 + type_b ×1）
log_office_error | 4 处调用
```

### reporter/server.py

```
日志类型      | 数量
DebugLogger   | 5 个 step（reporter 组件）
log_office_error | 1 处调用
```

### reporter/agent.py

```
日志类型      | 数量
DebugLogger   | 12 个 step（reporter_type_b ×3 + reporter_round ×9）
log_office_error | 2 处调用
```

### office/fetcher.py

```
日志类型      | 数量
DebugLogger   | 0（不使用）
log_office_error | 4 处调用
```

---

## 5. Mail Tower 日志系统

Mail Tower 有独立的日志系统，写入**同一 SQLite 数据库**：

### 文件日志 — `reporting/debug_log.py`

```
路径: mail_tower/logs/debug_{YYYYMMDD}.log
格式: JSONL（逐行 JSON）
类: DLog
  - DLog.log(step, **kwargs)            # 通用调试
  - DLog.log_extract(session_id, engine, article_id, url, step, status, elapsed_ms, body_len, error, extra)  # 文章提取专用
特点: 单文件（非按组件分），值>300字符截断
```

### 数据库错误日志 — `reporting/error_reporter.py`

```
表: error_log（service_name 无统一前缀，直接用 engine 名）
错误码定义: 14 个标准错误码
  - ENGINE_TIMEOUT / ENGINE_ERROR / ENGINE_EMPTY / ENGINE_ANTI_CRAWL / ENGINE_NAME_RESOLVE
  - BODY_EXTRACT_FAIL / BODY_EXTRACT_EMPTY / PDF_DOWNLOAD_FAIL / PDF_EXTRACT_FAIL
  - SESSION_NOT_FOUND / SESSION_CLOSED
  - RATE_LIMIT / INTERNAL_ERROR / WORKER_BUSY
API:
  - report_error(error_code, engine, session_id, error_msg, detail, data, function)
  - report_exception(error_code, engine, session_id, function, data)  # 自动捕获异常
```

### 数据库服务日志 — `reporting/service_log.py`

```
表: service_log_v3
用途: 单次请求的分步追踪（与 error_log 互补）
API:
  - log_svc(session_id, engine, step, message, elapsed_ms, error_code, level, extra)
标准 step 标识:
  search_start → search_queue_wait → search_complete → search_error → search_timeout
  body_extract_start → body_extract_done → body_extract_fail
  article_fetch → article_ready → article_error
  session_close → session_expire
```

> **注意**：mail_tower 的 `error_reporter.py` 和 office 的 `database.py` 是**两套独立实现**，但都写入 `error_log` 表。

---

## 6. Commander 日志系统

Commander（调度层）有独立的日志，与 Office 日志不重叠：

### 运行日志

```
位置: office/log/task_{YYYYMMDD}.log
格式: 标准 logging（asctime [level] message）
内容: 完整运行流水，包括:
  - 健康检测结果
  - 股票池查询
  - Writer API 调用（请求/响应/耗时）
  - 分发记录
  - 异常堆栈
```

### 摘要日志

```
位置: office/log/summary_{YYYYMMDD}.json
格式: JSON
内容: 结构化摘要，包括:
  - status（completed / partial / health_check_failed / skipped）
  - health_check 结果
  - 各用户股票数
  - 去重后股票数
  - batch1 / batch2 统计
  - final_failed 列表
  - 分发结果
```

### 数据库错误日志

```
表: error_log（service_name='commander'）
error_code:
  - BATCH1_FAILED: Writer API 第一批失败
  - BATCH2_FAILED: 第二批（重试）仍失败
  - REPORT_FILE_NOT_FOUND: 报告文件在 output/ 中不存在
  - REPORT_COPY_FAILED: 复制到用户目录失败
```

---

## 7. 移除指南

> 如需移除调试日志（DebugLogger），按以下步骤操作，不影响业务功能。

### 安全的移除范围（DebugLogger 全部可删）

DebugLogger **仅用于调试/性能追踪**，核心业务不依赖它：

| 文件 | 操作 |
|:-----|:------|
| `office/dlog/debug_logger.py` | 删除整个文件 |
| `office/dlog/` | 删除整个目录 |
| `office/test_drive/results/debug_logs/` | 可删除（历史数据）|

### 保留范围（不可移除）

| 内容 | 理由 |
|:-----|:------|
| `database.log_office_error()` | 写入 `error_log` 表，异常追溯必需 |
| Office 标准 logging | 运行信息输出（print/info）|
| Commander 任务日志 | 任务流水和摘要 |
| Mail Tower error_reporter | 引擎错误追溯 |

### 移除后需清理的代码引用

DebugLogger 在以下文件中有 `import` 和调用：

| 文件 | 移除内容 |
|:------|:---------|
| `office/writer/server.py` | 删 `from dlog.debug_logger import get_logger`、`log = get_logger(...)`、所有 `log(...)` 调用 |
| `office/middleman/server.py` | 同上 |
| `office/reporter/server.py` | 同上 |
| `office/reporter/agent.py` | 同上（含 `_dl = get_logger(...)`）|

> **建议**：移除时搜索 `get_logger` 确保无遗漏。
> 移除前后运行 `test_e2e.py` 确认功能正常。

---

## 附录：数据库 error_log 表结构

```sql
CREATE TABLE error_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    module          TEXT NOT NULL,      -- 'office.writer' / 'etl' / 'commander'
    function        TEXT NOT NULL,
    level           TEXT NOT NULL DEFAULT 'ERROR',
    stock_name      TEXT,
    ts_code         TEXT,
    api_name        TEXT,
    error_type      TEXT,
    error_msg       TEXT,
    detail          TEXT,               -- traceback
    data_snapshot   TEXT,               -- 上下文 JSON
    resolved        INTEGER DEFAULT 0,
    resolved_at     TEXT,
    resolve_note    TEXT,
    created_at      TEXT DEFAULT (datetime('now', 'localtime')),
    service_name    TEXT,               -- 'office' / 'commander' / 'etl'
    error_code      TEXT,
    engine_name     TEXT,
    session_id      TEXT,
    worker_id       TEXT
);
```

### service_name 使用约定

| service_name | 写入方 |
|:-------------|:-------|
| `office` | `office/database.py`（`log_office_error`）|
| `commander` | `commander/scheduled_task.py`（`log_error_to_db`）|
| `etl` | `etl/run_if_trading_day.sh`（Shell 脚本内嵌 Python 写入）|
| (无/引擎名) | mail_tower `error_reporter.py` |
