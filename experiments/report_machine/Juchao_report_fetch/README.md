# 巨潮盘后公告提取工具

> 从巨潮资讯网获取 A 股上市公司盘后公告，下载 PDF 并提取文字内容。

---

## 快速开始

```python
from fetch import fetch_announcements, fetch_single

# 单只股票，指定日期范围
result = fetch_announcements("300395", start_date="20260720", end_date="20260721")

# 多只股票
result = fetch_announcements(
    ["300395", "600519", "000001"],
    start_date="20260720",
    end_date="20260721",
)
```

---

## API 参考

### `fetch_announcements(symbols, start_date, end_date, include_pdf_text=True)`

获取指定股票在指定日期范围内的盘后公告。

**参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `symbols` | `str \| list[str]` | ✅ | 股票代码（6位纯数字）或代码列表 |
| `start_date` | `str` | ✅ | 开始日期，`YYYYMMDD` 或 `YYYY-MM-DD` 格式 |
| `end_date` | `str` | ✅ | 结束日期，同上 |
| `include_pdf_text` | `bool` | 否 | 是否提取 PDF 正文（默认 `True`） |

**返回**

```python
{
    "300395": [
        "公告: 2026年半年度业绩预告\n日期: 2026-07-20\n--- PDF 正文 ---\n证券代码：300395 ...",
    ],
    "300436": None,                  # 该日期范围无公告
    "600519": [
        "公告: ...\n--- PDF 正文 ---\n...",
        "公告: ...\n--- PDF 正文 ---\n...",  # 同一天多条
    ],
}
```

- 有公告：`{code: [str, str, ...]}`（每条公告一条字符串）
- 无公告：`{code: None}`
- 每条公告字符串格式：`公告标题 + 日期 + PDF正文（可选）`

---

### `fetch_single(symbol, start_date, end_date)`

获取单只股票的公告文本，多条公告自动合并。

**参数** 同上。

**返回**
- `str` — 多条公告用 `==========` 分隔
- `None` — 无公告

---

### 输入格式要求

| 字段 | 正确示例 | 错误示例 |
|------|----------|----------|
| 股票代码 | `"300395"` | `"300395.SZ"` / `"sz300395"` |
| 开始日期 | `"20260720"` 或 `"2026-07-20"` | `"2026/07/20"` |
| 结束日期 | `"20260721"` 或 `"2026-07-21"` | 同上 |

> **注意**：股票代码是纯 6 位数字，不带交易所后缀（.SH/.SZ）。可以从知识图谱 `kg_query.search_stock('菲利华')` 返回的代码截取前 6 位。

---

### 输出示例

#### 有公告 → 返回字符串列表

```
公告: 2026年半年度业绩预告
日期: 2026-07-20
--- PDF 正文 ---
证券代码：300395 证券简称：菲利华 公告编号：2026-47
湖北菲利华石英玻璃股份有限公司
2026 年半年度业绩预告

一、本期业绩预计情况
（一）业绩预告期间：2026 年 1 月 1 日至 2026 年 6 月 30 日
（二）业绩预告情况：预计净利润为正值且属于同向上升情形

项 目                      本报告期          上年同期
营业收入                   120,000～145,000    90,784.42
归属于上市公司股东的净利润   27,000～31,000     22,171.99
...
```

#### 无公告 → 返回 None

```python
{"300436": None}
```

---

### 可选：关闭 PDF 下载

```python
# 只返回公告标题和日期，不下载 PDF
result = fetch_announcements("300395", "20260720", "20260721", include_pdf_text=False)
```

---

## 错误处理

| 场景 | 行为 |
|:----|------|
| 日期范围内无公告 | 返回 `None`，不抛异常 |
| 股票代码不存在 | 返回 `None` |
| PDF 下载或解析失败 | 跳过该公告的 PDF 正文，返回标题+日期 |
| 网络中断 | 抛 `requests` 异常（上层捕获） |
| 多个股票部分成功 | 每个股票独立处理，互不影响 |

