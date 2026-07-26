# 午间数据取数模块 — 文档

> 最后更新: 2026-07-23

## 目录结构

```
midday/
├── intro/                        # 本文档目录
├── config/                       # 配置文件目录（不提交版本控制）
│   └── snowball_token.json       # 雪球 API Token
├── test_drive/                   # 测试目录
│   ├── run_test.py               # fetch_midday_data 测试脚本
│   ├── run_message_test.py       # fetch_midday_message 测试脚本
│   └── results/                  # 测试输出
├── .cache/                       # 本地缓存目录（自动生成）
│   ├── stock_basic.pkl           # 股票基础信息缓存
│   ├── stock_basic_meta.json     # 股票缓存元数据
│   ├── trade_calendar.pkl        # 交易日历缓存
│   └── trade_calendar_meta.json  # 日历缓存元数据
├── config.py                     # API Token 配置中心
├── fetch_midday_data.py          # 盘中数据取数主脚本（核心）
├── fetch_midday_message.py       # 午间消息补充脚本（快讯/板块/跌停/异动）
├── name_to_code.py               # 股票名称 ↔ 代码转换工具
└── trade_calendar.py             # 交易日历工具
```

---

## 一、核心脚本说明

### 1.1 `fetch_midday_data.py` — 盘中数据取数主脚本

**功能**：对指定股票列表，从多个数据源（本地DB、Tushare、pysnowball、新浪K线）获取午间（11:30）收盘数据，输出为格式化文本或 JSON。

**对外接口**：

| 函数 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `fetch_all(stock_names)` | `list[str]` 股票名称列表 | `dict[str, str]` 股票名→文本 | **统一入口**，一次调用获取全部数据 |
| `fetch_supplementary_info(names, ts_codes, trade_date, ann_date)` | 股票列表+日期 | `dict[str, list]` 股票名→行列表 | 获取 Tushare 补充信息（昨日公告+昨日波动） |
| `fetch_quotes_from_db(stock_names)` | 股票名称列表 | `dict[str, dict]` | 从 DB 获取个股实时行情 |
| `fetch_yesterday_turnover(ts_codes)` | ts_code 列表 | `dict[str, dict]` | Tushare 昨日换手率 |
| `fetch_margin(ts_codes)` | ts_code 列表 | `dict[str, dict]` | Tushare 融资融券 |
| `fetch_capital_flow(xueqiu_codes)` | 雪球代码列表 | `dict[str, dict]` | pysnowball 资金流向 |
| `fetch_capital_assort(xueqiu_codes)` | 雪球代码列表 | `dict[str, dict]` | pysnowball 资金细分 |
| `fetch_sector_ranking(stock_names)` | 股票名称列表 | `dict[str, dict]` | THS 板块排名 |
| `fetch_ths_daily_benchmark(stock_names)` | 股票名称列表 | `dict[str, dict]` | THS 板块日终基准 |
| `fetch_technical_analysis(names_codes)` | [(名称, ts_code)] | `dict[str, dict]` | 技术面 MA5/10/20/BOLL |
| `log_error(...)` | 错误参数字段 | 写入 DB `error_log` 表 | 错误日志记录 |

**数据来源概览**：

| 数据 | 来源 | 时效 |
|------|------|------|
| 个股实时行情 | 本地 DB `mid_stock_intraday` | 午间11:31快照 |
| 昨日换手率/PE/PB | Tushare `daily_basic` | T-1 日终 |
| 融资融券 | Tushare `margin_detail` | T-1 （含T-2变化率）|
| 资金流向（逐分钟） | pysnowball `capital_flow` | 盘中实时 |
| 资金细分（大/中/小单） | pysnowball `capital_assort` | T-1 日终 |
| 板块排名 | DB `mid_sector_ths` | 根据午间快照实时计算 |
| 板块日终基准 | DB `stg_ths_daily` | T-1 日终 |
| 技术面 MA5/10/20/BOLL | 新浪 K-line API | 最近640个交易日 |
| 昨日公告（8个财务接口） | Tushare | 按公告日期查询 |
| 昨日波动（异常波动+增减持） | Tushare | 按交易日期查询 |

**补充信息包含的 Tushare 接口**（共11个）：

**查询范围**：上一个交易日 ~ 今日（逐日循环查询并合并）

**昨日公告（按公告日期 `ann_date` 逐日查）**：
- `fina_audit` — 财务审计意见
- `fina_indicator` — 财务指标数据
- `dividend` — 分红送股
- `express` — 业绩快报
- `forecast` — 业绩预告（全市场批量查再过滤）
- `cashflow` — 现金流量表
- `balancesheet` — 资产负债表
- `income` — 利润表

