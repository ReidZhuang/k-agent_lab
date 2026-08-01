# 报告系统通用化优化升级方案 v1.0 — 2026-08-01

> 目标: 把当前"午间专用"的报告生成链路(office/commander)改造为"报告类型可配置"的通用链路, 支持午间/日终两类报告共用同一套 fetcher/writer/reporter, 由 commander 配置驱动选择取数脚本。
> 本文档是优化升级的唯一依据, 含: 背景 / 需求 / 修改点探查 / 优化方案 / 开发方案。

---

## 一、优化背景(全面)

### 1.1 系统现状

报告系统由四层构成, 目前全部为午间报告服务:

```
crontab(40 11 * * *) → commander/scheduled_task.py → Writer API(:8310)
                                                        ├─ fetcher.py
                                                        │    ├─ fetch_midday_data.fetch_all    (路1: 行情/资金/融资/板块/技术/公告)
                                                        │    └─ fetch_midday_message.fetch_all (路2: 快讯/异动/跌停/热门板块)
                                                        ├─ middleman(:8311) → engine+mailtower(资讯/新闻/公告)
                                                        └─ reporter(:8312) → agent.py → DeepSeek(deepseek-v4-flash)
                                                              ├─ prompts(系统 prompt: soul/agent/preference + skills/)
                                                              └─ 输出 → office/output/{股票}/ → commander 分发到 user/
```

### 1.2 演进需求

1. **日终报告**(新): 交易日 18:30 生成"日终收盘分析报告", 数据优势为 T 日龙虎榜实锤、全日资金流、完整涨停炸板数据。需求文档 `office/demand/endday_report/requirements.md` 已定稿, 取数脚本 `data_fetch/endday/fetch_endday_data.py` 已开发并验证(14 节, 含融资融券多日/机构行为/风险日历/业绩趋势/大宗交易)。
2. **午间报告升级**(新): 决策触发型定位, 三问直答置顶, 分析为骨数据为证。新版 skill 已定稿(prompt_drafts_v2), 取数脚本 `data_fetch/midday/fetch_midday_data_v2.py` 已开发并验证(16 节, 含融资多日/机构/异常扫描/大宗交易)。
3. **两套报告共用一条链路**: 不复制 office/commander, 而是让链路"报告类型可配置"。

### 1.3 现状问题(为什么必须通用化)

**A. 链路为午间写死**(工作一排查结论):

| 层 | 写死点 | 后果 |
|---|---|---|
| fetcher.py | L27-28 硬编码 import 两个 midday 脚本; L17-19 sys.path 只加 midday 目录 | 无法接入 endday 脚本 |
| reporter/agent.py | L153 user prompt 首行"午间分析报告"; L369 文件名"午间收盘报告" | 日终报告会被当成午间 |
| reporter/agent.py | L118 `_load_all_skills()` 全量扫描 skills/ 目录 | 新增 endday skill 后两份 skill 同时注入, LLM 不知道该用哪个(最大隐患) |
| writer/server.py | L219 响应丢失恢复检查的文件名写死"午间" | 日终报告恢复检查失效 |
| models.py | L73-74 字段注释绑定 midday 脚本 | 语义混乱(字段名本身通用) |
| commander | query 已配置化 ✅; find_report_file 按日期前缀匹配 ✅ | 这两处已是通用设计, 无需改 |

**B. 消息数据重复集成**(工作二讨论结论):

- v2 脚本为"单脚本自包含"而 import 了 fetch_midday_message 的 4 个函数(快讯/异动/跌停/热门板块), 与生产链路的路2 完全重叠
- endday 脚本则没有任何消息数据(财联社快讯/热门板块原因缺失——审计发现的问题)
- 正确架构: 消息是"报告类型无关"的数据, 应独立成一路、一份代码, 午间日终共用

**C. 消息脚本命名不通用**: `fetch_midday_message.py` 名字绑定"午间", 实际将服务两类报告, 需改名 `fetch_message.py`。

**D. 资讯日期窗口过窄**(工作三排查结论):

- middleman `_get_date_range()`: 普通资讯(sinafin/baidufin/thsfin/thsnews)和公告(juchao)窗口 = "上一个交易日 ~ 今天"(2 个自然日), 不满足需求文档"驱动因素近 5 日"
- 需求: 普通资讯 + 公告均需**近 5 个交易日**窗口; 非交易日以最近有效交易日为终点
- 配置方式: 不能是"往前 N 天"的模糊天数, 必须是**起始日期 + 终止日期**的显式日期

