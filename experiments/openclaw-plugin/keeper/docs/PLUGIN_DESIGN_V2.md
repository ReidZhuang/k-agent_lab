# keeper 档位2插件设计 v2 —— 语料语义压缩（discard_lines / JSON 行集版）

> ⚠️ 架构勘误（2026-08-30，v2.4 已落地）：本文多处把压缩接缝写成 `api.on("context")`，那在
> 插件 API（typed-hook 白名单无 "context"）与嵌入式 extension 路径（`noExtensions:true`）都是**死路**。
> **实际落地的每轮视图接缝 = 插件 API 的 ContextEngine 槽位**（`registerContextEngine` +
> `plugins.slots.contextEngine` + `info.ownsCompaction:true`，selection 每轮调 `assemble()`），
> discard_lines 行级压缩在 `plugin/src/context-engine.js`；v2.4 起 `assemble` 内 `liveTagger` 先改写
> 门控 toolResult 为 keeper 行集（模型可见可删）。compressor 语义不变（见 `plugin/src/compressor.js`）。
> 本文设计时序/契约部分仍有效；凡提到"context 事件/extension context"处一律以 context-engine.js 为准。
> 版本：2026-08-26 · 取代 `docs/PLUGIN_DESIGN.md`（v1：`key_findings_used` + CITATION 围栏文本方案）
> 配套文档：`docs/OPENCLAW_AGENT_MECHANISM.md`（OpenClaw 机制详解，插件设计机制依据）、`docs/LOGGING.md`（日志体系 v1，本文件的第 6 章是对它的落地细化）
> 配套 skill：`skills/cite-and-discard/SKILL.md`（LLM 端契约，已创建）

---

## 0. 一次看懂（TL;DR，大白话）

你现在这个插件要解决的事：**agent 每取一次数，都会把"一整页语料"塞给大模型看。取多了以后，发给模型的文字越来越长，越来越贵，还容易撞上模型能读的上限（超窗）被系统截断。** exp02 的想法是：让大模型自己说"哪几行对我没用"，下一次发消息时把这几行删掉再发。

v2 相比 v1 的三处简化，全是你拍板的：

1. **只删"完全没用的行"，不报"有用的行"**。老设计让模型去标"关键行"，一旦标错就误删了真正有用的数据。新设计反过来：只要一行里有一个字可能有用，就留下。宁可啥也不删，也不误删。
2. **去掉 priority / context，只留一个行号列表**。让模型少想一件事，输出更规范。
3. **语料整体改用 JSON 结构（行号 = 字段 `n`）**，取代老式的 `<<<CITATION_BLOCK>>>` + `N~ 行` 文本围栏。JSON 符合 OpenClaw 的工作方式（理由见第 2.4 节），而且模型读 `{"n":3,"t":"…"}` 比读 "3~ ……" 更不容易数错。

另外你还要：**尽可能详细的日志**、**一个能在浏览器里实时看到每一轮循环的前端驾驶舱**、**一个全程动态跟踪的 token 计数器（输入/输出分开算）**。这三件在本文件第 5/6/7 章有完整设计。

最后：v1 文档里列的几条风险（跟内置压缩抢先后、误删不可恢复、只改内存不改盘、compaction 时序、行号映射稳定），v2 全盘保留并给了对策，见第 8 章。

---

## 1. 与 v1 的差异（以及为什么这么改）

| 维度 | v1（旧设计，废弃） | v2（本文件） | 为什么 |
|---|---|---|---|
| 模型报告什么 | `key_findings_used`：保留哪些行 + priority(critical/useful/related) + context(摘要) | `discard_lines: [n,…]`：只报**完全没用**的行号 | 反向挑选天然保守，误删概率大幅下降；模型负担轻，输出更稳定 |
| 载体格式 | `<<<CITATION_BLOCK>>>` + `N~ 行` 纯文本围栏 | JSON 行集，行号 = `n` 字段 | JSON 是结构化寻址，模型按字段读，比"数行号"准确；见 2.4 |
| 摘要 | 要求模型顺便给"保留行的小结"(context) | 不给 | 压缩时旧行上一轮模型已看过，不需要二次小结 |
| 删除语义 | "只保留被引用的行" | "删掉被点名的行" | 语义安全；模型先看到的永远是完整原文，被删的是它自己判定无用的 |

一句话：**v1 是"信任模型的判断去删除"，v2 是"只允许模型在极端保守的规则下删除"**。代价是压缩率可能不如 v1（模型可能什么也不删），收益是几乎不可能误删。先看效果，数据说话。

---

## 2. 核心契约（v2 一定要统一的两件东西）

> "契约"就是"取数的工具、插件、模型、skill 四方都认的一套格式"。格式统一，插件才能可靠地解析、压缩；模型才能可靠地引用。

### 2.1 取数侧：JSON 行集格式

每个取数工具（`hithink-*` 系列等）的返回，在进入"发给模型的那份消息"之前，被插件标准化成下面这样——`content` 是一个 text block，里面是一段 JSON 文本：

