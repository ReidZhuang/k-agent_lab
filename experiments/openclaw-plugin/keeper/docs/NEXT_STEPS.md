# keeper 联调 & 效果实验 —— 操作步骤（含你需要参与的部分）

> 状态：开发已完成（U1–U11 + 集群 A–E，72 node + 23 python 测试全绿），
> 剩余 4 项**全部需要真实 gateway**：联调观测 → U9 浏览器验收 → 效果对比实验 →
> 联调中新问题的记录-修复。本文档逐条列明**每一步谁做、做什么、成功标准、失败怎么办**。
>
> 日志与落盘规范见 `docs/LOGGING.md`；测试产出一律落 `artifacts/`（第五章）。

---

## 〇、现在已就绪的东西（不用你做）

- [x] keeper 插件本体 `plugin/`（manifest + 7 源件 + 73 单测），内容全绿。
- [x] 仓库内 `config/openclaw.json`：已含 keeper agent + `plugins.entries.keeper-corpus-compress`
      （`allowConversationAccess=true`、`traceDir` 指向 `keeper/logs`）+ 取数工具白名单。
- [x] 日志体系：trace 事件目录、`KEEPER-LOG` 包裹约定、落盘规范（`docs/LOGGING.md`）。
- [x] 对比工具 `scripts/compare.py`（23 单测；`--out` 一次产 compare_report.md + compare_metrics.json 两件套）。
- [x] 驾驶舱 `scripts/dashboard.mjs`（U9；渲染 trace 用）。

---

## 一、阶段 0：接入真实 OpenClaw（首次一次性；需要你 2 次操作）

> 变更目标：把 keeper 插件装进 gateway 的插件发现源 + 把 keeper 配置并入全局
> `~/.openclaw/openclaw.json`。**两处都会动生产 gateway 环境**，所以重启这一步由你执行。

### 步骤 0.1 装插件 —— ✅ 已完成（我做）
```bash
openclaw plugins install --link /home/stockagent/project_space/research/experiments/openclaw-plugin/keeper/plugin
openclaw plugins list | grep keeper-corpus-compress   # → 已可见 keeper-corpus-compress, Status=enabled
```
> 过程中发现并修复一个真问题：**OpenClaw 要求 register 必须同步**，原 `async register +
> await createLogger` 会 register 失败。已把 logger 改为同步 fs 构造、register 同步调用
> createKeeper（单测 73/73 仍全绿）。`--link` = 链接本地目录，改代码无需重装。

### 步骤 0.2 合并 keeper 配置进全局（**需要你执行或明确授权**）
把仓库 `config/openclaw.json` 的三段并入 `~/.openclaw/openclaw.json`：
- `agents.list` 追加 `keeper` agent；`plugins.entries` 追加 `keeper-corpus-compress`；
  `skills.load` 追加 keeper `skills/` 目录。
已备好合并脚本（**自动备份** `~/.openclaw/openclaw.json.bak-keeper-<时间戳>`，增量合并，不打印任何 key 值）：

```bash
# 方式 A：你在此会话输入框敲（效果等同"你给我跑"）：
! /home/stockagent/miniforge3/envs/stock_agent/bin/python /home/stockagent/.claude/jobs/a68df480/tmp/merge_keeper_config.py /home/stockagent/project_space/research/experiments/openclaw-plugin/keeper/config/openclaw.json /home/stockagent/.openclaw/openclaw.json

# 方式 B：你在终端直接跑同一条命令
```
> ⚠️ 我此前尝试代为执行时被权限护栏拦下（改全局配置属敏感系统变更，需你点头）。
> 合并是**增量、可回滚**的：不删除任何现有键，只加 keeper 相关段。

### 步骤 0.3 重启 gateway（**你执行**；会短暂打断当前 agent/通道）
```bash
systemctl --user restart openclaw-gateway
systemctl --user status openclaw-gateway     # running；日志无启动即失败的 secret 引用报错
```
> 为什么留给你：生产服务归 systemd user 管（memory 规定不得手动抢端口/越权）。选低峰时刻。

