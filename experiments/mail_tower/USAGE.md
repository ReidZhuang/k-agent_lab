# mail_tower API — 使用文档

## 快速开始

### 启动服务

```bash
cd research/experiments/mail_tower

# 跳过代理检查（国内金融站点直连），启动服务
PROXY_SKIP=1 nohup conda run -n stock_agent python3 -m uvicorn api:app \
  --host 0.0.0.0 --port 8300 --workers 12 --backlog 2048 > /tmp/mail_tower.log 2>&1 &
```

### 验证服务

```bash
curl http://localhost:8300/
# → {"service":"bot_search API","version":"3.0.0",...}
```

---

## 典型场景：个股新闻查询

### 场景一：先看标题，再取正文（推荐 — sinafin 按需加载）

#### 第 1 步：搜索文章列表

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"000001",
    "engine":"sinafin",
    "mode":"list",
    "filter_days":3
  }'
```

**响应：**
```json
{
  "session_id": "s_20260724_174624_...",
  "status": "list_ready",
  "preview": {
    "articles": [
      {"id": "a_01", "title": "...", "body_avail": "有", "date": "2026-07-24 16:06", ...},
      {"id": "a_02", "title": "...", "body_avail": "有", "date": "2026-07-24 14:17", ...}
    ]
  }
}
```

> sinafin 不启动后台线程取正文。返回的 `body_avail: "有"` 表示该文章有 URL 可提取，
> 正文在 `/article` 第一次调用时按需加载（经过 1.8s 全局节流）。

#### 第 2 步：取正文（触发按需加载）

```bash
curl -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"s_20260724_174624_...",
    "article_ids":["a_01", "a_02"]
  }'
```

**响应：**
```json
{
  "session_id": "s_...",
  "articles": [
    {"article_id": "a_01", "status": "ready", "body_text": "...", "title": "...", ...},
    {"article_id": "a_02", "status": "ready", "body_text": "...", "title": "...", ...}
  ],
  "session_closed": false
}
```

> sinafin 每篇正文的 HTTP 请求之间有 **≥ 1.8 秒** 的全局间隔（跨所有 worker），
> 避免触发新浪财经反爬。因此 `/article` 请求在 N 篇文章时耗时约 `N × 1.8s`。

**可能的状态：**
| status | 说明 |
|--------|------|
| `ready` | 正文已就绪 |
| `error` | 三条路（httpx → readability → PDF 下载）全部失败，`fetch_error` 含原因 |
| `processing` | 极少出现，仅当并发争抢时其他 worker 正在提取同一篇文章 |

### 其他引擎（baidufin / thsfin / dcfin / juchao）

这些引擎在 `/search` 返回后 **自动启动后台线程** 提取正文。

```bash
# 搜索 → 后台立即开始提取
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"000001","engine":"baidufin","mode":"list","filter_days":2}'

