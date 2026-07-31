# v3.0 API 使用手册

> 版本: 3.0.0  
> 更新: 2026-07-23  
> 架构: 12 workers, 16 并发槽位, 90s 超时

---

## 一、快速开始

```bash
# 启动服务
cd /home/stockagent/project_space/research/experiments/web_bot_agent/version_3.0
./start.sh

# 自定义 worker 数
WORKERS=4 ./start.sh

# 跳过代理检查
PROXY_SKIP=1 ./start.sh
```

---

## 二、搜索 (/search)

### 2.1 请求格式

```json
POST /search
{
    "query": "600985",              // 股票代码 或 名称（juchao 支持名称）
    "engine": "sinafin",            // 见引擎列表
    "mode": "list",                 // 固定 "list"
    "max_results": 10,
    "filter_days": 5,               // 可选：近 N 天
    "start_date": "2026-07-20",     // 可选：起始日期
    "end_date": "2026-07-22"        // 可选：截止日期
}
```

### 2.2 引擎列表

| 引擎 | query 格式 | 分类字段 | 特有字段 | 说明 |
|:-----|:----------|:---------|:---------|:-----|
| `sinafin` | 6 位代码 | `_category`: 资讯/公告 | — | 新浪财经个股新闻+公告 |
| `baidufin` | 6 位代码 | `_category`: 资讯 | `sentiment`: 利好/利空/中性 | 百度股市通 |
| `juchao` | **名称** 或 6 位代码 | `_category`: 公告 | `_announce_id`, `_announce_time` | 巨潮盘后PDF公告 |
| `thsfin` | 6 位代码 | `_category`: 从标题提取 | — | 同花顺F10公司大事 |
| `qnainfo` | **6 位代码** | `_category`: 互动易问答 | `_question`, `_answerer`, `_answer`, `_ask_time`, `_update_time` | 巨潮互动易问答 — **首次调用即返回完整问答内容（含 body_text），无列表/正文分离，无需 /article** |

### 2.3 响应字段

```json
{
    "session_id": "s_20260723_123456_xxxxx",
    "status": "list_ready",        // 见状态说明
    "engine": "sinafin",
    "preview": {
        "articles": [
            {
                "id": "a_01",
                "title": "公告标题",
                "body_avail": "有",       // "有"=有URL/PDF可提取，"无"=无正文来源
                "date": "2026-07-23",
                "date_source": "sinafin",
                "date_confidence": "high",
                "snippet": "摘要内容",
                "_category": "资讯",       // 引擎相关的分类
                "sentiment": "利好",       // baidufin 特有
                "body_status": "processing"  // processing | ready | error
            }
        ],
        "total": 10,
        "total_raw": 20,
        "filter_stats": {
            "raw_count": 20,
            "filtered_count": 10,
            "dropped_count": 10,
            "filter_days": 5
        }
    },
    "elapsed": 1.2
}
```

### 2.4 状态流转

```
请求 → status: "list_ready"     ← 列表返回，正文后台提取中
        后台提取完成 → /poll 返回 "done"
        报错 → status: "error"，session 自动关闭

qnainfo 特殊: status 为 "done"（首次调用即返回完整问答内容，无等待）
```

### 2.5 各引擎正文提取方式

| 引擎 | 提取方式 | 提取时机 |
|:-----|:---------|:---------|
| **sinafin** | httpx → trafilatura | 后台线程自动 |
| **baidufin** | httpx → trafilatura → Playwright 兜底 | 后台线程自动 |
| **juchao** | 下载PDF → pypdf 提取文字 | 后台线程自动 |
| **thsfin** | httpx → trafilatura → Playwright 兜底 | 后台线程自动 |
| **qnainfo** | 无需提取，问答内容已在 API 返回中直接包含 | `/search` 返回时即就绪，无需 `/article` |

### 2.6 thsfin 标题拆分

thsfin 的原始标题格式为 `类型：详情内容`，返回时自动拆分为：

```
原始: "融资融券： 详情>> 融资余额182.2亿元..."
返回: _category: "融资融券"
      title: "详情>> 融资余额182.2亿元..."
```

常见分类值：`融资融券`、`大宗交易`、`发布公告`、`股东人数变化`、`投资互动`、`异动提醒`、`监管问询`

### 2.7 关于正文提取

**thsfin** 的部分文章类型无法提取正文：

| 类型 | 原因 |
|:-----|:-----|
| 融资融券 / 股东人数变化 / 投资互动 / 监管问询 | 无外部链接，信息卡片 |
| 发布公告（news.10jqka.com.cn） | 同花顺页面仅显示"请下载原文" |
| 异动提醒（iwencai.com） | SPA 页面，需浏览器渲染 |

