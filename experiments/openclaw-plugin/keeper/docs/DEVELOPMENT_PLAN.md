# keeper 档位2插件 开发方案（DEV PLAN）v1

> 版本：2026-08-26 · 承接设计定稿：`docs/PLUGIN_DESIGN_V2.md`（v2.1，含 2026-08-26 拍板记录）
> 目标：把插件按**小的、尽量独立的开发单元**拆解，每个单元开发+测试（冒烟+案例），集群协同测试，
> 最后驾驶舱联调观测 + 效果对比实验。本文件是开发阶段的**操作手册**。

---

## 0. 执行顺序一览（先做不依赖 gateway 的，最后再做需要真环境的）

```
Step1  纯函数单元：U1→U2→U3→U4→U5→U6   （不需要 keeper gateway，现在就能做）
   ↑ 每单元做完：冒烟 + 案例测试（50%，冒烟+常规）
Step2  驾驶舱：U8 → U9                   （用样本 trace 数据渲染）
Step3  插件装配：U7                      （需要 gateway：先填入 gateway token）
Step4  集群协同测试：Cluster A→B→C→D→E  （A/B/C/D 可不依赖 gateway 先做; E 需 gateway）
Step5  全链路冒烟 + 联调观测（驾驶舱看真实 loop）
Step6  效果对比：U11（三方案 + 指标表）
```

> M1 基线（无插件的 token/耗时/质量基线）可以并行进行：一旦 gateway token 就位，先跑基线再跑插件组。
> U1–U6、U8、U9、以及 Cluster A/B/C/D 的协同测试**全程不需要网关**，不阻塞。

---

## 1. 设计定稿摘要（v2.1 已拍板，详见 PLUGIN_DESIGN_V2.md §2.5）

- 取数结果 = JSON 行集（`doc_id` + `sections[].rows[{n,k,t}]` + `_meta`）；行粒度 = 语义单元混合（表格按行、散文按段/句）；行号 `n` 稳定不重编号。
- 模型只报"完全没用的行"：下一工具调用参数 `discard_lines: [n,…]`（可省略）；skill `cite-and-discard` 已就位。
- 三钩子（v2.4 定稿）：`tool_result_persist` 打标（盘上 archive）→ `before_tool_call` 剥离
  `discard_lines` 辅助参数 → **ContextEngine 槽位**的 `assemble()` 做 live 视图改写+行级压缩
  （v2.4 起 assemble 先经 `liveTagger` 把门控 toolResult 改写为 keeper 行集——模型才真正看到行号，
  能按 `discard_lines` 申报——再走 `compressView` 删行；只改发给模型的内存视图，不动盘上 transcript）。
  ⚠️ `api.on("context")` 在插件 API（typed-hook 白名单）与网关嵌入式 extension 路径（`noExtensions:true`）
  均无入口；插件可达的"每轮视图"接缝 = `registerContextEngine` + `plugins.slots.contextEngine` +
  `ownsCompaction:true`（selection 的 `installContextEngineLoopHook` 每轮调 `assemble()`，见 §9.1）。
- 已筛文档带 `_pruned` 标记 + `doc_id`；模型只筛"最新一份未标记文档"。
- 追回机制（restore）：**v2 不做**；trace 日志作为"恢复源"永久保存原文+删除记录。
- 无状态幂等：`transformContext` 返回值不回写 `context.messages`，压缩视图每轮从原始消息重建。

---

## 2. 工程纪律（用户定，全员遵守）

1. **一个单元一个主题**，接口尽量小、内部尽量纯函数，先测纯函数再薄适配。
2. **每单元必有测试**：冒烟测试（能不能跑 / 最主要路径）+ 案例测试（3–10 个，正常/边界）。测试不通过=单元不算完成。
3. **案例两段式**：开发方案阶段写 50%（冒烟+常规，见第 4 节每个单元的 `T-Ux-*` 清单）；开发后结合踩坑补另外 50%（极端/罕见情况），补进"第 8 节 测试案例追踪表"。
4. **变更纪律（重要）**：测试发现问题时——
   1. 先在"变更日志"（第 7 节）记录：问题、复现输入、期望 vs 实际、影响面；
   2. 先尝试**局部优化**（改这个单元内部）；
   3. 局部优化达不到预期 → 考虑**整体优化**（跨单元/跨集群改动）；
   4. **整体设计变更必须通知用户，由用户决定**后才可动（PLUGIN_DESIGN_V2.md §2.5 底部同样记录此纪律）。
5. **紧密联系单元组成集群**，单独测完必做集群协同测试（第 5 节）。集群划分在本文件第 3 节就定死，不事后补。
6. **实现语言约定（2026-08-26 定）**：插件全部用**零依赖 JS ESM**（`*.js`，type:module）+ JSDoc 类型标注，**不用 TypeScript/构建步骤**；单测用 Node 内置 `node --test`（环境已确认 node v24.16.0）。理由：插件体量小、OpenClaw 侧以运行时 JS 为准，去构建链降低装配与调试摩擦。

---

## 3. 开发单元划分（U1–U11）