### 步骤 0.4 验证插件加载（我做，**0.3 之后跑**）
```bash
openclaw plugins doctor      # 期望现在只见到 "hook-only 兼容路径" 的 info 提示（正常），无 register/load 错误
openclaw plugins list | grep keeper
openclaw agent --agent keeper --message "ping"   # 轻量回路（gateway 在线时；此步消耗 1 次极小额模型调用）
```
失败 → 按 doctor 输出修配置再 **重新执行 0.3**。改动会**通过 --link 实时生效**，无需重装。

---

## 二、阶段 1：第一次真实 smoke run（联调观测；烧 token 前先看成本）

> **纪律**：真实 model 调用**只测一次、失败即停、绝不自动重试**（memory：report_rc
> 只测一次不重试；额度是稀缺资源）。冒烟用小 prompt，不跑完整报告。

### 步骤 1.1 定标与清单（5 分钟，我做）
- **新会话强制**：`--session-key "agent:keeper:smoke-<日期>"` —— 实测 `openclaw agent --agent keeper`
  默认复用主 session 文件（smoke1/2/3 全堆在一个 session 里），模型看到历史直接复用旧数据不取数，
  压缩链无从触发。**每次 smoke 必须显式开新 session-key。**
- 选一个**会触发取数工具**的新提问（**新公司**，历史里没有的），例如"生成 XX 公司的公司分析报告"
  —— 保证 `before_tool_call → tool_result_persist → tagger_doc → llm_output` 都会走到。
- 按 `docs/LOGGING.md` 第四章 4.1 跑一遍"测试前检查单"。
- 已知架构约束（2026-08-30 定稿，替代 2026-08-28 旧版）：插件 API 的 typed-hook 白名单**无 `context` 钩子**、
  extension 路径（嵌入式 loader `noExtensions:true`）也死路——但**插件 API 的 ContextEngine 槽位
  （`registerContextEngine` + `plugins.slots.contextEngine` + `info.ownsCompaction:true`）是活的每轮视图
  接缝**：selection 每轮调 `assemble()`，返回的新数组即发给模型的 prompt（v2.4 起 engine 内 `liveTagger`
  先把门控取数结果改写为 keeper 行集——模型真正看到行号才能按 `discard_lines` 申报——再走
  `compressView` 行级压缩）。persist（打标落盘 archive）与 live（打标+压缩进模型视图）两路共用同一份
  doc（按 toolCallId 记忆化，doc_id/行号一致）。判据 trace：`view_before`/`view_after`/`tagger_doc(source:
  live)`/`discard_applied`/`plugin_error=0`。v2.4.2 补充：① resume 会话的历史 exec 结果无 live 登记
  （新实例 execReg/docsByTcId 为空、exec 不在 tagTools 白名单）→ liveTagger 新增 `reconstructCmdHit`
  （沿消息序列向前定位该 toolCallId 的 assistant toolCall，复刻命令模式命中判定），历史取数结果照常
  打标；② compressor 由"只消费最新未消费 doc"改为**显式 doc_id 精确命中优先**（未指定才退最新；
  `_pruned` 不进候选天然防重复删），resume 多 doc 窗口下模型指向更早大表的申报不再被拒。

### 步骤 1.2 执行（我做；**单次**、`--json`、`--session-key`）
```bash
cd /home/stockagent/project_space/research/experiments/openclaw-plugin/keeper
openclaw agent --agent keeper --session-key "agent:keeper:smoke-$(date +%Y%m%d)" --json -m "<新公司，强制取数>"
```
（若该 agent 路由需要 `--channel last` 或其他参数，联调时按 gateway 提示调整；优先直连本地。）

### 步骤 1.3 整理产物（我做）
把 `logs/` 下本次 trace 与报告按规范搬进 `artifacts/e2e_smoke/<run_tag>/`（LOGGING.md 第五章），
跑 `run_stats` 核对 4.2/4.3 检查单。

