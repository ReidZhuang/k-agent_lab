# keeper 日志体系 —— 完整文档

> 本文件是 keeper 日志体系的**唯一权威说明**：双轨日志结构、插件 trace 事件目录、
> 统一 track 注释约定、每阶段日志检查单、测试产出落盘规范、以及**单独成章的
> "清除日志代码说明"**（见第七章）。
>
> 配套文档：`docs/DEVELOPMENT_PLAN.md`（设计/测试/变更）、`docs/LAB.md`（实验手册）、
> `docs/NEXT_STEPS.md`（操作步骤，含逐次落盘命令）。

---

## 一、目的与双轨结构

keeper 的日志分**两条轨道**，各司其职：

| 轨道 | 位置 | 谁写 | 内容 | 状态 |
|---|---|---|---|---|
| 轨道 1：运行实验日志 | `logs/{run_tag}/` | `gen_report.py`（实验运行骨架） | run.json / prompt.txt / usage.json / report.md / result.json | **兼容保留**（gen_report 时代产物，字段见第四章附录） |
| 轨道 2：插件 trace（主力） | `traceDir/`（默认配置指向 `keeper/logs`；每次真实运行应由 runner 指到 `artifacts/<场景>/<run_tag>/`） | keeper 插件（U6 logger） | `trace.jsonl`（每行一个事件）+ `run_stats.json`（汇总）+ `trace_payloads/`（超大 payload 外联） | **全新主力**，本文件重点 |

两条轨道**独立**：没接插件也能跑轨道 1；轨道 2 只依赖插件钩子，不依赖轨道 1。
接入真实 OpenClaw 后，轨道 2 的 trace 是效果对比（方案 A/B/C）的唯一数据基础。

---

## 二、插件 trace 事件目录（完整清单）

文件：`trace.jsonl`（JSON Lines，每行一个事件对象）、`run_stats.json`（汇总）、
`trace_payloads/<id>.json`（`view_before`/`view_after` 的 payload 超过 `payloadMax`
默认 50000 字符时，payload 外联至此、事件里只留 `payload_ref`）。

事件按"产生节点"分组。字段 `runId` 区分一次 agent run；同一 run 内按行序回放即时间线。

### 2.1 生命周期

| 事件 | 产生节点 | 关键字段 | 用途 |
|---|---|---|---|
| `run_start` | 钩子 `before_agent_run` | `tagTools` / `use_trace` / `persist_view_payloads` / `ts` | run 起点；**配置快照**，驾驶舱时间线锚点 |
| `run_finalized` | 钩子 `agent_end` | `events_total` / `warn_fallbacks` | run 终点；事件总数核对 |
| `plugin_error` | 任意钩子异常（失败隔离） | `hook` / `error` | 插件内部错误定位；**有则优先排查** |

### 2.2 打标（tool_result_persist）

| 事件 | 关键字段 | 用途 |
|---|---|---|
| `tagger_doc` | `doc_id` / `n_rows` / `n_sections` | 一次工具结果被转为 JSON 行集（doc 诞生） |
| `tagger_skip` | `tool` / `reason`(`no_info`|`tagger_error`) / `n_chars` | 工具结果无信息/失败，**没**产 doc 的原因 |

### 2.3 工具调用（before_tool_call）

| 事件 | 关键字段 | 用途 |
|---|---|---|
| `tool_call` | `tool` / `toolCallId` / `args_after_strip` | 白名单取数工具被调用（不含辅助参数） |
| `assistant_discard` | `doc_id` / `discard_lines` / `args_after_strip` | 模型申报丢弃行（discard_lines 被剥离，真工具看不到） |

### 2.4 压缩（context 钩子内）

compressor 产生的子事件经装配层 `pumpEvents` **原样透传**：

| 事件 | 关键字段 | 含义 |
|---|---|---|
| `view_before` | `tokens` / `n_messages` / `payload`(或 `payload_ref`) | 该轮压缩**前** messages 全量（方案 A 数据基础） |
| `view_after` | `tokens` / `n_messages` / `saved` / `payload`(或 `payload_ref`) | 该轮压缩**后** messages + 节省量 |
| `discard_applied` | `doc_id` / `n_del` / `n_left` / `lines` | 真正删了行（最核心事件；驱动 saved 计数） |
| `compress_skip` | `reason`(`no_unconsumed_doc`|`doc_id_mismatch`) / `doc_id` | 没有可消费的 doc / doc_id 对不上，跳过 |
| `doc_already_pruned` | `doc_id` | 该 doc 上一轮已压缩（`_meta._pruned`），跳过 |
| `discard_empty` | — | discard_lines 为空数组 |
| `tool_result_error` | `at`(下标) | 错误结果不进入候选 |

### 2.5 输入/token（llm_input / llm_output）

| 事件 | 关键字段 | 用途 |
|---|---|---|
| `llm_input` | `n_messages` / `est_tokens` | **每轮**进模型的消息规模（usage 缺失时的估算旁证） |
| `token_round` | `round` / `input` / `output` / `saved` / `total` / `input_total` / `output_total` | 每轮 token 实测（usage）或估算；`*_total` 为**逐轮累计**。`saved` 恒为 `token_round` 权威值（见 2.6） |

