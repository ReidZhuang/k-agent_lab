# bot_search API v3.0 使用说明

## 概述

bot_search API v3.0 是一个**可插拔搜索引擎的网页内容提取与分析服务**。支持三种搜索引擎（DDG 通用搜索、新浪财经个股新闻、百度股市通资讯）、三种执行模式（preview / full / list）。

### 服务架构

```
客户端 ──▶ v3.0 API (端口 8300) ──▶ search_engine (DDG / Sinafin / Baidufin)
                                        │
                                        ├─▶ DDG: DuckDuckGo 通用搜索（需代理）
                                        ├─▶ Sinafin: sinafin_artical_tool (端口 8000)
                                        │       └─▶ 新浪财经个股新闻列表
                                        └─▶ Baidufin: Playwright + Chromium
                                                └─▶ 百度股市通个股资讯
```

---

## 快速开始

### 启动服务

```bash
# 终端 1：启动 sinafin 新闻源（sinafin 引擎需要）
cd research/experiments/report_machine/sinafin_artical_tool
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8000

# 终端 2：启动 v3.0 API
cd research/experiments/web_bot_agent/version_3.0
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300
```

### 验证服务

```bash
curl http://localhost:8300/
# → {"service":"bot_search API","version":"3.0.0",
#     "modes":["preview","full","list"],"engines":["ddg","sinafin","baidufin"]}
```

---

## 参数详解

### `POST /search` — 完整参数表

| 参数 | 类型 | 默认 | ddg | sinafin | baidufin | 说明 |
|------|------|------|-----|---------|----------|------|
| `query` | str | **必填** | 搜索关键词 | 股票代码或名称 | **股票代码** | DDG: `"固态电池"`；Sinafin: `"宁德时代"`；Baidufin: `"300436"` |
| `engine` | str | `"ddg"` | ✅ 默认值 | ✅ 需显式设为 `"sinafin"` | ✅ 需显式设为 `"baidufin"` | 搜索引擎选择 |
| `mode` | str | `"full"` | ✅ | ✅ | ✅ | 执行模式：`"preview"` / `"full"` / `"list"` |
| `llm_mode` | str | `"segments"` | preview/full 有效 | preview/full 有效 | ❌ 强制 none | LLM 处理模式 |
| `max_results` | int | 5 | 返回条数 | 翻页页数 | 最大条数 | |
| `site` | str | `null` | ✅ 站内限定 | ❌ | ❌ | |
| `timelimit` | str | `null` | ✅ d/w/m/y | ❌ | ❌ | |
| `filter_days` | int | `null` | ✅ 提取正文后过滤 | ❌ | ❌ | |
| `filter_title` | str | `null` | ✅ | ✅ | ✅ | |
| `start_date` | str | `null` | ❌ | ✅ 服务端过滤 | ✅ 服务端过滤 | |
| `end_date` | str | `null` | ❌ | ✅ 服务端过滤 | ✅ 服务端过滤 | |
| `keyword` | str | `""` | ✅ | ✅ | ❌ | |

### `response.empty` 字段

| 值 | 含义 |
|----|------|
| `false` | 有结果 |
| `true` | 无结果，正常空（非错误） |
| `null` | 请求出错或尚未完成 |

客户端判断：

```python
if response.empty:
    print("没有文章（正常空结果）")
elif response.error:
    print(f"出错: {response.error}")
else:
    print(f"有 {response.preview.total} 篇")
```

---

## 三种执行模式（mode）

### mode=preview — 预览模式

工作流：
```
请求 → Phase 0 (搜索) + Phase 1 (fetch HTML + 提取正文 + 提取日期) 同步执行
     → 返回文章预览列表
     → 后台 Phase 2 (LLM 分析，仅 llm_mode≠none 时)
     → /poll 轮询 LLM 结果
```

适用场景：先看文章列表，后台自动做 LLM 分析。

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"固态电池 2026",
    "engine":"ddg",
    "mode":"preview",
    "llm_mode":"segments",
    "max_results":10,
    "filter_days":30
  }'
# → status=preview, preview.articles=[...], 后台 LLM 进行中
# → /poll 直到 status=done，取 articles/segments
```

### mode=full — 完整模式

工作流：
```
请求 → 返回 session_id（status=processing）
     → 后台线程：Phase 0 → Phase 1 → Phase 2 (LLM)
     → /poll 直到 status=done
```

适用场景：一次性全自动处理，无需用户交互。

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"宁德时代",
    "engine":"sinafin",
    "mode":"full",
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }'
# → session_id, status=processing
# → /poll/{session_id} 直到 done
```

### mode=list — 列表模式（v3.0 新增）

**engine=sinafin 时**：
```
请求 → Phase 0 (sinafin API) → 返回文章列表（含精确日期）
     → 不提取正文，等待用户选择
     → POST /extract {article_ids:[...]} 触发后台提取
     → POST /article 取单篇正文
```

