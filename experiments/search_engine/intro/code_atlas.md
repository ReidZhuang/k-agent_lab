# search_engine 代码图谱

```mermaid
graph TB
  subgraph API["对外接口"]
    SEARCH["search(query, max_results,<br/>site, timelimit)"]
  end

  subgraph Backend["后端实现"]
    BASE["SearchBackend<br/>抽象基类"]
    DDGS["DDGSSearchBackend<br/>ddgs 实现"]
  end

  subgraph Cfg["配置"]
    CFG["config.py<br/>PROXY"]
  end

  API -->|调用| DDGS
  DDGS -->|继承| BASE
  DDGS -->|读取| CFG
  DDGS -->|调用| DDGS_LIB["ddgs.DDGS.text()"]
  DDGS_LIB -->|返回| RAW["原始结果<br/>{title, href, body}"]
  DDGS -->|映射| OUT["统一输出<br/>{title, url, snippet}"]
```

## 调用链

```mermaid
sequenceDiagram
  actor C as 调用方（core.py 等）
  participant SE as search_engine
  participant DDGS as ddgs.DDGS
  participant DDG as DuckDuckGo

  C->>SE: search(query, site, timelimit)
  SE->>SE: 拼接 site: 到 query
  SE->>SE: 设置代理环境变量
  SE->>DDGS: text(query, timelimit, max_results)
  DDGS->>DDG: HTTP 请求
  DDG-->>DDGS: 原始结果
  DDGS-->>SE: {title, href, body}
  SE->>SE: 映射为 {title, url, snippet}
  SE-->>C: 统一格式结果
```

## 目录结构

```
search_engine/
  ├── __init__.py        # search() 统一接口
  ├── config.py          # 代理配置
  ├── backends/
  │   ├── __init__.py
  │   ├── base.py        # 抽象基类
  │   └── ddgs.py        # ddgs 实现
  └── intro/
      ├── user_guide.md  # 使用说明
      └── code_atlas.md  # 代码图谱
```

## 扩展方式

新增后端：在 `backends/` 下创建新文件，继承 `SearchBackend`，实现 `search()`，返回 `[{title, url, snippet}]`。