### 2.6 汇总（run_stats.json）

`run_finalized` 时写盘：

```json
{
  "runId": "...", "trace_file": "trace.jsonl",
  "events_total": 15,
  "events_by_type": { "run_start": 1, "tagger_doc": 2, "token_round": 3, "discard_applied": 2, "run_finalized": 1, "..." : 0 },
  "saved_total": 0,
  "warn_fallbacks": 0
}
```

- `events_by_type` 求和 == `events_total`（Cluster C 测试 T-CE-5 钉住）。
- **`saved_total` 只累计 `token_round.saved`**（`view_after.saved` 仅在其缺失时兜底），
  避免同一轮被计两次（历史 bug，见 DEVELOPMENT_PLAN §7）。

---

## 三、统一 track 注释约定（KEEPER-LOG 包裹）

**规则（必须遵守）**：每一处 `logger.log(...)` 调用点，代码里用**成对的固定格式注释**包裹：

```js
// ====[KEEPER-LOG: <事件类型> begin]====
if (logger) { await logger.log({ type: '<事件类型>', ... }); }
// ====[KEEPER-LOG: <事件类型> end]====
```

- 包裹注释的关键词**恒为 `KEEPER-LOG`**，永远成对、首尾呼应、大小写固定。
- 事件类型与注释里的 `<事件类型>` 一致（多事件共用一个节点的用 `a|b` 形式）。
- 新增任何日志调用点**必须**带包裹；删除时按第七章章操作。

**当前全部节点清单**（`plugin/src/assembly.js`；新增节点须同步更新此表与第二章）：

| 节点 | 事件类型 | 位置 |
|---|---|---|
| before_agent_run | `run_start` | assembly.js 钩子 0 |
| tool_result_persist | `tagger_doc` / `tagger_skip` | assembly.js 钩子 1 |
| before_tool_call | `tool_call` / `assistant_discard` | assembly.js 钩子 2 |
| context | `view_before` / `view_after` + compressor 透传 | assembly.js 钩子 3 |
| llm_input | `llm_input` | assembly.js |
| llm_output | `token_round` | assembly.js |
| agent_end | `run_finalized` | assembly.js |
| pumpEvents | compressor 子事件透传 | assembly.js |
| safe() | `plugin_error` | assembly.js |

---

## 四、测试/联调阶段日志检查单

> 原则：**每阶段开始前必先确认日志就绪**；跑完立即核对 trace。发现缺日志 → 按
> DEVELOPMENT_PLAN §2"先记录后修复"处置，**绝不带病往下跑**。

### 4.1 测试前（每阶段必查）
- [ ] `plugin/src/` 全量测试通过（`cd plugin && node --test`），日志改动不影响 73 个测试。
- [ ] 新事件类型已登记第二章表 + 第三章节点清单（grep `KEEPER-LOG` 核对包裹成对）。
- [ ] trace 目录可写：`artifacts/<场景>/<run_tag>/` 已创建（见第五章）。

### 4.2 单测/冒烟后
- [ ] mock api 冒烟（assembly.test.js）：`run_start` → `tagger_doc` → `assistant_discard` →
      `llm_input` → `token_round` → `view_before/after` → `run_finalized` 依序出现（T-CE-1/5/6）。
- [ ] `run_stats.json`：`events_by_type` 求和 == `events_total`；`saved_total` 只来自 `token_round`。

### 4.3 真实联调 run 后（落地 artifacts/）
- [ ] trace 有 `run_start` 与 `run_finalized`（跑完是"完整闭环"而非"被中断"）。
- [ ] 若非 `usage` 缺失，`token_round.usage_unavailable` 应为 0；有 `warn_fallbacks` 则查估算口径。
- [ ] `tagger_skip` 高发 → 取数结果本身信息不足或 tagger 规则误判；`plugin_error` 有则最先排查。
- [ ] 报告 + 对比报告均已落盘（第五章命名规范），未被静默覆盖。

---

## 五、测试产出落盘（artifacts/）

所有端到端运行 / 对比实验的产出**必须落盘**到 keeper 仓库内固定目录：

```
keeper/artifacts/
└── <场景>/                       # 场景名（e2e_smoke / e2e_baseline_vs_plugin / e2e_case_<标的>…）
    ├── <run_tag>/                # 一次 run：YYYYMMDD_HHMMSS_<标签>（如 20260827_2359_keeper01）
    │   ├── trace.jsonl           # 插件 trace（traceDir 指向本目录）
    │   ├── run_stats.json
    │   ├── trace_payloads/       # 超大 payload 外联（自动）
    │   ├── report.md             # 本次 run 的**产出报告**（报告生成器最终正文）
    │   ├── report.json           # 本次 run 的**结果摘要**（ok/model/usage/elapsed…）
    │   └── (raw_response.json 等, 若有)
    ├── compare_report.md         # **对比报告一：人工可读报告**
    └── compare_metrics.json      # **对比报告二：机器可读指标**
```

