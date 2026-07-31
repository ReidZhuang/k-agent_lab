# mail_tower 中间层重试策略

> 适用场景：中间层（middleman）调用 mail_tower 的重试机制。
> 独立于 mail_tower 内部每引擎的重试（第 0 层），两层互不干扰。
> 分两部分：**第一次调用 `/search`** 和 **第二次调用 `/article`**，策略不同。

---

## 第一部分：第一次调用 `/search`

### 总策略

| 返回类型 | 判断条件 | 重试？ | 间隔 | 最多重试次数 |
|:--------:|----------|:-----:|:----:|:----------:|
| **503** | `resp.status_code == 503` | ✅ | 3~5s | 3 |
| **504** | `resp.status_code == 504` | ✅ | 10~15s | 2 |
| **500 网络类** | 500 + detail 含 `ConnectionResetError` / `ConnectError` / `TimeoutError` | ✅ | 2~3s | 3 |
| **500 参数类** | 500 + detail 含 `无法解析` / `valueError` | ❌ | — | 0 |
| **500 其他** | 500 + 不符合以上两种 | ✅ | 3~5s | 3 |
| **200 empty:true** | 200 + `data["empty"] == true` | ❌ | — | 0 |
| **200 有结果** | 200 + `data["empty"] == false` | ❌ | — | 0 |
| **连接失败** | `requests.ConnectionError` / `Timeout`（无 HTTP 响应） | ✅ | 5→10→15s 递增 | 3 |

### 各类型详解

#### 1. 503 — WORKER_BUSY（服务繁忙）

**HTTP 响应**
```
503 Service Unavailable
{"detail": "服务繁忙，请稍后重试（所有搜索槽位已满）"}
```

**何时触发：** 16 个全局并发槽位全部被占用，请求排队超过 300s。

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 3~5s（带随机 jitter） |
| 最多重试 | 3 次 |
| 理由 | 槽位很快释放，短间隔重试即可恢复。 |

#### 2. 504 — ENGINE_TIMEOUT（搜索超时）

**HTTP 响应**
```
504 Gateway Timeout
{"detail": "搜索超时 (90s)"}
```

**何时触发：** 后端引擎执行超过 90s 超时限制。

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 10~15s（长间隔） |
| 最多重试 | 2 次 |
| 理由 | 90s 超时说明引擎本身慢或站点拥堵。短间隔大概率也超时，等 10s+ 让拥堵缓解。 |

#### 3. 500 — ENGINE_ERROR（引擎内部错误）

**HTTP 响应**
```
500 Internal Server Error
{"detail": "搜索失败: ..."}
```

按 detail 内容分三种：

##### 3a. 网络类（可重试）

detail 含 `ConnectionResetError` / `ConnectError` / `TimeoutError`

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 2~3s |
| 最多重试 | 3 次 |
| 理由 | 网络抖动，短时间可自愈。加上引擎内部已重试，总计最多 5 次。 |

示例 detail：
```
搜索失败: ConnectionResetError(104, 'Connection reset by peer')
搜索失败: ConnectError: [Errno 111] Connection refused
搜索失败: TimeoutError: page.goto timed out after 30000ms
```

##### 3b. 参数类（不重试）

detail 含 `无法解析` / `valueError`

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | 股票代码传错了，重试一百次也一样。直接抛给上层改参数。 |

示例 detail：
```
搜索失败: 无法从 'invalid' 解析出股票代码。请提供6位数字代码或A股股票名称。
搜索失败: ValueError: no such stock code
```

##### 3c. 其他未知类（重试）

不符合以上两种模式的其他 500 错误。

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 3~5s |
| 最多重试 | 3 次 |
| 理由 | 不确定是临时抖动还是永久性异常，给 3 次机会试探。 |

示例 detail：
```
搜索失败: KeyError: 'adjunctUrl'
搜索失败: 'NoneType' object has no attribute 'get'
搜索失败: JSONDecodeError: Expecting value: line 1 column 1
```

#### 4. 200 empty:true（正常空结果）

**HTTP 响应**
```
200 OK
{"status": "list_ready", "empty": true, "session_closed": true, "preview": {"total": 0, "articles": []}}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | 引擎正常运行，当天确实无该股票的文章/公告。不是错误。session 已自动关闭（`session_closed: true`），不可再调 `/article`。 |

#### 5. 200 有结果（正常成功）

**HTTP 响应**
```
200 OK
{"status": "list_ready", "empty": false, "preview": {"total": 5, "articles": [...]}}
```
或
```
200 OK
{"status": "done", "empty": false, "preview": {"total": 3, "articles": [...]}}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | 正常成功响应，直接往下走 `/article` 取正文或取用已有结果。 |

#### 6. 客户端连接失败（无 HTTP 响应）

**错误表现：** `requests.ConnectionError` 或 `requests.Timeout` 异常抛出，无 HTTP 响应。

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 5s → 10s → 15s（递增 + jitter） |
| 最多重试 | 3 次 |
| 理由 | 服务可能正在重启或网络闪断。递增间隔避免在服务还没恢复时狂打。 |

---

## 第二部分：第二次调用 `/article`

### 总策略