| 单元 | 文件 | 职责 | 依赖 | 类型 | 集群 |
|---|---|---|---|---|---|
| U1 | `plugin/src/contract.js` | JSON 行集类型+校验；`normalizeRowset`/`normalizeDiscard`；常量与 `doc_id` 生成 | — | 纯函数 | A |
| U2 | `plugin/src/tagger.js` | 原文→JSON 行集（语义单元切分、k 分类、n 编号、source 元数据、_meta） | U1 | 纯函数 | A |
| U3 | `plugin/src/cleaner.js` | `stripAuxParams`：从工具参数剥离 discard_lines 等辅助字段 | U1 | 纯函数 | B |
| U4 | `plugin/src/compressor.js` | `indexActiveDoc`/`pruneDoc`/`applyCompression`：配对→删行→_pruned 标记→事件输出 | U1,U2 | 纯函数 | B |
| U5 | `plugin/src/tokenizer.js` + `counter.ts` | 本地 token 估算（消息/文档级）与 provider usage 回填、累计 | U1 | 纯函数 | C |
| U6 | `plugin/src/logger.js` | trace 事件构造+写入(trace.jsonl/run_stats/payload 落盘)、低延迟批量 | U5 | 函数+IO | C |
| U7 | `plugin/src/index.js` + manifest | definePluginEntry、注册三钩子、读 pluginConfig、失败隔离、装配 | U2,U3,U4,U6 | 装配(需 gateway) | E |
| U8 | `scripts/dashboard.mjs` | 零依赖 Node 服务：静态页 + /api/runs + SSE /api/events（回放+尾随） | — | 服务 | D |
| U9 | `scripts/dashboard/index.html` | 驾驶舱前端：事件卡片/Token 面板/消息预览/A 与 B 对比(压缩前后)/run 切换 | U8 | 前端 | D |
| U10 | （不开发）restore 追回 | 已拍板 v2 不做，M4+ 增强待命；恢复源由 U6 保证 | — | — | — |
| U11 | `scripts/compare.py` | 效果对比三方案执行 + 指标计算 + 报告生成 | 各插件/日志产物 | 脚本 | E |

## 4. 单元详细设计 + 测试案例清单（本轮先给 50%：冒烟+常规）

> 案例编号 `T-Ux-脚本`；断言全部在代码里可执行（纯函数直接单测，装配用模拟事件对象）。
> 极端/罕见案例（另一半 50%）开发后补，见第 8 节待办区。

### U1 contract.js
输入：原始 JSON 行集 / discard 数组。输出：规范化后的行集 / 规范化 discard。
核心函数：`normalizeRowset(json)→{ok,value|errors}`（字段检查：sections/rows/n 连续唯一/t/k 合法/_meta）、`normalizeDiscard(dl,maxN)→number[]`（去重、排序、剔除不存在行号、忽略非法）、`genDocId(seq)→"doc_<seq>"`。
冒烟：
- `T-U1-1`：一个合法完整行集通过 normalizeRowset，字段齐全、n 连续。
常规：
- `T-U1-2`：`normalizeDiscard([3,1,3,99], maxN=10)` → `[1,3]`（去重排序+越界剔除）。
- `T-U1-3`：discard 传 null/undefined/非数组 → 视为无删除。
- `T-U1-4`：行集缺 sections 或缺 rows → 校验失败并给出错误信息。
- `T-U1-5`：n 不连续（跳号）→ 校验失败。
- `T-U1-6`：k 出现非法值 → 校验失败。

### U2 tagger.js
输入：工具返回的文本块数组 + 元数据{tool, query, fetched_at}。输出：JSON 行集文档。
核心：语义单元切分（表格/列表按行、散文按段/完整句）、空行剥离、k 启发式分类（信号词表：免责/仅供参考/版权→u；含数字→v；表头分隔符样式→h；其余→t）、n 编号、`_meta` 组装。
冒烟：
- `T-U2-1`：典型表格文本 → 每个数据行一行、n 连续、k 合理，输出是合法行集（过 U1 校验）。
常规：
- `T-U2-2`：长散文段落 → 按段落/完整句切，**无任何一行是半个句子**（断言：每行以句号/分号/换行结尾或长度<阈值）。
- `T-U2-3`：空文本/全空行 → 返回 n_rows=0 或 null（约定：无信息不产 doc）。
- `T-U2-4`：多个文本块（表格+备注）→ 各成 section，行号跨 section 连续。
- `T-U2-5`：超长单行（>maxRowChars）→ 按规则截断或升级为段内切分（策略写死一个，后续极端案例再验）。
- `T-U2-6`：免责声明/版权信号词行 → k=u。

### U3 cleaner.js
输入：工具参数对象。输出：`{rest, aux}`（rest=发给真工具的参数，aux=被剥离的辅助字段）。
冒烟：
- `T-U3-1`：参数含 discard_lines → rest 无该字段、aux 保留其值。
常规：
- `T-U3-2`：参数不含 discard_lines → rest 原样、aux 为空。
- `T-U3-3`：discard_lines 为 null → 照常剥离。
- `T-U3-4`：嵌套其他参数不受影响（浅拷贝不改原对象）。

### U4 compressor.js（核心，案例最多）
输入：AgentMessage[]（模拟 OpenClaw 消息序列）。输出：`{messages, events[]}`。
核心：`applyCompression(messages)` 一趟扫描——维护"最新未消费 doc"指针；assistant 带 `discard_lines` 时消费该 doc。
冒烟：
- `T-U4-1`：单工具结果 + 下一条 assistant 带 discard → 该 doc 按声明删行、_meta 加 _pruned、其余消息不动、返回事件。
常规：
- `T-U4-2`：无任何 discard（assistant 无工具调用）→ 不变。
- `T-U4-3`：旧 doc + 新 doc 混在一起，模型 discard 指向最新一份 → **只删最新那份**，旧 doc 不动。
- `T-U4-4`：连续三轮（doc0→dl1→doc1→dl2）→ doc0 被 dl1 删、doc1 被 dl2 删，两两独立。
- `T-U4-5`：discard 含不存在行号 → 忽略，只删存在的。
- `T-U4-6`：错误 toolResult（isError）夹在中间 → 跳过不删。
- `T-U4-7`：幂等：同一输入跑两次输出完全一致（事件列表也一致）。
- `T-U4-8`：删行后剩余行号**不变号**（n 保持原值）。
- `T-U4-9`：doc 已带 _pruned（上一轮产物）出现在消息里 → 不再被新 discard 消费（跳过）。

