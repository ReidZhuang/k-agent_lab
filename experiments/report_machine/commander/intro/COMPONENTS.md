# Commander 模块开发手册

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                scheduled_task.py                 │
│  定时任务编排（交易日判定→健康检测→查池→生成→分发）│
└───────────────┬─────────────────────────────────┘
                │ 调用
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│health  │ │service │ │ 外部   │
│_check  │→│_manager│ │ Writer │
│.py     │ │.py     │ │ API    │
└────────┘ └────────┘ └────────┘
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
     mail_   middle-  reporter
     tower    man
```

## service_manager.py — 服务生命周期管理

### 功能

- 通过端口 PID 发现（`lsof` → `ss` 兜底）
- 进程验证（`/proc/{pid}/cwd` + cmdline）
- 优雅停止（SIGTERM → SIGKILL）
- 依赖顺序启动（`SERVICE_START_ORDER`）
- 单服务/全量启停

### 核心函数

| 函数 | 说明 |
|:-----|:------|
| `find_pids_on_port(port)` | 查找端口上的所有 PID |
| `kill_processes(pids, force)` | 杀进程（默认 SIGTERM，force 加 SIGKILL）|
| `start_service(svc)` | 启动单个服务（子进程）|
| `stop_service(svc)` | 停止单个服务 |
| `restart_service(svc)` | 重启单个服务 |
| `check_service_health(svc, timeout)` | HTTP 健康检查（含 expected field 匹配）|
| `start_all_services()` | 按依赖顺序启动全部 |
| `stop_all_services()` | 逆序停止全部 |
| `get_service_configs(config)` | 从 dict 解析 ServiceConfig 列表 |

### ServiceConfig

```python
@dataclass
class ServiceConfig:
    name: str        # 服务名
    port: int        # 端口号
    cwd: str         # 工作目录
    cmd: str         # 启动命令
    health_url: str  # 健康检查 URL
    health_field: str = ""     # 响应字段名
    health_expected: str = ""  # 期望字段值
```

### 依赖顺序

```python
SERVICE_START_ORDER = ["mail_tower", "middleman", "reporter", "writer"]
SERVICE_STOP_ORDER  = ["writer", "reporter", "middleman", "mail_tower"]
```

### 扩展：添加新服务

1. 在 `config.yaml` `services` 段添加配置
2. 在 `SERVICE_START_ORDER` 适当位置插入服务名
3. 在 `health_check.py` `_is_expected_process()` 中添加识别规则

---

## health_check.py — 三级健康检测（独立模块）

### 设计原则

- **独立可调用**：可作为库函数、CLI、子进程三种方式使用
- **分级别**：L0 清理 → L1 检测 → L2 局部恢复 → L3 全体恢复
- **幂等**：多次执行不产生副作用
- **可配置**：所有检测目标来自 config.yaml

### 检测级别详解

#### Level 0 — 端口归属校验

对每个服务的端口：
1. 列出所有监听进程（PID）
2. 用 `/proc/{pid}/cwd` 验证工作目录是否匹配
3. 不匹配 → 按 cmdline + 服务特征二次判断
4. 仍不匹配 → 视为僵尸/错位进程 → kill
5. 端口无合法进程 → 标记 L0 失败

**意图**：清理启动残留、端口劫持、僵尸进程，避免 L1 误报。

#### Level 1 — 健康检测

检测项：
| 组件 | 检测方式 | 通过条件 |
|:-----|:---------|:---------|
| HTTP 服务 | `requests.get(health_url)` | HTTP 200 + 字段匹配（如有配置）|
| Neo4j | `MATCH (s:Stock) RETURN count(s)` | 返回 > 0 |
| SQLite | `SELECT 1 FROM stock_pool` | 可执行 |
| TradeCalendar | `is_trading_day(today)` | 不抛异常 |

#### Level 2 — 定向重启

- 只重启 L1 失败的 HTTP 服务
- Neo4j / SQLite / TradeCalendar 不重启（基础设施）
- 重启后重新做 L1 检测

#### Level 3 — 全体重启兜底

- 杀全部 → 依赖顺序启动全部
- 对所有 HTTP 服务重新 L1 检测
- Neo4j / SQLite / TradeCalendar 保持原结果

### HealthCheckResult

```python
@dataclass
class HealthCheckResult:
    ok: bool                    # 全部通过？
    timestamp: str              # 检测时间
    elapsed: float              # 耗时
    components: dict[str, ComponentResult]
    level3_triggered: bool      # 是否触发 L3
    error: str                  # 异常信息
