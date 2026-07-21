# bot_search API v3.0 — 使用文档

## 快速开始

### 启动服务

```bash
# 1. 启动 sinafin 新闻源（端口 8000）
cd research/experiments/report_machine/sinafin_artical_tool
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8000

# 2. 启动 v3.0 API（端口 8300）
cd research/experiments/web_bot_agent/version_3.0
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300
```

### 验证服务

```bash
curl http://localhost:8300/
# → {"service":"bot_search API","version":"3.0.0","modes":["preview","full","list"],"engines":["ddg","sinafin"]}
```

---

## 典型场景：个股新闻查询

### 场景一：先看标题，再挑着看正文（推荐）

#### 第 1 步：搜索文章列表

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"宁德时代",
    "engine":"sinafin",
    "mode":"list",
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }'
```

**响应：**

```json
{
  "session_id": "s_20260721_174624_...",
  "status": "list_ready",
  "preview": {
    "articles": [
      {"id": "a_01", "title": "宁德时代19GWh储能大单，黄了！", "date": "2026-07-21", ...},
      {"id": "a_02", "title": "宁德时代成立新公司，含多项物联网相关业务", "date": "2026-07-21", ...}
    ]
  }
}
```

#### 第 2 步：挑选文章提取正文

```bash
curl -X POST http://localhost:8300/extract \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"s_20260721_174624_...",
    "article_ids":["a_01", "a_03"]
  }'
```

**响应：**

```json
{
  "session_id": "s_20260721_174624_...",
  "status": "processing",
  "requested": 2,
  "ignored": 0,
  "message": "已提交 2 篇正文提取任务"
}
```

> 如果传入了不存在的 article_id（如 `a_99`），会被自动忽略，`ignored` 会增加。

#### 第 3 步：获取单篇正文

```bash
curl -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"s_20260721_174624_...",
    "article_id":"a_01"
  }'
```

**响应（提取完成）：**

```json
{
  "session_id": "s_20260721_174624_...",
  "article_id": "a_01",
  "status": "ready",
  "title": "宁德时代19GWh储能大单，黄了！",
  "body_text": "据储能知家获悉，7月20日...\n\n[截断 全文长于8000字]\n",
  "truncated": false
}
```

**响应（尚未提取完成）：**

```json
{
  "session_id": "s_20260721_174624_...",
  "article_id": "a_02",
  "status": "processing",
  "title": "宁德时代成立新公司..."
}
```

#### 第 4 步：轮询进度

```bash
curl http://localhost:8300/poll/s_20260721_174624_...
```

| status 值 | 含义 |
|-----------|------|
| `list_ready` | 已返回文章列表，等待提交提取 |
| `done` | 所有提交的文章已提取完成 |

也可通过 `/status` 查看精简信息：

```bash
curl http://localhost:8300/status/s_20260721_174624_...
# → {"status":"done","article_count":2,"elapsed":2.3}
```

---

### 场景二：全自动获取（搜索+提取+LLM 一次性完成）

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"淮北矿业",
    "engine":"sinafin",
    "mode":"full",
    "llm_mode":"segments",
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }'

# 返回 session_id，轮询直到 done
curl http://localhost:8300/poll/s_...
```

### 场景三：通用网页搜索（DDG 默认引擎）

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"锂电池 新技术 2026",
    "mode":"preview",
    "filter_days":7,
    "filter_title":"固态"
  }'
