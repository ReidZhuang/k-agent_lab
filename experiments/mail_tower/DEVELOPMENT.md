# mail_tower — 开发文档

## 概述

mail_tower 是一个 **可插拔引擎的网页搜索 + 内容提取 + LLM 分析** 全链路 Pipeline 服务。
在 v3.0 基础上重构了 sinafin 正文提取流程，并修复了多项稳定性问题。

## 版本演进

| 版本 | 核心能力 |
|------|----------|
| v1.0 | DDG 搜索 → 提取正文 → LLM 分组/摘要 |
| v2.0 | 双阶段 Pipeline + 分层日期提取 + 过滤模块 |
| **v3.0** | 引擎分发（ddg/sinafin/baidufin/thsfin/dcfin）；list 模式 |
| **mail_tower** | **sinafin 按需加载 + 全局节流 + 代理清理 + 稳定性修复** |

## 架构

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ 客户端      │────▶│  api.py          │────▶│  core.py          │
│ POST /search│     │  FastAPI 入口    │     │  Pipeline 引擎    │
└─────────────┘     └──────────────────┘     └──────────────────┘
       │                     │                          │
       │              ┌──────┴──────┐           ┌───────┴────────┐
       │              │ session_    │           │ search_engine/  │
       │              │ manager.py  │           │ 统一搜索接口    │
       │              │ 会话管理     │           │ ddg / sinafin   │
       │              └──────┴──────┘           │ baidufin/thsfin │
       │                     │                  │ dcfin/juchao    │
       │              ┌──────┴──────┐           │ qnainfo         │
       │              │  sessions/  │           └───────┬────────┘
       │              │  文件持久化  │                   │
       │              └─────────────┐                   │
       │                            │            ┌──────┴──────┐
       │              ┌─────────────┴────┐       │ 直连国内站点  │
       │              │ sinafin_rate_    │       │ 不走 Clash    │
       │              │ limiter.py       │       └─────────────┘
       │              │ 跨进程节流 1.8s   │
       │              └──────────────────┘
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `api.py` | FastAPI 路由，请求/响应模型，后台线程管理，sinafin 按需加载 |
| `core.py` | 搜索、提取、Playwright 兜底、PDF 下载三路兜底链 |
| `session_manager.py` | 会话管理（线程安全 + 文件持久化），跨 worker 缓存回退 |
| `sinafin_rate_limiter.py` | 跨进程文件锁节流器，确保全局 1.8s sinafin URL 间隔 |
| `reporting/debug_log.py` | JSONL 调试日志 |

---

## 引擎正文提取方式对比

| 引擎 | search 后 | /article 行为 | 提取技术栈 |
|------|-----------|---------------|------------|
| **sinafin** | **不启动后台线程**，URL 存入 `_phase1_raw` 池子 | 按需加载（1.8s 节流） | httpx(15s) → readability → PDF(15s) |
| baidufin | 后台线程自动提取 | 读缓存，秒回 | httpx → Playwright 兜底 |
| thsfin | 后台线程自动提取 | 读缓存，秒回 | httpx → Playwright 兜底(60s) |
| dcfin | 后台线程自动提取（Playwright 全程） | 读缓存，秒回 | Playwright |
| juchao | 后台线程提取（PDF 下载） | 读缓存，秒回 | httpx → pypdf |
| qnainfo | 正文随 search 返回 | — | akshare |

---

## Sinafin 按需加载（核心架构变更）

### 设计目标

原版 v3.0 在 `/search` 返回后立即启动后台线程提取所有正文。这在并发高时大量浪费 worker 资源：
用户可能只挑 2/10 篇文章看正文，但后台却提取了全部 10 篇。

mail_tower 改为：**search worker 只返回列表，/article worker 按需加载**。

### 数据流

