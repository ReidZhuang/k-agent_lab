# Commander — 定时报告调度系统

## 概述

Commander 是报告机器的**定时任务调度与运维系统**，负责：
- 每日 11:40 自动触发午间报告生成
- 三级健康检测（端口校验 → HTTP 检测 → 服务重启）
- 服务生命周期管理（按依赖顺序启停）
- 多用户股票池去重与报告分发

```
 cron: 11:40
    │
    ▼
┌─────────────────────┐
│  scheduled_task.py  │  ← 主入口
│  交易日判定 →         │
│  健康检测 →           │
│  查股票池 →           │
│  去重 →              │
│  调 Writer API →     │
│  重试失败 →           │
│  分发报告 →           │
│  写任务摘要            │
└─────────┬───────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐  ┌────────┐
│ health │  │service │
│_check  │  │_manager│
│ .py    │  │ .py    │
└────────┘  └────────┘
```

## 目录结构

```
commander/
├── intro/               # 文档
│   ├── README.md        # 本文件
│   ├── USAGE.md         # 运维使用指南
│   └── COMPONENTS.md    # 模块开发手册
├── config.yaml          # 核心配置
├── service_manager.py   # 服务生命周期管理
├── health_check.py      # 三级健康检测（独立模块）
├── scheduled_task.py    # 定时任务主入口
├── test_e2e.py          # 端到端测试
└── __init__.py          # 包标记
```

## 外部依赖

| 依赖 | 路径/地址 | 说明 |
|:-----|:----------|:-----|
| SQLite | `/home/.../database/report_market.db` | 用户/股票池/错误日志 |
| Neo4j | `bolt://localhost:7687` | 知识图谱（DataField 数据源）|
| Mail Tower | `localhost:8300` | 新闻资讯引擎 |
| Middleman | `localhost:8311` | 搜索中间层 |
| Reporter | `localhost:8312` | 报告生成 LLM 服务 |
| Writer | `localhost:8310` | 报告入口 API |
| TradeCalendar | `data_fetch/midday/trade_calendar.py` | 交易日历 |

## 定时任务

| cron | 任务 | 脚本 |
|:----:|:----|:-----|
| `40 11 * * *` | Commander 定时报告 | `commander/scheduled_task.py` |
| `31 11 * * *` | ETL 午间快照 + 中间层 | `etl/run_if_trading_day.sh --snapshot-only && ... --mid-only` |
| `0 18 * * *` | ETL 全量数据 | `etl/run_if_trading_day.sh` |

详见 [USAGE.md](USAGE.md)。
