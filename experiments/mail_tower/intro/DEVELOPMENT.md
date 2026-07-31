# bot_search API v3.0 开发文档

## 版本演进

| 版本 | 核心能力 |
|------|----------|
| **v1.0** | DDG 搜索 → 提取正文 → LLM 分组/摘要（纯异步） |
| **v2.0** | 双阶段 Pipeline（Phase 1 同步预览 + Phase 2 后台 LLM）；分层日期提取；过滤模块 |
| **v3.0** | **引擎分发**（ddg / sinafin / baidufin / thsfin）；**list 模式**（先列表后按需/自动提取正文）；正文截断 8000 字；sinafin/baidufin/thsfin/dcfin 精确日期跳过提取；空白字符治理；**baidufin 双重兜底提取**（httpx → Playwright）；**thsfin 同花顺 F10 公司大事**（Playwright 抓取，后台自动提取有 URL 的文章）；**PDF 公告异步后台提取**（Phase 1 跳过 → 后台 15s 超时）；**list 模式会话生命周期**（45 分钟超时 / max_body_returns=10 自动关闭 / close 信号）；**日期过滤上下界包夹**（精确到分钟，自动剔除未来日期） |

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                       v3.0 API (端口 8300)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ api.py   │  │ core.py  │  │session_manage│  │baidu_fin │ │
│  │ FastAPI  │─▶│ Pipeline │  │.py 会话管理  │  │ance.py   │ │
│  │ 路由     │  │ 引擎     │  │              │  │Playwright│ │
│  └──────────┘  └────┬─────┘  └──────────────┘  │ 兜底提取  │ │
│                     │                          └──────────┘ │
│              ┌──────┴──────┐                                 │
│              │ search_engine/                                 │
│              │ 统一搜索接口  │                                 │
│              └──────┬──────┘                                 │
│                     │                                         │
│        ┌────────────┼────────────────┐                       │
│        ▼            ▼                ▼                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐                 │
│  │ ddgs.py  │ │sinafin.py│ │ baidufin.py  │ │ thsfin.py │ │dcfin.py  │   │
│  │DDG搜索   │ │个股新闻   │ │百度股市通    │ │同花顺F10  │ │东方财富   │   │
│  │(需代理)   │ │HTTP API  │ │Playwright    │ │Playwright │ │BS4        │   │
│  └──────────┘ └────┬─────┘ └──────────────┘                 │
│                    │           │                              │
│                    ▼ HTTP      ▼ 浏览器                       │
│        ┌──────────────────┐  ┌─────────────────┐            │
│        │ sinafin_artical  │  │ 百度股市通        │            │
│        │ _tool (端口8000)  │  │ finance.baidu.com│            │
│        └──────────────────┘  └─────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

## 目录结构

```
mail_tower/
├── api.py                 # FastAPI 路由、请求/响应模型、后台线程管理
├── core.py                # Phase 0/1/2 全链路引擎、编码检测、Playwright 兜底提取
├── baidu_finance.py       # （已迁移至 search_engine/backends/baidufin.py）
├── session_manager.py     # 线程安全会话管理 + 逐篇正文存储
├── date_extractor.py      # 分层日期提取（6 层置信度 HIGH→LOW）
├── filter.py              # 文章过滤（时间范围 + 标题关键词）
├── config/
│   └── config.json        # 运行时配置
├── prompts/               # LLM Prompt 模板（grouping / summary / point_locate）
├── results/               # 测试结果输出
├── intro/
│   ├── USER_GUIDE.md      # 使用说明
│   └── DEVELOPMENT.md     # 开发文档（本文件）
└── test_v2.py             # 测试套件
```

## 核心模块详解

### 1. api.py — API 层

**职责**：FastAPI 路由定义、请求参数校验、响应序列化、后台线程管理。

**关键设计**：

```
SearchRequest (Pydantic) → 校验 → 分发到三种 mode 分支
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                mode=list     mode=preview     mode=full
                    │               │               │
         ┌──────────┼──┐            ▼               ▼
         ▼          ▼   ▼    同步 Phase 0+1   后台 Phase 0+1+2
     ddg/bai  sinafin  等   后台 Phase 2
     自动提取   /extract
```

**model_validator 自动推算 empty**：
```python
@model_validator(mode='after')
def _auto_empty(self):
    total = (self.preview or {}).get("total", 0)
    if self.status == "error":          self.empty = None
    elif total > 0:                     self.empty = False
    elif self.status not in ("processing",):  self.empty = True
    else:                               self.empty = None
```

