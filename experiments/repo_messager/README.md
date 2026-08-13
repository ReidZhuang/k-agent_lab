# 新浪研报查询服务

输入股票代码 + edition,返回研报列表与正文。高并发快返回(缓存 + in-flight 合并)。

## API

```
POST /reports  {"code": "002821", "edition": 0}
GET  /health
```

| edition | 返回 |
|---|---|
| 0 | 最近12篇列表(标题/机构/日期) + 最新6篇正文(标题/日期/机构/正文) |
| 1 | 第7~12篇正文, 不含列表; 总数<6 → bodies: null; 6~11篇 → 返回实际存在的后几篇 |

正文最多 6000 字,超出截断并附 `truncated: true` + 正文尾部提示。

## 启动

```bash
conda run -n stock_agent python -m uvicorn report_service:app \
    --host 0.0.0.0 --port 8700 --workers 1
```

## 高并发设计

- **TTL 缓存**: 列表 600s / 正文 24h(rptid 级),LRU 上限防膨胀
- **in-flight 合并**: 同股票并发请求共享一次抓取(12并发冷缓存总耗时 0.5s)
- **正文并行**: 6篇 asyncio.to_thread 并行,httpx 共享连接池(trust_env=False 直连)
- **限流**: 请求级 Semaphore(32),超出排队

## 超时

| 环节 | 值 |
|---|---|
| 单篇正文 | 45s + 重试 1 次 |
| 整请求 | 120s → 504 |
| 单页列表 | httpx 15s + 重试 |

## 异常返回

- 400: invalid_code / invalid_edition
- 503: list_fetch_failed(列表抓取失败)
- 200 内嵌: 部分正文失败 → 失败篇 `{error: "body_timeout"|"body_fetch_failed"}`;全部正文失败 → bodies: []
- 504: 整请求超时

## 压测结果(本机 16核/62G, 2026-08-10)

| 场景 | 结果 |
|---|---|
| 同股票12并发(冷缓存) | 0.5s 全返, 每请求 ~470ms |
| 同股票10并发(热缓存) | 33ms 中位 |
| 混合10股票并发 | 0.5s 全返 |
| 20股票顺序并发 edition=0 | 2.1s, 零失败零截断 |

## 失败案例分析(第3阶段待办)

首轮 20 只股票扫描零失败。后续如出现解析失败,集中分析:
- 详情页结构变体(标题/机构/正文容器变化)
- PDF 型研报(需 pypdf 兜底)
- JS 渲染页(需 playwright 兜底)