### U5 tokenizer.js + counter.js
输入：文本/消息数组/usage。输出：token 估算 & 累计统计对象。
冒烟：
- `T-U5-1`：一段已知文本 countTokens>0，空文本=0。
常规：
- `T-U5-2`：同一文本重复计数稳定（确定性）。
- `T-U5-3`：中文文本估算合理（>0 且量级正确，与 usage 校正系数联动）。
- `T-U5-4`：estimate((viewBefore)) − estimate((viewAfter)) = 节省量，方向正确。
- `T-U5-5`：usage 缺失 → 走估算回退，标志 `usage_unavailable`。
- `T-U5-6`：累计器：多轮累加/均值/环比结果正确。

### U6 logger.js
输入：事件(构造器)+ 运行上下文。输出：trace.jsonl 追加、run_stats.json、payload 落盘。
冒烟：
- `T-U6-1`：写一条事件 → 文件产生且内容可反序列化为 JSON。
常规：
- `T-U6-2`：目录不存在 → 自动创建。
- `T-U6-3`：批量写入（多事件）顺序与内容正确。
- `T-U6-4`：写失败（只读目录/磁盘错误模拟）→ 不抛、回退 console 警告。
- `T-U6-5`：payload 过大 → 写 trace_payloads/<id>.json，trace.jsonl 只留引用。

### U7 index.js（装配）
输入：definePluginEntry register(api)。输出：三个钩子被注册、配置生效、失败隔离。
冒烟：
- `T-U7-1`：enabled=false → 钩子不注册（或注册后立即 return）。
- `T-U7-2`：enabled=true → 三个钩子都注册成功。
常规：
- `T-U7-3`：tagTools 配置决定哪些工具被打标（命中/不命中各一例）。
- `T-U7-4`：某个钩子 throw → 其它钩子照常，插件不崩（模拟 event 触发）。
- `T-U7-5`：traceDir 配置生效，日志写对位置。

### U8 dashboard.mjs
输入：logs 目录。输出：HTTP 服务（/、/api/runs、/api/events SSE）。
冒烟：
- `T-U8-1`：服务起来后 `/api/runs` 返回已有 run 列表（用样本 logs 目录）。
常规：
- `T-U8-2`：SSE：先回放已有全部事件、后续新行增量推送（模拟写文件验证收到的顺序）。
- `T-U8-3`：无运行/目录不存在 → 空列表、页面不报错。
- `T-U8-4`：端口占用/异常 → 清晰报错退出而非静默。
- `T-U8-5`：run 切换 → 加载对应 trace。

### U9 index.html
输入：/api/events 数据流。输出：渲染。
冒烟/常规（手动+数据样本驱动）：
- `T-U9-1`：用一段完整样本 trace（含全部 10 类事件）渲染，无 JS 报错。
- `T-U9-2`：Token 面板累计正确（与样本数字对照）。
- `T-U9-3`：压缩前后 diff 可见（删除行可见标识）。
- `T-U9-4`：断连/重连有提示（EventSource onerror 处理）。

### U11 compare.py
输入：两组运行产物（插件组/对照组 + trace）。输出：对比报告（markdown + JSON 指标）。
冒烟：
- `T-U11-1`：合成数据（固定数字）跑出正确指标与报告。
常规：
- `T-U11-2`：缺某组数据 → 报缺失项不是崩。
- `T-U11-3`：质量分规则（骨架完整/草稿污染/引用准确/免责结尾）各给正反例。
- `T-U11-4`：性价比=质量/token 计算正确。
（方案 A/B/C 的执行细节见第 6 节。）

---

## 5. 集群划分与协同测试

> 原则：单独测完的单元，在集群里用"真实形状的模拟数据"串起来再测一轮——冒烟 + 案例，方法同单元。

| 集群 | 成员 | 协同测试做什么（冒烟+案例要点） |
|---|---|---|
| A | U1+U2 | tagger 输出**必须**是 U1 校验通过的合法行集；对样本原文（表格/散文/混合）全链路验证 | ✅ 2026-08-26（contract.test.js 联合校验 + T-CE-1 全链路内验证）|
| B | U3+U4 | 用一段"模拟 OpenClaw 消息序列"（user → toolResult(原文) → assistant(discard) → …）跑 Cleaner→Tagger→Compressor 全流程：打标→剥离→配对→删行→_pruned | ✅ 2026-08-26 T-CE-1/T-CE-4（装配层全链路，见 assembly.test.js）|
| C | U5+U6 | TokenCounter 的数字与 trace 事件的 token 字段一致；run_stats 汇总=各事件求和 | ✅ 2026-08-27 T-CE-5（llm_output×2 → token_round 逐轮累计断言 + events_by_type 求和==events_total）|
| D | U8+U9 | 样本 trace（Cluster C 产出一个真实样例）→ 驾驶舱渲染 → 手动验收清单（§7.3 的对照表打勾）|
| E | U7 + A+B+C | 插件全链路冒烟：模拟 gateway 环境装配插件，跑一次"伪 loop"（构造 messages 序列喂给 context 处理器），验证 注册→打标→剥离→压缩→日志→汇总 全部生效 | ✅ 2026-08-26 T-CE-1（mock api + OpenClaw 真实 Message 形状，见 assembly.test.js）|
| 联调 | E + D | 真 gateway（需 token）：跑一次真实报告，驾驶舱实时看到全部事件；再跑对照组，对比 |

**集群划分即为此版本字面约定**，后续如有调整同样走"变更纪律"（第 2 节）。

---

## 6. 效果对比机制设计（U11，任务点 8）

**目标**：对比"有插件 vs 无插件"的 **报告质量、token 消耗、token 性价比**，且要**压制 temperature≠0 随机性**造成的可比性失真。