**后台线程函数**：
| 函数 | 用途 |
|------|------|
| `_run_full_pipeline_in_thread` | full 模式：Phase 0→1→2 |
| `_run_preview_phase2_in_thread` | preview 模式：仅 Phase 2 LLM |
| `_run_list_phase1_in_thread` | list 模式：按文章 ID 提取正文（20 篇并行） |
| `_run_baidufin_phase1_in_thread` | baidufin 模式：自动提取全部正文 + Playwright 兜底 |

#### baidufin 后台提取流程 (`_run_baidufin_phase1_in_thread`)

```python
第1步: httpx + trafilatura 并行提取（phase1_fetch_and_extract，20篇并行）
  ↓
第2步: 检查失败项（body_text 为空或 < 20 非空白字符）
  ↓
第3步: Playwright 兜底渲染提取（_extract_with_playwright）
  ↓
第4步: 存入 session.article_bodies（失败的文章也存，body_text="" + fetch_error）
  ↓
第5步: set_list_done → status=done
```

### 2. core.py — Pipeline 引擎

**Phase 0 — 搜索**：
```python
raw_results = search_web(query, max_results, site, timelimit,
                          engine=engine, start_date=start_date, end_date=end_date)
```
通过 `search_engine` 统一接口调度，返回 `[{title, url, snippet, _known_date?, _baidu_*?}]`。

**编码检测**（v3.0 新增）：
```python
def _decode_html_bytes(raw: bytes, declared_encoding: str | None = None) -> str:
    """解码 HTML 字节数据，自动检测编码（GBK/GB2312/GB18030/UTF-8）。"""
    # 1. 优先使用响应头声明的编码
    # 2. 常见中文编码依次尝试
    # 3. 解码后检查乱码特征（替换字符/中文字符占比）
    # 4. 发现乱码自动换编码重试
```

**Phase 1 — 提取**：
- `_fetch_single(url)` — 下载 HTML（httpx，15s 超时，GBK 自动检测）
- `_extract_body_from_html(html)` — trafilatura 提取 + readability 兜底
- 日期提取：有 `_known_date` 直接使用（sinafin/baidufin），否则走 `date_extractor` 分层提取
- **PDF 公告 fallback**：正文为空或含"无法在线阅读"等占位标记时，扫描 HTML 中 PDF 链接 → 下载 → pypdf 提取 → 替换正文
- **空白治理**：`has_excessive_whitespace()` → 空白占比 > 50% → `clean_excessive_whitespace()`
- **正文截断**：`truncate_body(body, max_chars=8000)` → 超 8000 字截断加标记

**Phase 1.5 — Playwright 兜底**（v3.0 新增）：
```python
def _extract_with_playwright(urls: list[str]) -> dict[str, str]:
    """
    当 httpx + trafilatura 提取失败时，用 Playwright 渲染页面后重新提取。
    
    策略1: trafilatura 在渲染后的 HTML 上提取
    策略2: 查找常见正文容器（article, div.content, div.detail 等）
    策略3: 取 body 全文
    → 空白治理 → PDF fallback（仍是占位文本时）→ 返回
    """
```

**Phase 2 — LLM**：
- 将正文按 token 切 ChunkUnit
- 并行调用 Ollama（`model="glm4:9b", temperature=0`）
- `segments` 模式：分组 + 摘要；`summary` 模式：全文摘要 + 核心要点

**mode=list 分支逻辑**：
```
mode=list
  ├── engine=ddg:
  │     Phase 0 → Phase 1（skip_pdf=True，跳过 PDF 提取）
  │       ├─ 正常 HTML → 正文即时就绪，立即存储
  │       └─ PDF 公告 → 标记 _is_pdf，/article 返回 processing
  │     → filter_days 过滤（上下界包夹，精确到分钟，未来日期剔除）
  │     → 返回预览（正文已就绪，PDF 页后台异步提取中）
  │     → 后台线程 _run_ddg_pdf_extraction_in_thread（15s 超时）
  │     → PDF 提取完 → set_article_body() 覆盖
  │
  ├── engine=sinafin:  Phase 0 → 返回预览 → 等 /extract → Phase 1
  │                    日期过滤在搜索引擎层（start_date/end_date）
  │
  └── engine=baidufin: Phase 0 → 返回预览（含情绪/来源/摘要）
                        → 后台自动 Phase 1（httpx → Playwright 兜底）
                        → 全部就绪 → status=done
                        日期过滤在搜索引擎层（start_date/end_date）
```