```
/search (mode=list, engine=sinafin)
  │
  ├─ search_engine.sinafin → 获取资讯+公告列表（含 URL）
  │
  ├─ 构建 preview（含 article_id → URL 映射）
  │
  ├─ set_preview(session_id, preview, _phase1_raw)  ← URL 存池子
  │    _phase1_raw = [{url, title, snippet}, ...]
  │
  └─ 返回 response（status=list_ready）
     ▲ worker 立即释放，不启动后台线程


/article (请求 a_01, a_02)
  │
  ├─ get_article_body() → 内存缓存未命中
  │
  ├─ for each article_id:
  │     ├─ get_article_info(session_id, article_id)  ← 从池子读 URL
  │     │
  │     ├─ wait_slot()  ← 全局节流 1.8s
  │     │     └─ fcntl.flock 文件锁，跨进程同步
  │     │
  │     ├─ re-check cache（等锁期间其他 worker 可能已取完）
  │     │
  │     └─ _fetch_single(url) → _extract_body_from_html(html)
  │           ├─ trafilatura OK → 返回
  │           ├─ readability OK → 返回
  │           └─ PDF 下载(15s) OK → 返回
  │                 全部失败 → set_article_body(fetch_error=原因)
  │
  └─ 返回结果（ready/error）
```

### 按需加载代码位置

`api.py` — `POST /article` 中 `if sess.engine == "sinafin":` 块（约 1117 行）。

---

## 全局节流器

### 文件：`sinafin_rate_limiter.py`

跨进程同步使用 `fcntl.flock` 文件锁 + 共享状态文件：

```python
# 所有 worker 对同一个文件做原子 读-判-写
fd = os.open(RATE_FILE, O_RDWR | O_CREAT)
fcntl.flock(fd, LOCK_EX)
# 读 last_access → 够间隔 → 写当前时间 → 返回
# 不够间隔 → 释放锁 → sleep → 重试
```

- 默认间隔：**1.8s**
- 文件位置：`sessions/.sinafin_rate.json`
- 每次 `/article` 的 sinafin 按需加载前调用 `wait_slot()`

---

## 三路提取兜底链

### 文件：`core.py`

`_extract_body_from_html(html)` 提取链：

```
trafilatura (markdown)
  ├─ 成功且 ≥200 字 → 返回 ✅
  └─ 失败或 <200 字
      └─ readability (html2text)
          ├─ 成功且 ≥200 字 → 返回 ✅
          └─ 失败或 <200 字
              └─ _try_extract_pdf_from_html(html, timeout=15)
                  ├─ 找到 PDF 链接 → 下载 → pypdf 提取 → 返回 ✅
                  └─ 无 PDF 或失败 → 返回空字符串 ❌
```

`_extract_with_playwright(urls)`（其他引擎兜底）：

```python
# 原版有 pass 死代码，Playwright 从未执行
# 改用 ThreadPoolExecutor(max_workers=1) + 60s 总超时
def _pw_worker(url_list):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ...

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    fut = pool.submit(_pw_worker, urls)
    return fut.result(timeout=60)  # 60s 超时兜底
```

---

## 代理清理（搜索引擎层）

### 修改的文件

| 文件 | 改动 |
|------|------|
| `search_engine/__init__.py` | 模块加载时清除 `http_proxy`/`https_proxy`/`HTTP_PROXY`/`HTTPS_PROXY` env var，设 `no_proxy=*` |
| `search_engine/backends/ddgs.py` | 不再用 `os.environ` 设全局代理，改传 `DDGS(proxy=PROXY)` 参数 |
| `search_engine/backends/sinafin.py` | `httpx.Client(trust_env=False)` + 连接池 + 重试 2 次 |

**设计原则：**
- 只有 DDG（DuckDuckGo 被墙）需要走 Clash 代理
- 所有国内金融站点（sinafin/thsfin/baidufin/juchao/qnainfo/dcfin）**直连**
- 代理通过构造函数参数传递，不污染进程级环境变量

### sinafin 连接池

```python
_HTTP_CLIENT = httpx.Client(
    follow_redirects=True,
    timeout=15,
    trust_env=False,  # 不读代理 env var
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
)
```

失败时自动重试 2 次（1-2s 间隔），应对偶发 `ConnectionResetError(104)`。