```json
{
  "tool": "hithink-market-query",
  "doc_id": "doc_0",
  "query": "比亚迪 近10个交易日涨跌幅 换手率 主力资金流向",
  "fetched_at": "2026-08-26 10:00:00+08:00",
  "sections": [
    {
      "id": "s0",
      "source": {
        "name": "同花顺 i问财 · 盘面数据",
        "url": "",
        "check": "出现涨跌幅异常时，回到此来源核对行情口径"
      },
      "rows": [
        { "n": 0,  "k": "h", "t": "比亚迪(002594) 盘面速览" },
        { "n": 1,  "k": "v", "t": "2026-08-15 收盘 346.00 涨跌 +2.10% 换手 3.2%" },
        { "n": 2,  "k": "v", "t": "近5日主力净流入 12.6亿" },
        { "n": 3,  "k": "u", "t": "免责声明：以上数据仅供参考，不构成投资建议" }
      ]
    },
    {
      "id": "s1",
      "source": { "name": "同花顺 i问财 · 资金面", "url": "", "check": "" },
      "rows": [ { "n": 4, "k": "v", "t": "融资余额 88.4亿 较上周 +2.1%" } ]
    }
  ],
  "_meta": {
    "n_rows": 5,
    "hint": "行号=n，全文唯一；下次工具调用时用 discard_lines 报告完全无用的行号"
  }
}
```

**字段约定（四方都认）：**

| 字段 | 含义 | 谁负责保证 |
|---|---|---|
| `n` | **行号**。0 开始、全文（跨 section）唯一连续、**永不重编号** | 插件（tagger） |
| `t` | 该行的正文 | 插件（从工具原文切行） |
| `k` | 行类型：`h`=标题/表头，`v`=数值/数据，`t`=说明文本，`u`=噪声/无信息 | 插件（启发式，仅参考，不承诺精确） |
| `sections[].source` | 这条语料的出处：数据来源名、链接、`check`（"要复核就回这里看"的提示） | 插件（从工具返回的元数据取；没有就给空） |
| `query` / `fetched_at` | 当时查了什么、何时取的 | 插件 |
| `doc_id` | 该份结果的稳定身份（`doc_0`, `doc_1`…），供 trace/驾驶舱/报告追溯；模型不依赖它做筛选 | 插件 |
| `_meta.hint` | 给模型的一句话使用说明 | 插件固定写入 |

**v2.1 行切分粒度（拍板：语义单元混合）**：tagger 按"语义单元"切行——表格/列表一行一行；散文按段落切，长段再按完整句切；**绝不把一句话切成两行**。每行 = 一个自洽的信息单元，模型按 `n` 顺序读这份 JSON 就是按顺序读原文，不受碎片化影响（对应讨论点 ①）。

**本地切分怎么实现（无 LLM，纯确定性规则，可单测）**：tagger 是全本地代码，不做语义理解；它只做"把切分点落在完整句法边界上"，语义价值判断留给 LLM。规则链：
1. 规整：统一换行符，剥离纯空行（空行无信息，不占行号）；
2. 判型：表格型（多数行含 2+ 个空格/Tab/`|` 分隔字段，或工具名在表格型白名单）→ 按行切；散文型 → 按双换行/空行切段落；
3. 长段落唯一允许的再切：在句子终结符（`。！？；.!?;`）后面切；找不到安全切点 → **整段保留为一行**（宁可行长，不切半句）；
4. **不变式（可测试）**：每行结尾必是句号/分号/换行，或长度 < `maxRowChars`（默认 400，可配）——即"没有半句话"，`T-U2-2` 直接断言此性质；
5. 语义判断（整行有没有用）完全由 LLM 按 `n` 做，tagger 不掺和。
（升级路线：若将来数据源侧（hithink cli）改为直接输出结构化 rows，tagger 降级为轻量规范化，切分规则就只负责兜底。）

**v2 的行号稳定性策略（关键）**：行号 `n` 一旦发出，**永远不变**。插件压缩时只删除"某几个 n 对应的行"，绝不重排剩余行的编号。这样模型上一轮看到的 `n=5`，压缩后还是 `n=5` 的含义——不会因为删了一行、后面全往前挪而把模型绕晕。（要不要全局跨批次唯一编号？不需要，见 2.3 的配对规则。）

### 2.2 引用侧：`discard_lines`

模型在**下一次工具调用的参数**里带一个字段：

```json
{ "query": "…下一个问题…", "discard_lines": [1, 4] }
```

- `discard_lines` 只允许放"完全没用、一个有用字都没有"的行号（规则详见 `skills/cite-and-discard/SKILL.md`）。
- 没得删 → 省略该字段。
- 该字段**永远不传给真工具**——插件在 `before_tool_call` 里把它剥掉（第 4.3 节）。

### 2.3 配对规则：`discard_lines` 作用在"哪一份"结果上

**规则：某份取数结果，只被"紧随它之后的第一次工具调用"声明的 `discard_lines` 处理一次。**

为什么是这个规则（大白话）：模型在发起下一查询之前，它"手上正在看"的就是上一份结果。它看完了，判断出"这几行没用"，顺手就在下一个查询参数里写下来——这时候它嘴里的行号，指的就是上一份。所以：

```
Round1: 调工具A，返回 结果A（40行）
Round2: 调工具B，参数里 discard_lines=[A的3,7,11]   ← 删结果A
        A 被"B"压缩成 37行
Round3: 调工具C，参数里 discard_lines=[B的……]      ← 删结果B
        B 被"C"压缩
Round4: 调工具D，参数里 discard_lines=[C的……]      ← 删结果C
        C 被"D"压缩
```