**昨日波动**：
- `stk_shock` — 个股异常波动（按 `trade_date` 全市场批量查）
- `stk_high_shock` — 个股严重异常波动（全市场批量查）
- `stk_holdertrade` — 股东增减持（按 `ann_date` 全市场批量查）

**输出格式**：

```python
# 返回格式
{
    "宁德时代": "## 宁德时代 (300750.SZ)\n\n【今日11:30收盘数据】...",
    "比亚迪":   "## 比亚迪 (002594.SZ)\n\n【今日11:30收盘数据】...",
}

# 补充信息仅在有数据时出现，所有子栏目无数据时整个板块隐藏
# 【补充信息——上一个交易日(20260722)】
# 【昨日公告】
#   【财务审计意见】
#     审计结果: 标准无保留意见 | 会计事务所: ...
#   ...
# 【昨日波动】
#   【个股异常波动】
#     异常说明: ...
```

**CLI 用法**：

```bash
conda run -n stock_agent python fetch_midday_data.py 宁德时代 比亚迪 菲利华
conda run -n stock_agent python fetch_midday_data.py --format json 宁德时代
```

---

### 1.2 `fetch_midday_message.py` — 午间消息补充脚本

**功能**：对指定股票列表，获取午间（11:30）消息类数据并匹配到个股。包含 4 个子模块：

| 模块 | 接口 | 数据源 | 说明 |
|------|------|--------|------|
| 今日快讯 | `lk.news_telegraph_cls(category='important')` | 财联社 | 上一个交易日至今日 11:30 的重要快讯，用股票名称+代码+知识图谱**MG 关键词**匹配，匹配度 >0.3 才输出 |
| 热门板块原因 | `lk.get_sector_hot_plates()` | 财联社 | 用个股知识图谱**MG 关键词**匹配板块标题，再用个股名称匹配板块全文 |
| 跌停监控 | `lk.stock_dt_pool_em()` | 东方财富 | 跌停板池中筛选关注的个股（按纯数字代码匹配） |
| 异动检测 | `lk.stock_changes_em()` 全量 22 种异动类型循环去重 | 东方财富 | 筛选个股的火箭发射/大笔买入等盘口异动，按类型分组展示 |

**对外接口**：

| 函数 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `fetch_all(stock_names)` | `list[str]` 股票名称列表 | `dict[str, str]` 股票名→文本 | **统一入口**，一次调用获取全部消息数据 |

**数据来源概览**：

| 数据 | 来源 | 时效 |
|------|------|------|
| 财联社快讯 | `levistock.news_telegraph_cls` | 实时（过滤今日 11:30 前） |
| 热门板块 | `levistock.get_sector_hot_plates` | 交易日实时 |
| 跌停板池 | `levistock.stock_dt_pool_em` | 交易日实时 |
| 盘口异动 | `levistock.stock_changes_em` | 交易日实时（22种类型全量循环） |
| 知识图谱关键词 | Neo4j `(Stock)-[:HAS_KEY]->(Keyword)` | 离线构建（5631 个股，3032 关键词） |

**关键词匹配算法**：

- **关键词标签体系**：每个行业类 Keyword 节点已打标 `match_class` + `grade`
  | 标签 | match_class | 含义 | grade | 倍率 |
  |------|------------|------|-------|------|
  | MG1 | MG | 有匹配意义（泛化） | 1 | ×0.8 |
  | MG2 | MG | 有匹配意义（适中） | 2 | ×1.0 |
  | MG3 | MG | 有匹配意义（专精） | 3 | ×1.2 |
  | NM1/NM2/NM3 | NM | 无匹配意义 | — | 不参与匹配 |

- **今日快讯**：仅使用 `match_class='MG'` 的行业类关键词
  - 基础权重：boosted（跨类别）=2.0，普通行业=1.0
  - 融合 grade 倍率后：`最终权重 = 基础权重 × 倍率`（MG1×0.8 / MG2×1.0 / MG3×1.2）
  - 匹配度 score = min(1.0, Σ最终权重 / 4)
  - 名称/代码命中 → score=1.0，纯关键词匹配 → score×0.75（折扣）
  - 阈值：>0.3 才输出

- **热门板块原因**：仅使用 `match_class='MG'` 的关键词（NM 已过滤），不计算匹配度
  - Step 1: MG 关键词匹配板块标题 `secu_name`
  - Step 2: 个股名称匹配板块全文
  - 使用 `ThreadPoolExecutor` 并行匹配

**错误日志**：脚本内部使用 `log_error()` 将各模块的 API 取数异常写入 DB `error_log` 表（包括 Neo4j 关键词查询、财联社快讯、热门板块、跌停板、盘口异动等）。