```

### 扩展：添加检测项

1. 在 `config.yaml` 的 `services` 中添加配置
2. 在 `health_check.py` 的 `_level1_health_check()` 中添加检测调用
3. 在 `_is_expected_process()` 中添加识别规则
4. 在 `SERVICE_START_ORDER` 中注册顺序

---

## scheduled_task.py — 定时任务编排

### 完整流程

```
┌─ 1. 交易日判定 ─────────────────────────────┐
│  is_trading_day() → 非交易日 → 写摘要 → 退出   │
├─ 2. 健康检测 ────────────────────────────────┤
│  HealthChecker.run() → 失败 → 写摘要 → 退出   │
├─ 3. 清理旧输出 ──────────────────────────────┤
│  clean_old_output() → 删非今日报告文件         │
├─ 4. 查股票池 ────────────────────────────────┤
│  query_stock_pools() + deduplicate_stocks()  │
├─ 5. 第一批 ──────────────────────────────────┤
│  call_writer() → POST Writer API             │
├─ 6. 第二批(重试) ────────────────────────────┤
│  只重试第一批失败 → 记录最终失败到 error_log   │
├─ 7. 分发 ────────────────────────────────────┤
│  distribute_reports() → output/ → user/      │
├─ 8. 摘要 ────────────────────────────────────┤
│  write_task_log() + print_summary_table()    │
└──────────────────────────────────────────────┘
```

### 去重策略

```python
# 多用户同持一只股票时，只调一次 Writer API
# 生成的文件同时分发到每个用户的目录
用户 A 持有: [茅台, 五粮液]
用户 B 持有: [茅台, 泸州老窖]
→ 去重后调 Writer: [茅台, 五粮液, 泸州老窖]
→ 分发: A→{茅台, 五粮液}, B→{茅台, 泸州老窖}
```

### 错误记录

写入 `error_log` 表的场景：

| 场景 | function | error_code |
|:-----|:---------|:-----------|
| 第一批生成失败 | `batch1_writer` | `BATCH1_FAILED` |
| 第二批仍失败 | `batch2_writer` | `BATCH2_FAILED` |
| 报告文件不存在 | `distribute_reports` | `REPORT_FILE_NOT_FOUND` |
| 复制报告到用户失败 | `distribute_reports` | `REPORT_COPY_FAILED` |

### 扩展：添加新用户

1. 在 `front/config/report_users.yaml` 的 `report_users` 列表中添加用户名
2. 在 SQLite `user` 表中确认用户存在
3. 在 `stock_pool` 表中为用户配置股票

---

## test_e2e.py — 端到端测试

### 测试点（20 项）

1. 交易日判定
2. SQLite 可读
3. 各服务 HTTP 可达（mail_tower/middleman/reporter/writer）
4. 健康检测
5. 清空 output
6. 股票池查询
7. Writer API 调用
8. 各股 output 文件验证
9. 分发到用户目录
10. 用户目录完整性

### 注意

- 默认跳过 L2/L3（不重启服务），`--full-hc` 开启
- 清理时删除 output 中**整个股票文件夹**（`shutil.rmtree`），非仅 .md 文件
- 不清理 `user/` 目录

---

## 配置文件 — config.yaml

所有配置集中管理。主要段：

| 段 | 内容 |
|:---|:-----|
| `commander` | 运行参数（query、路径、日期格式）|
| `services` | 4 个服务的端口、命令、健康检测 |
| `database` | SQLite + Neo4j 连接 |
