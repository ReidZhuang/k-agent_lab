# 数据库设计 — 前端新增表

数据库位置：`/home/stockagent/project_space/database/report_market.db`

## 一、新增表概述

前端系统在原有数据库基础上新增了 4 张表，用于支持用户认证、股票池管理、收藏夹功能和股票基础信息缓存。

```
┌──────────┐       ┌────────────────┐       ┌──────────────────┐
│   user   │──1:N──│  stock_pool    │       │  stg_stock_basic │
└──────────┘       └────────────────┘       │ (Tushare 缓存)   │
       │                                     └──────────────────┘
       │
       │ 1:N
       ▼
┌──────────────────┐
│  user_favorite   │
└──────────────────┘
```

## 二、表结构

### 2.1 `user` — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|:----:|------|
| `id` | INTEGER | PK AUTOINCREMENT | 用户 ID |
| `username` | TEXT | NOT NULL UNIQUE | 用户名 |
| `password` | TEXT | NOT NULL | 密码哈希值（SHA256） |
| `created_at` | TEXT | DEFAULT now | 创建时间 |

**DDL：**
```sql
CREATE TABLE IF NOT EXISTS user (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
```

**设计说明：**
- 密码不存储明文，使用 `hashlib.sha256().hexdigest()` 哈希后存储
- 生产环境建议升级为 bcrypt 算法（`passlib.hash.bcrypt`）
- 用户由管理员通过命令行直接操作数据库创建/删除，前端无注册功能
- 默认初始用户：`admin` / `admin123`（首次启动时创建，可在 `init_default_users()` 中调整）

**插入用户：**
```python
from database import db
from auth import hash_password
db.create_user("用户名", hash_password("密码"))
```

**查询用户：**
```python
user = db.get_user_by_username("用户名")
# → {"id": 1, "username": "admin", "password": "hash..."}
```

### 2.2 `stock_pool` — 股票池表

| 字段 | 类型 | 约束 | 说明 |
|------|------|:----:|------|
| `id` | INTEGER | PK AUTOINCREMENT | 自增 ID |
| `user_id` | INTEGER | NOT NULL | 关联 `user.id` |
| `ts_code` | TEXT | NOT NULL | TS 股票代码（如 300750.SZ） |
| `stock_name` | TEXT | NOT NULL | 股票名称 |
| `created_at` | TEXT | DEFAULT now | 加入时间 |

**DDL：**
```sql
CREATE TABLE IF NOT EXISTS stock_pool (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    ts_code     TEXT NOT NULL,
    stock_name  TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, ts_code)
);
```

**设计说明：**
- `UNIQUE(user_id, ts_code)` 防止同一用户重复添加同一只股票
- `user_id` 为逻辑外键，未设置物理外键约束（SQLite 默认不强制外键）
- 股票名称冗余存储，避免每次查询都需要关联 `stg_stock_basic` 表
- 每日行情数据不落库，前端每次查看时从 Tushare 实时拉取

### 2.3 `user_favorite` — 收藏夹表

| 字段 | 类型 | 约束 | 说明 |
|------|------|:----:|------|
| `id` | INTEGER | PK AUTOINCREMENT | 自增 ID |
| `user_id` | INTEGER | NOT NULL | 关联 `user.id` |
| `file_path` | TEXT | NOT NULL | 文件路径（相对 user_001/） |
| `file_name` | TEXT | NOT NULL | 文件名（含扩展名） |
| `created_at` | TEXT | DEFAULT now | 收藏时间 |

**DDL：**
```sql
CREATE TABLE IF NOT EXISTS user_favorite (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    file_path   TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, file_path)
);
```

**设计说明：**
- `UNIQUE(user_id, file_path)` 防止同一用户重复收藏同一文件
- `file_name` 冗余存储，方便在收藏夹列表直接显示，无需读文件系统
- 取消收藏使用 `DELETE`，不做软删除

### 2.4 `stg_stock_basic` — 股票基础信息缓存

| 字段 | 类型 | 约束 | 说明 |
|------|------|:----:|------|
| `ts_code` | TEXT | PK | TS 代码（如 300750.SZ） |
| `symbol` | TEXT | | 6 位数字代码 |
| `name` | TEXT | | 股票名称 |
| `area` | TEXT | | 地域 |
| `industry` | TEXT | | 所属行业 |
| `market` | TEXT | | 市场类型（主板/创业板/科创板/CDR） |
| `list_date` | TEXT | | 上市日期 YYYYMMDD |
| `update_date` | TEXT | | 最后刷新日期 YYYYMMDD |