**输出格式**：

```python
{
    "宁德时代": "## 宁德时代 (300750.SZ)\n\n【今日快讯】\n  ...\n\n【热门板块上涨原因】\n  ...\n\n【跌停监控】\n  ...\n\n【盘中异动监测】\n  ...",
    "warning": {
        "300124.SZ": "no data"   # 仅在三部分（快讯+板块+异动）全部为空时出现
    }
}
```

`warning` key：数据完整性检查。三个非关键部分（今日快讯、热门板块上涨原因、盘中异动监测）**全部同时为空**时，记录 `"no data"`。只有部分为空时不触发。正常时 `warning: {}`。

**CLI 用法**：

```bash
conda run -n stock_agent python fetch_midday_message.py 宁德时代 比亚迪
```

---

### 1.2 `name_to_code.py` — 股票名称 ↔ 代码转换

**功能**：基于 Tushare `stock_basic` 接口，实现股票名称到多种格式代码（ts_code、腾讯格式、雪球格式）的转换。

**对外接口**：

| 函数 | 说明 |
|------|------|
| `name_to_ts_code(name)` | 股票名称 → ts_code（如 "宁德时代" → "300750.SZ"） |
| `name_info(name)` | 一键获取名称 → 所有代码格式（见下方返回字段说明） |
| `batch_name_info(names)` | 批量转换，只拉一次 Tushare |
| `ts_code_to_tencent(ts_code)` | ts_code → 腾讯格式（sz300750） |
| `ts_code_to_xueqiu(ts_code)` | ts_code → 雪球格式（SZ300750） |

** `name_info()` 返回字段**：

```python
{
    "name": "宁德时代",          # 股票名称
    "ts_code": "300750.SZ",     # Tushare 格式（带后缀）
    "symbol": "300750",         # 纯数字代码 ← 常用
    "tencent": "sz300750",      # 腾讯行情格式
    "xueqiu": "SZ300750",       # 雪球格式
}
```

**CLI 用法**：

```bash
conda run -n stock_agent python name_to_code.py 宁德时代 比亚迪
conda run -n stock_agent python name_to_code.py --refresh 宁德时代
```

---

### 1.3 `trade_calendar.py` — 交易日历工具

**功能**：基于 Tushare `trade_cal` 接口，提供交易日判断、上一个交易日查询等功能。缓存覆盖 [去年, 今年] 范围。

**对外接口**：

| 函数 | 说明 |
|------|------|
| `TradeCalendar()` | 交易日历类，支持 refresh 参数 |
| `get_calendar()` | 获取全局单例 |
| `last_trading_day()` | 最近一个已收盘交易日（≥15:00返回今日，否则T-1） |
| `prev_trading_day(date, n)` | 从指定日期往前推 n 个交易日 |
| `is_trading_day(date)` | 判断是否为交易日 |
| `last_two_trading_days()` | 返回 (T-1, T-2) 两个交易日 |

**CLI 用法**：

```bash
conda run -n stock_agent python trade_calendar.py last          # 显示最近交易日
conda run -n stock_agent python trade_calendar.py check 20260722 # 判断是否交易日
conda run -n stock_agent python trade_calendar.py prev 20260722 3  # 往前3个交易日
```

---

### 1.4 `config.py` — API Token 配置中心

**功能**：封装所有外部 API Token/密钥的读取逻辑。

| 函数 | 说明 |
|------|------|
| `get_snowball_token()` | 读取雪球 Token（带惰性缓存） |
| `get_tushare_token()` | 读取 Tushare Token（环境变量 / tk.csv） |
| `check_all_tokens()` | 检查所有 Token 状态（诊断用） |

**Token 来源**：

| 服务 | 来源文件 | 更新方式 |
|------|---------|---------|
| pysnowball (雪球) | `config/snowball_token.json` | 手动从浏览器 Cookie 更新，有效期7-30天 |
| Tushare | 环境变量 `TUSHARE_TOKEN` 或 `~/tk.csv` | 由 tushare 库自行管理 |

**诊断命令**：

```bash
conda run -n stock_agent python config.py --check
```

---

## 二、开发指南

### 2.1 环境要求

- Python 3.10+
- conda 虚拟环境 `stock_agent`
- 依赖包: `tushare`, `pysnowball`, `pandas`, `requests`, `numpy`

### 2.2 数据库依赖

