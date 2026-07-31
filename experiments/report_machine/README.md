# Report Machine — 股票午间报告自动生成系统

## 系统架构

```
                         用户
                          │
                     ┌────▼────┐
                     │ Frontend │
                     │(待开发)  │
                     └─────────┘
                          │
┌─────────────────────────┼──────────────────────────┐
│  Commander 调度层        │                          │
│  定时触发生成任务          │                          │
│  健康检测 + 服务管理      │                          │
└─────────────────────────┼──────────────────────────┘
                          │ POST /api/v1/report
                          ▼
┌─────────────────────────────────────────────────────┐
│  Office 报告生成引擎                                  │
│  ┌────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Writer │→│ Middleman │→│ Reporter │             │
│  │ :8310  │  │ :8311     │  │ :8312    │             │
│  └────────┘  └────┬─────┘  └──────────┘             │
│                   │                                  │
│             ┌─────▼──────┐                           │
│             │ Mail Tower │                           │
│             │ :8300      │                           │
│             └────────────┘                           │
│  ┌────────────────────────────────────────────┐      │
│  │ DataField: Neo4j・SQLite・ETL               │      │
│  └────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

## 组件概览

| 模块 | 目录 | 说明 |
|:-----|:-----|:------|
| **Commander** | `commander/` | 定时任务调度、健康检测、服务管理 |
| **Office** | `office/` | Writer/Middleman/Reporter 报告生成引擎 |
| **ETL** | `etl/` | 数据管道（从多数据源采集股票数据）|
| **Mail Tower** | 独立项目 | 新闻资讯引擎（sinafin/baidufin/thsfin/juchao/qnainfo）|
| **Data Fetch** | `data_fetch/` | 交易日历、盘中取数脚本 |
| **Frontend** | 独立项目 | Web 前端（展示报告）|

## 定时任务

| 时间 | 任务 | 说明 |
|:----:|:-----|:------|
| `11:31` | [ETL 午间快照](etl/intro/README.md) | 腾讯快照 + 中间层计算（~15s）|
| `11:40` | [Commander 报告生成](commander/intro/README.md) | 检查交易日 → 健康检测 → 生成分发 |
| `18:00` | [ETL 全量更新](etl/intro/README.md) | 板块成分 + 日行情 + 快照 + 中间层（~9min）|

## 文档索引

### Commander（调度层）
- [README](commander/intro/README.md) — 架构总览
- [USAGE.md](commander/intro/USAGE.md) — 运维使用指南
- [COMPONENTS.md](commander/intro/COMPONENTS.md) — 模块开发手册

### Office（报告生成）
- [README](office/intro/README.md) — 架构与使用
- [LOGGING.md](office/intro/LOGGING.md) — 日志记录清单
- [error_codes.md](office/intro/error_codes.md) — 错误代码

### ETL（数据管道）
- [README](etl/intro/README.md) — 数据模型与运维

## 数据库

- **SQLite**: `/home/stockagent/project_space/database/report_market.db`
  - `user` / `stock_pool` — 用户与股票池
  - `stg_*` / `mid_*` — ETL 数据
  - `error_log` — 统一异常记录（service: office/commander/etl）
  - `meta_update_log` — ETL 更新日志
- **Neo4j**: `bolt://localhost:7687` — 知识图谱

## 环境

- Python 3.10+
- Conda 环境: `stock_agent`
- 路径: `/home/stockagent/miniforge3/envs/stock_agent/bin/python`
- DeepSeek API Key: `DEEPSEEK_API_KEY` 环境变量
- Tushare API Token: `tushare_token.txt`
