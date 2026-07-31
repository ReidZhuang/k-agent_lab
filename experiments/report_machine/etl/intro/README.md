# ETL 数据管道 — 使用与开发手册

## 概述

ETL 系统负责从多个数据源采集股票数据，构建盘中数据仓库。输出为 SQLite 数据库`report_market.db`，供 Writer/Reporter 生成午间报告使用。

```
 ┌──────────┐  ┌──────────┐  ┌──────────┐
 │ Tushare  │  │ 同花顺    │  │ 通达信    │
 │ DC       │  │ THS      │  │ TDX      │
 │(东方财富)│  │          │  │          │
 └────┬─────┘  └────┬─────┘  └────┬─────┘
      │              │              │
      └──────┬───────┴──────┬───────┘
             │  并行 3 线程 │
             ▼              ▼
      ┌────────────┐ ┌────────────┐
      │ 概念板块    │ │ 板块日行情  │
      │ stg_*_index│ │ stg_*_daily│
      │ stg_*_member│ │            │
      └────────────┘ └────────────┘
             │
             ▼
      ┌─────────────────────┐
      │ 腾讯财经全量快照      │
      │ stg_tencent_snapshot │  ← `--snapshot-only`
      └──────────┬──────────┘
                 │
                 ▼
      ┌─────────────────────┐
      │ 盘中板块计算         │
      │ mid_sector_dc/ths/tdx│  ← `--mid-only`
      ├─────────────────────┤
      │ 个股宽表             │
      │ mid_stock_intraday  │
      └─────────────────────┘
```

## 目录结构

```
etl/
├── intro/
│   └── README.md          # 本文件
├── config.py              # 配置（路径、API 参数）
├── db_manager.py          # SQLite 数据库管理器（线程安全）
├── etl_runner.py          # ETL 调度主脚本
├── run_if_trading_day.sh  # 交易日包装脚本（含重试）
├── init_schema.sql        # 建表脚本（14 张数据表 + 1 张日志表）
├── utils.py               # 工具函数（日志、令牌桶、分块）
└── logs/
    ├── etl_runner.log     # ETL 运行日志
    └── etl_wrapper.log    # 包装脚本日志（[RUN]/[RETRY]/[FAIL] + error_log 写入结果）
```

## 架构：两层数据模型

| 层级 | 前缀 | 说明 | 表数 |
|:-----|:-----|:-----|:-----|
| **贴源层** | `stg_` | 按数据源原样存储，无业务聚合 | 10 |
| **中间层** | `mid_` | 基于快照实时计算，供下游直接查询 | 4 |
| **元数据** | `meta_` | 更新日志，用于运维监控 | 1 |

### 贴源层（10 张表）

| 表名 | 数据源 | 内容 |
|:-----|:-------|:-----|
| `stg_dc_member` | 东方财富 | 个股→板块索引（DC 概念板块成分） |
| `stg_dc_index` | 东方财富 | 板块分类（概念/行业/地域） |
| `stg_dc_daily` | 东方财富 | 板块日行情（前交易日收盘）|
| `stg_ths_member` | 同花顺 | 个股→THS 板块索引 |
| `stg_ths_index` | 同花顺 | THS 板块分类 |
| `stg_ths_daily` | 同花顺 | THS 板块日行情 |
| `stg_tdx_member` | 通达信 | 个股→TDX 板块索引 |
| `stg_tdx_index` | 通达信 | TDX 板块分类 |
| `stg_tdx_daily` | 通达信 | TDX 板块日行情 |
| `stg_tencent_snapshot` | 腾讯财经 | **A 股全量盘中快照**（54 字段，含 5 档盘口）|

### 中间层（4 张表）

| 表名 | 计算方式 | 内容 |
|:-----|:---------|:-----|
| `mid_sector_dc` | stg_dc_member + stg_tencent_snapshot | DC 板块平均涨跌幅、上涨/下跌家数 |
| `mid_sector_ths` | stg_ths_member + stg_tencent_snapshot | THS 板块行情 |
| `mid_sector_tdx` | stg_tdx_member + stg_tencent_snapshot | TDX 板块行情 |
| `mid_stock_intraday` | stg_tencent_snapshot + 板块归属 | 个股宽表（含所属板块列表）|

### 元数据表

| 表名 | 内容 |
|:-----|:------|
| `meta_update_log` | 每次 ETL 步骤的记录（成功/失败/行数）|

---

## 运行模式

### 全量运行

```bash
conda run -n stock_agent python3 etl/etl_runner.py
```

流程：
1. `init_schema.sql` → 重建全部表结构
2. 并行取 DC/THS/TDX（3 线程）
3. 取股票基础信息
4. 取腾讯财经全量快照
5. 计算盘中板块行情（3 套）
6. 构建个股宽表

**耗时**：约 9 分钟（取决于 Tushare API 限流）