这些文章的 `body_avail` 会标记为 `"无"`，`body_status` 保持 `"processing"`。

---

## 三、取正文 (/article)

### 3.1 请求格式

```json
POST /article
{
    "session_id": "s_20260723_123456_xxxxx",
    "article_ids": ["a_01", "a_02", "a_03"]
}
```

### 3.2 响应示例

```json
{
    "session_id": "s_20260723_123456_xxxxx",
    "articles": [
        {
            "article_id": "a_01",
            "status": "ready",           // ✅ 正文就绪
            "title": "公告标题",
            "date": "2026-07-23",
            "body_text": "证券代码：600985 ...",
            "truncated": false
        },
        {
            "article_id": "a_02",
            "status": "error",           // ❌ 永久失败（勿重试）  
            "title": "公告标题",
            "date": "2026-07-23",
            "fetch_error": "PDF 下载失败"
        },
        {
            "article_id": "a_03",
            "status": "processing"       // ⏳ 还在提取，稍后重试
        }
    ],
    "session_closed": false
}
```

### 3.3 返回规则

`/article` 采用**全或无**策略：

- **有任意一篇是 `processing`** → 全部返回 `processing`，**不消耗请求次数**
- **全部就绪（ready/error）** → 正常返回，每篇独立状态

### 3.4 各状态说明

| status | 返回值 | 含义 | 建议操作 |
|:-------|:-------|:-----|:---------|
| `processing` | `body_text=""` | 后台还在提取 | 几秒后重试同一组 ID（不计次） |
| `ready` | `body_text=全文` | 正文就绪 | 直接使用 |
| `error` | `body_text=""` | 该篇正文永久失败 | **不要再请求这个 ID**，换其他文章 ID 请求 |
| | `fetch_error=原因` | | |

> `error` 状态的正文不会恢复，重复请求同一篇 ID 永远返回 error。
> 无需重新做 `/search`，换其他文章 ID 即可。

**注意**：error 状态的正文不会恢复，重复请求同一篇 ID 永远返回 error。无需重新做 `/search`，换其他文章 ID 即可。

### 3.4 请求次数限制

- 每个 session 最多 **2 次** `/article` 请求（无论每次请求多少篇）
- 仅 `status=ready` 的返回**消耗次数**，全部 `processing`/`error` 不计次
- 第 2 次消耗后 session 自动关闭

---

## 四、错误处理

### 4.1 HTTP 状态码

| 状态码 | 含义 | 用户操作 |
|:------|:-----|:---------|
| `200` | 请求成功 | — |
| `500` | 引擎内部错误 | **重新发送请求**（旧 session 已自动关闭） |
| `504` | 搜索超时（>90s） | **重新发送请求**（旧 session 已自动关闭） |
| `503` | 服务繁忙，所有槽位满 | 等待后重试 |
| `404` | Session 不存在或已过期 | 重新做 `/search` |

### 4.2 Session 报错后

```
/search 返回 500/504
    ↓
session 立即关闭（close_on_error）
    ↓
旧 session 不可用，也无法恢复
    ↓
用户操作: 直接重新发起 /search
```

### 4.3 /article 报错

```
/article 返回某篇 status=error
    ↓
仅该篇正文不可用
    ↓
不影响其他文章 ID
    ↓
用户操作: 跳过该 ID，换其他 ID 请求
```

### 4.4 完整错误代码表

| 错误代码 | 级别 | HTTP | 含义 |
|:---------|:----:|:----:|:-----|
| `WORKER_BUSY` | WARNING | 503 | 服务繁忙，排队超时 |
| `ENGINE_TIMEOUT` | ERROR | 504 | 搜索超过 90s |
| `ENGINE_ERROR` | ERROR | 500 | 引擎异常 |
| `ENGINE_EMPTY` | WARNING | 200 | 搜索 0 条结果 |
| `ENGINE_ANTI_CRAWL` | WARNING | 200 | 触发反爬（如 dcfin） |
| `ENGINE_NAME_RESOLVE` | WARNING | 500 | 股票代码解析失败 |
| `PDF_DOWNLOAD_FAIL` | ERROR | — | 后台 PDF 下载失败 |
| `BODY_EXTRACT_FAIL` | WARNING | — | 后台正文提取失败 |
| `SESSION_NOT_FOUND` | WARNING | 404 | Session 不存在或已过期 |

所有错误自动记录到 `/home/stockagent/project_space/database/report_market.db` 的 `error_log` 表。
每个请求的完整步骤链记录在 `service_log_v3` 表（含步骤耗时和 worker ID）。