**核心手段**：provider 若支持 `temperature` 参数，对比实验统一固定（如 0）；不支持则用"同上下文重放"（方案 B）与"多次重复取中位数"（方案 C）消除上下文与随机差异。

### 方案 A（隔离"压缩对质量的影响"）
1. 插件组完整跑完 loop 产出报告 `R_plug`，trace 已记录**每轮实际发送（压缩后）**消息与**原始（压缩前）**消息。
2. 用同一份"原始未删减上下文"（按各轮完整组装）喂给**全新 LLM 会话**，生成报告 `R_full`。
3. 对比 `R_plug` vs `R_full`：同一上下文输入下，删减只影响模型"看到什么"，从而隔离出压缩本身对报告质量的净影响。
4. 意义：如果 `R_plug` ≈ `R_full`，说明删减无碍质量；若显著劣化，说明压缩策略过度。

### 方案 B（隔离"上下文差异"——去皮重放）
1. 无插件组完整跑 loop（不用插件），得到一组上下文 `ctx_noplug` 与报告 `R_base`。
2. 把 `ctx_noplug` **逐段重放**给装有插件的 agent 模型：每段输入后，**不看模型的任何输出，只运行插件的删行逻辑**，得到删减后的段落。
3. 将所有删减结果**按顺序拼接**成一个新上下文，喂给同一 LLM 生成报告 `R_replay`。
4. 对比 `R_replay` vs `R_base`：两者**输入上下文同源**（一段原始、一段被插件删减过），LLM 只差"看到删减版还是全量版"，直接量化 token 节省的同时观察质量损失。
5. 意义：这是衡量"插件在同等信息量下能省多少 token、代价多少质量"的最严苛口径。

### 方案 C（重复取样）
同 stock 同 prompt，插件组/对照组各跑 N 次（N≥3，尽力而为），token 取中位数、质量分取中位数，做带离散度的对比（避免单次随机结果误导）。

### 指标矩阵（compare.py 统一产出）

| 维度 | 指标 | 数据来源 |
|---|---|---|
| 质量 | 骨架完整（必需章节是否齐全）、草稿污染（是否出现规划草稿被当正文）、数据引用准确性（抽查关键数值与源一致）、免责声明结尾 | 规则打分（quality_score()）+ 人工抽查 |
| token | prompt/completion/total（每轮+累计）、压缩节省（before-after）| U5/U6 + usage |
| 性价比 | 质量分 ÷ total_tokens | 上两行合成 |
| 稳定性 | 是否触发超窗 / compaction / 截断 | trace 事件 + transcript |

> 方案 A/B/C 的具体脚本实现（怎么组装上下文、怎么调用模型）留在 U11 开发阶段细化，**但数据基础现在就要铺**：U6 的 trace 必须记录"每轮压缩前/压缩后的 messages（存 payload 文件）+ 原始 tool 结果"——这是方案 A/B 的前提，写进 U6 验收。

---

## 7. 变更日志

> 纪律：测试发现问题先在此记录（再修）；整体设计变更须先经用户批准。

