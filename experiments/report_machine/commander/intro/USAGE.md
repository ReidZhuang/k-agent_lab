# Commander 运维使用指南

## 快速启动

所有 commander 脚本必须使用 conda 环境的 Python，不能用系统 Python：

```bash
# 正确
/home/stockagent/miniforge3/envs/stock_agent/bin/python commander/scheduled_task.py

# 或
cd /home/stockagent/project_space/research/experiments/report_machine
conda run -n stock_agent python3 commander/scheduled_task.py
```

## 定时任务管理

### 查看当前 crontab

```bash
crontab -l
```

### Commander 定时任务

```
40 11 * * * cd /home/stockagent/project_space/research/experiments/report_machine && /home/stockagent/miniforge3/bin/conda run -n stock_agent python3 commander/scheduled_task.py > /tmp/commander_cron.log 2>&1
```

- 每天 11:40 触发（交易日自动判断，非交易日跳过）
- 日志输出到 `/tmp/commander_cron.log`（cron 自身输出）
- 任务详细日志写到 `office/log/`

### 手动触发

```bash
# 完整运行
conda run -n stock_agent python3 commander/scheduled_task.py

# 预览模式（不调 Writer，不生成报告）
conda run -n stock_agent python3 commander/scheduled_task.py --dry-run

# 指定配置文件
conda run -n stock_agent python3 commander/scheduled_task.py -c /path/to/config.yaml
```

## 服务管理

### 查看服务状态

```bash
conda run -n stock_agent python3 commander/service_manager.py status
```

各服务端口、健康 URL 见 `config.yaml` `services` 段。

### 启动/停止/重启

```bash
# 全量操作（依赖顺序启动，逆序停止）
conda run -n stock_agent python3 commander/service_manager.py start
conda run -n stock_agent python3 commander/service_manager.py stop
conda run -n stock_agent python3 commander/service_manager.py restart

# 单个服务
conda run -n stock_agent python3 commander/service_manager.py restart --service writer
```

### 启动顺序（由 SERVICE_START_ORDER 定义）

```
mail_tower (8300) → middleman (8311) → reporter (8312) → writer (8310)
```

停止顺序相反。

## 健康检测

### 独立运行

```bash
# 完整三级检测（含服务重启）
conda run -n stock_agent python -m commander.health_check

# 静默模式（只输出一行摘要）
conda run -n stock_agent python -m commander.health_check --quiet
```

### 检测级别

| 级别 | 内容 | 触发 |
|:----:|:-----|:-----|
| L0 | 端口归属校验（清理残留/僵尸进程） | 始终执行 |
| L1 | HTTP 健康检测 + Neo4j + SQLite + 交易日历 | 始终执行 |
| L2 | 定向重启失败的服务 | 有组件 L1 失败 |
| L3 | 全体重启兜底 + 重新检测 | L2 后仍有失败 |

### 作为库调用

```python
from commander.health_check import HealthChecker

hc = HealthChecker()
result = hc.run()
if not result.ok:
    print(result.summary)
    sys.exit(1)
```

## 端到端测试

```bash
conda run -n stock_agent python3 commander/test_e2e.py

# 带完整健康检测（含重启）
conda run -n stock_agent python3 commander/test_e2e.py --full-hc
```

测试流程：
1. 前置检查（交易日、SQLite、各服务 HTTP 可达）
2. 健康检测（默认 L0+L1，`--full-hc` 含 L2+L3）
3. 清空 `office/output/` 中的所有报告目录
4. 查股票池（从 SQLite 读取配置用户的股票）
5. 调 Writer API 生成报告
6. 验证 output 文件
7. 分发到用户目录
8. 验证用户目录文件

## 配置说明

### `commander/config.yaml`

```yaml
commander:
  query: "生成该股票的午间收盘分析报告"     # Writer API 的 query 参数
  date_format: "%Y%m%d"                     # 日期格式
  log_dir: /path/to/office/log              # 任务日志目录
  output_dir: /path/to/office/output        # 报告输出目录
  user_base_dir: /path/to/user              # 用户目录根
  users_config: /path/to/report_users.yaml  # 用户列表

services:
  mail_tower:
    port: 8300
    cwd: /path/to/mail_tower
    cmd: "conda run -n stock_agent uvicorn ..."
    health_url: "http://localhost:8300/"
    health_expected: "bot_search API"
  middleman:
    port: 8311
    ...
  reporter:
    port: 8312
    ...
  writer:
    port: 8310
    ...

database:
  sqlite_path: /path/to/report_market.db
  neo4j_uri: bolt://localhost:7687
  neo4j_user: neo4j
  neo4j_password: kg_route_2026
```

### 用户配置 (`front/config/report_users.yaml`)

```yaml
report_users:
  - zgx
  - zqt
```

## 输出与日志

| 内容 | 路径 | 格式 |
|:-----|:-----|:-----|
| 运行日志 | `office/log/task_{YYYYMMDD}.log` | 文本 |
| 摘要日志 | `office/log/summary_{YYYYMMDD}.json` | JSON |
| 临时报告 | `office/output/{stock_name}/{date}_{stock_name}_午间收盘报告.md` | Markdown |
| 用户报告 | `user/{username}/{stock_name}/{date}_{stock_name}_午间收盘报告.md` | Markdown |
| Cron 日志 | `/tmp/commander_cron.log` | 文本 |
| 错误记录 | SQLite `error_log` 表 (`service_name=commander`) | 结构化 |

## 错误诊断

### 常见问题

| 现象 | 可能原因 | 排查 |
|:-----|:---------|:-----|
| 报告未生成 | 非交易日 | 检查 `office/log/summary_*.json` 的 status |
| 服务不可用 | 端口被占/进程挂掉 | 运行健康检测 |
| 股票池为空 | 数据库无用户 | 检查 `report_users.yaml` 和 `stock_pool` 表 |
| 报告数据缺失 | ETL 未及时运行 | 检查 ETL 日志 `etl/logs/etl_runner.log` |
| Cron 未触发 | crontab 异常 | 检查 `crontab -l` 和 `/tmp/commander_cron.log` |

### 查询错误日志

```sql
-- Commander 当日错误
SELECT id, timestamp, function, stock_name, error_msg
FROM error_log
WHERE service_name = 'commander'
  AND created_at >= datetime('now', '-1 day')
ORDER BY id DESC;
```