---

## 依赖

| 库 | 用途 |
|:---|:----|
| `akshare` | 查询公告列表 |
| `requests` | 调用巨潮 API、下载 PDF |
| `pypdf` | PDF 文字提取 |
| `re`, `logging` | 工具（标准库） |

---

## 运行环境

```bash
conda run -n stock_agent python3 fetch.py    # 运行自测
```

---

---

### PDF 正文截断

PDF 正文超过 **3000 中文字** 时自动截断，在末尾追加 `[截断，只保留3000字]` 提示。

```text
...
免疫抑制类产品收入增长主要由吡美莫司销售增长带动，具有合理性。
4、其他类产品收入变动及毛利率变动的原因及合理性
公司其他类产品主要包括非达米星、达巴万星及舒更葡糖钠等。2025 年度，
公司其他

[截断，只保留3000字]
```

- 短公告（≤ 3000 字）不受影响，完整保留
- 长公告只保留前 3000 个中文字，非中文字符不计入上限
- 3000 字阈值适用于每条公告正文，与公告数量无关

---

## 数据流

```
调用方
   │
   ▼
fetch_announcements(symbols, start_date, end_date)
   │
   ├── 对每个股票代码:
   │      │
   │      ├── akshare: 查询公告列表
   │      │      └── stock_zh_a_disclosure_report_cninfo()
   │      │
   │      └── 对每条公告:
   │             │
   │             ├── 巨潮 API: 获取 PDF 地址
   │             │      └── POST /new/announcement/bulletin_detail
   │             │
   │             ├── 下载 PDF
   │             │      └── GET http://static.cninfo.com.cn/finalpage/{date}/{id}.PDF
   │             │
   │             └── pypdf: 提取文字
   │
   └── 返回 {code: [text, ...] | None}
```

---

## v3.0 服务集成

本模块已集成到 `v3.0 API`（`web_bot_agent/version_3.0/`）和 `search_engine` 统一搜索接口。

### search_engine 接口

```python
from search_engine import search

# 查列表（秒回，不下载 PDF）
results = search("300395", engine="juchao")
results = search("菲利华", engine="juchao",
                 start_date="2026-07-20", end_date="2026-07-21")
```

返回格式不含正文，正文需后台异步下载：

```python
# 返回格式
[
    {
        "title": "2026年半年度业绩预告",
        "url": "",
        "snippet": "证券代码：300395 ...",
        "_known_date": "2026-07-20",
        "_category": "公告",
        "_announce_id": "1225432055",    # 供 PDF 下载
        "_announce_time": "2026-07-20",  # 供 PDF 下载
    },
]
```

### v3.0 API 调用

```bash
# 查列表（快慢分离：列表秒回 + 后台PDF提取）
curl -X POST /search \
  -H "Content-Type: application/json" \
  -d '{"query":"688166","engine":"juchao","mode":"list",
       "max_results":10, "filter_days":3}'
# → status: "list_ready", ~1s

# 取正文（后台PDF提取完成后立即可取）
curl -X POST /article \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s_...","article_ids":["a_01"]}'
# → status: "ready", 正文完整
```

### 架构说明

```
Phase 0 (search):  akshare → 公告列表（标题/日期/announceId）
                   状态: list_ready (0.3~2s)
Phase 1 (后台线程): 逐条下载 PDF → pypdf 提取文字
                   状态: done (3~15s)
取正文 (/article):  从 session 内存读取
                   状态: ready (即时)
```

### 注意事项

- 公告时间只精确到 **天**（YYYY-MM-DD），无分钟精度
- 时间筛选用 `start_date` / `end_date` 或 `filter_days=N`（近 N 天）
- 所有巨潮公告均为 PDF 格式，后台自动下载提取
- PDF 下载失败或内容为空时标记 `fetch_error`，不影响其他公告
- 依赖：`akshare`、`requests`、`pypdf`