**排查流程**: `error_log` 发现错误 → `service_log_v3` 查同一 `session_id` 的步骤链 → 定位问题环节。

---

## 五、配置说明

### config.json

```json
{
  "search": {
    "timeout_seconds": 90,          // 搜索超时
    "max_results": 5
"max_wait_seconds": 300,        // 排队超时（槽位满时等待时间，超时返回 503）
  },
  "extraction": {
    "timeout": 15,
    "max_body_chars": 8000          // 正文截断字数
  },
  "session": {
    "ttl_minutes": 60,              // 普通 session 超时
    "list": {
      "ttl_minutes": 45,            // list 模式 session 超时
      "max_calls": 20,
      "max_body_returns": 2         // /article 最大调用次数
    }
  }
}
```

### 配置说明

```json
"server": {
    "workers": 12            // uvicorn worker 进程数
}
```

Worker 数在 `config.json` 中配置，无需在启动时输入。`start.sh` 会自动读取。

### 并发控制

```
12 workers × 每个 16 槽位
最大排队请求: 由 OS socket backlog 决定
排队超时: 300s（超过返回 503，可配 search.max_wait_seconds）
搜索超时: 90s（超过返回 504，可配 search.timeout_seconds）
```

---

## 六、时间过滤

两种方式，可同时使用：

### 相对天数（推荐）

```
filter_days=5
→ 保留近 5 天的文章（today - 5d ≤ date ≤ now）
```

### 绝对日期

```
start_date="2026-07-20"
end_date="2026-07-22"
→ 保留该日期范围内的文章
```

### 引擎对 filter_days 的支持

| 引擎 | filter_days | start_date / end_date |
|:-----|:-----------:|:--------------------:|
| sinafin | ✅ 后端过滤 | ✅ 传给后端 |
| baidufin | ✅ 后端过滤 | ✅ 传给后端 |
| juchao | ✅ 后端过滤 | ✅ akshare 层过滤 |
| thsfin | ✅ 后端过滤 | ✅ 传给后端 |
| dcfin | ✅ 后端过滤 | ✅ 传给后端 |
| qnainfo | ✅ 后端过滤 | ✅ 后端过滤 |

---

## 七、返回字段说明

所有列表响应中的每篇文章包含以下字段：

| 字段 | 类型 | 说明 |
|:-----|:-----|:------|
| `id` | string | 文章编号，如 `a_01` |
| `title` | string | 标题 |
| `body_avail` | string | `"有"`=可提取正文，`"无"`=无正文来源 |
| `date` | string | 日期 |
| `date_source` | string | 日期来源 |
| `date_confidence` | string | `high` / `medium` / `low` |
| `snippet` | string | 摘要 |
| `_category` | string | 分类（引擎相关） |
| `sentiment` | string | baidufin 特有：利好/利空/中性 |
| `body_status` | string | `processing` / `ready` / `error` |
| `_question` | string | qnainfo 特有：问题全文 |
| `_answerer` | string | qnainfo 特有：回答者 |
| `_answer` | string | qnainfo 特有：回答内容 |
| `_ask_time` | string | qnainfo 特有：提问时间 |
| `_update_time` | string | qnainfo 特有：更新时间 |

---

## 八、更新记录

### 2026-07-24

| 更新 | 说明 |
|:-----|:------|
| qnainfo 引擎 | 新增巨潮互动易问答后端 — 首次调用即返回完整问答内容，无列表/正文分离 |

### 2026-07-23

| 更新 | 说明 |
|:-----|:------|
| 多 worker 架构 | 12 workers，请求由 OS 均衡分发 |
| 并发信号量 | Semaphore(16)，超载返回 503 |
| 搜索超时 | 90s，超时返回 504 |
| session 文件持久化 | 多 worker 共享 session 数据 |
| 错误报送 | 14 种标准化错误代码，自动写入 error_log |
| 报错自动关闭 session | `/search` 报错后立即 close session |
| `body_avail` 字段 | 列表新增"有无正文"标记 |
| `_category` 统一 | baidufin 固定"资讯"，thsfin 从标题提取 |
| qnainfo 引擎 | 互动易问答 — 首次调用即返回完整问答内容，无列表/正文分离，无需 /article |
| baidufin `sentiment` | 利好/利空/中性 情绪标签 |
| thsfin 标题拆分 | 冒号前→分类，冒号后→标题 |
| `filter_days` 通用 | 所有引擎支持相对天数过滤 |
| `url` 移除 | 返回列表不再包含 URL 字段 |
| sinafin 正文提取 | 新增后台提取线程 |
| thsfin Playwright 线程化 | 修复 async worker 兼容性 |