| 日期 | 单元/集群 | 问题（复现/期望/实际） | 处置（局部/整体/待用户决定） | 状态 |
|---|---|---|---|---|
| 2026-08-26 | U1 测试 | T-U1-10 断言子串 `n_rows mismatch` 与实际报错文本（`_meta.n_rows (99) mismatch actual row count (2)`）不符，断言落空。复现：跑 `node --test`。期望：断言匹配实际错误文案。 | 局部（改测试断言，源码未变；源码同类校验逻辑复核无误，`reduce((sum,s)=>…)` 绑定正确） | ✅ 已修复 |
| 2026-08-26 | U2 | T-U2-1/8 失败：`isSeparatorLine` 只允许纯横线字符，遇到带空格的 `------- -------- ------`（每列一截横线，真实爬取常见形态）判不出分隔线 → 整块被当散文切。期望：识别为表格。 | 局部（`isSeparatorLine` 去内部空白后再判横线；连带散文模式也不会再见到分隔线） | ✅ 已修复 |
| 2026-08-26 | U2 | T-U2-3 失败：空文本块当前实现返回 ok=false，与设计约定（空文本/全空行 → 不产 doc，value=null）不符。 | 局部（空文本块改"跳过不产 section"，仅缺 text 字段才算结构错误；测试 T-U2-11 同步修正） | ✅ 已修复 |
| 2026-08-26 | U2 | 真实样本校准（凯莱英 round02 完整输入）：i问财盘面输出是 `## 标题` + `key: value \| key: value` 管道记录 + `- 列表` 形态，原"仅表格按行"判定会把这些当散文按句切（管道记录被并成一行或截断）。 | 局部（`isTableLike` 泛化为"结构化块"判定：分隔线/\t/\|/列表项/markdown 标题任一触发即按行切；标题→h、列表去标记；新增 T-U2-13 用真实形态做回归） | ✅ 已修复 |
| 2026-08-26 | U4 测试 | T-U4-7 幂等断言最初写错语义：要求"压缩后再压缩事件一致"；实际第二次已被 _pruned 挡掉、事件为 skip（合理）。正确语义：同输入重复压缩一致 + 压缩视图是固定点（再压不变）。 | 局部（改测试断言为"同输入重跑一致 + 固定点"；源码不变） | ✅ 已修复 |
| 2026-08-26 | U8 测试 | 集成测试整文件挂死 120s：SSE 响应带 `connection: keep-alive`，`server.close()` 会等空闲 keep-alive 连接自然关闭 → 死等，进程不退出。 | 局部（测试关服助手加 `closeAllConnections()` 强制断开；服务端逻辑未动） | ✅ 已修复 |
| 2026-08-27 | U11 | `replay_prereqs_plan_b`：目录含 `requests/`（只有 prompt.txt、无 json）时误判 prereq_missing，命中不了"单段重放"partial 语义。复现：T-U11-6 `test_plan_b_partial_prompt_only`。期望：partial + 说明局限。 | 局部（`requests/` 分支重排：先找 json，再以 prompt.txt 独立信号转 partial） | ✅ 已修复 |
| 2026-08-27 | U11 | `quality_score` 的 `details` 漏 `citation_miss` 字段（断言 KeyError）。复现：T-U11-3 `test_citation_accuracy`。期望：细节可追踪。 | 局部（补 details.citation_miss；规则逻辑未动） | ✅ 已修复 |
| 2026-08-27 | U11 设计 | trace 中同一轮的 `saved` 在 `token_round` 与 `view_after` 各写一次，直接求和会重复计（样本即如此）。期望：每轮节省只计一次。 | 局部（`token_round.saved` 为准，`view_after.saved` 仅在其缺失时兜底；测试 T-U11-1 断言 saved=1050 而非 1350 回归） | ✅ 已修复 |
| 2026-08-27 | §6 数据基础 | §6 验收要求 trace 记录"每轮压缩前/后 messages + 原始 tool 结果"，装配层当时只写 token 摘要 → 方案 A/B 无数据可重放。 | 局部（`view_before`/`view_after` 事件携带 `payload`=该轮 messages 全量，配置 `persistViewPayloads` 默认 true；logger 对超大 payload 自动外联 `trace_payloads/` 留 `payload_ref`；compare.py 方案 A 同时认 inline payload 与 payload_ref。新增 T-CE-2/3 与 compare 测试） | ✅ 已落地 |
| 2026-08-27 | §9 实测 | 源码核查发现：`llm_output`/`agent_end` 被 `hooks.allowConversationAccess` 门控（非内置插件必须显式开启），若不加 → token_round/run_finalized 静默不触发，trace 缺 token 与汇总（对比失真）。 | 局部（`config/openclaw.json` 的 `plugins.entries.keeper-corpus-compress.hooks.allowConversationAccess=true` 已配置；manifest configSchema 补 `persistViewPayloads`/`payloadMax` 字段文档） | ✅ 已配置 |
| 2026-08-27 | 集群 C 联动覆盖 | 复盘：Cluster C（U5+U6）只有 logger 单测级 run_stats 求和（T-U6-6），缺"装配层 token_round 事件值 == TokenCounter 逐轮累计"与"run_stats.events_by_type 求和 == events_total"的显式断言 → 联动没有测试钉住。 | 局部（新增 T-CE-5：mock api 连发两次 llm_output（usage 1000/200、1500/300）→ 断言第 1/2 轮 round/input/output/input_total/output_total/total 与累计一致；run_stats 求和闭环。12/12 通过） | ✅ 已补齐 |
| 2026-08-27 | §8 表格卫生 | 极端(待补)列对 U1..U8 仍写"待补"，与"另补批次已并入常规列并全绿"的事实不符（名不副实）。 | 局部（列头改为"极端(另补批次)"，各单元填 ✅ 指向常规列另补批；U9 保持 ⏳ 实机验收待联调） | ✅ 已更新 |
| 2026-08-27 | 日志体系 | 需求：测试前检查日志、每阶段日志做齐全、能写日志的节点尽量都写（但不搞复杂日志脚本）、统一可 track 注释便于未来清除、独立完整日志文档并**单独成章"清除日志代码说明"**、端到端与对比报告必须落盘且命名清晰。 | 局部（新增 `run_start`/`tagger_skip`/`llm_input` 三事件 + 全部日志节点加 `// ====[KEEPER-LOG: <事件> begin/end]====` 成对包裹（10/10 校验）；重写 `docs/LOGGING.md`（事件目录/包裹约定/阶段检查单/artifacts 落盘/第七章清除说明）；新增 `artifacts/<场景>/<run_tag>/` 落盘规范 + `docs/NEXT_STEPS.md` 操作手册；新增 T-CE-6 锁定新节点；README 状态同步） | ✅ 已落地 |
| 2026-08-27 | 接入联调 | OpenClaw 强制 register **同步**：原 `async register` + `await createLogger`（logger 用 promises fs）在 `plugins install/doctor` 阶段报 "plugin register must be synchronous"，插件无法加载。复现：`openclaw plugins doctor`。 | 局部（`logger.js` 全部 IO 改同步 fs（`mkdirSync/appendFileSync/writeFileSync`），`createLogger` 同步构造；`assembly.js` 去 await；`index.js` `register` 同步调用 createKeeper——其同步段（cfg 解析→logger 构造→各钩子 api.on 挂载）在返回前完成。73/73 单测不破；doctor 通过（仅剩 "hook-only 兼容路径" info 提示）） | ✅ 已修复 |
| 2026-08-27 | 接入联调 | keeper 插件已 `plugins install --link` 接入（主 checkout 路径，改代码实时生效）；全局配置合并脚本 `scripts/merge_keeper_config.py`（自动备份+增量合并）。**待办**：合并全局配置（需授权/用户执行）→ gateway 重启 → smoke。 | 局部（无代码变更；流程记录见 docs/NEXT_STEPS.md 阶段 0） | ✅ 已完成（2026-08-28：全局配置合并 validate 通过，gateway 重启加载成功） |
| 2026-08-28 | 联调 smoke | 真 gateway 首跑（平安银行涨跌幅/换手率）：trace 只有 run_start/token_round/run_finalized —— **压缩链路零触发**。根因：keeper 环境无 hithink MCP 工具，模型取数走 exec+read（跑 cli.py），工具名 ≠ 白名单 `hithink-market-query`，tagger 未命中 → 无 doc 无压缩。**附带得证**：token_round 带 usage（opencode-go 实测 usage 成立，§9.2 达成）。 | 局部（v2.1.1：tagTools 升级**子串匹配**；新增 **exec 登记管线**——before_tool_call 解析命令文本命中 hithink/cli.py → 登记 pendingExec，persist 消费；configSchema 加 execTools/execCommandPatterns；T-CE-7 锁定命中/未命中两态） | ✅ 已修复（74/74） |
| 2026-08-28 | 联调 smoke | **所有 hook 必须同步**（smoke2 java 日志实证）：`returned a Promise; this hook is synchronous and the result was ignored` —— `tool_result_persist`/`before_tool_call`/`context` 的 async 返回值被静默丢弃 → 压缩永远不生效（context 的 `{ messages: next }` 也没有 reviewers）。复现：真 gateway 跑完整 skill（黄河旋风），log 出现警告且 tagger_doc 恒为 0。 | 局部（全 7 个钩子同步化：`async (event)` → `(event)`；`await logger.log` → `logger.log`（logger 已是同步 fs 实现）；`agent_end` 同步 `logger.finalize()`；`runId` 提取统一 `runKey(event)`（修 run_start runId='default' 与 agent_end 不一致）；**exec 登记改为 sequence-pairing**：persist 消费"后随的 exec persist"（不再按 toolCallId 匹配——toolCallId 在 persist 事件不可靠），非 exec persist 先到则清除 pendingExec（保守不误配对）；T-CE-7 改写为 3 场景（命中产 doc/未命中静默/被清除静默），74/74 全绿） | ✅ 已修复（74/74） |
| 2026-08-28 | 联调 smoke | **persist 事件拿不到 runId**（类型定义实证 `PluginHookToolResultPersistEvent = {toolName?, toolCallId?, message, isSynthetic?}`）→ sequence-pairing 的 pendingExec 记在 before_tool_call 的 runId state 上，persist 的 `runKey(event)` 恒解析 'default' → 跨两个 run state，pendingExec 永远 false → **tagger_doc 恒 0**。smoke3b（凯莱英，`--session-key` 新会话强制重取数）9 次 exec 登记全部成功但 persist 零消费。 | 局部（**改回 toolCallId 登记表**：before_tool_call 命中时 `execReg.set(toolCallId, runId)`；persist 从 `event.toolCallId ?? ctx.toolCallId` 反查，命中即消费（不等 tool 名）；`runKey` 优先级改 **runId > sessionKey > sessionId**（此前提 sessionId 优先，llm_output 解析出 sessionId、before_tool_call 解析出 runId，同一次运行拆两个 run state）；全部钩子签名加 `(event, ctx)` 让 `ctx.runId` 参与解析；T-CE-7 改为工具 3 场景：t1/t3 各自 toolCallId 隔离配对产 2 doc、未命中静默） | ✅ 已修复（74/74） |
| 2026-08-28 | 架构核查 | **OpenClaw 2026.6.1 插件 hook 体系无 `context` 钩子**（`PLUGIN_HOOK_NAMES` 无此项，运行时亦无别名）→ 原设计"context→compressor 视图级压缩（view_before/view_after）"在**插件 hook 路线**无入口，`api.on('context')` 静默不触发。可改写单条 message 内容的入口是 `tool_result_persist`（源头压缩，已实现）。`before_prompt_build`/`agent_turn_prepare` 只能注入字符串；`before_compaction`/`llm_input`/`llm_output` 均只读。 | 局部（keeper 压缩能力暂收敛为**源头压缩**：persist 改写 exec/取数结果为 JSON 行集已可生效；视图级压缩结论下修（见 2026-08-29 行）：api.on("context") 死讯确认，但**插件 API 的 ContextEngine 槽位**（registerContextEngine + slots.contextEngine + ownsCompaction）被证实为可达的每轮视图接缝——非「API 不支持」，是之前走错了注册路线） | ✅ 已停用（2026-08-29 推翻：ContextEngine 槽位补位，见下行） |
| 2026-08-28 | 联调 smoke4 | **源头压缩链首次完整打通**：smoke4（博瑞医药，`--session-key agent:keeper:smoke4-borui` 新会话强制重取数）11 次 exec 取数 → **11 tagger_doc（100% 命中）**、0 skip、0 error；**runId 全域一致**（36 事件全落 `4f831dbc`，run_start/persist/llm_output 不再拆成 default/sessionId/runId 三态）；token 实测 input 53037/output 8453。报告落盘 `reports/博瑞医药_公司分析_20260828.md`，artifacts → `20260828_2231_smoke004_borui/`。 | 验证（无代码变更；上一行两处修复的实证闭环：persist 拿不到 runId 靠 toolCallId 登记表、runKey 优先级 runId 优先） | ✅ 已落地（2026-08-28，74/74 单测不破） |
| 2026-08-29 | 视图级接缝（重点实证） | **ContextEngine 槽位 = 每轮视图压缩的活接缝，非「API 不支持」**。实证链：① bogus slot `keeper-does-not-exist` → journal 记录 resolve 失败并 quarantine 回退 legacy —— 证明 slot 被读取、resolve 在运行路径上；② 分布式源码核查（selection/embedded-agent/attempt-execution/agent-command）：`runEmbeddedAttempt` 有一次性 resume assemble seam（fresh session 下 0 条消息，永不触发，explains smoke6 全零）；真正**每轮接缝** = `installContextEngineLoopHook`（包装 `agent.transformContext`，每次模型调用都走，gate `activeContextEngine?.info.ownsCompaction === true`）→ `contextEngine.assemble({messages: providerMessages})`，`assembled.messages !== providerMessages` 即替换模型视图；③ **ownsCompaction:false ⇒ 钩子从未安装 ⇒ 从未每轮压缩**（v2.3.1 修复为 true）；④ smoke7 实机：`view_before=6 / view_after=6` 进入 trace（真 gateway run）。 | 局部（context-engine.js v2.3.1：`ownsCompaction:true` 钥匙；KEEPER-DIAG instrumentation 证明 factory/assemble 命中、n_msgs 0→1；compact() not-compacted 安全已确认——宿主只读 `result.compacted` 决定 adopt） | ✅ 已落地（smoke7） |
| 2026-08-30 | live 视图改写（Task 4 闭环） | smoke7 遗案：`discard_applied=0` —— **tagger 改写仅落盘（persist 路径），发给模型的 live 视图仍是原始 JSON**，模型无从按 n 申报 delete。排查备选 seam `registerAgentToolResultMiddleware`（types/registry）：**bundled-only**（`record.origin !== "bundled"` → error），文件系统插件不可用。定案：**assemble 内 liveTagger**（context-engine.js 输入的实时改写，完全插件可控）：assembly 侧按 toolCallId 记忆化 doc（docsByTcId + 全局 seq），persist/live 两路共用同一 doc（doc_id/行号一致）；live 门控 = tagTools 白名单 ∪ 该 toolCallId 已有 doc/登记（exec 结果靠 persist 先行落 memo 兜住，read/SKILL 等非取数不动）；assemble 改回条件 `hit || rewrote > 0`（改写即换视图）。单测 T-U7-8 锁定：persist→live 同 doc_id → 见行集 → discard_lines 申报 → assemble 压缩（_pruned/n_del/n_left 断言全过）。 | 局部（assembly.js v2.4：computeDocFor/liveTagger/shouldTagLive + persist 复用 memo；context-engine.js v2.4：assemble 接 liveTagger；79/79 单测全绿；sync 回主 checkout，gateway 重启） | ✅ 已修复（v2.4.0；待实机判据 → 下行 v2.4.2 达成） |
| 2026-08-30 | Task 4 实机判据 + v2.4.2（resume 历史打标 + 压缩器精确命中） | smoke9 判据（resume 会话 4207a8fa：11 条历史 exec 结果但 **0 tagger_doc**）根因实证二连：**① resume 历史 toolResult 无 live 登记** —— 新插件实例下 execReg/docsByTcId 均为空、exec 又不在 tagTools 白名单（DIAG：`byName:false`），shouldTagLive 恒 false；persist 只对当轮新 exec 触发（probe：新 exec `hasReg:true,execHit:true` 正常产 memo）。修复：liveTagger 门控新增 `reconstructCmdHit` —— 沿消息序列向前定位该 toolCallId 的 assistant toolCall，复刻 before_tool_call 命令模式判定（含 OpenAI tool_calls[] JSON-string 兜底）。实机命中：resume probe `tagger_doc_live=43`（17 唯一 doc = 11 历史+6 新增全部重建打标）、`view_before/after=3`、两窗口各省 498/684 tokens。**② 压缩器契约修正**：模型诚实申报"删 39 行资金流向表"被 `doc_id_mismatch` 拒 —— applyCompression 只消费"最新未消费 doc"（T-U4-10），resume 多 doc 窗口下模型自然指向更早的大表即被拒。改为 **显式 doc_id 精确命中**（未指定才退最新；已剪 `_pruned` 不进 pending 天然防重复删；doc_id 全局唯一+memo 稳定=强句柄）。实机闭环：resume2 `discard_applied=3`（doc_0 删 21 行×2 窗口幂等 + doc_13 删 6 行）、`saved_gt_zero=True`。 | 局部（assembly.js v2.4.2：reconstructCmdHit/shouldTagLive 带 idx；compressor.js v2.4.2：显式 doc_id 优先命中；T-U7-9 新增 / T-U4-10 改判 / T-U4-13 新增；83/83 单测全绿；sync 主 checkout，gateway 重启） | ✅ 已落地（Task 4 判据达成：view_before/view_after/discard_applied>0，saved_gt_zero） |