### 3. session_manager.py — 会话管理

**状态流转**：
```
list 模式 (baidufin):
  created → list_ready (等后台提取) → done

list 模式 (sinafin):
  created → list_ready (等 /extract) → processing → done

list 模式 (ddg):
  created → done (正常 HTML 正文就绪；PDF 页后台异步提取中)

list 模式 会话生命周期（仅 list 模式）:
  调用次数: /search(1) → `max_body_returns`(10) → 第 10 次返回后自动关闭
           processing 不计入次数，close:true 可提前关闭
  超时: 从列表返回起 15 分钟未操作自动关闭

preview 模式:
  created → preview (Phase 1 完成) → done (Phase 2 完成)

full 模式:
  created → processing → done
```

**逐篇正文存储**（v3.0 新增）：
```python
session.article_bodies: dict[str, dict] = {
    "a_01": {
        "body_text": "...",      # 截断后的正文（失败则为空）
        "truncated": True/False,
        "fetch_error": "",       # 提取失败时的错误信息
        "fetched_at": 1234567890,
    }
}
```

### 4. date_extractor.py — 分层日期提取

6 层置信度体系（对 baidufin 引擎，直接使用 API 返回的 `_known_date`，跳过此流程）：

| 层 | 置信度 | 来源 |
|----|--------|------|
| 1 | HIGH | JSON-LD script → `datePublished` |
| 2 | HIGH | `<meta property="article:published_time">` |
| 3 | HIGH | `<time datetime="...">` |
| 4 | HIGH | URL 路径含 `YYYY/MM/DD` |
| 5 | MEDIUM | 正文前缀 "发布时间：YYYY-MM-DD" |
| 6 | LOW | 正文前 200 字首次出现的日期 |

`sinafin` / `baidufin` 引擎跳过此流程，直接使用 API 返回的精确日期。

### 5. filter.py — 文章过滤

```python
ArticleFilter.apply(articles, days=7, title_pattern="固态")
```

- `days` — 时间过滤（基于 `date` 字段，无日期文章保留）
  - **上下界包夹**：`cutoff <= date <= now`，未来日期自动剔除
  - **分钟精度**：如日期字段含 `HH:MM`，精确到分钟比较；仅日期则按天比较
  - **统计打点**：过滤日志输出无日期（保留）和未来日期（丢弃）的数量
- `title_pattern` — 标题关键词匹配（支持正则）

## PDF 公告自动提取

### 提取模式（两种策略）

**同步提取**（DDG list 以外的模式 / Playwright 兜底）：
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

### 核心函数
1. `_find_pdf_urls_in_html(html)` — 扫描 HTML 提取 PDF 链接
2. `_extract_pdf_from_url(url, timeout)` — 下载 + pypdf 提取（时长受 timeout 限制）
3. `_try_extract_pdf_from_html(html, timeout)` — 编排：找链接 → 逐个下载 → 取最长文本
4. `extract_pdf_from_article(article, timeout)` — 公开函数，供后台线程使用
5. `_run_ddg_pdf_extraction_in_thread()` — DDG list 模式后台线程入口

### PDF 链接发现
`_find_pdf_urls_in_html()` 支持多种链接格式：
- `<a href="...pdf">` — 锚链接
- `<iframe src="...pdf">` / `<embed src="...pdf">` — 嵌入式 PDF
- JavaScript 变量：`pdfsource = '...'`、`otherSource = '...'`
- 自动补全 `//`（协议相对）和 `/`（根相对）URL

### URL 编码处理
PDF 文件名常包含中文字符（如`博瑞医药：关于...公告.pdf`），直接传给 `requests` 会导致 latin-1 header 编码异常。`_extract_pdf_from_url()` 自动对路径中的非 ASCII 字符做百分号编码。

