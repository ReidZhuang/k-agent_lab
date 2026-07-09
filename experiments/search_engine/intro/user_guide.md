# search_engine 使用说明

## 概述

统一搜索接口，目前使用 ddgs（DuckDuckGo）作为后端，可扩展其他引擎。

```
pip install ddgs
```

## 快速开始

```python
from search_engine import search

# 基础搜索
results = search("中国芯片", max_results=5)

# 站内搜索
results = search("中国芯片", site="zhihu.com")

# 站内 + 时间过滤
results = search("中国芯片", site="stcn.com", timelimit="y", max_results=10)
```

## 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `query` | str | 必填 | 搜索关键词 |
| `max_results` | int | 10 | 返回结果数 |
| `site` | str | None | 站内限定域名 |
| `timelimit` | str | None | `d`(天) / `w`(周) / `m`(月) / `y`(年) |

## 返回格式

```python
[
    {"title": "标题", "url": "https://...", "snippet": "摘要..."},
    ...
]
```

## 配置

代理在 `config.py` 中设置，仅搜索需要代理。

## 添加新后端

1. 在 `backends/` 下创建新文件，继承 `SearchBackend`
2. 实现 `search()` 方法，返回统一格式
3. 在 `__init__.py` 中导入并调用