**E. prompts 残留午间字样**(已修): soul.md 的"今日午间"→"今日"、"如:午间报告"→"当前分析任务的 skill"。

---

## 二、需求

### 2.1 功能需求

| # | 需求 | 说明 |
|---|---|---|
| R1 | 报告类型可配置 | commander 配置驱动: 每份 config 声明 report_type(noon/endday), 链路据此选择取数脚本、prompt 首行、报告文件名、skill |
| R2 | 午间报告升级 | 使用 v2 取数脚本(16 节) + 新版 noon skill(三问直答/分析为骨) |
| R3 | 日终报告上线 | 使用 endday 取数脚本(15 节) + 新版 endday skill |
| R4 | 消息数据统一 | 快讯/异动/跌停/热门板块由独立的 message 路提供(午间日终共用一份代码) |
| R5 | 资讯日期窗口 | 普通资讯 + 公告均近 5 个交易日; 非交易日以最近有效交易日为终点; 配置为显式起始/终止日期 |
| R6 | 脚本改名 | fetch_midday_message.py → fetch_message.py(同步所有引用) |
| R7 | 现有午间链路不破坏 | report_type 默认 noon 时行为与现在一致 |

### 2.2 非功能需求

- 取数脚本统一契约: 每个脚本导出 `fetch_all(stock_names) -> {name: text, "warning": {...}}`
- 消息路对两类报告输出相同结构(节标题不绑定午间)
- 新增报告类型时: 只加 config + 注册表一行 + 新 skill, 不改链路代码

---

## 三、修改点探查(逐文件)

### 3.1 fetcher.py(127 行)

```
L17-19  _MIDDAY_DIR sys.path 硬编码
L27     from fetch_midday_data import fetch_all as _fetch_data
L28     from fetch_midday_message import fetch_all as _fetch_message
L33     def fetch_all(stock_names) -> tuple[dict, dict]   # 无 report_type 参数
L50-74  路1 数据取数块
L77-100 路2 消息取数块
```

改造: 注册表 + report_type 参数 + sys.path 覆盖 midday+endday。

### 3.2 writer/server.py(339 行)

```
L28-32  _MIDDAY_DIR sys.path 硬编码
L93     def _run_sub_writer(..., query="")
L218-219 expected_path 文件名"午间收盘报告"写死
```

改造: sys.path 通用化; _run_sub_writer 增加 report_type 透传; 恢复检查文件名由 report_type 推导(或改为按"日期前缀+任意 md"匹配——find_report_file 已是前缀匹配, writer 可复用同逻辑)。

### 3.3 reporter/agent.py(605 行)

```
L118-131 _load_all_skills() 全量加载 → 需按 report_type 只加载对应 skill
L153     user prompt 首行"午间分析报告" → 由 report_type 推导
L206-207 需求: {query} → 已通用(保留)
L337     _save_report()
L369     文件名"午间收盘报告" → 由 report_type 推导
L381     def run(ctx) → ReportContext 增加 report_type 字段
```

改造: 3 处(首行/文件名/skill 选择)+ ReportContext 加字段。

### 3.4 models.py

```
L69-79  ReportContext: 加 report_type: str = "noon"
L73-74  注释改为通用表述
```

### 3.5 commander/scheduled_task.py

```
L551   query = cmd_cfg.get("query", "")  → 增加 report_type 透传
L284   call_writer 请求体 → 加 report_type
```

### 3.6 commander/config.yaml → 新增 config_endday.yaml

```
commander:
  query: "生成该股票的日终收盘分析报告"
  report_type: "endday"
```

### 3.7 middleman/server.py(工作三)

```
L103-121 _get_date_range(): 非 qnainfo 窗口 2 天 → 5 个交易日; 非交易日终点修正
        → 改读配置(start_date/end_date 显式表达式)
```

### 3.8 脚本层

- `fetch_midday_data_v2.py`: 剥离消息部分(删 4 个 import + 消息拉取块 + 节 11/12 组装中消息部分, 保留板块排名)
- `fetch_message.py`(改名自 fetch_midday_message.py): 内容不变, 快讯 cutoff 已动态化(上午/全天自适应)
- `fetch_endday_data.py`: 不变(无消息, 由 message 路提供)

### 3.9 引用点更新(改名影响面)

| 文件 | 引用 | 动作 |
|---|---|---|
| fetcher.py | import fetch_midday_message | 改 fetch_message |
| fetch_midday_data_v2.py | import 4 函数(将剥离) | 剥离后无需改 |
| models.py | 注释 | 改通用表述 |
| test_drive/run_random_test.py, run_message_test.py, run_message_test_4stocks.py | import | 改 fetch_message |
| intro/README.md, office/intro/error_codes.md, office/intro/LOGGING.md | 文档 | 可选同步 |
| design/midday/part3.md, part4.md | 设计文档 | 不动(历史记录) |

