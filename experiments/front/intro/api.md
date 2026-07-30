# API 文档

## 概述

- 基础地址：`http://<host>:8320/api`
- 认证方式：HTTP Header `Authorization: <token>`（登录接口除外）
- 请求体格式：`application/json`
- 响应体格式：`application/json`

## 认证 API

### `POST /api/auth/login` — 登录

**请求：**
```json
{"username": "zgx", "password": "68697311"}
```

**响应：**
```json
{"token": "abc123...", "user_id": 2, "username": "zgx"}
```

### `GET /api/auth/me` — 当前用户信息

**请求头：** `Authorization: <token>`

**响应：**
```json
{"user_id": 2, "username": "zgx"}
```

## 股票 API

### `GET /api/stock/search?q=<关键词>` — 搜索股票

按名称或代码搜索 A 股（自动拉取/刷新 `stg_stock_basic` 缓存）。

**参数：** `q` — 搜索关键词（支持模糊匹配）

**响应：**
```json
{
  "results": [
    {"ts_code": "300750.SZ", "symbol": "300750", "name": "宁德时代", "industry": "电气设备"},
    {"ts_code": "300750.SZ", "symbol": "300750", "name": "宁德时代", "industry": "电气设备"}
  ]
}
```

### `POST /api/stock/resolve` — 解析股票名称

将用户输入的股票名称列表解析为标准代码格式。

**请求：**
```json
{"stock_names": ["宁德时代", "比亚迪"]}
```

**响应：**
```json
{
  "results": [
    {"ts_code": "300750.SZ", "symbol": "300750", "name": "宁德时代", "industry": "电气设备"}
  ]
}
```

## 股票池 API

### `GET /api/stock/pool` — 查看股票池

返回用户自选股列表，自动附带昨日行情数据。

**响应：**
```json
{
  "stocks": [
    {
      "ts_code": "300750.SZ",
      "stock_name": "宁德时代",
      "created_at": "2026-07-28 12:00:00",
      "daily": {
        "trade_date": "20260728",
        "open": 185.5, "high": 188.2, "low": 182.1, "close": 183.8,
        "pre_close": 186.2, "change": -2.4, "pct_chg": -1.29,
        "vol": 285300, "amount": 524156000,
        "turnover_rate": 0.87, "amplitude": null
      }
    }
  ],
  "total": 1
}
```

> `daily` 字段说明：数据来自 Tushare `daily` + `daily_basic` 接口。
> 交易日 15:00-16:00 入库，非交易日返回空。`turnover_rate` 从 `daily_basic` 获取。

### `POST /api/stock/pool` — 加入股票池

**请求：**
```json
{"stock_names": ["宁德时代", "比亚迪"]}
```

**响应：**
```json
{"added": [{"ts_code": "300750.SZ", "stock_name": "宁德时代"}], "count": 2}
```

> 内部通过 `stg_stock_basic` 将名称解析为代码，写入 `stock_pool` 表。
> 已存在的股票不会重复添加（UNIQUE 约束）。

### `DELETE /api/stock/pool/{ts_code}` — 移除股票

**参数：** `ts_code` 路径参数，如 `300750.SZ`

**响应：**
```json
{"status": "ok"}
```

## 文件浏览 API

### `GET /api/explorer/list?path=<路径>` — 列出目录内容

**参数：** `path` — 相对于 `user_001/` 的路径，空字符串表示根目录

**响应：**
```json
{
  "items": [
    {"name": "2026半年报", "path": "2026半年报", "type": "dir", "is_favorite": false},
    {"name": "市场综述.md", "path": "2026半年报/市场综述.md", "type": "file", "is_favorite": true}
  ],
  "path": ""
}
```

> - 自动防止路径穿越（`/../` 攻击）
> - 文件夹不显示收藏状态（只有文件可收藏）
> - 结果按 目录 > 文件 排序，同类型按名称字母序

### `GET /api/explorer/content?path=<路径>` — 读取文件内容

**参数：** `path` — 文件路径（仅支持 `.md` / `.txt`）

**响应：**
```json
{"content": "# 文件标题\n\n正文内容...", "path": "2026半年报/市场综述.md"}
```

### `GET /api/explorer/download?path=<路径>` — 下载单个文件

将 `.md` 文件转换为 `.docx` 后返回文件流。

**返回：** `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`
**文件名：** 原文件名 `.md` → `.docx`

> 转换引擎：`office/output/md_to_docx.py`
> 转换后的临时文件在系统临时目录，下载完成后不会立即清理。

### `POST /api/explorer/download-batch` — 批量下载

**请求：**
```json
{"paths": ["2026半年报/市场综述.md", "2026半年报/煤炭行业分析.md"]}
```

**返回：** `Content-Type: application/zip`，文件名 `documents_YYYYMMDD_HHMMSS.zip`

> 将多个 `.md` 文件分别转为 `.docx`，打包为 zip 下载。
> 转换失败的单个文件会被跳过，不会影响其他文件。

## 收藏夹 API

### `GET /api/explorer/favorites` — 查看收藏

**响应：**
```json
{
  "favorites": [
    {"file_path": "2026半年报/市场综述.md", "file_name": "市场综述.md", "created_at": "2026-07-28 12:00:00"}
  ]
}
```

### `POST /api/explorer/favorites` — 添加收藏

**请求：**
```json
{"file_path": "2026半年报/市场综述.md", "file_name": "市场综述.md"}
```

**响应：**
```json
{"status": "ok"}
```

### `DELETE /api/explorer/favorites?path=<路径>` — 取消收藏

**参数：** `path` — 收藏的文件路径

**响应：**
```json
{"status": "ok"}
```

## 错误处理

### HTTP 状态码

| 状态码 | 含义 | 典型场景 |
|:------:|------|---------|
| 200 | 成功 | 正常返回数据 |
| 400 | 请求参数错误 | 股票列表为空、路径穿越 |
| 401 | 未登录/Token 过期 | Token 缺失或无效 |
| 404 | 文件不存在 | 路径无效 |
| 500 | 服务器内部错误 | Tushare API 异常、文件读取失败 |

### 错误响应格式

```json
{"detail": "错误描述信息"}
```

401 错误时前端会自动跳转到登录页。
