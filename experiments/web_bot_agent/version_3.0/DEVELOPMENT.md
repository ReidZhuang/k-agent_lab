# bot_search API v3.0 — 开发文档

## 概述

bot_search API v3.0 是一个 **可插拔引擎的网页搜索 + 内容提取 + LLM 分析** 全链路 Pipeline 服务。
在 v2.0 基础上新增了 **sinafin 引擎**、**list 模式**和 **按需提取正文** 能力。

## 版本演进

| 版本 | 核心能力 |
|------|----------|
| v1.0 | DDG 搜索 → 提取正文 → LLM 分组/摘要（全异步） |
| v2.0 | 双阶段 Pipeline（Phase 1 同步预览 + Phase 2 后台 LLM）；分层日期提取；过滤模块 |
| **v3.0** | **引擎分发（ddg / sinafin / baidufin / thsfin / dcfin）；list 模式（先列表后按需提取）；正文截断8000字；精确日期；空白字符治理；Playwright 兜底渲染；PDF 公告异步后台提取（Phase 1 跳过 → 后台 15s 超时）；thsfin 同花顺 F10 公司大事（Playwright 抓取，后台自动提取有 URL 的文章）；dcfin 东方财富股吧（Playwright 驱动 + 人类行为模拟，热门/资讯/公告三分类，精确到分钟日期）；sinafin 合并 sinafin_artical_tool（httpx 直抓新浪，资讯+公告双分类，资讯精确到分钟）；；list 模式会话生命周期（15 分钟超时 / 3 次调用关闭 / close 信号）；日期过滤上下界包夹（精确到分钟，自动剔除未来日期）** |

## 架构

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ 客户端      │────▶│  api.py          │────▶│  core.py          │
│ POST /search│     │  FastAPI 入口    │     │  Pipeline 引擎    │
└─────────────┘     └──────────────────┘     └──────────────────┘
                           │                          │
                    ┌──────┴──────┐           ┌───────┴────────┐
                    │ session_    │           │ search_engine/  │
                    │ manager.py  │           │ 统一搜索接口    │
                    │ 会话管理    │           │ ddg / sinafin   │
                    └─────────────┘           └───────┬────────┘
                                                      │
                                             ┌────────┴────────┐
                                             │ sinafin_backend  │
                                             │ → sinafin_artical│
                                             │   _tool API      │
                                             └─────────────────┘
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `api.py` | FastAPI 路由，请求/响应模型，后台线程管理 |
| `core.py` | Phase 0（搜索）、Phase 1（fetch+提取）、Phase 2（LLM）全链路 |
| `session_manager.py` | 会话状态管理（线程安全），逐篇正文存储 |
| `date_extractor.py` | 分层日期提取（6层置信度 HIGH→LOW） |
| `filter.py` | 文章过滤：时间范围（上下界包夹，精确到分钟，自动剔除未来日期）+ 标题关键词/正则 |

### 依赖的外部服务

| 服务 | 用途 | 配置 |
|------|------|------|
| Ollama（端口 11434） | LLM 推理（分组/摘要） | `config.ollama` |
| DuckDuckGo（通过 ddgs 库） | DDG 引擎的搜索源 | `search_engine/config.py` 代理设置 |
| Playwright + Chromium | baidufin 引擎 + 兜底渲染 + PDF 公告提取 | 需手动安装 |

## 三种 Mode

### `mode=full`
- **异步**：API 立即返回 session_id
- **流程**：后台线程 Phase 0 → Phase 1 → Phase 2（LLM）
- **结果**：通过 `/poll` 轮询获取完整 LLM 分析结果

### `mode=preview`
- **半同步**：API 等待 Phase 1 完成后返回文章预览
- **流程**：API 线程 Phase 0 → Phase 1（同步）→ 返回预览，后台 Phase 2（LLM）
- **结果**：先拿文章列表，后 `/poll` 拿 LLM 结果

### `mode=list`（v3.0 新增）
- **同步 + 按需**：API 立即返回文章列表，不等待 PDF 提取
- **流程**：API 线程 Phase 0 → Phase 1（同步，跳过 PDF）→ 返回列表；PDF 后台异步提取（15s 超时）；/article 按需取正文
- **结果**：通过 `/article` 按需取单篇正文；PDF 公告页 body 在后台加载完成后就绪
- **会话生命周期**：从返回列表起 15 分钟超时；累计 3 次 /article 调用（ready/error 才计数）后自动关闭；支持 close 信号提前关闭
- **流程**：API 线程 Phase 0（同步）→ 返回列表；用户通过 `/extract` 提交需要正文的文章
- **结果**：通过 `/article` 按需取单篇正文
- **适用场景**：用户先浏览标题和日期，挑出感兴趣的文章再提取