---

## 四、优化方案

### 4.1 总体架构: report_type 贯穿全链路(方案 A: 两路分工)

```
commander(config_noon.yaml / config_endday.yaml)
   │  query + report_type
   ▼
Writer API(:8310) → ReportRequest{stock_names, query, report_type}
   │
   ▼
fetcher.fetch_all(stock_names, report_type)   ← 注册表驱动
   │  注册表:
   │    "noon":   {"data": "fetch_midday_data_v2",  "message": "fetch_message"}
   │    "endday": {"data": "fetch_endday_data",     "message": "fetch_message"}
   │
   ├─ data 路: 对应取数脚本.fetch_all(stock_names) → data 文本
   └─ message 路: fetch_message.fetch_all(stock_names) → message 文本(两类报告共用)
   │
   ▼
sub_writer → ReportContext{..., report_type}
   │
   ▼
reporter agent.run(ctx)
   ├─ system prompt: soul/agent/preference + skills/{noon_report|endday_report}/SKILL.md(只加载一个)
   ├─ user prompt 首行: "请生成 X(X)的{午间|日终}分析报告。"
   └─ 文件名: "{today}_{stock}_《{午间|日终}收盘报告》"
```

### 4.2 注册表设计(静态, 可读)

```python
# fetcher.py
_FETCH_REGISTRY = {
    "noon":   {"data": "fetch_midday_data_v2", "message": "fetch_message"},
    "endday": {"data": "fetch_endday_data",    "message": "fetch_message"},
}
_REPORT_TYPE_NAME = {"noon": "午间", "endday": "日终"}

def fetch_all(stock_names, report_type="noon"):
    cfg = _FETCH_REGISTRY.get(report_type, _FETCH_REGISTRY["noon"])
    import importlib
    data_mod = importlib.import_module(cfg["data"])
    msg_mod = importlib.import_module(cfg["message"]) if cfg["message"] else None
    ...(其余逻辑不变, 数据/消息两路独立 try/except 不变)...
```

注意: 采用**静态注册表**(模块名写死在代码里), 不做动态加载任意模块——模块集合是固定已知的, 静态表更清晰可审查; report_type 只做注册表查表, 不接受任意模块名。

### 4.3 报告类型命名约定

| report_type | 中文名 | 取数脚本 | skill | 文件名后缀 |
|---|---|---|---|---|
| noon | 午间 | fetch_midday_data_v2 | noon_report | 午间收盘报告 |
| endday | 日终 | fetch_endday_data | endday_report | 日终收盘报告 |

### 4.4 资讯日期窗口方案(工作三)

middleman 配置化(显式日期, 非天数):

```yaml
# middleman config
date_range:
  news:      {start: "prev_trading_day(4)", end: "today_or_last_trading"}   # sinafin/baidufin/thsfin/thsnews
  announce:  {start: "prev_trading_day(4)", end: "today_or_last_trading"}   # juchao 公告
  qnainfo:   {start: "prev_trading_day(5)", end: "today"}                   # 保持现状
```

- 交易日运行时: end = 今天; 非交易日: end = last_trading_day()
- start = prev_trading_day(end, n=4) → 共 5 个交易日窗口(注意: 是"5 个交易日"不是"5 个自然日")
- 表达式由 middleman 解析为具体 YYYY-MM-DD 传给 mail_tower(透传, mail_tower 无需改)

### 4.5 v2 剥离消息(方案 A 配套)

fetch_midday_data_v2.py 变更:
- 删: `from fetch_midday_message import (_get_stock_codes, fetch_telegraph_news, fetch_abnormal_movements, fetch_limit_down, fetch_hot_sectors)`
- 删: 消息拉取块(ThreadPoolExecutor 4 任务: news/sectors/limit/changes)
- 删: 节 11(涨停异动快讯)与节 12(热门板块原因)组装中消息部分——保留板块排名(DB 数据, 属数据脚本)
- _SECTION_NAMES 调整(11/12 节含义变化, 或改编号)
- 完整度检查同步调整

剥离后 v2 节结构: 全市场情绪/行业关键词/半日行情/融资融券多日/龙虎榜/资金流/机构持仓/机构调研/股东户数/风险日历/板块排名/技术面成本地图/业绩趋势/公告补充/大宗交易(消息类数据由 message 路提供, 报告组装时两块文本都有)

