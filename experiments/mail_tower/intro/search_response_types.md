# `/search` 与 `/article` 返回类型全解（mode=list，dcfin 除外）

> 适用引擎：sinafin / baidufin / thsfin / juchao / qnainfo / ddg

---

## 基础知识：HTTP 状态码在哪？

HTTP 状态码（status code）**不在 JSON 报文里**，它在 **HTTP 响应行（status line）** 里。

原始 HTTP 响应长这样：

```
HTTP/1.1 200 OK                                          ← 状态码在这行
content-type: application/json
content-length: 512
...

{"session_id": "s_...", "status": "list_ready", ...}     ← JSON body
```

- `200` → 正常，JSON body 是 `PollResponse` 结构
- `503` / `504` / `500` → 异常，JSON body **只有 `{"detail": "..."}`**，**不包含** `session_id`、`status`、`preview` 等任何正常字段

**客户端如何拿到状态码：**
- `curl`：`-w "%{http_code}"` 或在输出中看
- `requests`：`response.status_code`
- `httpx`：`response.status_code`

---

## 一、正常返回（HTTP 200）

### 1. `status = "list_ready"`

**引擎：** sinafin / baidufin / thsfin / juchao

**含义：** 搜索成功，已拿到文章列表。正文可能还在后台提取（baidufin/thsfin/juchao），或等待按需加载（sinafin）。需调 `/article` 获取正文。

```json
{
  "session_id": "s_20260726_182345_a1b2c3d4",
  "status": "list_ready",
  "mode": "list",
  "llm_mode": "none",
  "engine": "sinafin",
  "empty": false,
  "session_closed": false,
  "preview": {
    "articles": [
      {
        "id": "a_01",
        "title": "宁德时代：关于2026年半年度报告的提示性公告",
        "body_avail": "有",
        "date": "2026-07-24 16:06",
        "snippet": "2026-07-24 16:06"
      },
      {
        "id": "a_02",
        "title": "宁德时代：关于新增募投项目的公告",
        "body_avail": "有",
        "date": "2026-07-24 14:17",
        "snippet": "2026-07-24 14:17"
      }
    ],
    "total": 5,
    "total_raw": 10,
    "filter_stats": {}
  },
  "elapsed": 3.2,
  "created_at": "2026-07-26T18:23:45"
}
```

### 2. `status = "done"`

**引擎：** ddg / qnainfo

**含义：** 正文已随 search 返回，无需再调 `/article`。qnainfo 的 session 自动关闭（`session_closed: true`）。

```json
{
  "session_id": "s_20260726_182345_a1b2c3d4",
  "status": "done",
  "mode": "list",
  "llm_mode": "none",
  "engine": "qnainfo",
  "empty": false,
  "session_closed": true,
  "preview": {
    "articles": [
      {
        "id": "a_01",
        "title": "宁德时代：固态电池最新进展",
        "body_avail": "有",
        "date": "2026-07-24",
        "snippet": "..."
      }
    ],
    "total": 3,
    "total_raw": 3,
    "filter_stats": {}
  },
  "elapsed": 1.5,
  "created_at": "2026-07-26T18:23:45"
}
```

### 3. 正常空结果（任何引擎，HTTP 200）

**含义：** 引擎正常运行，但当天无该股票的文章/公告。**不是错误。**
**注意：** 空结果的 session 在服务端已立即关闭（`session_closed: true`），不可再调 `/article`。

```json
{
  "session_id": "s_20260726_182345_a1b2c3d4",
  "status": "list_ready",
  "mode": "list",
  "llm_mode": "none",
  "engine": "juchao",
  "empty": true,
  "session_closed": true,
  "preview": {
    "articles": [],
    "total": 0,
    "total_raw": 0,
    "filter_stats": {}
  },
  "elapsed": 0.8,
  "created_at": "2026-07-26T18:23:45"
}
```

---

## 二、错误返回（HTTP ≠ 200）

错误时 FastAPI 默认只返回 `{"detail": "..."}`，**没有** `session_id` / `status` / `preview` 等字段。