### 午间快照

```bash
conda run -n stock_agent python3 etl/etl_runner.py --snapshot-only
conda run -n stock_agent python3 etl/etl_runner.py --mid-only
```

- `--snapshot-only`：仅取腾讯快照（~15 秒）
- `--mid-only`：从已有快照计算中间层（~3 秒）

### 其他模式

```bash
# 仅建表
conda run -n stock_agent python3 etl/etl_runner.py --init-only

# 仅股票基础信息
conda run -n stock_agent python3 etl/etl_runner.py --stock-basic-only
```

### 交易日包装

```bash
# 自动判断交易日，非交易日跳过
/bin/bash etl/run_if_trading_day.sh              # 全量
/bin/bash etl/run_if_trading_day.sh --snapshot-only  # 快照
/bin/bash etl/run_if_trading_day.sh --mid-only       # 中间层
```

---

## 失败重试机制

### 级别一：API 调用级重试（`_safe_api_call`）

Tushare 接口发生 **频率超限** 时自动重试，最多 5 次：

| 重试次数 | 等待时间 |
|:---------|:---------|
| 1 | 30s |
| 2 | 60s |
| 3 | 90s |
| 4 | 120s |
| 5 | 120s |

其他异常（网络超时、数据为空）**不重试**，直接返回 `None` 跳过。

### 级别二：脚本级重试（`run_if_trading_day.sh`）

```bash
# 流程: 首次运行 → 失败 → 等 60s → 重试一次
```

| 结果 | 行为 |
|:-----|:------|
| 首次运行成功 | 正常结束 |
| 首次失败 | 写 `error_log` 表（`level=WARNING`），等 60s 重试 |
| 重试成功 | 正常结束 |
| 重试仍失败 | 写 `error_log` 表（`level=ERROR`），退出码非 0 |

> **error_log 写入加固**（2026-07-31）：`_log_error` 带 30s 锁等待（DB 忙时不再静默失败）+ 最多 3 次重试；参数经环境变量传递，消息内含引号也不会破坏 SQL。每次写入结果（成功/失败及原因）记录到 `logs/etl_wrapper.log`，该文件同时记录包装脚本的 `[RUN]/[RETRY]/[FAIL]/[DONE]` 全程（脚本 stdout 走 cron 邮箱不可见，排查问题看此文件）。

### 级别三：Cron 级

下次定时触发自动重试（如 11:31 失败，明天 11:31 再试）。

---

## 数据库错误记录

ETL 失败时写入 `error_log` 表：

```sql
-- 查看当日 ETL 错误
SELECT id, timestamp, level, error_msg
FROM error_log
WHERE module = 'etl' AND created_at >= datetime('now', '-1 day')
ORDER BY id DESC;

-- 查看所有 ETL 警告（首次失败后恢复）
SELECT id, timestamp, error_msg
FROM error_log
WHERE module = 'etl' AND level = 'WARNING'
ORDER BY id DESC;
```

| 场景 | level | error_msg 示例 |
|:-----|:------|:--------------|
| 首次失败，即将重试 | `WARNING` | `ETL 首次失败 (args=--snapshot-only, exit=1)，即将重试` |
| 重试仍失败 | `ERROR` | `ETL 重试后仍失败 (args=--mid-only, exit=1)` |

---

## 定时任务

| cron | 模式 | 说明 |
|:----:|:-----|:------|
| `31 11 * * *` | `--snapshot-only && --mid-only` | 午间取盘中快照 + 计算中间层 |
| `0 18 * * *` | 全量 | 日终全量更新（板块成分 + 日行情 + 快照 + 中间层）|

11:31 的午间任务约 15 秒完成，有充足余量等待 11:40 的 commander 调度。

---

## 开发说明

### db_manager.py — 线程安全

```python
class DatabaseManager:
    def __init__(self, db_path=None):
        self._local = threading.local()  # 每个线程独立连接

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn
```

- 使用 `threading.local()` 避免多线程共享 SQLite 连接
- 启用 WAL 模式提升并发读写性能
- 提供 `get_conn()` 上下文管理器（自动提交/回滚）

### 令牌桶限流（`utils.py`）

```python
_API_BUCKET = TokenBucket(rate=8, burst=20)  # 每秒 8 次 + 突发 20 次
```

全局共享，所有 Tushare API 调用前 acquire()，避免触发频率限制。

### 数据源并行

DC/THS/TDX 在 `run_all()` 中通过 3 线程 `ThreadPoolExecutor` 并行取数。

### 新增数据源

1. 在 `init_schema.sql` 增加 `stg_` 表
2. 在 `etl_runner.py` 实现 `etl_xxx()` 函数
3. 在 `run_all()` 的 `sources` 列表注册
4. 如需盘中板块行情，在 `etl_mid_sector()` 添加 `_calc_sector_mid()` 调用
