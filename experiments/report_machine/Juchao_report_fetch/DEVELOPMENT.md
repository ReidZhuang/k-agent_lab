# 巨潮公告提取工具 — 开发文档

> 版本: v1.1 | 最后更新: 2026-07-21

---

## 目录

1. [模块结构](#1-模块结构)
2. [数据流详解](#2-数据流详解)
3. [巨潮 API 逆向说明](#3-巨潮-api-逆向说明)
4. [PDF 提取流程](#4-pdf-提取流程)
5. [错误处理策略](#5-错误处理策略)
6. [边界情况](#6-边界情况)
7. [测试](#7-测试)

---

## 1. 模块结构

```
Juchao_report_fetch/
├── fetch.py          # 主模块（API 实现）
├── README.md         # 使用文档
└── DEVELOPMENT.md    # 本文件（开发文档）
```

### 函数依赖树

```
fetch_announcements()              # 入口：接收 symbols + 日期范围
  └── _fetch_single()              # 单只股票处理
        ├── ak.stock_zh_a_         # akshare 公告列表查询
        │   disclosure_report_
        │   cninfo()
        └── _build_announcement_   # 构建单条公告文本
              text()
              └── _fetch_pdf_text()    # 下载 PDF 并提取文字
                    ├── _get_pdf_url()      # 巨潮 API → PDF 直链
                    ├── requests.get()      # 下载 PDF
                    ├── PdfReader()         # pypdf 文字提取
                    └── _clean_text()       # 清理 + 截断
                          └── _truncate_by_chinese_count()  # 按3000中文字截断

fetch_single()                     # 快捷函数：单只 + 合并输出
```

---

## 2. 数据流详解

### 2.1 完整调用时序

```
调用方                         fetch.py                 巨潮(cninfo)          akshare
  │                              │                         │                    │
  │  fetch_announcements(        │                         │                    │
  │    ["300395"],               │                         │                    │
  │    "20260720",               │                         │                    │
  │    "20260721")               │                         │                    │
  │ ──────────────────────────►  │                         │                    │
  │                              │                         │                    │
  │                              │ _fetch_single("300395") │                    │
  │                              │ ──────────────────────► │                    │
  │                              │                         │                    │
  │                              │ akshare API 调用        │                    │
  │                              │ ────────────────────────────────────────────► │
  │                              │                         │                    │
  │                              │ ◄── DataFrame ────────────────────────────── │
  │                              │   (代码,简称,公告标题,    │                    │
  │                              │    公告时间,公告链接)     │                    │
  │                              │                         │                    │
  │                              │ 解析公告链接提取          │                    │
  │                              │ announcementId 和       │                    │
  │                              │ announceTime            │                    │
  │                              │                         │                    │
  │                              │ POST bulletin_detail    │                    │
  │                              │ ──────────────────────► │                    │
  │                              │   announceId=1225431454 │                    │
  │                              │   announceTime=2026-07-20│                    │
  │                              │                         │                    │
  │                              │ ◄── JSON ─────────────  │                    │
  │                              │   {fileUrl: "http://..."}│                    │
  │                              │                         │                    │
  │                              │ GET {fileUrl}           │                    │
  │                              │ ──────────────────────► │                    │
  │                              │   (PDF binary)          │                    │
  │                              │ ◄────────────────────── │                    │
  │                              │                         │                    │
  │                              │ pypdf 文字提取          │                    │
  │                              │                         │                    │
  │ ◄── {"300395": [公告文本]} ── │                         │                    │
  │                              │                         │                    │
```

### 2.2 公告链接 → PDF 的过程

akshare 返回的 `公告链接` 格式：

```
http://www.cninfo.com.cn/new/disclosure/detail
  ?stockCode=300395
  &announcementId=1225431454
  &orgId=9900023110
  &announcementTime=2026-07-20
```

从中提取 `announcementId` 和 `announcementTime` 后，调用巨潮的内部 API：

```
POST http://www.cninfo.com.cn/new/announcement/bulletin_detail
Content-Type: application/x-www-form-urlencoded

announceId=1225431454&flag=true&announceTime=2026-07-20
```

返回 JSON：

```json
{
  "announcement": {
    "adjunctUrl": "finalpage/2026-07-20/1225431454.PDF",
    ...
  },
  "fileUrl": "http://static.cninfo.com.cn/finalpage/2026-07-20/1225431454.PDF"
}
```

`fileUrl` 即为 PDF 直链。

---

## 3. 巨潮 API 逆向说明

### 3.1 公告查询（akshare）

akshare 的 `stock_zh_a_disclosure_report_cninfo()` 封装了巨潮的公告搜索接口。从 akshare 源码（v1.18.64）可知其内部流程：

1. 调用巨潮搜索 API，传入 `stock`（股票代码）、`startTime`、`endTime` 等参数
2. 解析返回的 JSON，提取公告列表
3. 筛选出特定列：代码、简称、公告标题、公告时间、公告链接

**注意**：akshare 此函数在**无公告返回时**会抛 `KeyError`（空 DataFrame 列选择失败）或 JSON 解析错误。这在 `fetch.py` 中被捕获并视为"无公告"信号。

### 3.2 公告详情 API（直接调用）

```
POST http://www.cninfo.com.cn/new/announcement/bulletin_detail
```

这是从前端 Vue 组件 `notice-detail.js` 中逆向得到的。页面加载时会调用此接口获取公告详情，包括 PDF 附件路径。

关键代码（来自 `notice-detail.js`）：

```javascript
getNoticeInfo: function() {
    axios({
        url: path + '/announcement/bulletin_detail',  // path = "/new"
        method: 'post',
        params: {
            announceId: announcementId,
            flag: plate == 'szse' ? true : false,
            announceTime: announcementTime
        }
    }).then(function(res) {
        this.pdfUrl = v3_cninfo + "/" + res.announcement.adjunctUrl;
    })
}
```

### 3.3 PDF URL 格式

```
http://static.cninfo.com.cn/finalpage/{yyyy-MM-dd}/{announcementId}.PDF
```

示例：`http://static.cninfo.com.cn/finalpage/2026-07-20/1225431454.PDF`

---

## 4. PDF 提取流程

### 4.1 选型

| 库 | 状态 | 说明 |
|:---|:----:|------|
| `pypdf` | ✅ 使用中 | 已在 conda stock_agent 环境，纯 Python，无系统依赖 |
| `PyPDF2` | ❌ 未安装 | `pypdf` 是其继任者，接口兼容 |
| `pdfminer` | ❌ 未安装 | 更强大但更慢 |
| `pdfplumber` | ❌ 未安装 | 依赖 `pdfminer` |
| `pdftotext` | ❌ 无系统工具 | 需安装 `poppler-utils` |

### 4.2 提取质量

```
证券代码：300395 证券简称：菲利华 公告编号：2026-47
湖北菲利华石英玻璃股份有限公司
2026 年半年度业绩预告

一、本期业绩预计情况
（一）业绩预告期间：2026 年 1 月 1 日至 2026 年 6 月 30 日
（二）业绩预告情况：预计净利润为正值且属于同向上升情形

项 目                      本报告期          上年同期
营业收入                   120,000～145,000    90,784.42
归属于上市公司股东的净利润   27,000～31,000     22,171.99
```

- 中文表格文字基本完整
- 表格线（边框）不会被提取，但数据单元格文字按阅读顺序排列
- 数字格式和换行保留

### 4.3 正文截断机制

PDF 正文超过 **3000 中文字** 时自动截断，在末尾追加 `[截断，只保留3000字]`。

**实现函数**: `_truncate_by_chinese_count()`

**截断逻辑**:

```python
def _truncate_by_chinese_count(text: str) -> str:
    chinese_chars = re.findall(r"[一-鿿]", text)
    if len(chinese_chars) <= MAX_CHINESE_CHARS:  # 3000
        return text                               # 未超限，原文返回

    # 找到第 3000 个中文字的位置
    count = 0
    for i, ch in enumerate(text):
        if "一" <= ch <= "鿿":
            count += 1
            if count == MAX_CHINESE_CHARS:
                cut_pos = i + 1
                break

    truncated = text[:cut_pos].strip()
    truncated += "\n\n[截断，只保留3000字]"
    return truncated
```

**设计要点**:

| 要点 | 说明 |
|:----|------|
| 计数范围 | 仅统计中文字（Unicode `一-鿿`），数字、英文字母、标点不计数 |
| 截断位置 | 在第 3000 个中文字之后立即截断，保留该中文字及之前所有内容 |
| 截断提示 | 截断时在末尾追加独占一行 `[截断，只保留3000字]` |
| 短公告 | ≤ 3000 中文字的公告不受影响，原文返回 |
| 配置 | `MAX_CHINESE_CHARS = 3000` 定义在模块顶部，便于调整 |

**实测效果**（博瑞医药 8.3 万字问询函回复）：

```
原始: 83,004 字符 / 30,175 中文字
截断后: 4,489 字符 / 3,000 中文字 + [截断，只保留3000字]
```

---

## 5. 错误处理策略

### 5.1 层级容错

```
fetch_announcements()
  │
  ├── 股票级容错
  │     _fetch_single() 内部 try/except
  │     ├── akshare 调用失败 → 区分"无公告"和"真异常"
  │     └── 返回 None（不会让整批失败）
  │
  └── 公告级容错
        _build_announcement_text() 内部
        ├── PDF URL 获取失败 → 返回标题+日期（无正文）
        ├── PDF 下载失败 → 同上
        └── PDF 文字提取失败 → 同上
```

### 5.2 已知无公告信号

| 异常特征 | 处理方式 |
|----------|---------|
| `None of [Index(['代码',...]] are in the [columns]` | 视为无公告，返回 None |
| `Expecting value: line 1 column 1 (char 0)` | 视为无公告，返回 None |
| `DataFrame.empty == True` | 视为无公告，返回 None |

### 5.3 请求间隔

每条公告间隔 `0.3秒`，每只股票间隔 `0.3秒`，避免对巨潮接口造成压力。

---

## 6. 边界情况

### 6.1 无公告

```python
>>> fetch_announcements("300436", "20250101", "20250105")
{"300436": None}
```

### 6.2 多只股票，部分有公告

```python
>>> fetch_announcements(["300395", "300436"], "20260720", "20260721")
{"300395": ["公告1..."], "300436": None}
```

### 6.3 同一天多条公告

按 akshare 返回的顺序排列，每条公告各自下载 PDF 并提取文字。

### 6.4 PDF 无法提取文字

原因：扫描件（图片型 PDF）、加密 PDF、格式异常。
→ 返回该公告的标题+日期，跳过 [PDF 正文] 部分。

### 6.5 股票代码不存在

akshare 返回空 → `None`。

### 6.6 日期范围跨多天

正常查询，支持任意日期范围。

### 6.7 PDF 正文超过 3000 字

自动截断，保留前 3000 个中文字，末尾追加 `[截断，只保留3000字]`。

### 6.8 PDF 正文刚好≤ 3000 字

原文保留，不追加截断提示。

---

## 7. 测试

### 7.1 自测（模块内置）

```bash
conda run -n stock_agent python3 fetch.py
```

内置 3 个测试场景：

| 测试 | 输入 | 预期 |
|------|------|------|
| 菲利华 2026-07-20~21 | `"300395"` | 1 条公告，含 PDF 正文 |
| 广生堂 2025-01-01~05 | `"300436"` | `None`（无公告） |
| 多只混合 | `["300395", "300436"]` | 300395 有 / 300436 无 |

### 7.2 手动测试

```python
from fetch import fetch_announcements

# 验证单只
r = fetch_announcements("300395", "20260720", "20260721")
assert r["300395"] is not None
assert "营业收入" in r["300395"][0]

# 验证无公告
r = fetch_announcements("300436", "20250101", "20250105")
assert r["300436"] is None

# 验证多只
r = fetch_announcements(["300395", "300436"], "20260720", "20260721")
assert r["300395"] is not None
assert r["300436"] is None
```