### 4. HTTP 503 — 服务繁忙（WORKER_BUSY）

**触发条件：** 16 个全局并发槽位全部被占用，请求排队超过 300s。

```
HTTP/1.1 503 Service Unavailable
content-type: application/json
```

```json
{
  "detail": "服务繁忙，请稍后重试（所有搜索槽位已满）"
}
```

### 5. HTTP 504 — 搜索超时（ENGINE_TIMEOUT）

**触发条件：** 后端引擎执行超过 90s 超时限制。

```
HTTP/1.1 504 Gateway Timeout
content-type: application/json
```

```json
{
  "detail": "搜索超时 (90s)"
}
```

### 6. HTTP 500 — 引擎内部错误（ENGINE_ERROR）

**触发条件：** 引擎抛出未预期的异常。常见子类型：

| 子类型 | detail 特征 | 常见引擎 |
|--------|-------------|:--------:|
| 股票代码格式错误 | `"搜索失败: 无法从 'xxx' 解析出股票代码..."` | juchao / sinafin |
| 网络连接失败 | `"搜索失败: ConnectionResetError(104, ...)"` | sinafin / baidufin |
| HTTP 连接超时 | `"搜索失败: ConnectError: ... Connection refused"` | 国内站点不稳定 |
| Playwright 异常 | `"搜索失败: TimeoutError: page.goto timed out"` | baidufin / thsfin |
| akshare 数据异常 | `"搜索失败: KeyError: ..."` / `"搜索失败: JSONDecodeError: ..."` | juchao / qnainfo |
| 其他未知异常 | `"搜索失败: ..."`（具体看后半段） | 任何引擎 |

```
HTTP/1.1 500 Internal Server Error
content-type: application/json
```

```json
{
  "detail": "搜索失败: 无法从 'invalid' 解析出股票代码。请提供6位数字代码或A股股票名称。"
}
```

```json
{
  "detail": "搜索失败: ConnectionResetError(104, 'Connection reset by peer')"
}
```

---

## 三、判别速查表

| 怎么判断 | HTTP 状态码 | JSON 特征 | 含义 |
|----------|:----------:|-----------|------|
| 正常有结果 | **200** | `status:"list_ready"` + `total>0` + `session_closed:false` | 文章列表就绪，正文待提取 |
| 正常有结果（已就绪） | **200** | `status:"done"` + `total>0` + `session_closed:false\|true` | 正文已就绪（ddg/qnainfo） |
| 正常空结果 | **200** | `empty:true` + `total:0` + **`session_closed:true`** | 当天无文章，session 已关 |
| 服务忙 | **503** | 只有 `{"detail":"服务繁忙..."}` | 并发超限，稍后重试 |
| 搜索超时 | **504** | 只有 `{"detail":"搜索超时 (90s)"}` | 引擎响应慢，可重试 |
| 引擎错误 | **500** | 只有 `{"detail":"搜索失败:..."}` | 看 detail 内容定原因 |

**判别流程（伪代码）：**

```python
resp = requests.post("http://localhost:8300/search", json=body)

if resp.status_code != 200:
    # 错误响应只有 {"detail": "..."}
    detail = resp.json()["detail"]  # 就这一个字段
    if resp.status_code == 503:   handle_worker_busy(detail)
    elif resp.status_code == 504: handle_engine_timeout(detail)
    elif resp.status_code == 500: handle_engine_error(detail)
    return

data = resp.json()
# 现在 status_code == 200，以下字段全部存在
session_id = data["session_id"]
status = data["status"]         # "list_ready" | "done"
engine = data["engine"]
empty = data["empty"]           # true / false
session_closed = data.get("session_closed", False)  # true 时不可再调 /article
total = data["preview"]["total"]  # article 数量
articles = data["preview"]["articles"]  # 文章列表
```

---

## 四、调用示例（Python 客户端）