- 刚取回来的最新结果**永远不压缩**（模型还没看过它，没资格判它删不删）。
- 压缩发生在"拿着 `discard_lines` 的下一次模型调用即将发生之前"——也就是 `api.on("context")` 事件里，逐条把"上一个结果"缩掉再发给模型。
- **模型如果在某一轮直接开始写最终报告（不再调工具），那么最后那份结果不压缩**——反正写完就结束，不压缩也不会超窗（这一条在超窗边缘时会由内置 compaction 兜底，见第 8 章风险 R2）。
- **（v2.1 拍板）已筛文档带状态标记**：压缩后的文档在 `_meta` 带 `_pruned:{discarded:[…], kept:k}` 与 `doc_id`；skill 指示模型"只对最新一份（未标记）做筛选，标记过的不再动"。正确性本就由配对规则保证，标记的用途是省模型心智、防它空耗 token 重新审视旧文档（对应讨论点 ③）。

### 2.4 回答你的问题：把 CITATION_BLOCK 和行号全并进 JSON，符合 OpenClaw 的工作方式吗？

**符合，而且比文本围栏更贴 OpenClaw 的脾性。** 依据：

1. **OpenClaw 的 tool 结果就是"内容块列表"，不是结构化字段。** `toolResult.content` 是 `[{type:"text", text}]` 这样的块数组。文本块里写什么，是插件自己决定的——写"3~ 营收1500亿"还是写 `{"n":3,"t":"营收1500亿"}`，对 OpenClaw 来说同样都是"一个文本块"。**没有任何机制上的障碍。**
2. **模型本来就活在 JSON 里。** OpenClaw 发给模型的工具 schema、工具调用参数，全都以 JSON 结构化字段的形式出现（`arguments: {query:"…", discard_lines:[…]}`）。模型对"读 JSON 字段"这件事的熟练度远高于它对"类人文本围栏的格式"的熟练度——`[3, 7, 11]` 这种 JSON 数组，模型几乎不会数错；`CITATION_BLOCK + 3~ 7~ 11~` 这种纯文本约定，模型偶尔会把"8~"错看成"3~"。
3. **"指导 model 去 review 哪个 citation"可以内嵌。** 你希望模型"找对需要查看的引用文章的位置"——`sections[].source.{name, url, check}` 正是为此设计的：每段语料带着自己的出处，模型要核实/展开时，能立刻说出"去查 s0（盘面数据）那一节"。这在纯文本围栏里要靠额外解析，在 JSON 里是字段直读。
4. **压缩/解析的动作因此变成纯 JSON 操作。** 插件删行 = `rows.filter(r => !discard.includes(r.n))`；不用正则去抠 `N~ ` 前缀。代码简单、不易错、可测试。

成本是有的，老实交代：JSON 比人读的文本多一点外壳字符（`{"n":1,"t":"…"}` 的引号逗号），单个语料的 token 会略增。这笔账，用"模型引用更准 + 插件代码更简单 + 压缩删除更可靠"来换，是划算的——而且行号压缩掉的行是整块整块消失，省的量远大于 JSON 外壳的增。

**（v2.1 拍板）还需要 CITATION_BLOCK 吗？不需要。** 编号 + JSON 文档边界就够了（对应讨论点 ②）：每一份结果 = 一个独立 JSON = 一个筛选单元，模型要挑的话，就在这份 JSON **已经存在的 `n` 里挑**；"旧内容 + 新内容 mix 后分不清该筛哪份"由插件的位置配对（§2.3）从根上消解——模型唯一需要知道的只有一句话："`discard_lines` 指你最新拿到的那一份"。围栏是给散装文本混排时代用的锚点，JSON 时代没有存在必要。

---

## 2.5 设计定稿记录（v2.1，2026-08-26 用户拍板）

| 讨论点 | 结论 | 落点 |
|---|---|---|
| ① JSON 行集会不会让 LLM 读得不连贯 | 根源在切法不在 JSON：按**语义单元**切（表格按行、散文按段/句），每行自洽 | §2.1 |
| ② 还需要 CITATION_BLOCK 指引吗 | **不要**：编号(n)+JSON 文档边界足够；筛选范围由位置配对（§2.3）保证，围栏废弃 | §2.4 |
| ③ 已筛文档要不要标"不再筛" | **要**：压缩文档带 `_pruned` 状态标记 + `doc_id`，模型只筛最新一份（未标记） | §2.3 |
| ④ 删除追回（restore）机制 | **v2 不做**：保守筛选下误删率低；trace 永久保存原文+每次删除记录（恢复源），将来想启用=翻转删除集合，M4 用对比数据决定 | §6 / U6 |

> 变更纪律：以上为 2026-08-26 用户拍板的设计决定；如未来测试触发**整体设计变更**，必须通知用户决定（见 `DEVELOPMENT_PLAN.md` 第 2 节）。

### 3.1 参与者一览

| 参与者 | 是谁 | 干什么 |
|---|---|---|
| 取数工具 | `hithink-*` 等（现有 skill）| 按 query 拉数据，返回原始文本 |
| 插件·Tagger | `tool_result_persist` 钩子 | 原始返回 → JSON 行集（打行号 n、带 source） |
| 模型 | deepseek-v4-flash | 看语料 → 决定下一个 query，顺手带 `discard_lines` |
| 插件·Cleaner | `before_tool_call` 钩子 | 执行前剥掉 `discard_lines` 字段，不让真工具看到 |
| 插件·Compressor | `api.on("context")` 事件 | 每次发消息前，把"上一个结果"按 `discard_lines` 缩掉，只改内存里那份 |
| 插件·Logger / TokenCounter | 所有钩子 + 观察钩子 | 把每一轮发生的事和 token 数字写进 trace 日志 |
| 驾驶舱 | 独立小页面 + 微型服务 | 实时播放 trace 日志给开发者的浏览器 |