---

## 跨 worker 缓存

### 问题

Worker A（后台线程）写入正文到 session 文件 → Worker B（/article 请求）内存中 session 是旧的
→ 查不到正文 → 返回 `processing`。

### 解决

`sessions_manager.py` — `get_article_body()` 内存未命中时读文件兜底：

```python
def get_article_body(self, session_id, article_id):
    sess = self.get(session_id)       # 内存缓存
    if not sess:
        return None
    body = sess.article_bodies.get(article_id)
    if body is not None:
        return body                   # ✅ 命中
    # 内存未命中 → 读文件
    file_sess = self._load_from_file(session_id)
    if file_sess:
        body = file_sess.article_bodies.get(article_id)
        if body is not None:
            with self._lock:          # 更新缓存
                self._sessions[session_id] = file_sess
        return body
    return None
```

不修改 `get()`，不引入 `_loaded_at`/`os.path.getmtime`，避免 fork 死锁。

---

## 稳定性优化总结

| 问题 | 原因 | 修复 |
|------|------|------|
| 服务瘫痪（/search 挂死） | `get()` 加文件 mtime 检查 + `_loaded_at` 在 fork 后产生死锁 | 回退到简洁版 `get()`，`get_article_body()` 仅内存未命中时读文件 |
| ConnectionResetError(104) | ddgs.py 设全局 `http_proxy` env var，所有引擎走 Clash 代理 | 清除全局代理 env var，DDG 用参数传 proxy，其他引擎 `trust_env=False` |
| Playwright 从不执行 | `_extract_with_playwright()` 首行 `pass` 导致后续代码死代码 | 改为 `ThreadPoolExecutor` + 60s 超时，同时降低单页超时 |
| PDF 公告提取不到 | 原版 trafilatura + readability 对 PDF 页无效 | 第三路兜底：`_try_extract_pdf_from_html(html, timeout=15)` |
| session_id 碰撞 | `id(self)` 在同一 worker 中重复 | 改为 `secrets.randbelow(10**10)` + 微秒级时间戳 |

---

## 重试策略

所有后端重试使用统一的随机抖动间隔：

| 层 | 文件 | 函数 | 重试次数 | 间隔 |
|----|------|------|:--------:|:----:|
| 测试脚本 Phase 1 | `test_comprehensive_v4.py` | `search_engine()` | 3 次 | 3~5s |
| 后端 retry — thsfin | `search_engine/backends/thsfin.py` | `_run()` | 2 次 | 1~2s |
| 后端 retry — baidufin | `search_engine/backends/baidufin.py` | `_scrape()` | 2 次 | 1~2s |
| 后端 retry — juchao | `search_engine/backends/juchao.py` | `_fetch_list()` | 2 次 | 1~2s |
| 后端 retry — juchao PDF | `search_engine/backends/juchao.py` | `juchao_fetch_pdf_text()` | 3 次 | 2~3s |
| 后端 retry — sinafin | `search_engine/backends/sinafin.py` | `_fetch_page()` | 2 次 | 1~2s |

## 配置

`config/config.json`：

```json
{
  "server": {"workers": 12},
  "search": {
    "timeout_seconds": 90,
    "max_wait_seconds": 300
  },
  "extraction": {
    "max_body_chars": 8000
  },
  "session": {
    "ttl_minutes": 60,
    "list": {
      "ttl_minutes": 15,
      "max_calls": 3,
      "max_body_returns": 2
    }
  }
}
```

---

## 测试

```bash
# 综合并发测试
conda run -n stock_agent python3 test_drive/test_comprehensive_v4.py

# 输出：test_drive/results/comprehensive_v4_YYYYMMDD_HHMMSS.md
```

测试特性：
- 20 随机股票 × 5 引擎并发搜索（Phase 1），失败自动重试 3 轮（3-5s）
- 错峰正文获取，每 session 间隔 1-3s（Phase 2）
- 每请求取全部 `body_avail=有` 的文章
- 20 分钟总体超时