```python
import requests
import time

BASE = "http://localhost:8300"

def search_stock(code: str, engine: str) -> dict | None:
    """返回 /search 结果，失败时打印并返回 None"""
    try:
        resp = requests.post(
            f"{BASE}/search",
            json={"query": code, "engine": engine, "mode": "list", "filter_days": 3},
            timeout=120,
        )
    except requests.exceptions.ConnectionError:
        print("[ERROR] 服务未启动或连接被拒")
        return None
    except requests.exceptions.Timeout:
        print("[ERROR] 请求超时（120s）")
        return None

    if resp.status_code == 503:
        print("[BUSY] 服务繁忙，稍后重试")
        return None
    if resp.status_code == 504:
        print("[TIMEOUT] 搜索超时")
        return None
    if resp.status_code == 500:
        detail = resp.json().get("detail", "")
        print(f"[ERROR] 引擎失败: {detail}")
        return None

    data = resp.json()
    if data.get("empty"):
        print(f"[EMPTY] {engine}: 无结果（session_closed={data.get('session_closed')}）")
        return data  # 仍是合法响应，只是 articles 为空，session 已关

    print(f"[OK] {engine}: {data['preview']['total']} 篇文章, status={data['status']}, session_closed={data.get('session_closed')}")
    return data
```

---

## 五、附录：各引擎 status 对照

| 引擎 | 正常 status | `session_closed` | 正文就绪时机 | body 在哪 |
|:----:|:----------:|:---------------:|-------------|:---------:|
| sinafin | `list_ready` | `false` | `/article` 按需加载（1.8s 节流） | 调 `/article` 后写入 session |
| baidufin | `list_ready` | `false` | 后台线程自动抓取（几秒后） | 调 `/article` 时读缓存 |
| thsfin | `list_ready` | `false` | 后台线程自动抓取（几秒后） | 调 `/article` 时读缓存 |
| juchao | `list_ready` | `false` | 后台线程下载 PDF（5~15s） | 调 `/article` 时读缓存 |
| qnainfo | `done` | `true` | 随 search 返回 | `body_text` 已就绪 |
| ddg | `done` | `false` | 随 search 返回（PDF 文章后台异步） | 已写入 session 缓存 |

---

## 六、第二步调用：`/article` 返回类型全解

在 `/search` 成功返回非空结果后，第二步调 `/article` 获取正文。

> 注意：engine=ddg 和 qnainfo 在 `/search` 时已返回 `status:"done"` 和正文，通常不需要再调 `/article`。

### ArticleResponse 结构

```json
{
  "session_id": "s_...",
  "status": "processing",          ← 顶层全局状态（新增）
  "articles": [
    {
      "article_id": "a_01",
      "status": "ready",
      "title": "...",
      "body_text": "...",
      "truncated": false
    }
  ],
  "session_closed": false
}
```

### 顶层 `status` 规则

| 各文章的实际状态 | 顶层 `status` |
|:----------------:|:------------:|
| 有任一 `processing`（不管其他） | `"processing"` |
| 全部 `error`（无一篇 ready） | `"error"` |
| 有任一 `ready`（不管有没有 error） | `"ready"` |

### 一、正常返回（HTTP 200）

#### 1. 全是 processing（正文还没好）

```json
{
  "session_id": "s_...",
  "status": "processing",
  "articles": [],
  "session_closed": false
}
```

**触发条件：** 至少有一篇文章还没提取完。所有文章统一返回顶层 `status: "processing"`，`articles:[]`。

**出现时机：**
- **sinafin：** `/article` 调用时正在按需加载（要等 1.8s 节流 × 文章数），耗时约 20~30s
- **baidufin/thsfin/juchao：** 后台线程还没跑完，几秒到十几秒不等

#### 2. 全 ready（全部成功）

```json
{
  "session_id": "s_...",
  "status": "ready",
  "articles": [
    {"article_id": "a_01", "status": "ready", "body_text": "...", "truncated": false},
    {"article_id": "a_02", "status": "ready", "body_text": "...全文过长已截断...", "truncated": true}
  ],
  "session_closed": false
}
```

#### 3. ready + error 混合（部分成功）