### 步骤 1.4 判据（你我各看一半）
- trace 闭环：`run_start … run_finalized`，`plugin_error` = 0，`tagger_skip` 合理。
- **你**确认：回答本身内容/质量没被压缩弄坏（对照 `view_before`/`view_after` 的差集）。
- 结果只有三态：**成功** → 进阶段 2；**插件没生效（trace 空）** → 回 0.1–0.4 修配置；
  **回答质量受损** → 停，先记录后修复（调 discard 契约/压缩规则），**不重试烧 token**。

---

## 三、阶段 2：U9 浏览器验收（你需要 10 分钟）

### 步骤 2.1 起驾驶舱（我做）
```bash
node scripts/dashboard.mjs --dir artifacts/e2e_smoke/<run_tag>/
```

### 步骤 2.2 你按 T-U9-2..4 条款逐项勾（对照 DEVELOPMENT_PLAN §7.3 验收清单）
- T-U9-2 时间线（run_start→run_finalized 闭环、事件顺序正确）？
- T-U9-3 事件明细面板（token_round 逐轮 / discard_applied 删行 / view 前后差集）可展开可读？
- T-U9-4 统计面板（run_stats 汇总 / saved_total 与面板一致）？

勾完把结果告诉我。任一不通过 → 记录到 §7 变更日志一起修。

---

## 四、阶段 3：效果对比实验（烧 token 最多的一步）

> 目的：同一批问题，跑**基线组**（keeper 插件禁用）与**插件组**（启用），用 compare.py
> 产出对比报告两件套。每次 run 都落 `artifacts/e2e_<标的>/<run_tag>/`。

### 步骤 4.1 定实验矩阵（我做，写进 artifacts 里，先给你过目再跑）
- 取 **2–3 个代表性提问/报告任务**（信息密度高 → 压缩收益明显）。
- 每组 **≥2 次** run（对照 temperature≠0 随机性；方案 C 中位数口径需 N≥3）。

### 步骤 4.2 跑基线组 / 插件组（我做；逐次单发，失败即停）
- 基线：`plugins.entries.keeper-corpus-compress.enabled=false`（改配置→重启 gateway←**你**再点一次头）
  或跑在另一个未装插件的 agent 上（执行时选轻量路径）。
- 插件组：阶段 1 同配置。

### 步骤 4.3 汇总（我做）
```bash
python scripts/compare.py --group baseline="artifacts/e2e_<标点>/baseline_*/;..." --group plugin="..." \
  --out artifacts/e2e_<标点>/ --role-baseline baseline
```
产出 + 解读（骨架/污染/引用/性价比维度；方案 A/B 条件满足则给出重放命令与报告）。

### 步骤 4.4 判据（你拍板）
- 插件组 token 节省 vs 质量分变化 → 出一个"上不上线"结论。
- 附带物：opencode-go 是否回传 usage（`token_round.usage_unavailable` 计数；DEVELOPMENT_PLAN §9.2 实测项）。

---

## 五、每阶段我产出什么给你

| 阶段 | 我交出的东西（都落盘） |
|---|---|
| 0 | 备份+diff 后的全局配置说明；`plugins doctor` 输出 |
| 1 | `artifacts/e2e_smoke/<run_tag>/`（trace + run_stats + report）+ 检查单结果 |
| 2 | 你勾选后的验收结论（回写 DEVELOPMENT_PLAN §7.3）|
| 3 | `artifacts/e2e_<标的>/compare_report.md` + `compare_metrics.json` + 结论建议 |
| 全程 | 新问题 → DEVELOPMENT_PLAN §7 变更日志（先记录后修复）|

---

## 六、明确需要你参与的清单（最短路径）

1. **0.3**：`systemctl --user restart openclaw-gateway`（+确认 running）。
2. **1.4 / 2.2**：10 分钟 —— 看一次 smoke 输出的质量、勾 U9 验收 4 条。
3. **4.2**：点头同意"禁用插件跑基线组"的配置变更 + 一次重启。
4. **4.4**：拍板"是否上线"。

其余（装插件、配置合并 diff、跑 run、汇总对比、写日志）都我来。token 消耗按"只测一次"
纪律逐步申报：阶段 1 一次小提问 ≈ 最省，阶段 3 才是有意义的消耗，跑之前在 4.1 先给你报数。