---

## 8. 测试案例追踪表

> 前半（冒烟+常规，本方案已列）开发中逐个打勾；后半（极端/罕见）开发后凭经验补齐。
> 补法：**另补批次直接并入常规列**（`另补 T-Ux-*`），极端列下述状态即该批次的完成标记。

| 单元 | 冒烟 | 常规(已列) | 极端(另补批次) | 通过日期 |
|---|---|---|---|---|
| U1 | ✅ T-U1-1 | ✅ T-U1-2..6（另补 T-U1-7..13：重复 n/负 n/空 rows/t 空/doc_id 非法/非对象根/常量冻结）| ✅ 即常规列 T-U1-7..13（破坏性/边界批 7 项全绿）| 2026-08-26（13/13 通过） |
| U2 | ✅ T-U2-1 | ✅ T-U2-2..6（另补 T-U2-7..13：残句合并不切半句/分隔线不产出行/u 优先于数字/同段多完句/blocks 边界/表格判定/真实形态校准）| ✅ 即常规列 T-U2-7..13（极端/真实形态批 7 项全绿）| 2026-08-26（13/13 通过） |
| U3 | ✅ T-U3-1 | ✅ T-U3-2..4（另补 T-U3-5..6：非对象参数防御/auxKeys 可配置+常量冻结）| ✅ 即常规列 T-U3-5..6（防御批 2 项全绿）| 2026-08-26（6/6 通过） |
| U4 | ✅ T-U4-1 | ✅ T-U4-2..9（另补 T-U4-10..11：doc_id 不匹配拒绝消费/空数组与非消息防御）| ✅ T-U4-12（§9.4 并行 discard 顺序配对）| 2026-08-26..27（12/12 通过） |
| U5 | ✅ T-U5-1 | ✅ T-U5-2..6（另补 T-U5-7..9：汇编估算/节省量不为负/stats 空轮安全）| ✅ 即常规列 T-U5-7..9（边界批 3 项全绿）| 2026-08-26（9/9 通过） |
| U6 | ✅ T-U6-1 | ✅ T-U6-2..5（另补 T-U6-6..7：run_stats 汇总/非对象事件忽略）| ✅ 即常规列 T-U6-6..7（汇总/防御批 2 项全绿）| 2026-08-26（7/7 通过） |
| U7 | ✅ T-U7-1 | ✅ T-U7-2..5（另补 T-U7-6..7：适配器/无标记消息原样/多 discard 提取；配套 Cluster E：T-CE-1 伪 loop 全链路 + T-CE-2/3（view payload 入库/外联）+ T-CE-4（并行 discard 全链路）+ T-CE-5（Cluster C 联动累计））| ✅ 即常规列另补批 + Cluster E T-CE-1..5 | 2026-08-26..27（12/12 通过） |
| U8 | ✅ T-U8-1 | ✅ T-U8-2..5（另补 T-U8-6：首页渲染冒烟，兼 U9 的自动化部分）| ✅ 即常规列 T-U8-6（首页冒烟）| 2026-08-26（6/6 通过） |
| U9 | ✅ T-U9-1（样本渲染，T-U8-6 覆盖服务端冒烟）| 待浏览器手动验收（T-U9-2..4 列验收清单见 §7.3 对照表）| ⏳ 实机验收待联调（T-U9-2..4；dev 侧无遗留） | 2026-08-26（前端已交付，实机验收待联调） |
| U11 | ✅ T-U11-1（合成固定数字→指标/报告正确）| ✅ T-U11-2..4（缺失组/质量四规则/性价比算术）| ✅ 已补 T-U11-5..7（布局识别/方案A·B前置校验/CLI 组装）+ T-U11-8..9（方案A 认 inline payload / payload_ref）| 2026-08-27（23/23 通过）|

