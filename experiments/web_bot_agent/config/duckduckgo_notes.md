# DuckDuckGo 搜索使用笔记

## 环境要点

### 代理
- WSL2 无法直连 DuckDuckGo，**必须走代理**
- 使用 `proxy_on`（172.20.32.1:7890）后再搜索
- 无代理时：`curl` 超时，Python/Node 库均无法连接

### 可用工具对比

| 工具 | 状态 | 备注 |
|---|---|---|
| **web-forager** (Python) | ✅ 推荐 | 底层用 `ddgs` 库，失败自动回退 Brave |
| ericthered926 duckduckgo-mcp | ❌ 不稳定 | `duck-duck-scrape` 经常 VQD 报错或被限速 |

---

## 搜索技巧

### 站内搜索要用 `site:` 语法

```
❌ "www.stcn.com 宁德时代"        → 返回无关结果（维基、新浪等）
✅ "site:stcn.com 宁德时代"       → 只返回 stcn.com 上的文章
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `max_results` | 5 | 最多返回条数（实测 20 条 OK，上限 ~50） |
| `safesearch` | moderate | `on` / `moderate` / `off` |
| `output_format` | json | `json` 或 `text` |
| `region` | wt-wt | 区域代码，例：`cn-zh` 偏向中文结果 |

### 频率限制
- DuckDuckGo 有反爬机制，连续请求会触发 **VQD 错误** 或 **"anomaly detected"**
- 建议两次搜索间隔至少 **1 秒**
- web-forager 会自动回退到 Brave 后端，但仍建议控制频率

---

## 返回结果字段

每条结果包含三个字段：

| 字段 | 说明 | 长度 |
|---|---|---|
| `title` | 文章标题 | 不等 |
| `url` | 完整 URL | — |
| `snippet` | 搜索引擎摘要片段 | ~150-250 字 |

> snippet **不是** 文章开头前几句，而是 DuckDuckGo 索引中最相关的段落。
> 通常是新闻文章的第一段（含时间、主体、事件），质量尚可。

### 如需更详细内容

```
搜索结果（snippet）→ 拿到 URL → jina_fetch(URL) → 文章全文 Markdown
```

web-forager 内置了 `jina_fetch`（底层走 r.jina.ai），可直接将 URL 转为 Markdown。

---

## 完整调用示例

```bash
source config/config.sh
proxy_on

# 搜索
web-forager search "site:stcn.com 宁德时代" --max-results 10

# 取某篇全文
web-forager fetch "https://www.stcn.com/article/detail/3991854.html"

# 或用 Python 调用 MCP
```

```python
# Python 方式
import httpx, json

resp = httpx.post("https://html.duckduckgo.com/html", data={"q": "site:stcn.com 宁德时代"})
# 解析 HTML 提取结果...
```

---

## 已知问题

1. **VQD 错误**：ericthered926 版经常 `Failed to get the VQD`，原因是 DuckDuckGo 的请求令牌验证。改用 web-forager（`ddgs` 库）可绕过。
2. **空结果**：偶发 `No results found`，通常是 DuckDuckGo 限流，web-forager 会自动重试 Brave。
3. **代理影响**：代理可能影响搜索结果的地理偏向（通过 Clash 可能定位到非中国节点），如需中文优先可加 `region=cn-zh`。