### 3.2 走一遍完整流程（用"比亚迪公司分析"举例）

**第 1 轮（第一次取数）**
1. 用户说"分析比亚迪"。
2. 模型看记录（company-analysis-simple skill 的骨架），决定先查盘面 → 调用 `hithink-market-query`，参数 `{query:"比亚迪 近10个交易日涨跌幅 换手率 主力资金流向"}`。
3. 工具返回一大段文本（同花顺问财的表格文字）。
4. **【插件·Tagger】** 把这段文本切行、去掉空行、打成行号，包成第 2.1 节的 JSON 行集，替换 `content`。
5. 这条 JSON 行集进入"发给模型的历史"（内存），同时按原样写在 disc transcript 里。
6. 下一轮模型调用时，**【插件·Compressor】** 跑一遍 `context` 事件：此刻还没有任何 `discard_lines`（模型还没看过任何结果），**什么都不动**。

**第 2 轮（第二次取数 + 第一次删行声明）**
1. 模型看到 JSON 行集（盘面 42 行）。它判断"其中第 36、38 行是完全没用的免责声明/版权行"。
2. 它决定查财务 → 调用 `hithink-finance-query`，参数里**带了** `discard_lines: [36, 38]`。
3. **【插件·Cleaner】** 在 `before_tool_call` 里把 `discard_lines` 从参数里剥掉，真工具只收到 `{query:"…"}`（不含 36/38）。
4. 财务结果返回 → 【插件·Tagger】 同样打成 JSON 行集。
5. **【插件·Compressor】** 运行：发现"上一条 assistant 消息带 `discard_lines:[36,38]`"，于是定位"它之前的最近一份结果"= 盘面那份，删除 n=36、38 两行，并在这份 JSON 的行集 `_meta` 里加一行 `"_pruned": {"discarded": [36,38], "kept": 40}`。**（注意：删的是上一份——盘面；这一轮刚拿到的财务结果原封不动。）**
6. 发给模型的 messages 里：盘面 40 行（已被精简）+ 财务 42 行（完整）。

**第 3、4……轮**：同样的舞步重复。模型每次都基于"上一次的完整结果"做删行声明，插件每次都在发送前把"上上次之后的那份"缩掉。

**最后一轮（写报告）**
1. 模型材料够了，直接输出最终报告，不再调工具 → 没有 `discard_lines` → 最后一份取数结果不压缩。
2. 报告写完，`agent_end` 事件 → 插件打一条最终汇总日志（累计 token、压缩了多少行、节省多少）。

### 3.3 对照：没有插件（或没挂 skill）时会发生什么

- 每次模型调用，messages 里是所有取数结果的**原始全文**，越滚越大；
- 逼近窗口上限时，OpenClaw 会触发**内置 compaction**（摘要压缩、"静默写记忆"，还可能要截断正在生成的报告——v1 文档里"黄河旋风"那次事故就是这么来的）；内置 `contextPruning`（启发式硬砍 tool 结果）在 keeper 的默认配置下是**关闭**的，所以没有任何东西帮它做语义取舍。
- 你的插件要补的正是这个位置：**用模型自己的判断，在发送给模型之前把确定无用的行删掉**，让 compiler 前的上下文不再滚雪球。

### 3.4 边界情况（都要处理）

| 情况 | 行为 |
|---|---|
| 模型回了 `discard_lines: []`（空数组） | 视为"没有可删的"，不压缩那行；照常发 |
| 模型省略 `discard_lines` | 同上 |
| 工具报错（isError） | Tagger 跳过不打行号；Compressor 不处理错误结果 |
| 工具返回不是纯文本（有图片等） | 文本块照常打行号；图片块透传，不参与删行 |
| `discard_lines` 里出现不存在的行号 | 忽略不存在的；只删真实存在的 |
| 模型在同一轮里掉了多个工具调用（并行） | v2 按顺序逐个配对：每个工具调用的 `discard_lines` 依次消费"最近的未消费结果"。并行队列的严格语义列为未决问题（见第 10 章） |
| 同一个 `discard_lines` 对应的结果已经在上一轮被收过 | 天然不会：每个模型调用从**原始消息**（`context.messages` 从未被替换）重新推导压缩视图，见 3.5 |

### 3.5 【重要】为什么压缩是安全的、不会"压两次"

源码实证：`streamAssistantResponse` 里
`let messages = context.messages; if (config.transformContext) messages = await config.transformContext(messages, signal); const llmMessages = await config.convertToLlm(messages);`

`transformContext` 的返回值**只用于当次模型调用**；`context.messages` 本身**永远不会被替换**——它始终累积的是原始（未压缩）消息。因此：

- **每次模型调用，Compressor 都是从同一份原始消息出发、用同一批 `discard_lines` 现场推导出压缩视图**——输入相同、输出必定相同：**确定性 + 幂等**。
- 不维护任何跨轮状态：没有"我已经删过了"的标记要清理，也没有状态可被并发/重试弄脏。
- 磁盘 transcript 从头到尾只含原始消息，永不触碰（可回看、可重放、可诊断）。

---

## 4. 插件实现设计

### 4.1 目录结构