---

## 9. 需要实测的技术点（逐项验证结果，2026-08-27）

1. ✅ **真正的每轮视图接缝 = 插件 API 的 ContextEngine 槽位**（v2.4 定稿，取代早前对 `api.on("context")`
   的误判）。实证：`registerContextEngine` 非 bundled-only（registry-CMq-i5MO.js，bogus slot 打入即
   journal 记录 resolve 失败 → quarantine 回退 legacy，证明 slot 被读取）；选中 = `config.plugins.slots.contextEngine`；
   调用 = selection 嵌入式 run loop 的 `installContextEngineLoopHook`（每次模型调用都包装
   `agent.transformContext` → `contextEngine.assemble({messages: providerMessages})`，**gate
   `info.ownsCompaction === true`**，selection:12010）——`assembled.messages !== providerMessages`
   即替换发给模型的 prompt（selection:12397 的一次性 resume seam + fresh session 0 消息 ⇒ 之前
   smoke6 全零的原因）。`api.on("context")` 确认死路：插件 SDK 的 `api.on` 只认 typed-hook 白名单
   （PLUGIN_HOOK_NAMES 无 "context"），extension 路径在网关嵌入式 loader 硬编码 `noExtensions:true`。
   官方 `contextPruning` 走内建工厂注入（buildContextPruningFactory），但仅 cache-ttl 供应商可用，
   deepseek（opencode-go）不满足 → 本栈官方模式恒空操作。⚠️ 我们的 `llm_output`（token_round）与
   `agent_end`（run_finalized）仍被 `hooks.allowConversationAccess` gate：非内置插件必须显式开启
   （config 已配好，见 §7 记录），否则静默不触发、trace 缺 token_round/run_stats。