## LLM Mode

| `llm_mode` | 说明 |
|------------|------|
| `segments` | 分段分组 + 每组摘要（默认） |
| `summary` | 全文摘要 + 核心要点 |
| `none` | 不做 LLM 处理（仅 list 模式适用） |

## Engine

| `engine` | 搜索后端 | 数据来源 |
|----------|----------|----------|
| `ddg`（默认） | DuckDuckGo | 通用网页搜索 |
| `sinafin` | httpx 直抓新浪财经 | 新浪财经个股新闻（资讯+公告双分类，含精确到分钟日期） |
| `baidufin` | Playwright + 百度股市通 | 百度个股资讯（含情绪/来源） |
| `thsfin` | Playwright + 同花顺 F10 | 同花顺个股公司大事（含日期/类型/详情/URL） |
| `dcfin` | Playwright 驱动 | 东方财富股吧（热门/资讯/公告三分类，含精确到分钟日期，人类行为模拟） |

### Sinafin 引擎特性

- **精确日期**：sinafin 返回的文章携带已发布的精确日期（`_known_date`），Phase 1 跳过日期提取，直接使用，置信度为 `high`
- **服务端过滤**：`start_date` / `end_date` 透传给 sinafin API，服务端翻页时提前 break
- **预过滤**：v3.0 侧对 sinafin 结果做标题关键词预过滤（`filter_title`）

## 数据流详解

### list + none + sinafin 流程

```
客户端                           v3.0 API                         sinafin_artical_tool
  │                                │                                    │
  │  POST /search                  │                                    │
  │  {mode:list, engine:sinafin,   │                                    │
  │   query:宁德时代}               │                                    │
  │───────────────────────────────▶│                                    │
  │                                │  GET /news?name=宁德时代&format=json│
  │                                │───────────────────────────────────▶│
  │                                │◀───────────────────────────────────│
  │                                │        JSON {news: [{title,url,date}]}
  │  ◀────────────────────────────│                                    │
  │  {status:list_ready,           │                                    │
  │   preview:{articles:[...]}}    │                                    │
  │  ▲ Phase 0 完成，不启动后台     │                                    │
  │  ║                            │                                    │
  │  ║ 用户选择 a_01, a_03        │                                    │
  │  ║                            │                                    │
  │  POST /extract                │                                    │
  │  {article_ids:[a_01, a_03]}   │                                    │
  │───────────────────────────────▶│                                    │
  │  ◀────────────────────────────│                                    │
  │  {status:processing,          │                                    │
  │   requested:2}                │                                    │
  │  ║                            │  后台线程启动（并行20篇）            │
  │  ║                            │  fetch HTML → trafilatura 提取正文  │
  │  ║                            │  → truncate_body(8000) 逐篇存储      │
  │  ║                            │                                    │
  │  POST /article                │                                    │
  │  {article_id:a_01}            │                                    │
  │───────────────────────────────▶│                                    │
  │  ◀────────────────────────────│                                    │
  │  {status:ready,               │                                    │
  │   body_text:"...",            │                                    │
  │   truncated:false}            │                                    │
```

## 状态流转

### list 模式

DDG 引擎（正常 HTML 文章即时就绪，PDF 公告异步后台提取）：
```
/search (call_count=1)
   │
   ├─▶ Phase 1 同步（跳过 PDF）
   │     ├─ 正常 HTML → body 即时可用 → /article: ready
   │     └─ PDF 公告 → 标记 _is_pdf → /article: processing
   │
   ├─▶ 返回列表（status=done）
   │
   └─▶ 后台线程（PDF 异步提取，15s 超时）
         └─ 提取完成 → set_article_body() → /article: ready
```

Sinafin 引擎（手动 /extract 触发正文提取）：
```
/search → status=list_ready → /extract → processing → done
  │                               │
  └─ 无正文，等 /extract           └─ 后台提取，完成后 /article 可取
```

Session 生命周期（仅 list 模式）：
```
调用次数: search(1) → /article × 2(3) → 第 3 次返回后自动关闭
  /article 中 processing 不计入次数（不消耗配额）
  /article 请求中 close:true 可提前关闭
超时: 从列表返回起 15 分钟未操作自动关闭
```

