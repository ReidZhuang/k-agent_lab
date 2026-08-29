# keeper 档位2插件设计要点 —— 把 exp02 语料压缩机制做成 OpenClaw 插件

> 这是 keeper 实验室**未来要开发的核心产物**的预设计文档。当前阶段（2026-08-19）
> **只写设计、不开发**。本文件供未来开发者（包括作者本人）在动工前彻底理解意图与约束。
> 背景与机制详见 exp02 两份文档；本文件聚焦"作为 OpenClaw 插件落地"的具体设计。

---

## 一、目标

在 OpenClaw **持久会话**里，实现 exp02 那种"LLM 语义级删减冗余语料"的能力，
从而缓解长期 tool 循环把上下文撑爆、触发超窗/compaction 截断的问题（如黄河旋风报告
生成时"单回合大输出途中被 compaction 截断、未写完文本被当最终内容落盘"）。

**一句话**：让"每次 tool 取回来的语料，只把模型真正会用到的行保留下来给下一次模型看"，
在 OpenClaw 里以一种不破坏 transcript、不影响历史回看的方式生效。

---

## 二、为什么需要插件，而不是直接用原生机制

OpenClaw 原生已有两种困上下文的手段，但它们**都不是语义级**：

| 原生机制 | 原理 | 局限（相对本插件目标） |
|---------|------|---------------------|
| `contextPruning`（session pruning）| 每次调模型前，在内存里按**长度/位置**修剪旧 tool 结果（软剪头尾、硬清超阈值）| 只看长度，**不知道哪些行语义上有用**；可能误剪关键数值行 |
| `compaction` | 把整段对话**摘要**后写回 transcript | 是"概括"，不是"按行取舍"；会改写 transcript |

本插件要补的正是：**让 LLM 自己判断"哪些行有用、哪些无用"，只保留有用的**——这是
启发式剪枝做不到的。

---

## 三、机制闭环（要实现的完整流程）

1. **取数带行号**：agent 调取数 tool（同花顺 IWENCAI 等），工具返回的语料以
   **可引用的行号格式**组织（如 `<<<CITATION_BLOCK>>>` + `N~ 行`），transcript 落盘。
2. **LLM 顺带打标**：模型在**本来就有的那条 assistant 回复里**，通过一个约定字段
   （exp02 里叫 `key_findings_used`）返回：保留哪些行号 + 每条优先级（critical/useful/related/useless）+ 摘要。
   —— **零额外推理轮次**（这是 exp02 的核心优势）。
3. **插件在 `api.on("context")` 改写**：在"发给模型前"拿到待发消息，找到
   "带行号的旧 tool 消息" + "上一条 assistant 的 key_findings_used"，把 tool 消息
   替换成"只保留被引用行 + 摘要"。
   —— **只改发模型的那份（内存），不动盘上 transcript**（与原生 pruning 同款语义，历史可回看）。
4. **下一轮模型只看到保留的行** → token 量级下降，超窗缓解。

---

## 四、必须解决的难点（动工前要想清楚，也是实验要验证的）

### 4.1 行号↔原文映射的稳定性（最关键）

exp02 是自建 loop，行号是它自己打的，100% 可控。在 OpenClaw 持久会话里：
- transcript 里的 tool 消息可能是 **JSON 结构**而非纯文本行，行号要能稳定映射到原文。
- **取数侧必须输出统一可引用格式**（如 `CITATION_BLOCK` 契约），插件才能可靠解析。
- 若 compaction/pruning 在插件处理之前先跑，行号可能对不上。
  → 需要设计"引用优先级高于启发式 pruning"，或对该类会话关闭启发式 pruning。

### 4.2 与原生机制的优先级 / 互斥

- 开了本插件就不需要原生 `contextPruning` 对同一批 tool 消息再剪一遍（避免双重/冲突）。
- grand compaction 可能仍会触发（它是全局兜底），需验证二者共存行为。

### 4.3 误删不可恢复

- 删是破坏性的。要约定"删除只针对格式性/冗余性内容，关键数值与语义承载体绝不轻删"。
- 建议本地保留原始 tool 结果快照（transcript 本就不删，天然满足"原始快照"要求）。

### 4.4 只在内存改写，不动 transcript

- 与 `contextPruning` 一致：**改的是发给 provider 的那份消息，不改磁盘 transcript**。
- 这样手段可逆、可诊断、不污染历史。

### 4.5 可观测性（配合日志体系）

- 插件应记录：每一轮"读到哪些 tool 消息、删了哪些行、保留哪些行、为何"。
- 这是未来评估"压缩是否有效、有无误删"的最精确数据源（比同步端点能拿到的更细）。

---

## 五、插件技术路线（参考调研结论）

- 接入点：`api.on("context")` 事件（源码先例：`dist/compaction-successor-transcript-CUmEvaGX.js`
  用 `pruneContextMessages` 改写 `event.messages` 后返回 `next`）。
- 复用 exp02 的 `core/tagger.py`（行号打标/还原/压缩）与 `cite-and-compress/SKILL.md`（LLM 规则），
  需按 OpenClaw transcript 结构改造。
- 插件结构建议：`manifest` + `src/`（入口、tagger 移植、引用解析、日志埋点）。

---

## 六、分阶段落地建议（避免一上来写大插件）

1. **阶段0（已完成）**：keeper 独立环境 + 简化报告 skill + 日志骨架。
2. **阶段1**：用 keeper 环境跑通"简化报告生成"，拿到基线（无插件）的质量/token/耗时。
3. **阶段2**：先验证"取数侧能否稳定输出带行号的引用格式"（在 keeper skill 层面实验，不写插件）。
4. **阶段3**：写插件最小闭环（hook → 解析 key_findings_used → 替换 tool 消息），在 keeper 验证。
5. **阶段4**：平行对比（基线 vs 有插件），量化质量/效率/token 性价比。

---

## 七、相关文档索引

- 机制总结：`/home/stockagent/project_space/research/experiments/exp02/SUMMARY_MECHANISM.md`
- 集成调研（含渊源/先例）：`/home/stockagent/project_space/research/experiments/exp02/OPENCLAW_INTEGRATION_RESEARCH.md`
- 实验环境总览：`keeper/README.md`
- 日志体系：`keeper/docs/LOGGING.md`
- 实验记录：`keeper/docs/LAB.md`
- 官方插件开发：`/usr/lib/node_modules/openclaw/docs/tools/plugin.md`、`docs/plugins/building-plugins.md`
- 官方 session pruning：`/usr/lib/node_modules/openclaw/docs/concepts/session-pruning.md`
