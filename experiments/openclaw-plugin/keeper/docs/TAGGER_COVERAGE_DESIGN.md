# Tagger 工具覆盖设计 —— 让压缩不依赖"写死的工具名"

- 状态: **设计稿**（不实现，先评审 + 测试）
- 背景: 阶段3 对比实验中 T3（板块前5对比）零压缩。根因: 该任务 agent 改走 `read` 读文件取数,
  tagger 门控只认 `tagTools` 白名单 + `execTools`/`execCommandPatterns`, 不在清单的工具一概不打标。

## 1. 现状（已核实，assembly.js）

| 判定 | 默认值 | 逻辑 |
|---|---|---|
| `tagTools` | `['hithink-market-query']` | toolName 子串匹配 → 打标 |
| `execTools` + `execCommandPatterns` | `['exec','bash','run_shell','shell']` + `['hithink','cli.py']` | 工具名 ∈ execTools **且** 命令含取数模式 → 打标 |
| resume 回溯 | — | 历史 exec 结果无登记时, 回看消息序列重建命令命中判断 |
| 其余 | — | **不打标**（T3 的 `read` 落在这里） |

问题: 清单是**静态快照**。MCP 工具千变万化（`mx-ds-mcp__*`、新装的第三方取数/数据库/HTTP 工具）,
靠人工维护名单永远追不上。`tag()` 本身不做工具名判断（只看内容结构）, **写死发生在门控层**。

## 2. 哪些工具"和 exec/read 同类"（候选覆盖面）

凡是"返回结构化大文本、塞进上下文是浪费"的工具都应覆盖, 分四类:

| 类别 | 例子 | 覆盖难度 |
|---|---|---|
| 通用执行 | exec / bash / run_shell / shell / command / terminal | 低（现有 execTools） |
| 文件/内容读取 | read / cat / ReadFile / read_file / fs.read / view | 低～中（T3 主犯） |
| MCP 数据查询 | `*__ashare_finance_data` / `*__stocks_screener` / `*__search_news` / hithink-* | 中（名字带前缀, 需子串/glob） |
| 数据库 / HTTP / 表格 | query_sql / db_query / fetch / http_get / curl / read_csv | 中（返回行集/网页, 与 exec 同质） |

判断共性: **返回文本≥某阈值 且 呈表格/JSON数组结构** 即可压 —— 这正是 `tag()` 已经会做的事。

## 3. 设计: 三层判定链（推荐）

在**门控层**（`shouldTagLive` / persist 侧）增加内容证据，取代"仅名字+命令"：

```
对任意 toolResult（含历史 resume 侧同判）：
  A. 显式命中规则(保留现有, 扩展)
      1) toolName ∈ tagTools(子串/glob)          → tag (signal=name)
      2) tool 的参数命中 toolArgsPatterns[该工具] → tag (signal=args)
           —— 泛化现有 execCommandPatterns: {exec:[hithink,cli.py], read:[reports/,snapshot,.json,.csv], ...}
  B. 内容证据(新增, 默认开) ★覆盖一切新工具
      返回文本长度 ≥ autoTagMinChars(默认 1200)
      且 (isTableLike 或 jsonRows 解析出数组)
                                             → tag (signal=content)
  C. 排除名单(新增)
      toolName ∈ excludeTools / 参数命中 excludeArgsPatterns → skip
  未命中 A/B: skip, 并写 trace: tagger_skip {tool, argSample, reason:'no_signal'}
```

要点:
- **B 是核心**——`read` 只要读的是数据文件（大 JSON/表格）就自动打标, T3 不再漏;
  读 SKILL.md 等小文件因长度不足自然不触发, 无需人为区分。
- 判定链顺序 A→B→C: 显式优先（防内容误判）, 排除最末（宁可 skip）。
- glob 支持（`*__ashare_*`）降低名单维护成本。

## 4. 新配置（仍在 `plugins.entries.keeper-corpus-compress.config.*`）

```jsonc
// 现有字段沿用, 新增:
"excludeTools": [],                    // 名单命中 → 永不压缩
"excludeArgsPatterns": {},             // {tool: [pattern,...]} 参数命中 → 永不压缩
"toolArgsPatterns": {                  // 泛化的 execCommandPatterns（保留旧字段兼容）
  "exec": ["hithink", "cli.py"],
  "read": ["snapshot", "reports/", ".json", ".csv"]
},
"autoTagByContent": true,              // 默认开; false 则仅名单模式
"autoTagMinChars": 1200
```

不侵入 `tag()`/`contract` 契约, 只改门控层。

## 5. "用户装了新取数工具"怎么配置

两步之一即可（都不配也行, 靠 B 自动覆盖）:
1. **什么都不做** —— 新工具返回大表格/大 JSON 时 B 自动打标;
2. **想要更准/防误压** —— 一行清单:
   - 按名: `tagTools: ["my-tool", "*__market_*"]`
   - 按参数: `toolArgsPatterns: { "my-tool": ["keyword"] }`
   - 要排除: `excludeTools: ["my-tool"]`

## 6. 测试计划（先测后接）

1. 单元测试（tagger/assembly 现有 suite 扩矩阵）: name/args/content/exclude 四分支 + resume 侧。
2. 复跑 T3（2 次）: 断言 tagger_doc>0, 质量回测不降, saved 出现非 0。
3. 对照验证 B 不误伤: 读小文件（SKILL.md）零打标。
4. 全量回归: T1/T2 各 1 次, 确认现有压缩路径不受影响。