| 返回类型 | 判断条件 | 重试？ | 间隔 | 最多重试次数 |
|:--------:|----------|:-----:|:----:|:----------:|
| **200 processing** | `status == "processing"` | ✅ | **5s（固定）** | **120 次**（直到不再 processing 为止） |
| **200 ready** | `status == "ready"` | ❌ | — | 0 |
| **200 error** | `status == "error"` | ❌ | — | 0 |
| **400** | status_code == 400 | ❌ **透传** | — | 0 |
| **404** | status_code == 404 | ❌ | — | 0 |
| **500** | status_code == 500 | ✅ | 1~3s | 3 |
| **连接失败** | `requests.ConnectionError` / `Timeout`（无 HTTP 响应） | ✅ | 5→10→15s 递增 | 3 |

### 各类型详解

#### 1. HTTP 200 + status: "processing"

**HTTP 响应**
```
200 OK
{"status": "processing", "articles": [], "session_closed": false}
```

**何时触发：** 至少有一篇文章正文还没提取完（后台线程仍在运行，或 sinafin 正在按需加载）。

**服务端内部已做过的重试（客户端无需关心）：**

| 引擎 | 内部重试 |
|:----:|:--------|
| sinafin | trafilatura → readability → PDF 全失败 → 等 1~3s → 重试三路，最多 **3 次** |
| baidufin | httpx → Playwright → 等 1~3s → 重新 httpx → Playwright，**1 次** |
| thsfin | 同上，**1 次** |
| juchao | PDF 下载失败 → 等 2~3s → 重试，最多 **3 次** |

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | **5s（固定）** |
| 最多重试 | **120 次**（约 10 分钟） |
| 终止条件 | `status` 不再为 `"processing"` |
| 理由 | `/article` 正文请求无次数限制（2026-08-01 起移除计数机制），随便重试多少次都不影响。5s 固定间隔给后台足够的完成时间。120 次 × 5s = 600s（10 分钟），远超所有引擎的最大提取耗时。 |

#### 2. HTTP 200 + status: "ready"

**HTTP 响应**
```
200 OK
{"status": "ready", "articles": [...], "session_closed": false}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | 正文已就绪，直接取用。如有部分是 error 也是永久结论，重试不会重新提取。 |

#### 3. HTTP 200 + status: "error"

**HTTP 响应**
```
200 OK
{"status": "error", "articles": [...], "session_closed": false}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | 服务端内部已重试耗尽，结果已缓存。再次调用 `/article` 返回相同结果。 |

#### 4. HTTP 400

**HTTP 响应**
```
400 Bad Request
{"detail": "get_article 仅适用于 list 模式"}
```
或
```
400 Bad Request
{"detail": "必须提供 article_id 或 article_ids"}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ **不透传** |
| 处理方式 | **向上游申请方透传**，说明请求参数错误 |
| 理由 | 400 是客户端逻辑错误，重试无法解决。 |

#### 5. HTTP 404

**HTTP 响应**
```
404 Not Found
{"detail": "Session not found"}
```

**何时触发：** session_id 无效、TTL 过期（45 分钟）、session 已关闭。

| 项 | 值 |
|:--|:---|
| 是否重试 | ❌ 否 |
| 理由 | session 已失效，需要重新走 `/search` 获取新 session。 |

#### 6. HTTP 500

**HTTP 响应**
```
500 Internal Server Error
{"detail": "搜索失败: ..."}
```

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 1~3s |
| 最多重试 | 3 次 |
| 理由 | 服务器抖动，短间隔重试可能恢复。 |

#### 7. 客户端连接失败（无 HTTP 响应）

**错误表现：** `requests.ConnectionError` 或 `requests.Timeout` 异常抛出，无 HTTP 响应。

| 项 | 值 |
|:--|:---|
| 是否重试 | ✅ 是 |
| 间隔 | 5s → 10s → 15s（递增 + jitter） |
| 最多重试 | 3 次 |
| 理由 | 服务可能正在重启或网络闪断。递增间隔避免在服务还没恢复时狂打。 |

---

## 间隔计算公式

### `/search` 间隔

| 条件 | 公式 |
|:----|:-----|
| 503 | `3 + random() * 2` → 3~5s |
| 504 | `10 + random() * 5` → 10~15s |
| 500 网络类 | `2 + random()` → 2~3s |
| 500 其他 | `3 + random() * 2` → 3~5s |
| 连接失败 | `5 + attempt * 5 + random() * 2` → 5→10→15s |

### `/article` 间隔

| 条件 | 公式 |
|:----|:-----|
| 200 processing | **5s（固定）** |
| 500 | `1 + random() * 2` → 1~3s |
| 连接失败 | `5 + attempt * 5 + random() * 2` → 5→10→15s |

---

## 关键原则

1. **分两层互不干扰** — mail_tower 内部重试（第 0 层）和中间层重试（第 1 层）独立运行
2. **`/search` 每次重试是全新请求** — 拿到新 `session_id`，不复用旧 session
3. **`/article` 只重试 `processing`** — 其他状态（`ready`、`error`）都是最终结论
4. **`/article` 正文请求无次数限制**（2026-08-01 起移除计数机制）— 重试 120 次也不影响
5. **400 向上游透传** — 中间层不做参数纠错
6. **所有间隔带随机 jitter** — 避免惊群
7. **重试耗尽后抛异常让上层处理** — 中间层不吞错误
