# 股票关键词知识图谱 — 开发与运维文档

> 版本: v1.0 | 最后更新: 2026-07-21

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [数据源与 ETL 管道](#3-数据源与-etl-管道)
4. [关键词文件解析](#4-关键词文件解析)
5. [Neo4j 图数据库设计](#5-neo4j-图数据库设计)
6. [匹配算法](#6-匹配算法)
7. [模块功能说明](#7-模块功能说明)
8. [部署与配置](#8-部署与配置)
9. [日常运维](#9-日常运维)
10. [注意事项与常见问题](#10-注意事项与常见问题)
11. [附录：实时行情快照](#11-附录实时行情快照)

---

## 1. 项目概述

### 1.1 业务目标

构建 A 股个股的**关键词知识图谱**，实现「新闻/资讯 → 相关股票」的智能路由匹配。核心流程：

```
关键词文件(kw_tree)  →  板块→关键词映射(SQLite)
                                          ↓
股票板块归属表(Tushare)  →  个股→关键词关系  →  Neo4j 图数据库
                                          ↓
              资讯文章  →  关键词匹配  →  匹配度评分推送给相关股票
```

### 1.2 关键数据

| 指标 | 当前值 | 说明 |
|------|:------:|------|
| 个股节点 | 5,631 | 全市场覆盖 |
| 关键词节点 | 3,032 | 来自 THS/DC/TDX 三源 |
| 跨类别关键词(boosted) | 46 | 同时属于概念+行业的关键词 |
| 个股→关键词关系 | ~48.5 万 | 平均每个股 ~86 个关键词 |
| 关键词来源板块 | 1,970 | DC 949 + THS 539 + TDX 482 |
| 匹配算法 | 行业×1 + boosted×2 + 地区×1/3 | score = min(1.0, m/4) |

---

## 2. 系统架构

### 2.1 组件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    外部数据源                                  │
│  Tushare Pro API  │  keyword_tree_final_v2.md  │  财联社快讯    │
└──────┬────────────────────┬──────────────────────┬───────────┘
       │                    │                      │
       ▼                    ▼                      ▼
┌──────────────┐  ┌─────────────────┐  ┌────────────────────┐
│  ETL Pipeline │  │  kg_loader.py   │  │  kg_matcher.py     │
│  etl_runner.py│  │  (解析关键词    │  │  (资讯→股票匹配)   │
│  (取板块成分) │  │  写入 SQLite)   │  │                    │
└──────┬───────┘  └───────┬─────────┘  └────────┬───────────┘
       │                  │                     │
       ▼                  ▼                     │
┌─────────────────────────────────────────────┐ │
│          SQLite (report_market.db)           │ │
│  ┌────────────────┐  ┌───────────────────┐  │ │
│  │ stg_{dc/ths/   │  │ meta_sector_      │  │ │
│  │ tdx}_{member/  │  │ keywords          │  │ │
│  │ index/daily}   │  │ (板块→关键词)     │  │ │
│  └────────────────┘  └───────────────────┘  │ │
└───────────────────┬─────────────────────────┘ │
                    │                           │
                    ▼                           │
┌──────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────┐   │
│  │ kg_builder.py│→ │   Neo4j 图数据库      │   │
│  │ (全量构建)    │  │  (Stock-HAS_KEY→     │   │
│  │ kg_incremen- │  │   Keyword)            │   │
│  │ tal.py(增量) │  │                     │   │
│  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 2.2 文件结构

```
knowledge_graph/
├── config.py                  # 配置中心（DB 路径、Neo4j 凭证）
├── kg_loader.py               # 关键词文件解析 → SQLite
├── kg_builder.py              # SQLite → Neo4j 全量构建
├── kg_incremental.py          # SQLite → Neo4j 增量更新
├── kg_matcher.py              # 资讯→股票匹配算法
├── kg_query.py                # Neo4j 查询接口
├── test_keywords_output.md    # 三只股票的全量关键词示例
├── KG_DEVELOPMENT_GUIDE.md    # 本开发文档
└── results/
    └── kg_test_report_20260721.md  # 完整测试报告
```

---

## 3. 数据源与 ETL 管道

### 3.1 数据源一览

| 数据源 | 接口 | 说明 | 限流 |
|--------|------|------|:----:|
| Tushare Pro | `PRO.ths_index/member/daily` | 同花顺板块体系（7 类） | 500次/分 |
| Tushare Pro | `PRO.dc_index/member/daily` | 东方财富板块体系（3 类） | 500次/分 |
| Tushare Pro | `PRO.tdx_index/member/daily` | 通达信板块体系（4 类） | 500次/分 |
| 腾讯财经 | `qt.gtimg.cn` | A股全量实时行情快照 | 无硬限制 |

### 3.2 ETL 调度 (`etl_runner.py`)

每日运行一次，3 个线程并行拉取 DC/THS/TDX 的板块数据：

```
etl_dc()   ───────┐
etl_ths()  ───────┤  ── ThreadPoolExecutor(3)
etl_tdx()  ───────┘
                      └── etl_tencent_snapshot()  →  stg_tencent_snapshot
                      └── etl_mid_sector()        →  mid_sector_{dc,ths,tdx}
                      └── etl_mid_stock_intraday() →  mid_stock_intraday
```

**限流机制**: 三个线程共享一个 `TokenBucket(rate=8, burst=20)` 令牌桶，总调用速率 ≤ 8次/秒。

### 3.3 关键表结构

```sql
-- 板块→关键词映射（知识图谱核心元数据）
CREATE TABLE meta_sector_keywords (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source   TEXT NOT NULL,       -- THS / DC / TDX
    ts_code  TEXT NOT NULL,       -- 板块代码 如 885311.TI
    name     TEXT,                -- 板块名称
    category TEXT NOT NULL,       -- 概念 / 行业 / 地区
    keywords TEXT NOT NULL,       -- 分号分隔的关键词列表
    UNIQUE(source, ts_code)
);

-- 个股板块归属（三张结构相同）
CREATE TABLE stg_dc_member (
    trade_date TEXT,
    ts_code    TEXT,    -- 板块代码
    con_code   TEXT,    -- 个股代码
    con_name   TEXT     -- 个股名称
);
```

---

## 4. 关键词文件解析

### 4.1 关键词文件格式

文件：`keyword_tree_final_v2.md`（1,970 个板块）

```
## 一、同花顺（THS）板块分类          ← 章: 确定数据源

### 1. N — 概念指数（412个）          ← 节: 确定分类

- `885311.TI` 智能电网;智能电力;电网;电力自动化  ← 板块代码 + 名称 + 关键词

### 2. I — 行业指数（36个）

- `885431.TI` 新能源汽车;新能源车;电动车;电动汽车

### 3. R — 地域指数（31个）

- `885645.TI` 福建                      ← 地区类无关键词，板块名即关键词
```

### 4.2 解析规则 (`kg_loader.py`)

| 章节标题关键词 | 映射类别 | 说明 |
|---------------|:--------:|------|
| `概念指数` 或 `概念板块` | 概念 | 纯概念标签，匹配时不直接使用 |
| `行业指数` 或 `行业板块` | 行业 | 行业关键词，匹配权重 ×1 |
| `地域指数` 或 `地域板块` 或 `地区板块` | 地区 | 地区关键词，匹配权重 ×1/3 |
| `同花顺` | THS | 数据源标记 |
| `东方财富` | DC | 数据源标记 |
| `通达信` | TDX | 数据源标记 |

### 4.3 关键词去重策略

**文件级去重**：解析时对每个板块内的关键词列表做去重（以板块名称为第一关键词，避免后续关键词与其重复）。

**图级去重**：在 `kg_builder.py` 的 `_build_stock_keywords()` 中，同一只股票通过不同板块获得相同关键词时，自动合并分类属性。例如：

> 股票 A 通过 THS "半导体"板块获得关键词"芯片"(概念)，再通过 DC "芯片设计"板块也获得"芯片"(行业)
> → 最终关键词"芯片"的 categories 合并为 `["概念", "行业"]`
> → 自动被标记为 `boosted = True`（跨类别）

### 4.4 运行方式

```bash
conda run -n stock_agent python3 kg_loader.py
```

输出：
- 解析板块数（当前 ~1,970）
- 各数据源分布（DC 949 / THS 539 / TDX 482）
- 各分类分布（概念 / 行业 / 地区）
- 写入 SQLite 行数

---

## 5. Neo4j 图数据库设计

### 5.1 图模型

```
(Stock:Stock {code, name})─[:HAS_KEY]─(Keyword:Keyword {keyword, categories, boosted})
```

### 5.2 节点属性

**Stock 节点**

| 属性 | 类型 | 示例 | 说明 |
|------|:----:|------|------|
| `code` | string | `600519.SH` | 唯一标识，带交易所后缀 |
| `name` | string | `贵州茅台` | 股票名称 |

**Keyword 节点**

| 属性 | 类型 | 示例 | 说明 |
|------|:----:|------|------|
| `keyword` | string | `半导体` | 唯一标识 |
| `categories` | list[string] | `["概念", "行业"]` | 所属分类列表 |
| `boosted` | boolean | `true` | 跨类别标记（概念+行业同时存在 = true） |

### 5.3 唯一约束

Neo4j 中存在两条唯一约束：

```
CREATE CONSTRAINT FOR (s:Stock)  REQUIRE s.code   IS UNIQUE
CREATE CONSTRAINT FOR (k:Keyword) REQUIRE k.keyword IS UNIQUE
```

### 5.4 构建方式

**全量重建**（首次或需要完全刷新时）：

```bash
python3 kg_builder.py
```

执行步骤：
1. 从 SQLite 读取 `meta_sector_keywords`（板块→关键词）和 `stg_{dc/ths/tdx}_member`（个股→板块）
2. 构建个股→关键词映射，自动去重合并分类
3. 清空 Neo4j 图谱
4. 创建唯一约束
5. 批量写入（每批 500 个股）

**增量更新**（日常新增大股东/新股时）：

```bash
python3 kg_incremental.py
```

执行步骤：
1. 对比 Neo4j 已有股票 vs SQLite 中全部股票
2. 找出差异股票（新出现的）
3. 查询新股票所属板块
4. 构建关键词并写入

---

## 6. 匹配算法

### 6.1 核心公式

只使用**行业 + 地区**关键词参与匹配（纯"概念"关键词排除在外）。

```
effective_m = Σ(命中关键词权重)
score = min(1.0, effective_m / 4.0)
```

### 6.2 权重体系

| 关键词类型 | 权重 | 条件 |
|-----------|:----:|------|
| **跨类别(boosted)** | ×2.0 | `categories` 同时包含"概念"和"行业" |
| **普通行业** | ×1.0 | `categories` 包含"行业"但不含"概念" |
| **地区** | ×1/3 ≈ 0.333 | `categories` 包含"地区" |

### 6.3 阈值参考

| effective_m | score | 含义 | 到达路径举例 |
|:-----------:|:-----:|------|:-----------:|
| 1.0 | 0.25 | 低相关 | 1 个行业关键词命中 |
| 2.0 | 0.50 | 中相关 | 1 个 boosted 命中，或 2 个行业命中 |
| 3.0 | 0.75 | 较强相关 | 1 个 boosted + 1 个行业 |
| 4.0 | 1.00 | 强相关 | 2 个 boosted，或 1 个 boosted + 2 个行业 |

### 6.4 匹配流程

```
输入: {stock_code, article_text}

1. 从 Neo4j 获取该股票的行业+地区关键词（带权重）
2. 逐个关键词在 article_text 中做子串匹配
3. 命中 ⇒ 累加该关键词的权重到 effective_m
4. score = min(1.0, effective_m / 4.0)
5. 返回 score
```

---

## 7. 模块功能说明

### 7.1 `config.py` — 配置中心

```python
NEO4J_URI = "bolt://localhost:7687"                     # Neo4j 地址
NEO4J_USER = "neo4j"                                    # Neo4j 用户名
NEO4J_PASS = "kg_route_2026"                            # Neo4j 密码
DB_PATH = Path("/home/stockagent/project_space/database/report_market.db")   # SQLite
KEYWORD_FILE = Path("/home/stockagent/project_space/demand/final/data/keyword_tree_final_v2.md")  # 关键词文件
```

### 7.2 `kg_loader.py` — 关键词文件加载

> 解析 keyword_tree_final_v2.md → 写入 SQLite meta_sector_keywords

**API**:
- `parse_keyword_file()` → list[dict] — 解析文件
- `init_schema(conn)` — 创建表结构
- `load_to_db(entries, conn)` → int — 写入 SQLite

### 7.3 `kg_builder.py` — 全量构建

> SQLite → Neo4j 全量迁移

**API**:
- `build_all()` — 全量构建（清空 + 重建）

**关键内部函数**:
- `_load_sector_keywords(conn)` — 加载板块→关键词
- `_load_member_stocks(conn)` — 加载个股板块归属
- `_build_stock_keywords(members, sector_keywords)` — 构建个股→关键词（去重合并）
- `_create_constraints(driver)` — 创建唯一约束
- `_clear_graph(driver)` — 清空图谱
- `_write_stock_keywords(driver, stock_data, batch_size=500)` — 批量写入

### 7.4 `kg_incremental.py` — 增量更新

> 补齐新出现的个股→关键词关系

**API**:
- `incremental_update()` — 增量更新入口

**流程**: 对比 Neo4j 已有股票 → 查 SQLite member 表全量股票 → 找出差异 → 写新股票。

### 7.5 `kg_matcher.py` — 匹配引擎

> 匹配新闻文章到股票

**API**:
- `match_stock_to_article(stock_code, article)` → float (0.0 ~ 1.0)
  - 单只股票匹配一篇资讯
- `match_stocks_to_article(stock_codes, article, top_n=None)` → list[{stock_code, score}]
  - 批量匹配，返回按分数降序排列

**内部函数**:
- `_get_matching_keywords(stock_code)` → list[{keyword, weight}]
  - 从 Neo4j 查询行业+地区关键词，按规则分配权重

### 7.6 `kg_query.py` — 查询接口

> 图数据库查询工具

**API**:
- `get_keywords(stock_code)` → list[{keyword, categories}] — 个股的关键词列表
- `get_stocks_by_keyword(keyword)` → list[{code, name}] — 关键词关联的股票列表
- `get_stock_count()` → int — 图谱个股总数
- `get_keyword_count()` → int — 图谱关键词总数
- `search_stock(name_or_code)` → list[{code, name}] — 模糊搜索个股

---

## 8. 部署与配置

### 8.1 环境依赖

| 组件 | 版本 | 用途 |
|------|:----:|------|
| Python | 3.10+ | 开发语言 |
| Neo4j | 5.x | 图数据库 |
| Tushare Pro | latest | 获取板块成分数据 |
| levistock | latest | 获取财联社快讯 |
| neo4j-driver | latest | Python Neo4j 驱动 |

### 8.2 Neo4j 安装与启动

参考已有配置：

```bash
# 查看 Docker Compose 配置
cat /home/stockagent/project_space/research/experiments/knowledge_graph/docker-compose.yml

# 默认连接信息（在 config.py 中配置）
# URI: bolt://localhost:7687
# 用户: neo4j
# 密码: kg_route_2026
```

### 8.3 完整初始化流程

```bash
# 1. 加载关键词文件到 SQLite
conda run -n stock_agent python3 kg_loader.py

# 2. 全量构建 Neo4j 知识图谱
conda run -n stock_agent python3 kg_builder.py

# 3. 验证
conda run -n stock_agent python3 -c "
import kg_query as q
print(f'个股: {q.get_stock_count()}, 关键词: {q.get_keyword_count()}')
print(q.search_stock('茅台'))
"
```

---

## 9. 日常运维

### 9.1 数据更新流程

```
每日 ETL (etl_runner.py)
    │
    ├── 3 个线程并行拉取 DC/THS/TDX 板块+成分+日行情
    ├── 拉取腾讯大盘快照
    └── 计算中间层宽表

知识图谱更新 (手动触发)
    ├── kg_incremental.py  ← 每日 ETL 完成后运行
    └── 补齐新出现的股票→关键词关系
```

### 9.2 运行频率建议

| 任务 | 频率 | 备注 |
|------|:----:|------|
| ETL 全量取数 | 每日 1 次 | 在 Tushare 500次/分限制下约 15-20 分钟 |
| 知识图谱增量 | ETL 之后 | 新增股票不多时几秒完成 |
| 全量重建 | 首次 / 关键词文件更新 | 约 1-2 分钟 |
| 匹配查询 | 实时调用 | 单次查询 < 100ms |

### 9.3 监控检查点

```python
# 检查知识图谱健康度
python3 -c "
import kg_query as q
cnt_stock = q.get_stock_count()
cnt_kw = q.get_keyword_count()
print(f'个股: {cnt_stock}, 关键词: {cnt_kw}')
assert cnt_stock > 5000, '个股数异常!'
assert cnt_kw > 2000, '关键词数异常!'
"

# 检查 ETL 完整度（SQLite 直接查）
python3 -c "
import sqlite3
conn = sqlite3.connect('/home/stockagent/project_space/database/report_market.db')
cur = conn.cursor()
for tbl in ['stg_dc_member', 'stg_ths_member', 'stg_tdx_member']:
    cur.execute(f'SELECT COUNT(DISTINCT ts_code) FROM {tbl}')
    print(f'{tbl}: {cur.fetchone()[0]} 个板块')
conn.close()
"
```

### 9.4 ETL 异常修复

如果出现板块成分缺失（历史曾发生过）：

1. **定位问题**：检查 ETL 日志中的 `_verify_member_completeness` 警告
2. **分步重跑**：对出问题的数据源单独重跑其 `etl_xx()` 函数
3. **全量检查**：确认 index 表与 member 表板块一致后，运行 `kg_incremental.py` 补齐
4. **极限重跑**：如果依然缺失，手动确认 Tushare 该接口是否有数据，确认后端问题

---

## 10. 注意事项与常见问题

### 10.1 限流相关

**问题**：ETL 时 Tushare 返回"频率超限(500次/分钟)"

**原因**：三个线程（DC/THS/TDX）同时循环调 `ths_member` / `dc_member` / `tdx_member`，如果不限流总调用量会超限。

**解决方案**：
- `TokenBucket(rate=8, burst=20)` 保证各线程共享不超过 8次/秒
- 对偶发的频率超限，`_safe_api_call()` 自动重试（间隔 30-120 秒，最多 5 次）
- 三个 member 循环结束后都会调用 `_verify_member_completeness()` 校验完整性

**验证**：查看 ETL 日志，确认有以下输出即表示完整：
```
[DC] 全部板块成分完整
[THS] 全部板块成分完整
[TDX] 全部板块成分完整
```

### 10.2 关键词匹配相关

**规则细节**：
- 纯概念关键词（只有"概念"分类）不参与匹配，仅行业和地区参与
- 跨类别关键词（同时有"概念"+"行业"）权重翻倍
- 地区关键词权重为行业的 1/3
- 匹配采用简单的子串包含判断（`keyword in article`），无分词/NLP
- 匹配度 score 最大为 1.0（当 effective_m ≥ 4 时）

**性能**：
- 单次 `match_stock_to_article()` 查询：~50ms（含 Neo4j 查询）
- 批量匹配多只股票时，串行计算，N 只股票约 N×50ms
- 如果路由数千只股票，建议缓存 `_get_matching_keywords()` 的结果

### 10.3 关键词文件更新

如果 `keyword_tree_final_v2.md` 文件有更新：

```bash
# Step 1: 重新解析文件写入 SQLite
python3 kg_loader.py

# Step 2: 全量重建 Neo4j
python3 kg_builder.py

# 或者: 如果是少量新增板块，可以运行增量更新
# （注意: 增量更新只添加新股票节点，不改已有的关键词关系）
# python3 kg_incremental.py
```

⚠️ **注意**：如果关键词文件修改涉及已有板块的关键词变更，必须全量重建。增量更新不会更新已有股票的关键词。

### 10.4 地区关键词的特殊处理

地区类板块在关键词文件中没有额外关键词列表，解析器自动使用板块名称作为关键词：
- 板块 "福建" → 关键词: ["福建"]
- 板块 "广东" → 关键词: ["广东"]

### 10.5 股票代码格式

系统中所有股票代码统一使用 `XXXXXX.{SH,SZ}` 格式：
- 上证: `600000.SH`
- 深证/创业板: `000001.SZ`, `300750.SZ`
- 北交所: `8XXXXX.BJ`

### 10.6 `conda run` 输出缓冲

在 shell 中直接调用 `conda run -n stock_agent python3 x.py` 时，输出可能被缓冲不显示。解决方法：将脚本写入临时文件再运行，或使用 `-u` 参数。

### 10.7 Neo4j 连接

- 默认连接信息由 `config.py` 集中管理，不要硬编码在其他模块中
- 每次查询后及时关闭 driver 连接（`driver.close()`）
- kg_matcher.py 为每次匹配创建/销毁连接，高频调用时建议改为长连接

### 10.8 匹配阈值建议

根据不同业务场景推荐不同的 score 阈值：

| 场景 | 推荐阈值 | 说明 |
|:----:|:--------:|------|
| 严格路由（少而精） | ≥ 0.50 | 至少 1 个 boosted 或 2 个行业关键词命中 |
| 中等路由（平衡） | ≥ 0.25 | 至少 1 个行业关键词命中 |
| 宽松路由（广覆盖） | > 0 | 任何命中（含弱相关） |

---

## 11. 附录：实时行情快照

### 11.1 腾讯财经批量接口 (`etl_runner.py`)

```
GET https://qt.gtimg.cn/q=sh600519,sz000001,sz300750
```

返回 54 个字段的完整快照，覆盖：价格、五档买卖、成交额、换手率、PE/PB、涨跌停价等。

### 11.2 财联社快讯 (`levistock`)

```python
import levistock as lk

# 重要快讯
news = lk.news_telegraph_cls(
    date="2026-07-21",        # 格式: YYYY-MM-DD
    category="important"       # "important"(重要) / "all"(全部)
)

# 每条包含字段: title, content, time
```

---

> **文档维护者** — 本文档随代码更新。修改知识图谱逻辑后请同步更新本文档。