# 等几秒后取正文
curl -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s_...","article_ids":["a_01","a_02"]}'
```

> baidufin/thsfin/dcfin/juchao 的后台线程直接连接国内站点，不走代理。

---

## 股票代码格式

所有引擎的 `query` 参数**统一传 6 位纯数字代码**（如 `"000001"`、`"300750"`）即可。

各引擎实际接受的格式详情：

| 引擎 | 纯数字 `300750` | `sz300750` | `300750.SZ` | `SZ300750` | 中文名称 |
|:----:|:--------------:|:----------:|:----------:|:----------:|:-------:|
| **sinafin** | ✅ 自动补前缀 | ✅ 透传 | ✅ → `sz300750` | ❌ | ❌ |
| **thsfin** | ✅ | ✅ strip 后 | ✅ strip 后 | ✅ strip 后 | ❌ |
| **baidufin** | ✅ | ✅ strip 后 | ✅ strip 后 | ✅ strip 后 | ❌ |
| **dcfin** | ✅ | ✅ strip 后 | ✅ strip 后 | ✅ strip 后 | ❌ |
| **juchao** | ✅ | ❌ | ✅ `.SZ` 后缀 | ❌ | ✅ 知识图谱 |
| **qnainfo** | ✅ **必须** | ❌ | ❌ | ❌ | ❌ |

说明：
- **thsfin/baidufin/dcfin** 内部 `re.sub(r'[^0-9]', '', query)` 把所有非数字字符扔掉，任何带字母的格式最终都变回纯数字
- **sinafin** 有独立的 `_resolve_code()`，识别 `sz300750`（小写前缀）和 `300750.SZ`（点后缀），但**不认大写 `SZ300750`**
- **juchao** 支持点后缀 `300750.SZ` 和 `SH600519` 格式，额外支持通过知识图谱解析中文股票名
- **qnainfo** 最严格，只接受 `re.match(r'^\d{6}$')` 的纯 6 位数字

---

## API 参考

### `POST /search`

发起搜索。

**请求参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `query` | str | **必填** | 股票代码（如 `"000001"`） |
| `engine` | str | `"ddg"` | `"ddg"` / `"sinafin"` / `"baidufin"` / `"thsfin"` / `"dcfin"` / `"juchao"` / `"qnainfo"` |
| `mode` | str | `"full"` | `"preview"` / `"full"` / `"list"` |
| `max_results` | int | 10 | 最大返回条数 |
| `filter_days` | int | - | 按天过滤，如 `3` 表示返回最近 3 天 |
| `filter_title` | str | - | 标题关键词/正则过滤 |
| `start_date` | str | - | 起始日期 `YYYY-MM-DD` |
| `end_date` | str | - | 截止日期 `YYYY-MM-DD` |

**引擎详细说明：**

| 引擎 | 数据源 | 正文方式 | 代理 |
|------|--------|----------|:----:|
| `sinafin` | httpx 直抓新浪财经（资讯+公告） | **按需加载**（/article 触发，1.8s 节流） | ❌ 直连 |
| `baidufin` | Playwright + 百度股市通 | 后台线程自动提取 | ❌ 直连 |
| `thsfin` | Playwright + 同花顺 F10 | 后台线程自动提取 | ❌ 直连 |
| `dcfin` | Playwright 东方财富股吧 | 后台线程自动提取 | ❌ 直连 |
| `juchao` | akshare 巨潮资讯 | 后台线程自动提取 PDF | ❌ 直连 |
| `qnainfo` | akshare 互动易 | 随 search 返回 | ❌ 直连 |
| `ddg` | DuckDuckGo | 随 search 返回 | ✅ 走 Clash |

### `POST /article`

获取文章正文（仅 list 模式）。

**请求参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `session_id` | str | - | session_id |
| `article_ids` | list[str] | - | 文章 ID 列表，如 `["a_01", "a_03"]` |
| `close` | bool | false | 设为 `true` 时本次返回后关闭 session |

**不同引擎的 /article 行为：**

| 引擎 | 首次调用 | 后续调用 |
|------|----------|----------|
| sinafin | 按需加载（httpx，每篇间隔 1.8s） | 缓存命中，秒回 |
| baidufin/thsfin/dcfin/juchao | 后台线程可能已就绪，秒回 | 缓存命中，秒回 |

**status 含义：**

| status | 说明 |
|--------|------|
| `ready` | 正文已就绪 |
| `error` | 所有提取方式均失败，`fetch_error` 含原因 |
| `processing` | 其他 worker 正在提取中，稍后重试 |

### `POST /extract`

手动提交需要提取正文的文章 ID 列表（仅 list 模式）。
主要用于非 sinafin 引擎的按需提取，sinafin 的 `/article` 已自带按需加载。

```bash
curl -X POST http://localhost:8300/extract \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s_...","article_ids":["a_01","a_03"]}'
```

---

## 常见问题

**Q: /article 调用后等待时间较长？**  
A: sinafin 每篇文章的 HTTP 请求之间有 1.8s 全局间隔（所有 worker 共享），
N 篇文章的首次 `/article` 耗时约 `N × 1.8s + 提取时间`。这是为了防止触发新浪的反爬。
后续调用直接读缓存，秒回。

**Q: 出现 ConnectionResetError(104)？**  
A: search_engine 所有非 DDG 后端（sinafin/thsfin/baidufin/juchao/qnainfo）均**直连国内金融站点**，
不走 Clash 代理。DDG 的代理通过参数传递，不设全局环境变量。
如果在高并发下仍遇到该错误，sinafin 有自动重试机制（最多 2 次，1-2s 间隔）。

**Q: /article 一直返回 processing？**  
A: 正常情况下不应出现。三路提取（httpx → readability → PDF 下载）全部失败后会返回 `error` 并带原因。
如果持续 `processing`，可能是并发争抢（其他 worker 正在提取同一篇文章），稍后重试。
若持续不解决，检查服务端日志。

**Q: 正文提取为空？**  
A: 系统自动走三路兜底：trafilatura → readability → PDF 链接下载（15s 超时）→ Playwright 渲染（60s 超时）。
全部失败返回 `error` + `fetch_error` 描述原因。

**Q: 正文截断了怎么办？**  
A: `truncated: true` 时末尾有 `[截断 全文长于8000字]` 标记。
可在 `config/config.json` 中调整 `max_body_chars`。

**Q: 调用 /article 会关闭 session 吗？**  
A: 不会（2026-08-01 起移除正文请求次数上限）。session 仅由 `close: true` 显式关闭，
或 45 分钟（list 模式从列表就绪起算）无操作自动超时。

**Q: 如何停止服务？**  
A: `fuser -k 8300/tcp`

---

## 测试

```bash
# 综合并发测试（20 随机股票 × 5 引擎，错峰正文获取）
conda run -n stock_agent python3 test_drive/test_comprehensive_v4.py
```