| 表名 | 用途 | 更新方式 |
|------|------|---------|
| `stg_tencent_snapshot` | 腾讯财经A股全量快照 | 每日午间 ETL |
| `stg_ths_member` | 同花顺板块成分 | 每日日终 ETL |
| `stg_ths_index` | 同花顺板块分类 | 每日日终 ETL |
| `stg_ths_daily` | 同花顺板块日行情 | 每日日终 ETL |
| `mid_sector_ths` | THS板块午间排名 | 每日午间 ETL |
| `mid_stock_intraday` | 个股盘中宽表 | 每日午间 ETL |
| `error_log` | 错误日志 | 运行时自动写入 |

### 2.3 关键业务流程

```
                   Tushare (日终)              腾讯财经 (午间)
                  ┌──────────┐              ┌──────────────┐
                  │ stg_*    │              │ 全量快照      │
                  │ index/   │              │ 5,251只股票   │
                  │ member/  │              └──────┬───────┘
                  │ daily    │                     │
                  └────┬─────┘                     │
                       │                           │
              ┌────────▼──────────┐                │
              │ fix_ths_member.py │                │
              │ （补齐缺失板块）   │                │
              └────────┬──────────┘                │
                       │                           │
              ┌────────▼──────────────────────────▼──┐
              │         etl_mid_sector()              │
              │    JOIN member + snapshot → ranking  │
              └────────────────┬─────────────────────┘
                               │
              ┌────────────────▼─────────────────────┐
              │          mid_sector_ths               │
              │     1158个板块（395个概念+N类）       │
              └────────────────┬─────────────────────┘
                               │
              ┌────────────────▼─────────────────────┐
              │      fetch_midday_data.py             │
              │      fetch_all() → 输出报告           │
              └──────────────────────────────────────┘
```

### 2.4 新增数据源步骤

1. 在 `fetch_midday_data.py` 中新增取数函数（错误处理用 `_safe_float` + `log_error`）
2. 若需要新的 Tushare 接口，在 `fetch_supplementary_info` 中添加（注意字段名→中文映射）
3. 在 `fetch_all` 的输出组装段中添加对应数据到 `lines`
4. 补充信息（Tushare 公告/波动类）走 `fetch_supplementary_info`，自动管理子栏目的显隐

### 2.5 错误处理规范

所有可能出错的取数操作统一使用：
- `_safe_float(v)` — 安全转换数值，`None`/非数值→ `0.0`
- `log_error(...)` — 记录错误到 `error_log` 表（参见数据库文档第七节）

### 2.6 测试指南

```bash
cd test_drive
conda run -n stock_agent python run_test.py

# 输出:
#   results/raw_dict.txt        → 原始 dict（JSON）
#   results/readable_report.md  → 可读 Markdown 报告
```

---

## 三、更新日志

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-07-23 | 新增补充信息 | 增加 Tushare 11个接口的昨日公告+昨日波动查询 |
| 2026-07-23 | 修复概念板块缺失 | 重跑 `etl_mid_sector()`，`mid_sector_ths` 从430→1158条 |
| 2026-07-23 | 修复 float(None) | `fetch_capital_assort` 增加 `_safe_float` 安全转换 |
| 2026-07-23 | 新增错误日志 | 创建 `error_log` 表 + `log_error()` 函数 |
| 2026-07-23 | 隐藏无数据子栏目 | 补充信息子栏目无数据时不显示，全部无数据时整个板块隐藏 |
| 2026-07-23 | 新增消息补充脚本 | `fetch_midday_message.py`：快讯+知识图谱匹配、热门板块、跌停监控、异动检测 |
| 2026-07-23 | 关键词MG/NM打标 | 行业类Keyword新增`match_class`+`grade`属性，MG三档倍率×0.8/×1.0/×1.2，NM不参与匹配 |
| 2026-07-23 | 匹配算法升级 | 快讯和板块匹配只取MG关键词，按grade调权；名称/代码命中→score=1.0，纯关键词匹配×0.75折扣 |
| 2026-07-25 | 消息完整性检查 | `fetch_midday_message` 返回 dict 增加 `warning` key，三部分（快讯+板块+异动）全部为空时记录 `"no data"` |
| 2026-07-25 | 融资融券N/A优化 | 两市均无数据时显示"无融资融券信息，股票可能非融资融券标的" |
| 2026-07-25 | 冗余行情段删除 | 删除【今日11:30收盘行情】段（已包含在【今日11:30收盘数据】中） |
| 2026-07-25 | 雪球Token自动刷新 | 新增 `snowball_token/refresh_token.py`（Playwright登录），`fetch_midday_data` 集成自动刷新 |
| 2026-07-25 | 资金流向None修复 | `fetch_capital_flow`/`capital_assort` 增加 None 判空，避免 ETF 类标的抛异常 |
| 2026-07-25 | 数据完整性检查 | `fetch_midday_data` 返回 dict 增加 `warning` key，9个数据段的完整性检查+关键部分重试3次 |