```
plugin/
├── openclaw.plugin.json          # manifest
├── package.json                  # name/version, openclaw.extensions 声明
├── src/
│   ├── index.ts                  # definePluginEntry({id, register})
│   ├── contract.ts               # JSON 行集类型定义 + 常量（行类型 h/v/t/u、_meta 字段名）
│   ├── tagger.ts                 # 钩子① tool_result_persist：原文 → JSON 行集
│   ├── cleaner.ts                # 钩子② before_tool_call：剥 discard_lines
│   ├── compressor.ts             # 钩子③ api.on("context")：按 discard_lines 删行
│   ├── tokenizer.ts              # 本地 token 估算（第 5 章）
│   ├── logger.ts                 # 结构化 trace 事件写入 logs/（第 6 章）
│   └── runStats.ts               # 本轮汇总（token/压缩统计）
├── test/
│   └── (tagger/compressor 单元测试，纯函数，不依赖 OpenClaw)
```

### 4.2 manifest 与配置

`openclaw.plugin.json`：

```json
{
  "id": "keeper-corpus-compress",
  "name": "keeper Corpus Semantic Compressor",
  "description": "按模型 discard_lines 对取数语料做语义级删行压缩（只删内存那份）",
  "version": "0.1.0",
  "contracts": {},
  "activation": "onStartup",
  "configSchema": {
    "type": "object",
    "properties": {
      "enabled": { "type": "boolean", "default": true },
      "tagTools": {
        "type": "array",
        "items": { "type": "string" },
        "description": "要打行号的取数工具名；默认自动匹配 hithink*/iwencai* 等"
      },
      "traceDir": { "type": "string", "description": "trace 日志输出目录，默认 keeper/logs/trace" }
    }
  }
}
```

`keeper/config/openclaw.json` 增量（开发阶段写入）：

```json
"plugins": {
  "entries": {
    "keeper-corpus-compress": {
      "enabled": true,
      "config": {
        "tagTools": ["hithink-market-query","hithink-finance-query","hithink-management-query","hithink-business-query","hithink-event-query","hithink-industry-query","hithink-basicinfo-query"],
        "traceDir": "/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper/logs/trace"
      }
    }
  }
}
```

> 注意：原生 contextPruning 在 keeper 是非 Anthropic 默认关闭；**实验期保持关闭**，避免与插件语义压缩在同一 `context` 链上抢先后（风险 R1）。

### 4.3 三个钩子的职责与伪代码

#### 钩子①：`tool_result_persist` —— Tagger（打行号）

```ts
api.on("tool_result_persist", (event) => {
  const { toolName, content, isError } = event;
  if (isError) return;                          // 出错不打
  if (!isTaggedTool(toolName)) return;          // 只处理取数工具
  const textBlocks = content.filter(b => b.type === "text");
  if (textBlocks.length === 0) return;          // 没有文本可打

  const doc = toJsonRowset(textBlocks.map(b => b.text), { tool: toolName, query: event.input.query });
  return {
    content: [{ type: "text", text: JSON.stringify(doc, null, 2) }],
    // details 保留原样（不进模型）
  };
});
```

`toJsonRowset` 规则（纯函数，可单测）：
1. 把文本块们按 `\n` 切行；
2. 去掉"纯空行/纯空白"（不算信息，直接丢，不占行号）；
3. 行分类启发式：`h`（表头/分隔/标题样式）、`v`（行内含数字）、`u`（含"免责声明/仅供参考/版权"等信号词），其余 `t`；
4. 从 0 起连续编号 `n`；
5. 有工具元数据则填 `sections[].source`（没有给 `name`=工具名占位）；
6. 尾部固定写 `_meta.{n_rows, hint}`。

#### 钩子②：`before_tool_call` —— Cleaner（剥辅助字段）

```ts
api.on("before_tool_call", (event) => {
  if (event.params && "discard_lines" in event.params) {
    const { discard_lines, ...rest } = event.params;
    logger.event("tool_call_stripped", { toolName: event.toolName, discard_lines, raw: event.params });
    return { params: rest };                    // 真工具只看到 rest
  }
});
```

#### 钩子③：`api.on("context")` —— Compressor（删行）

```ts
api.on("context", async (event, ctx) => {
  const messages = event.messages;              // 深拷贝（emitContext 已 clone）
  let pendingDocIdx = -1;                        // 最近一份"还没被消费"的行集
  const out = [];
  for (const msg of messages) {
    if (msg.role === "toolResult" && docId(msg) != null) pendingDocIdx = out.length;
    if (msg.role === "assistant") {
      const dl = firstDiscardLines(msg);         // 该 assistant 任一 toolCall.arguments.discard_lines
      if (dl && pendingDocIdx >= 0) {
        const before = tokenCount(messagesView); // 压缩前估算（第 5 章）
        const pruned = pruneDoc(out[pendingDocIdx], dl);
        out[pendingDocIdx] = pruned;
        logger.event("context_compress", { toolCallId, discarded: dl, rowsBefore, rowsAfter, tokensBefore, tokensAfter });
        pendingDocIdx = -1;                       // 已消费
      }
    }
    out.push(msg);
  }
  return { messages: out };
});
```

