# search_engine 使用说明

## 概述

统一搜索接口，支持多后端分发。当前支持：

| 引擎 | 后端 | 用途 | 依赖 |
|------|------|------|------|
| `ddg`（默认） | DuckDuckGo | 通用网页搜索 | 代理（WSL2 自动检测） |
| `sinafin` | sinafin_artical_tool API | 新浪财经个股新闻 | sinafin 服务（端口 8000） |
| `baidufin` | 百度股市通（Playwright） | 百度个股资讯（含情绪/来源） | playwright + chromium |

## 安装

```bash
pip install ddgs httpx

# baidufin 引擎需要：
pip install playwright
playwright install chromium
```

## 快速开始

```python
from search_engine import search

# DDG 基础搜索
results = search("中国芯片", max_results=5)

# DDG 站内搜索
results = search("中国芯片", site="zhihu.com")

# DDG 站内 + 时间过滤
results = search("中国芯片", site="stcn.com", timelimit="y")

# Sinafin 个股新闻
results = search("宁德时代", engine="sinafin", max_results=3)
results = search("300750", engine="sinafin", start_date="2026-07-20")

# Baidufin 百度股市通资讯
results = search("300436", engine="baidufin")                       # 今日全部
results = search("600519", engine="baidufin", max_results=10)       # 限制条数
results = search("002821", engine="baidufin",                       # 日期范围
                 start_date="2026-07-15", end_date="2026-07-21")
```

## 参数

| 参数 | 类型 | 默认 | ddg | sinafin | baidufin |
|------|------|------|-----|---------|----------|
| `query` | str | 必填 | 搜索关键词 | 股票代码或名称 | 股票代码 |
| `max_results` | int | 10 | 返回条数 | 翻页页数 | 最大条数（最多 100） |
| `site` | str | None | ✅ 站内限定 | ❌ | ❌ |
| `timelimit` | str | None | ✅ d/w/m/y | ❌ | ❌ |
| `start_date` | str | None | ❌ | ✅ YYYY-MM-DD | ✅ YYYY-MM-DD |
| `end_date` | str | None | ❌ | ✅ YYYY-MM-DD | ✅ YYYY-MM-DD |
| `engine` | str | `"ddg"` | ✅ 默认 | ✅ 显式指定 | ✅ 显式指定 |

## 返回格式

### DDG 引擎
```python
[{"title": "标题", "url": "https://...", "snippet": "摘要..."}, ...]
```

### Sinafin 引擎
```python
[{"title": "标题", "url": "https://...", "snippet": "日期 时间",
  "_known_date": "2026-07-21"}, ...]
# _known_date 是精确发布日期，调用方应直接使用，无需重新提取
```

### Baidufin 引擎
```python
[{"title": "标题",
  "url": "https://...",               # 原文链接
  "snippet": "摘要...",                # 新闻摘要（可作正文预览）
  "_known_date": "2026-07-21",        # 精确发布日期
  "_baidu_sentiment": "利好",          # 情绪: 利好/中性/利空
  "_baidu_provider": "证券之星",       # 来源: 证券之星/东方财富网/同花顺
  "_baidu_abstract": "全文摘要...",    # 完整摘要
  "_baidu_ts": 1784597673}, ...]      # Unix 时间戳
```

## 配置

代理在 `config.py` 中设置，仅 DDG 搜索需要代理：
```python
PROXY = "http://172.25.32.1:7890"  # 自动检测或环境变量 SEARCH_PROXY
SNAFIN_ENDPOINT = "http://localhost:8000"  # 环境变量可覆盖
```

baidufin 引擎无需配置，直接使用 Playwright 访问百度股市通。

## 注意事项

### baidufin 引擎
- 需要安装 Playwright + Chromium（首次使用约下载 200MB）
- 每次搜索启动浏览器 → 抓取 → 关闭，耗时约 8~15 秒
- 支持通过 `start_date`/`end_date` 做服务端日期过滤
- 返回结果含 `_known_date` 精确日期，无需重新提取
- 每页约 20 条，`max_results` 决定翻页次数（默认 1 页，最多 5 页）

## 添加新后端

1. 在 `backends/` 下创建新文件，继承 `SearchBackend`
2. 实现 `search()` 方法，返回 `[{title, url, snippet, ...}]`
3. 在 `__init__.py` 中的 `search()` 函数里添加分发逻辑
