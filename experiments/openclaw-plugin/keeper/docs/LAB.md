# LAB 实验记录 —— keeper 插件实验室

> 每个实验/阶段追加记录。按时间倒序。

## 2026-08-27 —— 档位2 插件开发完成（U1–U11，全部单测通过）

**目标**：按 DEVELOPMENT_PLAN.md 把"exp02 语料压缩"做成 OpenClaw 插件，小单元 + 测试驱动，
最终交付驾驶舱与效果对比能力。

**已完成**：
- U1–U7 插件主体（contract/tagger/cleaner/compressor/tokenizer+counter/logger/index 装配）：
  `node --test` 73/73 通过；含集群 A–E 协同测试，集群 E 用 Mock api + OpenClaw 真实 Message 形状
  跑通"注册→打标→剥离→配对删行→_pruned→日志→汇总"全链路（assembly.test.js 8 例）。
- U8/U9 驾驶舱：`scripts/dashboard.mjs`（/api/runs + SSE /api/events 回放+尾随）+ index.html
  事件卡片/Token 面板/压缩前后 diff/run 切换；dashboard.test.js 覆盖 U8 接口与首页冒烟。
- U11 效果对比：`scripts/compare.py`（stdlib-only，conda stock_agent 运行）——
  布局自动识别（gen_report run 目录 / 插件 trace 目录）、逐轮 token（usage 优先、缺 use 走估算，
  与 counter.js 同口径）、压缩节省（token_round.saved 为准防重复计）、质量四规则（骨架/草稿污染/
  引用抽查/免责结尾，无源引用记 N/A）、性价比（质量÷total）、稳定性可疑事件；
  方案 A/B 做前置数据校验+上下文重建并落盘，方案 C 多 run 中位数聚合；`compare.test.py` 21/21 通过。
- 变更纪律执行：测试发现 3 个局部缺陷（plan_b partial 判定、quality details 漏字段、
  saved 重复计）均记录 DEVELOPMENT_PLAN.md §7 并局部修复。

**未做（下一步）**：
- 真 gateway 联调观测（需先配 keeper profile gateway token）：跑基线组/插件组各若干 run，
  驾驶舱实时看事件，compare.py 出对比报告。
- 方案 A/B 重放执行：需先在 U6/装配层把"每轮压缩前/后 messages + 原始 tool 结果"持久化到
  trace（compare.py 输出已给出缺失规格）。
- 方案 C 需 N≥3 组数据才有效力；当前无真数据。

**关键约定（延续）**：测试结果必须同步回主 checkout（keeper 目录不入 git，以主 checkout +
jobs 备份为交付位）；插件/misc JS 用零依赖 ESM + node --test，Python 一律 conda stock_agent。

## 2026-08-19 —— 初建 keeper 实验室骨架

**目标**：为"把 exp02 语料压缩机制做成 OpenClaw 插件（档位2）"建立独立实验环境。

**已完成**：
- 独立 OpenClaw 环境机制：`openclaw --profile keeper`（隔离到 `~/.openclaw-keeper/`，
  独立 state/config/port，不碰生产）。
- 配置 `config/openclaw.json`：new agent `keeper`、无 mx MCP、模型 deepseek-v4-flash、
  compaction 已按实验设置为 midTurnPrecheck.enabled=false（保持默认 disabled）。
- 简化版报告 skill `company-analysis-simple`（数据源用同花顺 IWENCAI，无 mx MCP 配额）。
- 脚本：`start_keeper.sh`（启动独立 gateway）、`run_report.sh` + `gen_report.py`
  （跑一次报告 + 记录全过程日志）。
- 日志体系设计 `docs/LOGGING.md`。
- 背景文档：`exp02/SUMMARY_MECHANISM.md`、`exp02/OPENCLAW_INTEGRATION_RESEARCH.md`。

**后续（用户指示：暂不开发，仅文档化）**：本次只做文档化，开发（启动 gateway、跑通报告、写插件、中问轮日志）均延后。

**未做（下一步，待用户触发开发）**：
- 真正启动 keeper gateway 并跑通一次报告（需先设置 keeper profile 的 gateway token）。
- 档位2插件开发（`plugin/` 目前只有 `src/` 空目录）。
- 中间轮明细日志（见 LOGGING.md "进阶强化"）。

**关键约定**：
- keeper 环境**严禁调用 mx MCP**（有限额）——一律用同花顺 IWENCAI。
- 配置属实验性质，随时可改，不影响生产（独立 profile）。