**DDL：**
```sql
CREATE TABLE IF NOT EXISTS stg_stock_basic (
    ts_code     TEXT PRIMARY KEY,
    symbol      TEXT,
    name        TEXT,
    area        TEXT,
    industry    TEXT,
    market      TEXT,
    list_date   TEXT,
    update_date TEXT
);
```

**设计说明：**
- 此表用于缓存 Tushare `stock_basic` 接口的全市场股票列表
- 每日首次查询股票时自动检查 `update_date`，若非今天则刷新
- 全量替换策略：刷新时先 `DELETE` 再 `INSERT`（约 5000+ 行）
- 刷新在后台线程进行，不阻塞 API 响应

**后端代码：** `stock_api.py` 中的 `ensure_stock_basic_refreshed()` 函数

## 三、各表数据量参考

| 表名 | 行数 | 增长 |
|------|:----:|:----:|
| `user` | 2+（手动添加） | 极少 |
| `stock_pool` | 按用户 × 自选数 | 低 |
| `user_favorite` | 按用户 × 收藏数 | 低 |
| `stg_stock_basic` | ~5,300 行 | 每日全量替换 |

## 四、与其他模块的关系

```
┌─────────────────────────────────────────────────────┐
│                 前端 FastAPI 服务                     │
│                                                      │
│  /api/stock/search ──→ stg_stock_basic（查询）       │
│                        ↑ 每日首次自动刷新             │
│  /api/stock/pool ────→ stock_pool（CRUD）            │
│  /api/auth/login ────→ user（验证）                  │
│  /api/explorer/fav ──→ user_favorite（CRUD）        │
│                                                      │
│  所有 Tushare 行情数据不落库，实时拉取                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                Office 报告生成系统                    │
│                                                      │
│  log_office_error() ──→ error_log（写入）            │
│  所有运行中错误的记录                                  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              Commander 定时调度系统                  │
│                                                      │
│  log_error_to_db() ──→ error_log（写入）             │
│  定时任务中报告生成的异常记录                          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              ETL 数据管道                            │
│                                                      │
│  run_if_trading_day.sh ──→ error_log（写入）          │
│  数据采集失败的异常记录（重试后仍失败时写入）           │
└─────────────────────────────────────────────────────┘
```

## 五、设计决策

### 5.1 为何行情数据不落库

- 股票池展示的是**昨日**行情，Tushare `daily` 接口一次查询即可获取全量
- 减少本地存储和 ETL 维护成本
- 数据始终最新，无需担心缓存过期

### 5.2 为何使用 SHA256 而非 bcrypt

- 当前为开发阶段，SHA256 实现简单且无需额外依赖
- 生产部署前建议切换到 bcrypt：
  ```python
  from passlib.hash import bcrypt
  hash = bcrypt.hash(password)
  bcrypt.verify(password, hash)
  ```

### 5.3 Token 为何存在内存而非 JWT

- 内存 Token 实现简单，服务重启后所有 Token 自动失效（安全性）
- 分布式部署时需改为 Redis 共享或 JWT 方案
- Token 有效期 24 小时

## 六、error_log 统一错误表

`error_log` 是所有模块的共用错误记录表，通过 `service_name` 字段区分来源：

| service_name | 写入方 | 说明 |
|:-------------|:-------|:------|
| `office` | Office writer/middleman/reporter | 报告生成过程的异常 |
| `commander` | Commander 定时调度 | 定时任务中的报告失败/分发失败 |
| `etl` | ETL 数据管道 | 数据采集失败（重试后仍失败） |
| `mail_tower_api` | mail_tower 新闻引擎 | 搜索/正文提取异常 |

```sql
-- 查所有模块当日错误
SELECT id, timestamp, service_name, function, level, substring(error_msg, 1, 80) as msg
FROM error_log
WHERE created_at >= datetime('now', '-1 day')
ORDER BY timestamp DESC;

-- 按模块统计
SELECT service_name, level, COUNT(*) as cnt
FROM error_log
GROUP BY service_name, level
ORDER BY cnt DESC;
```

## 七、常见查询

```sql
-- 查看某用户的股票池
SELECT s.ts_code, s.stock_name, s.created_at
FROM stock_pool s
JOIN user u ON s.user_id = u.id
WHERE u.username = 'zgx'
ORDER BY s.created_at;

-- 查看所有用户的收藏
SELECT u.username, f.file_name, f.created_at
FROM user_favorite f
JOIN user u ON f.user_id = u.id
ORDER BY u.username, f.created_at;

-- 查看股票基础信息缓存时间
SELECT MIN(update_date) as earliest, MAX(update_date) as latest
FROM stg_stock_basic;

-- 搜索股票
SELECT ts_code, name, industry
FROM stg_stock_basic
WHERE name LIKE '%宁德%';
```
