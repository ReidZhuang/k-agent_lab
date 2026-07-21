# search_engine 代码图谱

## 架构

```mermaid
graph TB
  subgraph API["对外接口"]
    SEARCH["search(query, max_results, site, timelimit,<br/>engine, start_date, end_date)"]
  end

  subgraph Backend["后端实现"]
    BASE["SearchBackend<br/>抽象基类"]
    DDGS["DDGSSearchBackend<br/>ddgs 实现"]
    SINA["SinaFinBackend<br/>sinafin 实现"]
    BAIDU["BaidufinBackend<br/>baidufin 实现"]
  end

  subgraph Cfg["配置"]
    CFG["config.py<br/>PROXY / SNAFIN_ENDPOINT"]
  end

  subgraph ExtDep["外部依赖"]
    SINATOOL["sinafin_artical_tool<br/>(独立 FastAPI 服务，端口 8000)"]
    PLAYWRIGHT["Playwright + Chromium<br/>(headless 浏览器)"]
  end

  API -->|engine=ddg| DDGS
  API -->|engine=sinafin| SINA
  API -->|engine=baidufin| BAIDU
  DDGS -->|继承| BASE
  SINA -->|继承| BASE
  BAIDU -->|继承| BASE
  DDGS -->|读取| CFG
  SINA -->|读取| CFG
  DDGS -->|调用| DDGS_LIB["ddgs.DDGS.text()"]
  SINA -->|HTTP| SINATOOL
  BAIDU -->|浏览器渲染| PLAYWRIGHT
  BAIDU -->|拦截 API| BAIDU_API["finance.pae.baidu.com<br/>vapi/sentimentlist"]
```

## 调用链

### DDG 引擎

```mermaid
sequenceDiagram
  actor C as core.py
  participant SE as search_engine
  participant DDGS as ddgs.DDGS
  participant DDG as DuckDuckGo

  C->>SE: search(query, engine="ddg")
  SE->>SE: 设置代理环境变量
  SE->>DDGS: text(query, timelimit, max_results)
  DDGS->>DDG: HTTP 请求（走代理）
  DDG-->>DDGS: 原始结果
  DDGS-->>SE: {title, href, body}
  SE->>SE: 映射为标准格式
  SE-->>C: [{title, url, snippet}]
```

### Sinafin 引擎

```mermaid
sequenceDiagram
  actor C as core.py
  participant SE as search_engine
  participant SA as sinafin_artical_tool
  participant SINA as 新浪财经

  C->>SE: search("300750", engine="sinafin")
  SE->>SA: GET /news?code=300750&format=json
  SA->>SINA: 抓取新浪新闻列表页（GB2312）
  SINA-->>SA: HTML →
  SA->>SA: 解析表格 → 提取标题/URL/日期
  SA-->>SE: {news: [{title, url, date, time}]}
  SE->>SE: 映射为标准格式 + _known_date
  SE-->>C: [{title, url, snippet, _known_date}]
```

### Baidufin 引擎

```mermaid
sequenceDiagram
  actor C as core.py
  participant SE as search_engine
  participant PW as Playwright
  participant BD as 百度股市通
  participant API as 百度API

  C->>SE: search("300436", engine="baidufin", start_date, end_date)
  SE->>PW: 启动 headless Chromium
  PW->>BD: 打开 finance.baidu.com/stock/ab-300436
  BD-->>PW: HTML shell → JS 渲染
  PW->>PW: 点击"资讯"标签
  PW->>API: GET vapi/sentimentlist?code=300436&pn=0&rn=20
  API-->>PW: {Result: [{TplData: {sentimentListInfo: [...]}}]}
  PW->>PW: 解析 → 去重 → 日期过滤 → 标准化
  PW-->>SE: [{title, url, snippet, _known_date, _baidu_*, ...}]
  SE-->>C: 返回结果列表
```

## 目录结构

```
search_engine/
├── __init__.py            # search() 统一接口（engine 分发）
├── config.py              # 代理配置 + sinafin 端点配置
├── backends/
│   ├── __init__.py
│   ├── base.py            # SearchBackend 抽象基类
│   ├── ddgs.py            # DDG 搜索实现
│   ├── sinafin.py         # sinafin 个股新闻实现
│   └── baidufin.py        # 百度股市通个股资讯实现（v3.0 新增）
└── intro/
    ├── user_guide.md      # 使用说明
    └── code_atlas.md      # 代码图谱
```

## 扩展方式

新增后端：
1. 在 `backends/` 下创建新文件，继承 `SearchBackend`
2. 实现 `search()` 方法
3. 在 `__init__.py` 中添加 `engine` 分发分支

返回格式必须为 `[{title, url, snippet, ...}]`。
可扩展自定义字段（如 `_known_date`、`_baidu_sentiment` 等），调用方按需读取。

### baidufin 特有字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `_known_date` | str | 精确发布日期 `"2026-07-21"` |
| `_baidu_sentiment` | str | 情绪分类：`"利好"` / `"中性"` / `"利空"` |
| `_baidu_provider` | str | 新闻来源：`"证券之星"` / `"东方财富网"` / `"同花顺"` |
| `_baidu_abstract` | str | 新闻摘要（可用作正文预览） |
| `_baidu_ts` | int | Unix 时间戳 |

### 注意事项

- baidufin 依赖 Playwright + Chromium，约 200MB
- 搜索在独立线程中执行（兼容 asyncio 调用方）
- 通过拦截百度内部 API 获取结构化数据，无需解析 HTML
