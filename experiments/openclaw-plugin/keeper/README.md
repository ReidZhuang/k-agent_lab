# keeper —— OpenClaw 插件实验实验室

> 目标：为"把 exp02 语料压缩机制做成 OpenClaw 插件（档位2）"提供一个**独立、可安全实验**的
> OpenClaw 环境。独立于现行生产 OpenClaw（生产环境在对外提供服务，不能在上面乱做实验）。

---

## 一、这个实验室是什么

- 一套**独立的 OpenClaw 实例**（通过 `openclaw --profile keeper` 隔离，不碰生产环境）。
- 一个**插件代码区**（`plugin/`）：档位2插件 keeper（语料压缩）已接入 —— ⚠️ 压缩接缝不是
  `api.on("context")`（插件 API 无此钩子、嵌入式 extension 路径 `noExtensions:true` 死路），而是
  **插件 API 的 ContextEngine 槽位**（`registerContextEngine` + `plugins.slots.contextEngine` +
  `info.ownsCompaction:true`，selection 每轮调 `assemble()`）；v2.4 起 `assemble` 内 `liveTagger`
  先把门控取数结果改写为 keeper 行集（模型可见可申报 discard_lines）再行级压缩。详见
  `docs/DEVELOPMENT_PLAN.md` §9.1 与 `plugin/src/context-engine.js`。
- 一个**简化版公司分析报告 skill**（`skills/company-analysis-simple/`）：不依赖 mx MCP（有限额），
  改用**同花顺 IWENCAI** 取数，用于复现/验证报告生成流程。
- **同花顺 hithink 系列 skills**（直接复用生产已有的，不走 mx MCP）。
- 一套**结构化日志体系**（`logs/`）：agent 每次运行时把全过程记录下来，供诊断、效果评估、
  平行实验对比（质量/效率/token 性价比）。

---

## 二、为什么不用 mx MCP、用同花顺

- mx-ds-mcp 有**积分/配额限制**，经实测会在中途返回配额耗尽错误（MX_QUOTA_EXHAUSTED），
  不适合做反复实验。
- 同花顺 hithink 系列 skill 依赖 `IWENCAI_API_KEY` / `IWENCAI_BASE_URL`（已在 shell 环境变量中），
  用标准库调用，无第三方依赖、无配额问题，适合实验。

---

## 三、目录结构

```
keeper/
├── README.md               # 本文件
├── config/
│   └── openclaw.json       # keeper profile 的独立 OpenClaw 配置
├── skills/                 # keeper 专属 skills（简化报告 skill + 复用的 hithink 说明）
│   └── company-analysis-simple/SKILL.md
├── plugin/                 # 【未来】档位2 插件代码位
│   ├── src/
│   └── (manifest 等后续)
├── scripts/
│   ├── start_keeper.sh     # 启动 keeper profile gateway / agent
│   ├── run_report.sh       # 跑一次简化公司分析报告（含日志）
│   ├── gen_report.py       # 简化版 report 生成脚本（对照 company_report_api.py）
│   ├── compare.py          # U11 效果对比：质量/token/性价比/稳定性 + 方案 A/B/C
│   └── compare.test.py     # compare.py 单测（T-U11-*，23 例）
├── logs/                   # 【核心】实验日志：每次运行的完整过程
│   ├── (按 run_id / 日期 组织)
├── data/
│   └── reports/            # 生成的报告落盘
├── artifacts/              # 【端到端产出落盘】（规范见 docs/LOGGING.md 第五章）
│   └── <场景>/<run_tag>/…  # 每次 run 的 trace + 报告；场景级 compare 两件套
└── docs/                   # 实验记录、设计文档、操作手册
```

---

## 四、如何启动 keeper 独立环境

keeper 用 OpenClaw 的 `--profile` 机制隔离：

```bash
# 启动 keeper profile 的 gateway（独立 state/config/port，不碰生产）
openclaw --profile keeper gateway run --port 19501

# 或跑单次 agent 任务（在 keeper 环境里）
openclaw --profile keeper agent ...
```

`--profile keeper` 会把 `OPENCLAW_STATE_DIR` / `OPENCLAW_CONFIG_PATH` 隔离到
`~/.openclaw-keeper/`，与生产 `~/.openclaw/` 完全分离。

> 注意：`config/openclaw.json` 需要被复制/链接到 keeper profile 的配置路径才生效，
> 或通过环境变量 `OPENCLAW_CONFIG_PATH` 显式指定。见 `scripts/start_keeper.sh`。

---

## 五、插件开发（档位2）—— 待办

目标插件：在 `api.on("context")` 钩子里，把"带行号的旧 tool 语料"按模型返回的
`key_findings_used` 替换成"只保留被引用行 + 摘要"，实现 OpenClaw 持久会话里的语义级语料压缩。

参考：
- exp02 机制：`/home/stockagent/project_space/research/experiments/exp02/SUMMARY_MECHANISM.md`
- 集成调研（含 api.on("context") 先例）：`/home/stockagent/project_space/research/experiments/exp02/OPENCLAW_INTEGRATION_RESEARCH.md`
- 官方插件开发：`/usr/lib/node_modules/openclaw/docs/tools/plugin.md`、`docs/plugins/building-plugins.md`