```

---

## API 参考

### `POST /search`

发起搜索。根据 `mode` 参数决定执行策略。

**请求参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `query` | str | **必填** | 搜索关键词（DDG）或股票代码/名称（sinafin） |
| `engine` | str | `"ddg"` | 搜索引擎，`"ddg"` 或 `"sinafin"` |
| `mode` | str | `"full"` | 执行模式，`"preview"` / `"full"` / `"list"` |
| `llm_mode` | str | `"segments"` | LLM 模式，`"segments"` / `"summary"` / `"none"` |
| `max_results` | int | 5 | DDG 返回条数，或 sinafin 翻页页数 |
| `start_date` | str | - | 起始日期 `YYYY-MM-DD`（仅 sinafin） |
| `end_date` | str | - | 截止日期 `YYYY-MM-DD`（仅 sinafin） |
| `filter_days` | int | - | 时间过滤（天），DDG 模式使用 |
| `filter_title` | str | - | 标题关键词/正则过滤 |
| `site` | str | - | 站内限制（仅 DDG） |
| `timelimit` | str | - | DDG 搜索时间限制 |
| `keyword` | str | `""` | LLM 分析关键词上下文 |
| `include_snippet` | bool | false | 预览结果是否包含 snippet |

### `POST /extract`

提交需要提取正文的文章 ID 列表（仅 list 模式）。

**请求参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | str | 搜索返回的 session_id |
| `article_ids` | list[str] | 文章 ID 列表，如 `["a_01", "a_03"]` |

**响应：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `requested` | int | 实际提交的有效文章数 |
| `ignored` | int | 被忽略的无效 ID 数 |
| `message` | str | 处理结果描述 |

### `POST /article`

获取单篇文章正文（仅 list 模式）。

**请求参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | str | session_id |
| `article_id` | str | 文章 ID，如 `"a_01"` |

**响应 status 值：**

| status | 含义 |
|--------|------|
| `processing` | 正文尚未提取完成，请稍后重试 |
| `ready` | 正文已就绪，`body_text` 含正文内容 |
| `error` | 提取失败，`fetch_error` 含错误信息 |

### `GET /poll/{session_id}`

轮询搜索进度状态。

| status | mode=list | mode=preview | mode=full |
|--------|-----------|-------------|-----------|
| `processing` | - | - | Phase 1+2 运行中 |
| `list_ready` | 列表就绪，等待 `/extract` | - | - |
| `preview` | - | 预览就绪，Phase 2 后台运行 | - |
| `done` | 全部完成 | 全部完成 | 全部完成 |
| `error` | 出错 | 出错 | 出错 |

### `GET /status/{session_id}`

查询会话状态（精简版）。

### `POST /close/{session_id}`

主动关闭会话。

---

## 调用示例速查

### Sinafin + List（按需提取）

```bash
# 搜索
SID=$(curl -s -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"菲利华","engine":"sinafin","mode":"list","start_date":"2026-07-21","end_date":"2026-07-21"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 提取
curl -s -X POST http://localhost:8300/extract \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"article_ids\":[\"a_01\",\"a_05\"]}"

# 取正文
curl -s -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"article_id\":\"a_01\"}"
```

### Sinafin + List + LLM 分组

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"宁德时代","engine":"sinafin","mode":"list","llm_mode":"segments","start_date":"2026-07-20","end_date":"2026-07-21"}'

# 提交流程同上，提取完成后自动运行 LLM 分组
# /poll 直到 status=done 后，取 segments 字段
```

### Sinafin + Preview（先预览后 LLM）

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"宁德时代","engine":"sinafin","mode":"preview"}'
```

## 常见问题

**Q: sinafin 引擎返回 0 篇文章？**
A: 确认 sinafin_artical_tool 服务正在运行（`curl http://localhost:8000/health`），以及股票名称/代码是否正确。

**Q: /extract 提示 "无效 ID"？**
A: `article_ids` 传入了不存在的 ID，会被自动忽略。检查 `/search` 返回值中的 `articles[].id`。

**Q: /article 一直返回 processing？**
A: 正文提取需要时间（每篇数秒）。如果长时间不返回，检查：1) 是否调了 `/extract`；2) 提取过程是否有错误（查看服务端日志）。

**Q: 正文截断了怎么办？**
A: 返回的 `truncated: true` 和末尾 `[截断 全文长于8000字]` 标记。可在 `config/config.json` 中调整 `max_body_chars`。

**Q: 如何停止所有后台服务？**
A: 使用 `fuser -k 8000/tcp; fuser -k 8300/tcp`。
