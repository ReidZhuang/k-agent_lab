# Sina Finance Stock News Tool

新浪财经个股新闻抓取工具 — FastAPI 服务。

## 概述

抓取新浪财经个股新闻列表页，返回结构化数据（标题、URL、发布时间）。
是 `web_bot_agent v3.0` 的 sinafin 引擎后端数据源。

## 启动

```bash
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8000
```

## API

### `GET /health`

健康检查。

### `GET /news`

抓取个股新闻列表。

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `code` | str | - | 股票代码，如 `300750`、`sz300750`、`300750.SZ` |
| `name` | str | - | 公司名称，如 `宁德时代`（与 code 二选一） |
| `pages` | int | 3 | 翻页页数，每页约 20 条 |
| `format` | str | `csv` | 输出格式，`csv` 或 `json` |
| `start_date` | str | - | 起始日期过滤 `YYYY-MM-DD`，翻页时自动提前 break |
| `end_date` | str | - | 截止日期过滤 `YYYY-MM-DD` |

**示例：**

```bash
# 按名称查询，JSON 格式
curl "http://localhost:8000/news?name=%E5%AE%81%E5%BE%B7%E6%97%B6%E4%BB%A3&format=json"

# 按代码查询，带日期过滤
curl "http://localhost:8000/news?code=300750&format=json&start_date=2026-07-20&end_date=2026-07-21"
```

## JSON 返回格式

```json
{
  "stock": {"code": "sz300750", "name": "宁德时代"},
  "total": 42,
  "pages_scraped": 3,
  "news": [
    {
      "title": "文章标题",
      "url": "https://finance.sina.com.cn/...",
      "date": "2026-07-21",
      "time": "20:46"
    }
  ]
}
```

## 日期过滤机制（v1.1+）

`start_date` / `end_date` 参数在服务端生效：

- **翻页提前 break**：列表页按时间倒序排列。如果当前页最新文章日期 < `start_date`，后续页只会更旧，直接停止翻页，节省请求。
- **结果过滤**：翻页完成后对全部结果做二次日期过滤。

## 开发说明

### 文件结构

```
sinafin_artical_tool/
├── api.py              # FastAPI 应用入口
├── config.py           # URL、超时等配置
├── sina_scraper.py     # 核心爬虫（抓取+解析+分页）
├── stock_lookup.py     # 股票代码解析（Tushare + 缓存）
└── data/               # 缓存目录
```

### 依赖

- `httpx` — HTTP 请求
- `fastapi` + `uvicorn` — API 服务
- `tushare` — 股票代码查询