要点：
- `pendingDocIdx` 从左到右推进：只有"顺序上在携带 `discard_lines` 的 assistant 之前、且离它最近"的行集会被「它」消费。这就是 3.5 节确定性/幂等性的实现。
- `pruneDoc`：`rows.filter(r => !discard.includes(r.n))`；`_meta` 追加 `_pruned:{discarded, kept}`；**不改任何剩余的 `n`**。
- 出错即回退：整个 handler 包 try/catch，任何异常 → 打印日志、**返回原 messages**（宁可白跑，不可让模型调用崩掉）。

### 4.4 插件需要记录的 trace 事件（第 6 章详表）

所有钩子内部写结构化日志：`run_start / tool_call_intent / tool_call_stripped / tool_result / tool_result_tagged / model_call (before/after tokens) / context_compress / agent_end`。

---

## 5. Token 计数器设计（任务 6）

### 5.1 双口径：为什么"预估"和"实测"都要

- **实测**（`usage.prompt_tokens / completion_tokens / total_tokens`，来自 provider 响应）是**真金白银的计费数字**，但它在"模型调用完成之后"才出现——**来不及**告诉你"这一刀压缩到底省了多少"。
- **预估**（本地 tokenizer 对即将发送的 messages 数一遍）在**发送之前**就能算出来——压缩前 vs 压缩后各数一遍，差就是"这一刀省的 token"。它用于预览和动态跟踪，模型不可见的瞬间就能报数。

两者配合：本地预估做主仪表（每轮、实时、前后对比），provider 实测做校准（最终账单、校正系数 `校准系数 = 实测prompt_tokens / 本地预估prompt_tokens`，用于把中英文 token 折算误差摊平）。

### 5.2 预估实现

- 选型：轻量 BPE 分词器（JS 实现 `cl100k_base`，如 `gpt-tokenizer` 包），对中文按字节回退处理——**不是精确的 deepseek 词表，但同一套分词器跑"前后对比"时误差互相抵消，差值是可信的**；最终以实测 usage 校正。
- 在哪些点数：
  - `context` 事件里：`tokenize(viewBefore)`、`tokenize(viewAfter)` → 本轮输入（压缩后）与节省量；
  - 系统提示 + 工具 schema 无法从 context 事件直接数到词表——用 `ctx.getSystemPrompt()` 长度近似，并明确标注"系统提示为估算"。
- 统计项（每轮）：
  - `input_tokens_est`（压缩后、发给模型的 messages 总 token 预估）
  - `output_tokens_est`（assistant 文本 + toolCall 参数的本地估算，供"等模型回答前"显示）
  - `compression_saved_tokens` / `compression_saved_pct`（= before − after）
  - `input_tokens_measured` / `output_tokens_measured`（收到 usage 后回填）
  - 累计：`loop_cum_input / loop_cum_output / loop_cum_total`（整个 agent loop 一路动态累加）

### 5.3 实测来源

- `model_call_ended` / `llm_output` 钩子里拿 provider 返回的 `usage`（openai-completions 协议通常回传 `prompt_tokens/completion_tokens/total_tokens`）。若某个 provider 不回传 → 标记 `usage_unavailable`，用本地预估顶上，并在驾驶舱标"估算"。
- `agent_end`：把本 loop 汇总写进 `logs/{run_tag}/run_stats.json`（累计、每轮明细、压缩合计）。

### 5.4 展示目标

驾驶舱 Token 面板（第 7 章）实时显示：本轮输入（压缩后）/ 本轮输出 / 本轮合计 / 累计输入 / 累计输出 / 累计合计 / 本轮压缩节省与节省率 / 环比（上一轮）。每轮一块，全局一行累计进度条。

---

## 6. 日志设计（任务 5 的"足够多的日志"，结构化 JSONL）

> 原则：所有日志**事件驱动、结构化、可重放**。每条事件一行 JSON，带 `ts / run_id / call_id / type`。按时间追加到 `logs/trace/<run_tag>/trace.jsonl`。驾驶舱就是"读这个文件 + 实时追加"。

### 6.1 事件目录（每种事件 = 一个日志点）

| 事件 type | 触发点 | 关键字段 | 在驾驶舱怎么展示 |
|---|---|---|---|
| `run_start` | agent 被调用（插件 register 时/第一条消息时） | run_id, session_key, model, prompt 摘要 | 顶部横幅：run 信息 |
| `tool_call_intent` | `before_tool_call`（**剥离前**） | toolName, toolCallId, raw 参数（含 discard_lines） | 卡片"模型要调工具"：完整参数 JSON |
| `tool_call_stripped` | 同上（剥离后） | 剥掉的 discard_lines | 同卡片内标注"已剥离 discard_lines" |
| `tool_result` | 工具返回、**打行号前** | toolName, toolCallId, 字符数/行数, isError | 卡片"工具返回原文"：字节数 + 前 N 行预览 |
| `tool_result_tagged` | `tool_result_persist` 打完行号后 | doc_id, n_rows, 各 section.source, JSON 预估 token | 卡片"已打成 JSON 行集"：行号范围、来源 |
| `model_call` | `context` 事件（发模型前） | round 序号, input_tokens_est(after), saved_tokens, saved_pct | Token 面板 + 卡头"本轮发送" |
| `model_reply` | 收到模型回复（含 usage） | round, 回复文本摘要, toolCalls(含 discard_lines), usage.measured | 卡片"模型回话"：文本 + 结构 JSON |
| `context_compress` | 压缩发生时 | doc_id, discarded[], kept[], rowsBefore/After, tokensBefore/After | 卡片"压缩了这一份"：删除行高亮 |
| `agent_end` | 循环结束 | 汇总：累计 token、压缩总行数、总节省、耗时、报告字符数 | 主页摘要 + 可下载的 run_stats.json |