### 集成路径
| 路径 | 触发位置 | 模式 |
|------|----------|------|
| DDG list Phase 1（`phase1_fetch_and_extract`） | `skip_pdf=True`，跳过 PDF，仅标记 `_is_pdf` | 异步后台 |
| DDG list 后台线程（`_run_ddg_pdf_extraction_in_thread`） | 调用 `extract_pdf_from_article(art, timeout=15)` | 异步（15s 超时） |
| 非 list 模式（`phase1_fetch_and_extract`） | `skip_pdf=False`，trafilatura 提取 + 空白治理后 | 同步 |
| Playwright 兜底（`_extract_with_playwright`） | 渲染提取 + 空白治理后 | 同步 |

## 正文空白治理

**检测函数** `has_excessive_whitespace(text)`：
```python
WHITESPACE_RATIO_THRESHOLD = 0.5  # 空白占比 > 50% 即判定为过量
ratio = ws_count / total_chars
return ratio > 0.5
```

**清理函数** `clean_excessive_whitespace(text)`：
1. 按行 `strip()` → 跳过空行 → 压缩行内连续空格
2. 段落间保留一个空行
3. 如清理后内容不足原文 5%，取可见字符前 500 字并标注

**位置**：trafilatura 提取正文后、其他处理前，在以下路径均生效：
- `phase1_fetch_and_extract()` — httpx + trafilatura 提取路径
- `_extract_with_playwright()` — Playwright 兜底提取路径

## 搜索引擎扩展

### Baidufin 引擎

`search_engine/backends/baidufin.py` 实现了百度股市通个股资讯抓取：

**技术方案**：
- 使用 Playwright headless Chromium 渲染页面
- 拦截百度内部 API `finance.pae.baidu.com/vapi/sentimentlist` 获取结构化数据
- 在独立线程中执行（兼容 asyncio 调用方）

**返回字段**（search_engine 统一接口的扩展）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | str | 文章标题 |
| `url` | str | 原文链接 |
| `snippet` | str | 新闻摘要 |
| `_known_date` | str | 精确发布日期 |
| `_baidu_sentiment` | str | 情绪：利好/中性/利空 |
| `_baidu_provider` | str | 来源名称 |
| `_baidu_abstract` | str | 完整摘要 |
| `_baidu_ts` | int | Unix 时间戳 |

**日期过滤**：
- 支持 `start_date` / `end_date` 参数
- 在 API 响应拦截时直接按 `publishTime` 过滤（不走爬虫端）
- 去重：按 `news_id` 去重

## 配置说明

### config/config.json

```json
{
  "search": {
    "sinafin": { "endpoint": "http://localhost:8000" }
  },
  "extraction": {
    "max_body_chars": 8000
  },
  "ollama": {
    "endpoint": "http://localhost:11434",
    "models": { "default": "glm4:9b-chat-q3_K_S" },
    "max_parallel": 4,
    "temperature": 0
  },
  "session": { "ttl_minutes": 60 }
}
```

baidufin 引擎无需额外配置。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SNAFIN_ENDPOINT` | `http://localhost:8000` | sinafin 服务地址 |
| `SEARCH_PROXY` | 自动检测 | DDG 搜索代理 |

## 测试

```bash
# 语法检查
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['api.py','core.py','session_manager.py']]; print('OK')"

# 运行单元测试
conda run -n stock_agent python3 test_v2.py

# 手动端到端测试（baidufin）
conda run -n stock_agent python3 -c "
import asyncio
from core import run_search_pipeline
async def test():
    r = await run_search_pipeline('300436', engine='baidufin', mode='list', max_results=3)
    print(f'Total: {r[\"total\"]}')
    for a in r['articles']:
        print(f'  {a[\"title\"][:50]} | {a[\"sentiment\"]} | {a[\"provider\"]}')
asyncio.run(test())
"
```

## Baidufin 双重提取机制

```
请求 → run_search_pipeline (Phase 0)
  │
  ├─▶ list_ready 返回给用户（含情绪/来源/摘要）
  │
  └─▶ 后台线程 _run_baidufin_phase1_in_thread()
        │
        ├─▶ 第1层: httpx + trafilatura
        │      _fetch_single() + _extract_body_from_html()
        │      ├ 支持 GBK/GB2312/UTF-8 自动检测
        │      ├ 空白字符治理（>50% 触发）
        │      └ 正文截断 8000 字
        │
        └─▶ 第2层: Playwright 兜底（第1层失败时）
               _extract_with_playwright()
               ├ 浏览器渲染 JavaScript 页面
               ├ trafilatura 提取（渲染后 HTML）
               ├ 选择器兜底（article / div.content / body）
               └ 空白字符治理 + 截断
```