- **目录名** = 场景 + run_tag（时间 + 标签）→ 每次测试、每次结果天然可区分、可追。
- **对比报告两件套固定文件名** `compare_report.md` + `compare_metrics.json`
  （compare.py `--out <场景>/` 一次产出两份，MT 不覆盖）。
- 冲突保护：run_tag 含到秒时间戳 + 标签，同秒重跑请加标签序号（`_b`/`_c`），不覆盖。
- 同步纪律：worktree 内跑出的 artifacts 同步回主 checkout（`script` 复制，见 MEMORY.md 工作区同步约定）。

---

## 六、驾驶舱（dashboard）读法

- 启动：`node scripts/dashboard.mjs --dir <artifacts>/<场景>/<run_tag>/`，浏览器开
  `http://localhost:<port>/`。
- 读法：时间线看 `run_start → … → run_finalized` 是否闭环；Token 面板看逐轮
  `token_round`（`input_total` 累计）/ `saved`；压缩面板看 `discard_applied` 每笔删行；
  异常看 `plugin_error` / `tagger_skip`。
- U9 手动验收清单（T-U9-2..4）针对驾驶舱逐项勾选，详见 DEVELOPMENT_PLAN §7.3。
- **注意**：`trace.jsonl` 是"真相"，驾驶舱只是渲染；任何怀疑先原始事件定位。

---

## 七、清除日志代码说明（单独成章）

> 目的：未来若需精简/移除日志（比如换日志平台、或确认 keeper 稳定想卸掉 trace 负担），
> 按本章操作可**干净、可回滚、不误删核心功能**地移除。

### 7.1 三档清除策略（先选档）

| 档 | 效果 | 操作量 | 何时选 |
|---|---|---|---|
| A. 只关事件 | 不写 trace.jsonl，但代码保留 | 最小：配置 `"trace": false` | 临时降噪 / 性能敏感期 |
| B. 移除调用点 | 删掉各节点 `logger.log` 调用与包裹注释 | 中：按 7.2 逐个节点 | 日志体系彻底退役 |
| C. 移除机制 | 连 logger.js / traceDir 配置一起删 | 大：按 7.3 | keeper 定位变化，不再需要 trace |

### 7.2 定位包裹段（B 档核心操作）

所有可移除的日志代码**都用 `KEEPER-LOG` 成对注释包裹**。定位方式：

```bash
grep -n "KEEPER-LOG" plugin/src/*.js          # 列出全部包裹对
grep -c "KEEPER-LOG:.*begin" plugin/src/*.js  # begin 数与
grep -c "KEEPER-LOG:.*end"   plugin/src/*.js  # end 数必须相等（成对完整校验）
```

逐节点删除一个包裹对 = 删除 `begin` 注释行 与 `end` 注释行**之间的全部代码**（含 `logger.log` 调用），
注释对本身一并删。**凭注释对删除，绝不凭"看起来像日志"手改**。

### 7.3 完整移除流程（B/C 档）

1. **先记**：在 DEVELOPMENT_PLAN §7 变更日志写一行"移除 xx 日志节点（原因/日期）"。
2. 按 7.2 删除目标节点包裹段（B 档）或删除 `plugin/src/logger.js` + 相关引用（C 档）。
3. **同步清理配置与 schema**：
   - `config/openclaw.json` / 全局 `~/.openclaw/openclaw.json`：删掉
     `plugins.entries.keeper-corpus-compress.config` 里的 `traceDir`、`trace`、`persistViewPayloads`、`payloadMax`。
   - `plugin/openclaw.plugin.json`：删掉 `configSchema` 里对应键（`traceDir`/`trace`/`persistViewPayloads`/`payloadMax`）。
   - `scripts/dashboard.mjs` 与 `docs/LOGGING.md`：标记"已退役"或删除（dashboard 读 trace，trace 没了它也没输入）。
4. **验证**：`cd plugin && node --test` 必须全绿（73 个测试不依赖日志存在性；
   只有 T-CE-1/5/6 会断言 trace 内容 —— 若同时开了 C 档，需同步更新这三个测试）。
5. **回滚预案**：git 未跟踪目录 → 删除前先备份（rsync 到 `jobs/<id>/tmp/` 或打 tar）；
   B 档每删一个节点单独验证，别一次删完再找回归。

### 7.4 不允许删的"日志"

- `run_stats.json` 汇总与 `view_before/view_after` payload 是**方案 A/B 重放与效果对比的
  数据基础**（DEVELOPMENT_PLAN §6 验收项）。永久关闭前必须确认不再需要效果实验。
- `token_round` / counter 是"动态 token 计算器"能力的本体（U5），删除即删功能，不在"清日志"范围内。

---

## 附录：轨道 1（logs/）字段参考（gen_report 时代，兼容保留）

`logs/{run_tag}/`：`run.json`（元信息：stock/时间/模型/skill/数据源/session_key）、
`prompt.txt`（本次 prompt）、`requests/`（每轮 messages）、`responses/`（每轮回复）、
`usage.json`（token/耗时/报告长度）、`report.md`（最终报告）、`result.json`（汇总）。
该轨道的诊断检查单见第二节历史版（repo 早期 README 摘录），不再维护；新实验一律走轨道 2。