每类事件的 `payload` 也存一份"原始大东西"的引用路径（如需看全文）：`trace_payloads/<event_id>.json`，避免 trace.jsonl 无限膨胀（日志目录约定见 `docs/LOGGING.md` 的 `run_tag` 组织，本次落成 `logs/{run_tag}/trace/*`）。

### 6.2 日志写入方式

插件用 `api.logger`（OpenClaw 自带）+ 自管文件写入。文件写入要**批处理 + 低延迟**（append、每事件 flush 或 200ms 批量），**绝不能因为 IO 拖慢每轮模型调用**（`context` 事件是同步热路径）。异常发生在写日志 → 不抛，只 console 警告。

---

## 7. 前端驾驶舱（任务 5：把 agent loop 摊在眼前）

### 7.1 架构（v0：零依赖、无构建）

```
浏览器(驾驶舱页, 无框架 vanilla JS)
   │ EventSource('/api/events') 实时事件 + 首次全量回放
   ▼
scripts/dashboard.mjs  —— 微型 Node 服务（只用 node:http/fs/path，零第三方依赖）
   │ 读 logs/trace/<run_tag>/trace.jsonl（fs.watch 尾随）
   ▼
keeper/logs/trace/<run_tag>/trace.jsonl   ← 插件（第 6 章）写的结构化事件
   ▲
keeper gateway（插件在它进程内跑，往日志文件写事件）
```

- 端口：**19600**（避开 5173/8320/19501，与生产互不干扰）。
- 为什么不由插件直接开 HTTP：插件背后的 gateway 有 token 鉴权等繁琐事，且被杀死时页面就没了；**独立小服务 + 文件尾随**让"历史回放/对照实验/离线分析"都免费获得。将来若要嵌进 gateway，可用 `api.registerHttpRoute` 演进（不阻塞 v0）。
- 启动：`node scripts/dashboard.mjs --logs keeper/logs --port 19600`，浏览器开 `http://127.0.0.1:19600`。

### 7.2 页面布局（ASCII 草稿）

```
┌────────────────────────────────────────────────────────────────┐
│ OPENCLAW Agent Loop 驾驶舱        run: 20260826_105312  ● LIVE │
│ model: opencode-go/deepseek-v4-flash  股票: 比亚迪(002594)      │
├──────────────────┬─────────────────────────────────────────────┤
│ Token 面板 (实时) │  事件时间线（从左到右 = 时间）                │
│ 本轮 输入  1,283  │  [R1] 模型→调 hithink-market-query           │
│ 本轮 输出    340  │       └ 参数 {query:"比亚迪 近10…"}            │
│ 本轮 合计  1,623  │  [R1] 工具返回 42 行 → 已打成 JSON 行集        │
│ 累计 输入  6,841  │       └ n:0..41, 来源: i问财·盘面             │
│ 累计 输出  1,290  │  [R2] 模型回话: 调 hithink-finance-query     │
│ 累计 合计  8,131  │       └ discard_lines 声明: [36,38]           │
│ ───────────────  │  [R2] context 压缩: 盘面 42→40 行             │
│ 本次压缩  -142 tok │       └ 省 142 tok (-6.2%)                   │
│ 节省率    6.2%   │                                               │
├──────────────────┴─────────────────────────────────────────────┤
│ 当前消息预览：要发给模型的那份（JSON 行集，删除行有删除线/高亮）    │
│ · section s0 盘面 (kept 40) · section s1 财务 (42 行完整) …      │
│ 点击任意 R 卡片展开：发出去的完整 messages / 模型完整 reply /      │
│   工具原始返回 / 压缩前后 diff ───────────────────────────────  │
└────────────────────────────────────────────────────────────────┘
```

### 7.3 对照你的要求逐条映射（写进实现验收单）

| 你想看到 | 对应组件/事件 | 验收标准 |
|---|---|---|
| 发送了什么 | R 卡片"本轮发送"＋消息预览区展开 | 展开里能看到这轮发给模型的完整 messages（含压缩后 JSON 行集） |
| LLM 反馈了什么 | R 卡片"模型回话" | 能看到完整 assistant 文本 + 全部 toolCalls（含 discard_lines） |
| 调用了什么 tool | 工具卡片 | 能看到 toolName + 完整参数（剥离前后对照）|
| 得到了什么数据 | 工具卡片"返回原文"+"JSON 行集" | 能看到字节数/行数、来源、前若干行预览；可点开全文 |
| 怎么组装 JSON | tool_result_tagged 事件 | 能看到行集 JSON 全文（含 section/source/行号）|
| 怎么发还给 LLM | model_call 事件 + 消息预览 | 能看到压缩前后两版 messages 的 diff |
| 插件反应（discard_lines）| tool_call_stripped + context_compress | 显示剥离的 discard_lines、删了哪几行、剩多少行 |
| 每轮节省多少 token | model_call / context_compress 事件 | Token 面板每轮实时刷新，带累计与节省率 |
| 历史回放 | /api/events 首次全量 + run 切换 | 下拉选 run_tag 即可回看任意一次实验 |

### 7.4 v0 实现清单（尽量小）

