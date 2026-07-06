# 配置文件说明

## config.sh — Shell 环境配置

```bash
source config/config.sh
```

加载后可用命令：

| 命令 | 说明 |
|---|---|
| `proxy_on` | 开启代理 (WSL2 → Windows Clash :7890) |
| `proxy_off` | 关闭代理 |
| `ollama_run "提示词"` | 用默认模型 (3B) 运行推理 |
| `ollama_run "提示词" qwen2.5:7b` | 用 7B 大模型 |
| `web-search "关键词"` | 走代理搜索 DuckDuckGo |
| `web-fetch "URL"` | 抓取网页为 Markdown（jina_fetch） |
| `extract_article "URL"` | 正文提取（默认 trafilatura） |
| `ARTICLE_EXTRACTOR=readability extract_article "URL"` | 改用 readability 提取 |

### 正文提取说明

两个本地工具（无需外网 API）从 HTML 中提取文章正文：

| 工具 | 角色 | 速度 | 依赖 | 特点 |
|---|---|---|---|---|
| **trafilatura** | 首选 | ~12ms/篇 | lxml, courlan, htmldate, justext | 直出 markdown，鲁棒性高 |
| **readability** | 备选 | ~7ms/篇 | lxml, cssselect | 更快，需 html2text 转换 |

- 提取时自动开代理
- trafilatura 提取为空时自动 fallback 到 readability
- 通过环境变量 `ARTICLE_EXTRACTOR` 切换默认工具

## config.json — Python 脚本配置

```python
import json
with open("config/config.json") as f:
    cfg = json.load(f)
# cfg["ollama"]["endpoint"] → "http://localhost:11434"
# cfg["extraction"]["primary"] → "trafilatura"  (首选工具)
# cfg["extraction"]["fallback"] → "readability" (备选工具)
```

## 完整流程示例

```bash
source config/config.sh

# 1. 开代理 → 搜索
proxy_on && web-search "site:stcn.com 宁德时代" --max-results 10

# 2. 抓取文章全文（两种方式）
web-fetch "https://www.stcn.com/article/detail/3991854.html"   # jina_fetch（需要外网 API）
extract   "https://www.stcn.com/article/detail/3991854.html"   # trafilatura（本地，推荐）

# 3. LLM 摘要
ollama_run "提取本文中关于钠电池量产的核心信息" qwen2.5:7b
```
