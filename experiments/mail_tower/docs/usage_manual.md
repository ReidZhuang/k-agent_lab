# mail_tower 使用手册

> ⚠️ **此文档已迁移。最新完整版请参见：**
> - [USAGE.md](../USAGE.md) — 用户使用文档
> - [DEVELOPMENT.md](../DEVELOPMENT.md) — 开发/架构文档
>
> 本文档保留仅为兼容旧引用，内容可能过时。

## 快速启动

```bash
cd research/experiments/mail_tower
PROXY_SKIP=1 nohup conda run -n stock_agent python3 -m uvicorn api:app \
  --host 0.0.0.0 --port 8300 --workers 12 --backlog 2048 > /tmp/mail_tower.log 2>&1 &
```

## 架构变更（vs v3.0）

| 变更 | 旧行为 | 新行为 |
|------|--------|--------|
| sinafin 正文提取 | `/search` 后后台线程拉全部正文 | `/article` 调用时按需加载，1.8s 节流 |
| Playwright | `pass` 死代码，从不执行 | ThreadPoolExecutor + 60s 超时 |
| 代理设置 | ddgs.py 设全局 `http_proxy` 污染所有引擎 | DDG 传参走 Clash，其他引擎直连 |
| 跨 worker 缓存 | 内存找不到正文即 processing | 文件回退自动更新缓存 |