**engine=ddg 时**：
```
请求 → Phase 0 (DDG 搜索) + Phase 1 (fetch HTML + 提取正文 + 提取日期) 自动执行
     → 返回文章列表（含日期、字数、snippet）
     → 正文已就绪，POST /article 立即可取（无需 /extract）
```

**engine=baidufin 时**：
```
请求 → Phase 0 (百度股市通 API, Playwright 浏览器)
     → 返回文章列表（含情绪、来源、摘要、日期）
     → 后台自动启动 Phase 1，提取全部文章正文：
            httpx + trafilatura 并行提取（20篇并行）
            ↓ 失败自动降级
            Playwright 兜底渲染提取（含空白治理）
     → 正文就绪后 status=done，POST /article 可取
```

适用场景：用户先看标题+情绪+摘要，后台自动提取全文。

```bash
# Baidufin + list：搜索 → 自动提取正文
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"300436",
    "engine":"baidufin",
    "mode":"list",
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }'
# → status=list_ready, preview.articles=[...含情绪/来源/摘要]
# → 后台自动提取，轮询到 status=done
```

---

## 两种搜索引擎（engine）

### engine=ddg（默认）

使用 DuckDuckGo 进行通用网页搜索。

**需要代理**：代理在 `search_engine/config.py` 中配置（自动检测 WSL2 网关）。

**工作流**（以 mode=list 为例）：
```
DDG 搜索 → fetch HTML → trafilatura 提取正文
        → 分层日期提取（JSON-LD / meta / URL / 正文前缀）
        → filter_days 时间过滤 → filter_title 标题过滤
        → 返回预览：{title, date, snippet, word_count, source}
        → 正文已就绪，/article 立即可取
```

**参数差异**：
- `timelimit` — DDG 搜索端的时间过滤（d/w/m/y）
- `filter_days` — 正文提取后的二次日期过滤
- `site` — 限定搜索域名
- `start_date` / `end_date` — 不生效

### engine=sinafin

通过 `sinafin_artical_tool` 服务获取新浪财经个股新闻。

**无需代理**，需要 sinafin 服务在端口 8000 运行。

**工作流**（以 mode=list 为例）：
```
sinafin API → 返回文章列表（含精确发布时间）
            → 服务端已按 start_date/end_date 过滤
            → 翻页时提前 break（节省请求）
            → 返回预览：{title, date}（无正文）
            → 用户 POST /extract 触发正文提取
            → POST /article 取单篇正文
```

**特性**：
- **精确日期**：sinafin 返回的 `date` 是新浪列表页的发布时间，无需重新提取，置信度 `high`
- **提前停翻页**：翻页时发现最新文章日期 < `start_date` 立即停止
- **服务端过滤**：`start_date` / `end_date` 在 sinafin 服务端生效

### engine=baidufin（v3.0 新增）

通过百度股市通获取个股资讯（Playwright 浏览器）。

**需要安装 Playwright**：
```bash
pip install playwright
playwright install chromium
```

**工作流**（以 mode=list 为例）：
```
百度股市通 → Playwright 浏览器渲染 → 拦截 sentiment API
           → 返回文章列表（含情绪/来源/摘要/精确日期）
           → **后台自动**提取全部文章正文：
               第1步: httpx + trafilatura 并行（20篇）
               第2步: 失败的 Playwright 兜底渲染
               第3步: 空白治理 + 截断
           → 正文就绪后 status=done
```

**返回的预览字段**比其它引擎更丰富：

| 字段 | 说明 | 示例 |
|------|------|------|
| `id` | 文章 ID | `"a_01"` |
| `title` | 标题 | `"凯莱英涨停，机构龙虎榜上出现分歧"` |
| `date` | 精确日期 | `"2026-07-21"` |
| `source` | 来源域名 | `"stock.stockstar.com"` |
| `snippet` | 摘要 | `"凯莱英今日涨停，全天换手率7.09%..."` |
| `word_count` | 字数 | `392` |
| `sentiment` | 情绪 | `"利好"` / `"中性"` / `"利空"` |
| `provider` | 来源名称 | `"证券之星"` / `"东方财富网"` / `"同花顺"` |

**特性**：
- **精确日期**：百度返回的 Unix 时间戳精确到秒
- **情绪分类**：每篇文章带利好/中性/利空标签
- **自动提取**：返回后立即后台提取全部正文，无需手动 /extract
- **双重兜底**：httpx 失败自动降级到 Playwright 渲染
- **空白治理**：模板页面自动检测+清洗大段空白

---

## 全部 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/search` | POST | 发起搜索（所有 mode/engine） |
| `/extract` | POST | 提交需要提取正文的文章 ID（仅 list + sinafin） |
| `/article` | POST | 获取单篇文章正文（仅 list 模式） |
| `/poll/{session_id}` | GET | 轮询搜索进度 |
| `/status/{session_id}` | GET | 查询会话状态（精简版） |
| `/close/{session_id}` | POST | 主动关闭会话 |
| `/segment` | POST | 获取指定段落的原文（仅 summary 模式） |
| `/point-text` | POST | 根据要点序号查找原文段落（仅 summary 模式） |