### preview / full 模式

```
   created          Phase 1 完成         Phase 2 完成
processing ──────▶ preview ───────────▶ done
                     │                    │
                     │ /poll preview      │ /poll 完整结果
```

## 正文截断

当文章正文超过 `max_body_chars`（默认 8000 字符）时，v3.0 会在 `/article` 返回的 `body_text` 中截断，并在末尾追加标记：

```
...[正文内容前8000字]
[截断 全文长于8000字]
```

返回字段 `truncated: true` 表示正文被截断。
截断仅在 **list 模式**下生效，preview/full 模式保留全文供 LLM 使用。

## PDF 公告自动提取

### 提取模式（两种策略）

系统对 PDF 公告页有两种处理策略：

**同步提取**（非 DDG list 模式）：
```
Normal article text → trafilatura → 空白治理 → 返回
PDF placeholder    → _try_extract_pdf_from_html() 同步提取 → 返回
```

**异步后台提取**（DDG list 模式 — default）：
```
Phase 1（同步，快）         后台线程（异步，15s 超时）
  trafilatura 提取              │
    ↓                           ├─ 扫描 HTML 找 PDF URL
  _is_pdf_announcement_page()   ├─ requests.download(pdf)
    ↓ True                      ├─ pypdf.PdfReader.extract()
  标记 _is_pdf → 跳过 PDF       ├─ 空白治理 + 截断
    ↓                           └─ set_article_body() → 覆盖占位正文
  返回列表（不等待 PDF）
```

### 触发条件
正文提取完成后，如果满足以下任一条件，自动触发 PDF 回退提取：
- 正文为空或少于 50 个字符
- 正文包含关键词：`无法在线阅读`、`下载原文`、`请下载原文` 等

### 提取流程（核心函数）
1. **扫描 HTML** — `_find_pdf_urls_in_html()` 从 `<a href>`、`<iframe>`、JavaScript 变量（`pdfsource`/`otherSource`）等位置提取 PDF 下载链接
2. **下载 PDF** — `_extract_pdf_from_url()` 使用 `requests` 下载，自动 URL 编码中文字符（解决 latin-1 header 限制），15s 超时
3. **文字提取** — 使用 `pypdf`（PdfReader）逐页提取并拼接
4. **后处理** — 与正文一致：空白治理 + 截断

### 集成位置
- `phase1_fetch_and_extract(skip_pdf=True)` — DDG list 模式，跳过 PDF 提取，仅标记
- `phase1_fetch_and_extract(skip_pdf=False)` — 其他模式，同步提取 PDF
- `_extract_with_playwright()` — Playwright 渲染后仍无正文时，httpx 取原始 HTML → PDF 提取
- 公开函数 `extract_pdf_from_article()` — 供 api.py 后台线程调用（DDG list 模式）
- 后台线程 `_run_ddg_pdf_extraction_in_thread()` — 异步处理，15s 超时，逐篇提取

## 配置

`config/config.json`：

```json
{
  "search": {
    "sinafin": {
      "endpoint": "http://localhost:8000"
    }
  },
  "extraction": {
    "max_body_chars": 8000
  },
  "session": {
    "ttl_minutes": 60,
    "list": {
      "ttl_minutes": 15,
      "max_calls": 3
    }
  }
}
```

| 配置项 | 默认 | 说明 |
|--------|------|------|
| `session.ttl_minutes` | 60 | 非 list 模式会话超时（分钟） |
| `session.list.ttl_minutes` | 15 | list 模式会话超时（从列表返回起算） |
| `session.list.max_calls` | 3 | list 模式最大 /article 调用次数（含 search） |

环境变量覆盖：
- `SNAFIN_ENDPOINT` — 覆盖 `http://localhost:8000`
- `SEARCH_PROXY` — 覆盖 DDG 搜索代理地址

## 测试

运行测试套件：

```bash
cd version_3.0
conda run -n stock_agent python3 test_v2.py
```

手动测试流程（需启动 sinafin 服务）：

```bash
# 启动 sinafin
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8000

# 启动 v3.0
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300

# list + none + sinafin 测试
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"宁德时代","engine":"sinafin","mode":"list","start_date":"2026-07-20","end_date":"2026-07-21"}'

# 提取指定文章
curl -X POST http://localhost:8300/extract \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s_...","article_ids":["a_01","a_03"]}'

# 取单篇正文
curl -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s_...","article_id":"a_01"}'
```