2. ⏳ opencode-go 是否回传 `usage`、prompt_tokens 口径 → 只能真 gateway 实测（counter 与 trace 双轨已就绪，
   缺 usage 自动走本地估算并标 `usage_unavailable`，不阻塞）。
3. ✅ `ContextEngine.assemble({messages})` 返回的 `{messages}` 即"该轮视图"：selection
   （installContextEngineLoopHook）只把 `assembled.messages !== providerMessages` 的数组交给
   `transformContext` 的返回值（本模型调用使用），**不回写持久 transcript / agent.state.messages**
   （fresh 会话下 state 不动，resume seam 除外）→ 无状态幂等成立：每轮从原始消息重建视图，
   v2.4 liveTagger 幂等（已打标跳过）。
   （若未来要"追回提示"类注入，官方通道是 `api.enqueueNextTurnInjection`，属生命周期外能力，v2 不做。）
4. ✅ 并行 toolCall discard 消费顺序 = 顺序逐个配对：U7 把同一 assistant 的 N 条 discard 展开为 N 条
   归一化消息，每条消费"当时最新未标注 doc"；后消费的 discard 可能 `compress_skip(no_unconsumed_doc)`。
   已用模拟数据锁定：T-U4-12（compressor 层）+ T-CE-4（装配层全链路）。
5. ✅ `structuredClone` 耗时实测（node 微基准，脚本在 jobs 临时区 keeper_clone_bench.mjs）：
   139KB→1.4ms / 701KB→6.3ms / 2.6MB→35ms（prune 全流程 38ms）——相对 LLM 秒级时延可忽略，
   **保留 structuredClone**（幂等收益），不做局部 clone 优化。

---

## 10. 交付物清单（阶段终了核对）

- [x] `plugin/`（manifest + src + test，U1–U7 + Cluster E 全部案例，72/72）
- [x] `scripts/dashboard.mjs` + `scripts/dashboard/index.html`（U8/U9）
- [x] `scripts/compare.py`（U11，23/23 含 T-U11-1..9）
- [x] 本文件第 8 节测试案例追踪表全绿（含极端案例补齐，U9 实机验收除外 → 见"待联调"行）
- [x] 第 7 节变更日志：无未处置项（全部 ✅ 已修复/已落地/已配置，2026-08-27 复核）
- [ ] `logs/`：基线组/插件组各若干 run（含 trace 与 run_stats）
- [ ] `data/reports/`：各 run 报告；效果对比报告（compare.py 产物）