- `scripts/dashboard.mjs`：静态页托管 + `GET /api/runs` + `GET /api/events?run=`（SSE：先补发已存在的全部事件，再 fs.watch 新追加）。
- `index.html`（内联 CSS/JS，约 300 行）：R 卡片列表 + Token 面板 + 消息预览/展开 + run 切换下拉。
- 不做：鉴权（仅监听 127.0.0.1）、不依赖框架、不做多用户。

---

## 8. 风险与对策（采纳 v1 结论 + v2 新增）

| # | 风险 | 对策（一致采纳） |
|---|---|---|
| R1 | **与内置 contextPruning 的先后**（同一条 `context` 链、无 priority） | 实验期 `contextPruning` 保持关闭（keeper 默认即 off）；若必须开，先实测加载顺序，让语义压缩先跑 |
| R2 | **compaction 先于插件压缩跑掉**（行号原文被摘要吞掉、或"静默写记忆"插入干扰） | 维持 keeper 现状：`midTurnPrecheck.enabled=false`、`reserveTokens=20000`；若实验中发现压缩前就被 compaction 拦截，再调大 reserveTokens / 抬高 maxActiveTranscriptBytes，让语义压缩优先发生 |
| R3 | **行号↔原文映射稳定性** | 行号由插件在 `tool_result_persist` **源头统一生成**（tagger），格式四方一致；压缩只删行、永不改号；行号跨批次不全局唯一，靠"紧邻配对"消歧 |
| R4 | **误删不可恢复** | 删除语义改为"完全无用才删"（见 skill 铁律）；原始全文永远留在 transcript / trace 日志，可回看；压缩只改内存那份；`context` 处理器失败即回退（不删） |
| R5 | **只改内存、不改盘** | 已由源码证实：`transformContext` 返回值不写回 `context.messages`；磁盘 transcript 只有原始行集 |
| R6 | **token 头开销（JSON 外壳）** | 记录并接受：以"引用准确 + 代码可靠"换外壳成本；节省率口径用同一 tokenizer 前后差分，不被外壳误导 |
| R7 | **模型不删行（可能什么也删不掉）** | 预期内，先看效果；驾驶舱的"节省率"如实显示 0% 也是一种结论。必要时（阶 4 后）再评估放宽规则 |
| R8 | **日志 IO 拖慢热路径** | context 事件内只做内存记账，日志走异步批量写；异常写日志不抛 |
| R9 | **A 插件炸了影响 agent 运行** | 三个钩子全部 try/catch；任一处失败 → 返回"未改动"（或抛轻量警告），绝不让模型调用崩掉 |

---

## 9. 落地里程碑

| 里程碑 | 内容 | 完成标志 |
|---|---|---|
| **M0** | 文档与契约定稿（本文件 + schema + skill v0）| ✅ 本文件落盘；skill `cite-and-discard` 已建 |
| **M1** | keeper gateway 真正跑起来：填 token、`start_keeper.sh`、无插件跑通一次"公司分析报告"，拿到基线（无压缩的 token/耗时/质量） | `gen_report.py` 成功产出一份报告 + `logs/` 有基线日志 |
| **M2** | 插件最小闭环：tagger + cleaner + compressor + 日志（无驾驶舱），重复跑同报告 | trace.jsonl 里能看到 `tool_result_tagged` / `context_compress` 事件，行数与 token 趋势正确 |
| **M3** | token 计数器 + 驾驶舱 v0（SSE 实时） | 浏览器实时看到每轮循环的全部日志与 Token 面板 |
| **M4** | 平行对照：基线 vs 插件（同舱位、同 prompt、多股票） | 出一张对比表（质量分 / 总 token / 每轮 / 压缩率 / 是否超窗）|

---

## 10. 未决问题（开发阶段逐一实测）

1. `api.on("context")` 是否被 `hooks.allowConversationAccess` 门槛影响？——官方 typed hooks 目录里没有 `context`，需要最小插件实测（M2 第一件事）。
2. openai-completions（opencode-go）是否回传 `usage`？回传的口径（prompt_tokens 是否含 system+tool schema）？——决定 token 面板"实测"栏是否可用。
3. 并行工具调用（同一 assistant 多个 toolCall）时 discard 消费顺序——M2 里用模拟数据测一次再定规则。
4. `structuredClone` 对超大 toolResult 的开销——测量 context 事件对单次模型调用耗时的增量，若超过可接受阈值，考虑只 clone 被改的路径（但需保持幂等语义）。

---

## 11. 附录：黑话 → 大白话（写文档/评审时对照）

| 黑话 | 大白话 |
|---|---|
| transformContext | "每次把消息发给大模型之前，最后一道修改手续" |
| api.on("context") | OpenClaw 给插件开的"发消息前最后看一眼/改一改"的窗口 |
| tool_result_persist | "工具结果归档之前，插件可以改它的内容"的钩子 |
| before_tool_call | "工具真正执行之前，插件可以改参数或拦下它"的钩子 |
| context.messages | 当前这轮对话要发给模型的所有消息（内存里） |
| transcript | 磁盘上永久保存的完整对话记录（不随压缩变） |
| compaction | 系统把"老对话"总结成摘要、腾出上下文空间的操作（会写盘） |
| contextPruning | 系统按长度把老工具结果的光头尾砍掉的启发式操作（只在内存） |
| prompt_tokens / completion_tokens | 发给模型的字数 / 模型回的字数（按词元计） |
| 超窗（context length exceeded） | 消息太长，超过模型能读的上限 |
| successor transcript | 压缩后系统新开的一个对话记录文件（老的封存） |