### POST /extract

提交需要提取正文的文章 ID（仅 sinafin 引擎需要，baidufin/ddg 自动提取）。

```json
{"session_id": "s_...", "article_ids": ["a_01", "a_03"]}
```

响应中 `ignored` 表示被忽略的无效 ID 数。

### POST /article

获取单篇文章正文（仅 list 模式）。

| status | 含义 |
|--------|------|
| `"processing"` | 正文尚未提取完成 |
| `"ready"` | 正文已就绪 |
| `"error"` | 提取失败（httpx + Playwright 均无法提取） |

### GET /poll/{session_id}

| status | list | preview | full |
|--------|------|---------|------|
| `processing` | — | — | Phase 1+2 后台运行 |
| `list_ready` | ✅ baidufin/sinafin 列表就绪 | — | — |
| `preview` | — | ✅ Phase 1 完成，Phase 2 后台 | — |
| `done` | ✅ 全部完成 | ✅ 全部完成 | ✅ 全部完成 |
| `error` | ✅ 出错 | ✅ 出错 | ✅ 出错 |

---

## 调用示例全集

### 场景 1：百度股市通个股资讯（推荐）

```bash
# 第 1 步：搜索 + 自动提取
SID=$(curl -s -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"002821",
    "engine":"baidufin",
    "mode":"list",
    "max_results":5,
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 第 2 步：轮询直到 done
curl -s http://localhost:8300/poll/${SID} | python3 -m json.tool

# 第 3 步：取单篇正文
curl -s -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"article_id\":\"a_01\"}"
```

### 场景 2：新浪财经个股新闻查询

```bash
# 第 1 步：搜索文章列表
SID=$(curl -s -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"宁德时代",
    "engine":"sinafin",
    "mode":"list",
    "start_date":"2026-07-20",
    "end_date":"2026-07-21"
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 第 2 步：选文章提交提取
curl -s -X POST http://localhost:8300/extract \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"article_ids\":[\"a_01\",\"a_05\"]}"

# 第 3 步：取单篇正文
curl -s -X POST http://localhost:8300/article \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SID}\",\"article_id\":\"a_01\"}"
```

### 场景 3：通用网页搜索 + 自动提取

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"固态电池 2026",
    "engine":"ddg",
    "mode":"list",
    "max_results":10,
    "timelimit":"m",
    "filter_days":30,
    "filter_title":"固态"
  }'
```

### 场景 4：百度股市通不限日期（全部资讯）

```bash
curl -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"600519",
    "engine":"baidufin",
    "mode":"list",
    "max_results":10
  }'
```

### 场景 5：搜索无结果时

```bash
curl -s -X POST http://localhost:8300/search \
  -H "Content-Type: application/json" \
  -d '{"query":"300436","engine":"baidufin","mode":"list","start_date":"2099-01-01"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); 
    print(f'empty={d[\"empty\"]}, total={d[\"preview\"][\"total\"]}')"
# → empty=true, total=0（正常空结果，非错误）
```

---

## 正文截断与空白治理

### 截断
文章正文超过 `max_body_chars`（默认 **8000** 字符）时自动截断，末尾加 `[截断 全文长于8000字]`，响应中 `truncated: true`。

### 空白治理
当正文中空白字符占比超过 50%（如同花顺 7×24 直播页等模板页面），系统自动清理：
- 压缩连续空白行
- 去除行首行尾空白
- 压缩行内连续空格
- `word_count` 始终统计治理后的非空白字符数

空白治理在所有引擎（ddg / sinafin / baidufin）的正文提取路径中均生效，包括 Playwright 兜底提取。

---

## 常见问题

**Q: baidufin 引擎返回 0 篇文章？**
A: 确认已安装 Playwright（`pip install playwright && playwright install chromium`），以及股票代码是否正确。

**Q: baidufin 搜索很慢（8~15秒）？**
A: 每次搜索需要启动 headless Chromium 浏览器，这是正常耗时。频繁查询时性能会受影响。

**Q: baidufin 需要代理吗？**
A: 不需要。百度股市通是国内服务，Playwright 直接访问。

**Q: /article 一直返回 processing？**
A: baidufin 引擎后台自动提取约需 5~15 秒，若超过 30 秒仍未就绪则可能是全部提取失败，会返回 error 状态。

**Q: 提取失败的文章会怎样？**
A: 返回 `status="error"` + `fetch_error="httpx + Playwright 均无法提取正文"`。文章依然在列表中可见（有标题/摘要/情绪），只是正文为空。

**Q: baidufin 的 sentiment/情绪标签可靠吗？**
A: 标签来自百度股市通 AI 分析，仅供参考。