### 4.6 消息脚本改名(工作二要求)

- `fetch_midday_message.py` → `fetch_message.py`(内容不变, cutoff 已动态化)
- 更新引用: fetcher.py / models.py 注释 / 3 个 test_drive 脚本
- 文档(intro/design)可选同步, 不强制

### 4.7 skill 选择

```python
# agent.py
def _load_skill(name):   # 只加载一个 skill
    path = os.path.join(_PROMPTS_DIR, "skills", name, "SKILL.md")
    ...
# _build_system_prompt 增加 skill_name 参数, 由 report_type 映射:
_SKILL_BY_TYPE = {"noon": "noon_report", "endday": "endday_report"}
```

---

## 五、开发方案

### 5.1 任务分解

| # | 任务 | 产出 | 依赖 |
|---|------|------|------|
| 1 | 本文档评审 | 定稿 | — |
| 2 | fetcher.py 通用化 | 注册表 + report_type 参数 + sys.path 通用化 | 1 |
| 3 | models.py + writer/server.py | ReportContext/ReportRequest 加 report_type; 文件名/恢复检查按类型; sys.path 通用化 | 1 |
| 4 | reporter/agent.py | 3 处: prompt 首行/文件名/skill 选择(按类型) | 1,3 |
| 5 | v2 剥离消息 | fetch_midday_data_v2.py 删消息部分 | 1 |
| 6 | 消息脚本改名 | fetch_midday_message.py → fetch_message.py + 引用更新 | 1 |
| 7 | middleman 日期窗口 | _get_date_range 改配置驱动(5 交易日 + 非交易日终点) | 1 |
| 8 | commander | scheduled_task 透传 report_type; 新增 config_endday.yaml; crontab 18:30 条目 | 1,2-4 |
| 9 | prompts 部署 | prompt_drafts_v2 → prompts_deepseek(soul/agent/preference + noon/endday 两 skill) | 4 |
| 10 | 联调(用户) | 午间回归 + 日终上线 + 分发验证 | 2-9 |

### 5.2 工作量预估

| 任务 | 预估 |
|---|---|
| 2 fetcher | 25 行 |
| 3 models+writer | 15 行 |
| 4 agent.py | 15 行 |
| 5 v2 剥离 | -40 行(纯删除) |
| 6 改名 | 2 处代码 + 3 个测试脚本 |
| 7 middleman | 15 行 + config |
| 8 commander | 10 行 + 新 config + crontab |
| 合计 | ~90 行代码 + 1 个新 config + 1 条 crontab |

### 5.3 风险与回滚

- **风险1: v2 剥离破坏午间取数** → 剥离后跑 3 股批量回归(fetch_all 正常 + 节数正确); 回滚: git revert
- **风险2: skill 按类型加载错误** → 联调验证 system prompt 只含一个 skill; 回滚: report_type 默认 noon
- **风险3: middleman 日期改动影响现有午间** → 窗口从 2 天变 5 天, 资讯量增多(只增不减, 不破坏); 配置化可随时调回
- **风险4: 改名遗漏引用** → 全局 grep `fetch_midday_message` 确认清空(除 design 历史文档)

### 5.4 验证清单

1. fetcher: `fetch_all(["宁德时代"], "noon")` 与 `fetch_all(["宁德时代"], "endday")` 均正常, 输出节数正确
2. v2 剥离后: 午间 fetch_all 16→14 节, 无 import 错误
3. reporter: report_type=endday 时 system prompt 只含 endday_report skill; 文件名含"日终"
4. commander: config_endday.yaml 触发 18:30 调度(query + report_type 透传正确)
5. middleman: 周一午间调用 → start=上周二; 周六补跑 → end=周五
6. 全链路: 午间报告(旧)回归通过 + 日终报告端到端生成

---

## 六、决策记录

| 决策 | 结论 | 理由 |
|---|---|---|
| 数据流架构 | 方案 A(两路分工) | 消息数据报告类型无关, 一份代码两用; v2 剥离回归正确架构 |
| 注册表 | 静态注册表 | 模块集合固定, 静态表清晰可审查, 不做任意模块动态加载 |
| 消息脚本改名 | fetch_midday_message → fetch_message | 命名不绑定午间, 同步引用点 |
| 日期窗口 | 5 个交易日, 显式起始/终止日期配置 | 满足"驱动因素近5日"; 非交易日以最近有效交易日为终点 |
| skill 加载 | 按 report_type 只加载一个 | 避免两份 skill 同时注入导致 LLM 混乱 |
| 文件名/首行 | 由 report_type 推导 | 替代硬编码"午间" |