迁移要点（来自调研）：
1. 行号稳定契约：取数工具需输出统一可引用格式（如 `<<<CITATION_BLOCK>>>` + `N~ 行`）。
2. 行号↔原文映射在持久 transcript 里需稳定（避免 compaction/pruning 先跑导致错位）。
3. 只改"发模型的那份"（内存），不动盘上 transcript（与原生 pruning 同款语义）。
4. 与原生 `contextPruning`（启发式）优先级：语义级优先或互相配合，需实验确定。

---

## 六、日志体系设计（诊断/评估核心）

每次实验运行应记录：

1. **运行元信息**：run_id、时间、stock、skill 版本、模型、参数。
2. **完整 transcript**：每轮 tool 调用、tool 结果（含是否删减）、模型回复、key_findings_used。
3. **上下文度量**：每轮输入/输出 token（prompt/completion）、tool 结果字节数、删减前后对比、
   命中的 compaction / pruning 事件。
4. **报告产物**：最终报告 markdown（落盘到 `data/reports/`）。
5. **耗时**：每轮 API 时延、总时长。

日志文件建议按 `logs/{YYYYMMDD}/{run_id}/` 组织，内含：
- `run.json`：运行元信息 + 汇总指标
- `requests/{round}.json`：每轮发给模型的 messages（含 tool 结果）
- `responses/{round}.json`：每轮模型返回（含 key_findings_used）
- `context_metrics.json`：token/字节/编译事件时间线
- `report.md`：最终报告

**对比实验设计**：同一 stock、同一 prompt，跑"无压缩 vs 有压缩（档位2插件）"两组，
对比：报告质量（人工/规则打分）、token 消耗（prompt/completion）、耗时、是否触发超窗/compaction。

---

## 七、文档索引

| 文档 | 内容 | 位置 |
|------|------|------|
| 本 README | 实验室总览、启动方式、目录结构 | `README.md` |
| 机制总结 | exp02 行号+引用+压缩机制的原理/实验数据/风险 | `exp02/SUMMARY_MECHANISM.md` |
| 集成调研 | 在 OpenClaw 持久会话落地的调研与三档路线 | `exp02/OPENCLAW_INTEGRATION_RESEARCH.md` |
| 日志体系设计（完整） | 双轨日志、trace 事件目录、KEEPER-LOG 包裹约定、阶段检查单、产出落盘、**清除日志代码说明** | `docs/LOGGING.md` |
| 下一步操作手册 | 联调/验收/效果实验的逐步操作（含需要你参与的步骤） | `docs/NEXT_STEPS.md` |
| 插件设计要点 | 档位2插件的完整预设计（机制闭环/难点/路线） | `docs/PLUGIN_DESIGN.md` |
| 实验记录 | 各阶段做了什么、下一步 | `docs/LAB.md` |
| 简化报告 skill | keeper 专用、同花顺取数、无 mx MCP | `skills/company-analysis-simple/SKILL.md` |

---

## 八、当前状态（2026-08-27）

> 当前阶段：**档位2 插件主体已开发完成（U1–U11），待真 gateway 联调观测**。

- [x] 目录骨架
- [x] exp02 机制总结 + OpenClaw 集成调研
- [x] 插件预设计文档（docs/PLUGIN_DESIGN.md）+ v2 设计定稿（PLUGIN_DESIGN_V2.md）
- [x] 开发方案（docs/DEVELOPMENT_PLAN.md，U1–U11 + 集群 A–E）
- [x] 档位2 插件主体（plugin/，U1–U7 七钩子，73/73 测试通过，含集群 E 全链路伪 loop、T-CE-5 集群 C 联动、T-CE-6 生命线日志）
- [x] 日志体系（docs/LOGGING.md：双轨日志 + KEEPER-LOG 包裹约定 + 清除章）+ 产出落盘（artifacts/）
- [x] 操作手册（docs/NEXT_STEPS.md：联调/验收/效果实验的逐步操作与用户参与清单）
- [x] 驾驶舱（scripts/dashboard.mjs + index.html，U8/U9）
- [x] cite-and-discard skill（skills/cite-and-discard/SKILL.md）
- [x] 效果对比脚本（scripts/compare.py，U11，21/21 测试通过）
- [ ] （未启动）keeper gateway 真跑一次报告并做插件联调观测（需先配 gateway token）
- [ ] （未启）方案 A/B 重放执行：compare.py 已做前置校验，需先补"每轮压缩前/后 messages"到
      trace（见 compare.py 输出的缺失规格；属 U6/装配层的小增强）
- [ ] （未开发）中间轮明细日志（见 docs/LOGGING.md "进阶强化"）

> 说明：插件、驾驶舱、对比脚本均已落地并可独立测试；**真 gateway 运行**（需 token）与
> 方案 A/B 重放的数据基础（trace 持久化每轮 messages）是剩余联调事项，按用户指示待触发。