```json
{
  "session_id": "s_...",
  "status": "ready",
  "articles": [
    {"article_id": "a_01", "status": "ready", "body_text": "..."},
    {"article_id": "a_02", "status": "error", "fetch_error": "ConnectionResetError(104)"}
  ],
  "session_closed": false
}
```

**顶层 `status` = `"ready"`**（有任一 ready 就算 ready）。

#### 4. 全 error（全部提取失败）

```json
{
  "session_id": "s_...",
  "status": "error",
  "articles": [
    {"article_id": "a_01", "status": "error", "fetch_error": "无可用 URL"},
    {"article_id": "a_02", "status": "error", "fetch_error": "提取正文失败"}
  ],
  "session_closed": false
}
```

**注意：** error 是**永久结论**——服务端已缓存结果，重试 `/article` 不会重新提取。

#### 5. session_closed 自动关闭（附加状态）

以上 2/3/4 都有可能带上 `session_closed: true`：

```json
{
  "session_id": "s_...",
  "status": "ready",
  "articles": [...],
  "session_closed": true    ← 这是最后一次 /article 调用
}
```

**触发条件：**
- `"close": true` 在请求体中指定
- 45 分钟 TTL 超时自动清理（见第五节）

### 二、错误返回（HTTP ≠ 200）

#### 6. HTTP 404 — session 不存在或已过期

```json
{"detail": "Session not found"}
```

**触发条件：** session_id 无效、TTL 过期、空结果 session 已关。

#### 7. HTTP 400 — 模式不对

```json
{"detail": "get_article 仅适用于 list 模式"}
```

#### 8. HTTP 400 — 缺少参数

```json
{"detail": "必须提供 article_id 或 article_ids"}
```

### 三、服务端内部重试

下面是 mail_tower 在后台 `/article` 调用前已经做过了的重试，**客户端无需重复**。

| 引擎 | 内部重试 | 详情 |
|:----:|:--------:|------|
| **sinafin** | ✅ **3 次**（1~3s 间隔） | trafilatura → readability → PDF 三路全失败 → 等 1~3s → 重新三路，最多 3 次。全部失败 → 永久 `error` |
| **baidufin** | ✅ **1 次**（1~3s 间隔） | httpx → Playwright 失败 → 等 1~3s → 重新 httpx → Playwright。还失败 → 永久 `error` |
| **thsfin** | ✅ **1 次**（1~3s 间隔） | 同上 |
| **juchao** | ✅ **2 次**（2~3s 间隔） | PDF 下载失败 → 等 2~3s → 重试，最多 3 次。全部失败 → 永久 `error` |

所以客户端看到的 `error` 已经是服务端内部重试耗尽后的结果，**再次重试 `/article` 不会有任何帮助**（结果已缓存）。

### 四、客户端重试策略

| 返回特征 | 判断方式 | 重试？ | 间隔 | 最多 | 说明 |
|:--------:|----------|:-----:|:----:|:---:|------|
| **processing** | `status == "processing"` | ✅ | 3~5s | **3 次** | 后台线程还没跑完，放心重试 |
| **ready** | `status == "ready"` | ❌ | — | 0 | 成功 |
| **error** | `status == "error"` | **❌ 不重试** | — | 0 | 服务端已缓存，重试 `/article` 结果一样 |
| **`session_closed: true`** | 该字段为 true | ❌ | — | 0 | session 已关，需重新 `/search` |
| **404** | status_code == 404 | ❌ | — | 0 | session 已失效 |
| **500** | status_code == 500 | ✅ | 3~5s | 2 次 | 服务器抖动 |
| **连接失败** | ConnectionError/Timeout | ✅ | 5→10s | 2 次 | 网络波动 |

### 五、关键设计原则

1. **正文请求无次数限制**（2026-08-01 起移除 max_body_returns 计数机制）— 轮询 `/article` 可无限次
2. **Error 是永久结论** — 服务端内部已重试耗尽并缓存，客户端重试 `/article` 无意义
3. **session 仅由显式 `close: true` 或 TTL 关闭**
4. **session_closed 后不可再调 /article** — 需要重新走 `/search`
5. **45 分钟 TTL** — session 超时自动清理，防止资源泄漏
