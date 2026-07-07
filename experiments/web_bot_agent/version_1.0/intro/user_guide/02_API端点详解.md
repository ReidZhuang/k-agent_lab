# API 端点详解

## 1. 发起搜索

### `POST /search`

启动一次完整的搜索 - 处理流程，异步执行。

### 请求体

```json
{
  "query": "信创产业 2025",
  "keyword": "信创",
  "max_results": 5,
  "mode": "segments",
  "session": "new"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `query` | string | 是 | — | 搜索关键词，传给 web-forager |
| `keyword` | string | 否 | `""` | 搜索用的关键字，留空则用 query |
| `max_results` | number | 否 | `5` | 返回多少条搜索结果（1-10） |
| `mode` | string | 否 | `"segments"` | `"segments"`=按段落分组，`"summary"`=整篇摘要+要点 |
| `session` | string | 否 | `"new"` | 固定传 `"new"` |

### 响应（202 Accepted）

```json
{
  "session_id": "s_20250707_143000_140737354094912",
  "status": "processing",
  "mode": "segments",
  "created_at": "2025-07-07T14:30:00+00:00"
}
```

| 字段 | 说明 |
|---|---|
| `session_id` | 会话 ID，后续轮询/查询都靠它 |
| `status` | 固定为 `"processing"` |
| `mode` | 请求时指定的 mode |
| `created_at` | 会话创建时间（ISO 8601） |

---

## 2. 轮询结果

### `GET /poll/{session_id}`

获取处理结果。需要反复调用直到 `status` 变为 `"done"`。

### 响应 — 处理中

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "processing"
}
```

### 响应 — 完成（segments 模式）

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "done",
  "mode": "segments",
  "articles": { ... },
  "segments": { ... },
  "elapsed": 45.2,
  "created_at": "2025-07-07T14:30:00+00:00"
}
```

### 响应 — 完成（summary 模式）

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "done",
  "mode": "summary",
  "articles": { ... },
  "segments": {},
  "elapsed": 32.1,
  "created_at": "2025-07-07T14:30:00+00:00"
}
```

| 字段 | 说明 |
|---|---|
| `articles` | 文章列表（详见[输出格式说明](03_输出格式说明.md)） |
| `segments` | 分组列表（summary 模式下为空 `{}`） |
| `elapsed` | 总耗时（秒） |

### 响应 — 出错

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "error",
  "mode": "segments",
  "error": "Ollama connection refused",
  "created_at": "2025-07-07T14:30:00+00:00"
}
```

---

## 3. 获取分组原文

### `POST /segment`

根据文章 ID 和分组 ID 获取该分组对应的原文内容。（仅 segments 模式有效）

### 请求体

```json
{
  "session_id": "s_20250707_143000_...",
  "article_id": "a_01",
  "segment_id": "s1"
}
```

### 响应

```json
{
  "session_id": "s_20250707_143000_...",
  "article_id": "a_01",
  "segment_id": "s1",
  "text": "（该分组覆盖的完整原文）"
}
```

---

## 4. 查询会话状态

### `GET /status/{session_id}`

查看会话的当前状态、耗时、文章数量等信息，不返回完整结果。

### 响应

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "done",
  "mode": "summary",
  "query": "信创产业 2025",
  "keyword": "信创",
  "created_at": "2025-07-07T14:30:00+00:00",
  "elapsed": 32.1,
  "article_count": 3,
  "error": null
}
```

| 字段 | 说明 |
|---|---|
| `mode` | 创建会话时指定的处理模式 |
| `status` | `processing` / `done` / `error` / `closed` |
| `article_count` | 成功处理的文章数量 |
| `elapsed` | 已耗时（秒） |
| `error` | 错误信息（如有） |

---

## 5. 获取要点原文（summary 模式）

### `POST /point-text`

根据要点序号查找对应的原文段落。仅 summary 模式可用。

### 请求体

```json
{
  "session_id": "s_20250707_143000_...",
  "article_id": "a_01",
  "point_indices": [2, 7]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话 ID |
| `article_id` | string | 是 | 文章 ID（如 `a_01`） |
| `point_indices` | array[int] | 是 | 要点序号列表（从1开始），如 `[2,7]` |

### 响应

```json
{
  "session_id": "s_20250707_143000_...",
  "article_id": "a_01",
  "results": [
    {
      "point_index": 2,
      "key_point": "国产化替代面临挑战，尤其在高端芯片和工业软件领域。",
      "found": true,
      "text": "近年来，在政策引导和市场需求双重驱动下..."
    },
    {
      "point_index": 7,
      "key_point": "开发者规模持续壮大，年轻开发者占比高，一线城市集中。",
      "found": true,
      "text": "**特点**：年轻开发者占比高（25-35岁占65%）..."
    }
  ]
}
```

**查找逻辑**：
1. 系统根据 `_kp_chunk_map` 直接定位该要点来自哪一块
2. 只送那一块给 LLM 定位段落号
3. 多个要点的不同块并行调用 LLM

---

## 6. 关闭会话

### `POST /close/{session_id}`

主动关闭一个会话。关闭后该会话不再可用。

### 响应

```json
{
  "session_id": "s_20250707_143000_...",
  "status": "closed"
}
```

---

## 7. 服务健康检查

### `GET /`

```json
{
  "service": "bot_search API",
  "version": "1.0.0"
}
```

---

**上一节：[快速开始](01_快速开始.md)** | **下一节：[输出格式说明](03_输出格式说明.md)**
