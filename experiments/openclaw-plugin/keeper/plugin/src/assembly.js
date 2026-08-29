// ==========================================================================
// U7 assembly —— 把 U1..U6 装配成 OpenClaw 插件（三个钩子 + token 钩子 + 失败隔离）
// ==========================================================================
// 三钩子（设计 v2.2，2026-08-28 架构修正）：
//   tool_result_persist  → tagger：取数结果改写为 JSON 行集（每行一个语义单元 + n 编号）
//   before_tool_call     → cleaner：剥离 discard_lines 等辅助参数，真工具看不到
//   api.on("context")    → compressor：每次调模型前按上轮 discard_lines 压缩最新未标记 doc（只改内存视图）
// ⚠️ 架构修正（v2.3，2026-08-29；v2.2 extension 路线作废）：
//   1. api.on("context") 在**插件 API** 上是死路——插件 SDK 的 api.on 只认 typed-hook 白名单
//      （PLUGIN_HOOK_NAMES），“context” 不在白名单 → 注册即被忽略。
//   2. context 是 **extension API** 的事件（emitContext 遍历 ext.handlers，官方 contextPruning 同形态），
//      但网关嵌入式 path 硬编码 noExtensions:true → 文件系统 extension 从不加载 → extension 也死路。
//   3. 实证可得：插件 API 提供 ContextEngine 槽位（registerContextEngine + plugins.slots.contextEngine），
//      selection 嵌入式 run loop 每轮调 assemble()，返回的 messages 成为发给模型的 prompt
//      （selection:12397，不 gate ownsCompaction）→ 等价 api.on("context") 语义，且保留
//      discard_lines 行级压缩。删行逻辑落在本插件 src/context-engine.js（registerContextEngine 工厂），
//      复用本文件纯函数 compressView / extractDocTexts / extractDiscards / encodeDoc（不 import openclaw，可单测）。
//   4. 每轮都从原始消息重建压缩视图（幂等：compressor 只消费未 _pruned 的最新 doc）；
//      只改发给模型的内存视图，不动盘上 transcript（可恢复）。
//   全程共享同一 trace.jsonl（观测层复用，删行计算零跨进程 IO）。
// 消息适配（OpenClaw Message ↔ 归一化消息）基于 types-DAMKpKGt.d.ts 实测：
//   ToolResultMessage.{role:'toolResult', content:(TextContent|ImageContent)[], isError, toolName, toolCallId}
//   AssistantMessage.{role:'assistant', content:(TextContent|ThinkingContent|ToolCall)[]}
//   ToolCall.{type:'toolCall', id, name, arguments}
//   TextContent.{type:'text', text}
// 行集编解码：text 块文本 = `__keeper1__` + JSON.stringify(rowset)（前缀可被幂等识别，不会误伤普通文本）。
// 失败隔离：任何钩子抛错 → console.warn + logger 事件，绝不让插件崩掉 agent loop。
// 本文件不 import openclaw（只有 index.js 薄适配层 import SDK），保证无网关也能单测。
// ==========================================================================

import { tag } from './tagger.js';
import { stripAuxParams } from './cleaner.js';
import { applyCompression, pruneDoc } from './compressor.js';
import { createTokenCounter } from './counter.js';
import { messagesTokens } from './tokenizer.js';
import { createLogger } from './logger.js';
import { KEEPER_CONTEXT_ENGINE_ID, createKeeperContextEngine } from './context-engine.js';

export const KEEPER_PREFIX = '__keeper1__';

const NOOP = () => {};

/** 从内容块里提取文本(toolResult persist / user 消息共用形态) */
function textBlocks(content) {
  if (typeof content === 'string') return [{ text: content }];
  if (Array.isArray(content)) return content.filter((b) => b && b.type === 'text');
  return [];
}

/** 编码：doc → text 块文本 */
export function encodeDoc(doc) {
  return KEEPER_PREFIX + JSON.stringify(doc);
}

/** 解码：在一组 text 块里找行集 JSON */
export function extractDocTexts(content) {
  return textBlocks(content)
    .map((b) => b.text)
    .filter((t) => typeof t === 'string' && t.startsWith(KEEPER_PREFIX))
    .map((t) => {
      try {
        return JSON.parse(t.slice(KEEPER_PREFIX.length));
      } catch {
        return null;
      }
    })
    .filter((d) => d !== null && d && typeof d.doc_id === 'string');
}

/** 从 assistant 消息提取 discard 申报（支持一条消息多个 toolCall 各带 discard） */
export function extractDiscards(message) {
  const out = [];
  if (!message || !Array.isArray(message.content)) return out;
  for (const block of message.content) {
    if (!block || block.type !== 'toolCall') continue;
    const args = block.arguments;
    if (args && Array.isArray(args.discard_lines)) {
      out.push({
        toolCallId: block.id,
        toolName: block.name,
        doc_id: typeof args.doc_id === 'string' ? args.doc_id : undefined,
        lines: args.discard_lines,
      });
    }
  }
  return out;
}

/** 把压缩后的 doc 回写进 toolResult 消息的 text 块 */
function hydratePruned(message, doc) {
  const content = Array.isArray(message.content) ? message.content.map((b) => ({ ...b })) : [];
  let found = false;
  for (let i = 0; i < content.length; i++) {
    if (content[i] && content[i].type === 'text' && typeof content[i].text === 'string'
      && content[i].text.startsWith(KEEPER_PREFIX)) {
      content[i] = { ...content[i], text: encodeDoc(doc) };
      found = true;
      break;
    }
  }
  if (!found) return { ok: false };
  return { ok: true, message: { ...message, content } };
}

/**
 * 在上下文接缝（ContextEngine.assemble / extension context 钩子）里跑压缩：
 * OpenClaw messages → 归一化 → applyCompression → 回写。
 * @param {Array} messages event.messages（AgentMessage[]，深拷贝，可安全改）
 * @param {{onDoc:(i:number, doc:object)=>void,
 *          onDiscard:(i:number, d:object)=>void,
 *          onEvent:(ev:object)=>void}} [sink] 观测点（日志/计数用）
 * @returns {{messages: Array, events: Array}}
 */
export function compressView(messages, sink = {}) {
  const onDoc = sink.onDoc ?? NOOP;
  const onDiscard = sink.onDiscard ?? NOOP;
  const onEvent = sink.onEvent ?? NOOP;
  const events = [];
  const norm = [];
  const byIndex = []; // norm[i] → messages 下标

  messages.forEach((m, i) => {
    if (m && m.role === 'toolResult') {
      const docs = extractDocTexts(m.content);
      if (docs.length > 0) {
        onDoc(i, docs[0]);
        norm.push({ role: 'toolResult', isError: !!m.isError, doc: docs[0] });
      } else {
        norm.push({ role: 'toolResult', isError: !!m.isError });
      }
      byIndex.push(i);
    } else if (m && m.role === 'assistant') {
      const discards = extractDiscards(m);
      if (discards.length === 0) {
        norm.push({ role: 'assistant' });
        byIndex.push(i);
      } else {
        for (const d of discards) {
          onDiscard(i, d);
          norm.push({ role: 'assistant', discard: { doc_id: d.doc_id, lines: d.lines } });
          byIndex.push(i);
        }
      }
    } else {
      norm.push({ role: 'user' });
      byIndex.push(i);
    }
  });

  const { messages: comp, events: compEvents } = applyCompression(norm);
  for (const ev of compEvents) {
    events.push(ev);
    onEvent(ev);
  }
  const next = messages.slice(); // event.messages 已是深拷贝，但保守起见再拷贝一份引用级
  for (let i = 0; i < comp.length; i++) {
    const idx = byIndex[i];
    if (messages[idx] && messages[idx].role === 'toolResult' && comp[i].doc
      && comp[i].doc._meta && comp[i].doc._meta._pruned) {
      const h = hydratePruned(messages[idx], comp[i].doc);
      if (h.ok) next[idx] = h.message;
    }
  }
  return { messages: next, events };
}

/**
 * 创建 keeper 插件注册体（供 index.js 与单测使用）。
 * @param {object} api plugin API 的 mock/真实对象（至少提供 pluginConfig、on）
 * @param {{baseDir?:string}} [opts]
 */
export async function createKeeper(api, opts = {}) {
  const cfg = (api && api.pluginConfig) ?? {};
  if (cfg.enabled === false) return { registered: false };
  // tagTools：直接命中的取数工具（**子串匹配**，兼容 MCP 工具名变体）。
  // execTools + execCommandPatterns：keeper 环境取数常走通用执行工具（exec 跑 hithink cli.py），
  // by-toolCallId 登记"待打标"，persist 时依 toolCallId 关联（见钩子 2/1）。
  const tagTools = Array.isArray(cfg.tagTools) && cfg.tagTools.length > 0
    ? cfg.tagTools : ['hithink-market-query'];
  const execTools = Array.isArray(cfg.execTools) && cfg.execTools.length > 0
    ? cfg.execTools : ['exec', 'bash', 'run_shell', 'shell'];
  const execCommandPatterns = Array.isArray(cfg.execCommandPatterns) && cfg.execCommandPatterns.length > 0
    ? cfg.execCommandPatterns : ['hithink', 'cli.py'];
  const traceDir = cfg.traceDir ?? opts.baseDir ?? 'keeper-logs';
  const useTrace = cfg.trace !== false;
  // §6 数据基础：每轮把"压缩前/压缩后 messages"持久化进 trace（方案 A/B 重放的前提）。
  // logger 对 >payloadMax 的 payload 自动外联到 trace_payloads/<id>.json 并留 payload_ref。
  const persistViewPayloads = cfg.persistViewPayloads !== false;
  // createLogger 同步构造（OpenClaw register 要求同步，见 docs/LOGGING.md）
  const logger = useTrace ? createLogger({
    traceDir, runId: cfg.runId,
    ...(cfg.payloadMax ? { payloadMax: cfg.payloadMax } : {}),
  }) : null;

  /** 每个 runId 一份状态：doc 序号 / token 计数 / exec 登记 */
  const runs = new Map();
  const ensureRun = (runId) => {
    if (!runs.has(runId)) {
      runs.set(runId, { seq: 0, counter: createTokenCounter(), pendingExec: false });
    }
    return runs.get(runId);
  };
  // 统一 run 标识：runId > sessionKey > sessionId > agentId
  // （联调实证：before_tool_call/agent_end 事件只给 runId，llm_output 同时给 runId+sessionId，
  //   persist 两者皆无（靠登记表反查）——必须以"最先出现在链路上、全钩子一致"的 turn 级 runId 为锚，
  //   否则 llm_output 解析出 sessionId、before_tool_call 解析出 runId，同一次运行被拆成两个 run state）
  const runKey = (ev = {}, ctx = {}) =>
    ev.runId ?? ctx.runId ?? ev.sessionKey ?? ctx.sessionKey ?? ev.sessionId ?? ctx.sessionId ?? ctx.agentId ?? ev.agentId ?? 'default';
  /** exec 登记表：toolCallId → runId（persist 事件拿不到 runId/sessionId，toolCallId 是唯一跨钩子可靠关联） */
  const execReg = new Map();
  // tagTools 子串匹配（兼容 MCP 工具名变体）
  const isTagTool = (tool) => typeof tool === 'string' && tagTools.some((t) => tool === t || tool.includes(t));
  const isExecishTool = (tool) => typeof tool === 'string' && execTools.includes(tool);

  // ---- v2.4: live/persist 共用 doc 计算（同一 toolCallId 同一 doc, 两路 doc_id/行号一致） ----
  // 修复"模型永远看不到行集"根因：之前 tagger 改写只走 tool_result_persist（写盘）, 发给模型的
  // 内存视图仍为原始 JSON ⇒ 模型无从按 n 申报 discard_lines ⇒ discard_applied 恒 0。
  // 现在：docsByTcId 按 toolCallId 记忆化 doc（先算的一路写入, 另一路复用）, 全局 seq 保证
  // doc_id 跨 run 唯一；ContextEngine.assemble 里的 liveTagger（见下方）把门控 toolResult 改写为
  // keeper 行集后返回新数组 ⇒ selection 把该视图发给模型 ⇒ 模型真正看到行号契约。
  const docsByTcId = new Map(); // toolCallId → doc（live/persist 共享, 防两路重复 tag 出不同 doc_id）
  let globalSeq = 0; // 全局 doc 序号（替代原 per-run st.seq：跨 run 唯一, 序行进 doc_id）
  // tcId 由调用方显式传入（persist 用事件字段 event?.toolCallId ?? ctx?.toolCallId；live 用消息字段
  // toolCallId）——同一工具调用在两路的 tcId 一致, 是两路 doc_id 对齐的关键（消息对象上不一定带）。
  const computeDocFor = (msg, tool, tcId) => {
    if (tcId && docsByTcId.has(tcId)) return { ok: true, value: docsByTcId.get(tcId) };
    const blocks = textBlocks(msg && msg.content);
    if (blocks.some((b) => typeof b.text === 'string' && b.text.startsWith(KEEPER_PREFIX))) {
      return { ok: true, value: null }; // 已打标（resume 场景从盘上重建的 keeper docs）, 不重复 tag
    }
    const raw = blocks.map((b) => b.text).join('\n');
    const out = tag({ tool, blocks: [{ source: { name: tool, check: 'keeper-tagged' }, text: raw }] }, { seq: globalSeq });
    if (out.ok && out.value) {
      globalSeq += 1;
      if (tcId) docsByTcId.set(tcId, out.value);
    }
    return out;
  };
  // live 门控：白名单工具 或 该 toolCallId 已有 doc/已登记 exec（persist 先于下一轮 assemble 消费
  // execReg, 但已把 doc 记入 docsByTcId ⇒ has(tcId) 兜住 exec 结果；SKILL.md(read) 等非取数不动）。
  /** resume 场景重建 cmdHit（复刻 before_tool_call 的登记判定）：历史 exec 结果无 live 登记表,
   *  也没有 memo —— 从消息序列向前找到对应 assistant toolCall 的 command, 命中取数模式才打标。
   *  只回看有限距离（toolResult 恒紧跟其 toolCall, 正常编排 ≤ 数条）, 防长会话 O(n²)。 */
  const reconstructCmdHit = (messages, idx, tool, tcId) => {
    if (!tcId || !isExecishTool(tool) || !Array.isArray(messages)) return false;
    const bound = Math.max(idx - 50, 0);
    for (let j = idx - 1; j >= bound; j--) {
      const a = messages[j];
      if (!a || (a.role !== 'assistant' && a.role !== 'message')) continue;
      // 网关 provider 形态：content[].type==='toolCall'；兜底兼容 OpenAI tool_calls[] 形态
      const tcs = [];
      if (Array.isArray(a.content)) {
        for (const c of a.content) {
          if (c && c.type === 'toolCall' && c.id) tcs.push(c);
        }
      }
      if (Array.isArray(a.tool_calls)) tcs.push(...a.tool_calls);
      for (const tc of tcs) {
        const tid = tc.id ?? tc.toolCallId;
        if (tid !== tcId) continue;
        let args = tc.arguments ?? (tc.function && tc.function.arguments);
        if (typeof args === 'string') { try { args = JSON.parse(args); } catch { return false; } }
        const cmd = args && typeof args === 'object' ? (args.command ?? args.cmd ?? args.script) : String(args ?? '');
        const cmdText = Array.isArray(cmd) ? cmd.join(' ') : String(cmd);
        return cmdText.length > 0 && execCommandPatterns.some((p) => cmdText.includes(p));
      }
    }
    return false;
  };
  const shouldTagLive = (msg, idx, messages) => {
    if (!msg || msg.role !== 'toolResult') return false;
    const tool = msg.toolName ?? '';
    const tcId = msg.toolCallId;
    if (isTagTool(tool)) return true;
    if (tcId && (docsByTcId.has(tcId) || execReg.has(tcId))) return true;
    // resume 兜底：没有 live 登记的历史 exec 结果, 用消息序列重建 cmdHit（复刻 persist/登记门控）
    if (reconstructCmdHit(messages, idx, tool, tcId)) return true;
    return false;
  };
  /** live 视图改写：把门控 toolResult 内容替换为 keeper 行集 doc；无改写时返回原数组原引用。 */
  const liveTagger = (messages, { runId } = {}) => {
    let rewrote = 0;
    const next = messages.slice();
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      if (!shouldTagLive(m, i, messages)) continue;
      const tool = m.toolName ?? '';
      const out = computeDocFor(m, tool, m.toolCallId);
      if (!out.ok || !out.value) {
        if (logger && !out.ok) logger.log({ type: 'tagger_skip', runId, tool, reason: 'tagger_error', source: 'live', ts: new Date().toISOString() });
        continue;
      }
      next[i] = { ...m, content: [{ type: 'text', text: encodeDoc(out.value) }] };
      rewrote += 1;
      // ====[KEEPER-LOG: tagger_doc begin]====
      if (logger) logger.log({ type: 'tagger_doc', runId, tool, doc_id: out.value.doc_id, n_rows: out.value._meta.n_rows, n_sections: out.value.sections.length, source: 'live' });
      // ====[KEEPER-LOG: tagger_doc end]====
    }
    return rewrote > 0 ? { messages: next, rewrote } : { messages, rewrote: 0 };
  };

  const pumpEvents = (runId, events) => {
    // ====[KEEPER-LOG: compressor 事件透传 begin]====
    for (const ev of events) { if (logger) logger.log({ runId, ...ev }); }
    // ====[KEEPER-LOG: compressor 事件透传 end]====
  };
  // ⚠️ 同步失败隔离：OpenClaw 要求 tool_result_persist / before_tool_call / context 等钩子
  // **同步**返回（async 包装的返回值会被忽略，联调实证：persist 改写 message 丢失）。
  // 因此所有钩子统一同步实现：logger.log 内部为同步 fs，调用不 await 即立即落盘。
  const safe = (label, fn) => (...args) => {
    try {
      return fn(...args);
    } catch (e) {
      const msg = `[keeper:${label}] ${e && e.message ? e.message : e}`;
      console.warn(msg);
      // ====[KEEPER-LOG: plugin_error begin]====
      if (logger) logger.log({ type: 'plugin_error', hook: label, error: msg, ts: new Date().toISOString() });
      // ====[KEEPER-LOG: plugin_error end]====
      return undefined; // 失败隔离：对宿主表现为"没处理"
    }
  };

  // ---- 钩子 0：before_agent_run → run_start（run 起点，驾驶舱时间线锚点） ----
  // ====[KEEPER-LOG: run_start begin]====
  api.on?.('before_agent_run', safe('before_agent_run', (event, ctx) => {
    const runId = runKey(event, ctx);
    ensureRun(runId);
    if (logger) {
      logger.log({
        type: 'run_start', runId,
        tagTools, use_trace: useTrace, persist_view_payloads: persistViewPayloads,
        ts: new Date().toISOString(),
      });
    }
    return undefined;
  }));
  // ====[KEEPER-LOG: run_start end]====

  // ---- 钩子 1：tool_result_persist → tagger（结果 → JSON 行集） ----
  api.on?.('tool_result_persist', safe('persist', (event, ctx) => {
    const msg = event && event.message;
    if (!msg) return;
    const tool = event.toolName ?? msg.toolName ?? '';
    // exec 登记反查：persist 事件没有 runId/sessionId，但从 before_tool_call 的登记表
    // 按 toolCallId 找回该次调用的 runId（exec 结果必紧跟其调用，跨钩子唯一可靠关联）
    const tcId = event?.toolCallId ?? ctx?.toolCallId;
    const regRunId = tcId ? execReg.get(tcId) : undefined;
    const runId = regRunId ?? runKey(event, ctx);
    const st = ensureRun(runId);
    // 命中判定：白名单子串匹配（MCP 取数工具）或 exec 登记配对（登记表优先，顺序兜底）
    const byName = isTagTool(tool);
    const execHit = regRunId
      ? (execReg.delete(tcId), true) // 登记表消费（不等 tool 名，登记与 persist 同一工具调用）
      : st.pendingExec && isExecishTool(tool);
    if (execHit) st.pendingExec = false; // 消费登记
    if (st.pendingExec && !execHit && !isExecishTool(tool)) st.pendingExec = false; // 悬置登记落在非 exec 结果 → 丢弃
    if (!byName && !execHit) return; // 非取数来源，不接手
    if (msg.role !== 'toolResult' && msg.role !== 'user') return;
    const raw = textBlocks(msg.content).map((b) => b.text).join('\n');
    // v2.4: 与 liveTagger 共用同一份 doc（docsByTcId 记忆化, live/persist 两路 doc_id/行号一致）
    const out = computeDocFor(msg, tool, tcId);
    if (!out.ok || !out.value) {
      // ====[KEEPER-LOG: tagger_skip begin]====
      if (logger) {
        logger.log({ type: 'tagger_skip', runId, tool, reason: out.ok ? 'no_info' : 'tagger_error', n_chars: raw.length, ts: new Date().toISOString() });
      }
      // ====[KEEPER-LOG: tagger_skip end]====
      return; // 无信息不产 doc（记录原因，便于驾驶舱诊断"为什么某次工具结果没进行集"）
    }
    // ====[KEEPER-LOG: tagger_doc begin]====
    if (logger) logger.log({ type: 'tagger_doc', runId, doc_id: out.value.doc_id, n_rows: out.value._meta.n_rows, n_sections: out.value.sections.length, source: 'persist' });
    // ====[KEEPER-LOG: tagger_doc end]====
    // ⚠️ 同步返回改写后的 message（async 会被 OpenClaw 丢弃，见联调实证）
    return { message: { ...msg, content: [{ type: 'text', text: encodeDoc(out.value) }] } };
  }));

  // ---- 钩子 2：before_tool_call → cleaner（剥离辅助参数）+ exec 取数命令登记 ----
  api.on?.('before_tool_call', safe('before_tool_call', (event, ctx) => {
    const params = event && event.params;
    if (!params || typeof params !== 'object') return;
    const { rest, aux } = stripAuxParams(params);
    const hasAux = Object.keys(aux).length > 0;
    const runId = runKey(event, ctx);
    const st = ensureRun(runId);
    // exec 管线：通用执行工具命令文本命中取数模式 → 置 pendingExec + 登记 toolCallId（供 persist 反查）
    const cmd = params.command ?? params.cmd ?? params.script ?? '';
    const cmdText = Array.isArray(cmd) ? cmd.join(' ') : String(cmd);
    const cmdHit = isExecishTool(event.toolName) && cmdText.length > 0 && execCommandPatterns.some((p) => cmdText.includes(p));
    if (cmdHit) {
      st.pendingExec = true;
      // 登记 toolCallId → runId，供 persist 反查（persist 事件本身无 runId；toolCallId 跨钩子可靠）
      if (event.toolCallId) execReg.set(event.toolCallId, runId);
    }
    if (logger && (hasAux || isTagTool(event.toolName) || cmdHit)) {
      // ====[KEEPER-LOG: assistant_discard|tool_call begin]====
      logger.log({
        type: hasAux ? 'assistant_discard' : 'tool_call',
        runId,
        tool: event.toolName,
        toolCallId: event.toolCallId,
        ...(hasAux ? { doc_id: aux.doc_id, discard_lines: aux.discard_lines } : {}),
        args_after_strip: hasAux ? rest : undefined,
      });
      // ====[KEEPER-LOG: assistant_discard|tool_call end]====
    }
    if (cmdHit) {
      // ====[KEEPER-LOG: exec_tool_match begin]====
      if (logger) {
        logger.log({ type: 'exec_tool_match', runId, tool: event.toolName, toolCallId: event.toolCallId, cmd_preview: cmdText.slice(0, 200), ts: new Date().toISOString() });
      }
      // ====[KEEPER-LOG: exec_tool_match end]====
    }
    // ⚠️ 同步返回剥离参数（async 会被 OpenClaw 丢弃 → 剥离不生效）
    return hasAux ? { params: rest } : undefined;
  }));

  // ---- 轮次诊断：llm_input → llm_input（每轮进模型的输入规模，usage 缺失时的估算旁证） ----
  // ====[KEEPER-LOG: llm_input begin]====
  api.on?.('llm_input', safe('llm_input', (event, ctx) => {
    const messages = event && (event.messages ?? event.input);
    if (!Array.isArray(messages)) return;
    const runId = runKey(event, ctx);
    ensureRun(runId);
    if (logger) {
      const inTokens = messagesTokens(messages);
      logger.log({ type: 'llm_input', runId, n_messages: messages.length, est_tokens: inTokens, ts: new Date().toISOString() });
    }
    return undefined;
  }));
  // ====[KEEPER-LOG: llm_input end]====

  // ---- token 实测：llm_output（usage） → token_round ----
  api.on?.('llm_output', safe('llm_output', (event, ctx) => {
    const usage = event && (event.usage || event.normalizedUsage);
    if (!usage) return;
    const runId = runKey(event, ctx);
    const st = ensureRun(runId);
    const input = usage.prompt_tokens ?? usage.input ?? 0;
    const output = usage.completion_tokens ?? usage.output ?? 0;
    st.counter.recordRound({ input, output, usage: { prompt_tokens: input, completion_tokens: output } });
    const stat = st.counter.stats();
    if (logger) {
      // ====[KEEPER-LOG: token_round begin]====
      logger.log({
        type: 'token_round', runId,
        round: stat.rounds, input, output, saved: 0,
        usage: { prompt_tokens: input, completion_tokens: output },
        total: stat.total, input_total: stat.input_total, output_total: stat.output_total,
      });
      // ====[KEEPER-LOG: token_round end]====
    }
  }));

  // ---- 上下文接缝 v2.3：ContextEngine 槽位注册（替代 extension api.on("context")） ----
  // 同步注册（OpenClaw register 强制同步；factory 惰性，在 resolveContextEngine 时才调用）。
  // 选中方式：openclaw.json plugins.slots.contextEngine = KEEPER_CONTEXT_ENGINE_ID。
  // 语义：selection 嵌入式 run loop 每轮迭代调 contextEngine.assemble()，返回的 messages
  //   替换发给模型的 prompt（selection:12397，不 gate ownsCompaction）——等价旧 design 里
  //   api.on("context") 的"只改内存视图"。失败隔离：assemble 内 try/catch + 宿主 fallback。
  api.registerContextEngine?.(
    KEEPER_CONTEXT_ENGINE_ID,
    // v2.4: 注入 liveTagger —— assemble 每轮先把门控 toolResult 改写为 keeper 行集（live 视图,
    //  模型可见可 discard）, 再走 compressView 行级压缩；live/persist 共用 doc 记忆化（assembly 闭包）。
    () => createKeeperContextEngine({ logger, persistViewPayloads, liveTagger }),
  );

  // ---- 汇总：agent_end → run_finalized + run_stats ----
  api.on?.('agent_end', safe('agent_end', (event, ctx) => {
    const runId = runKey(event, ctx);
    if (logger) {
      // ====[KEEPER-LOG: run_finalized begin]====
      const counts = logger.counts();
      logger.log({ type: 'run_finalized', runId, events_total: counts.total, warn_fallbacks: logger.warnFallbacks() });
      logger.finalize();
      // ====[KEEPER-LOG: run_finalized end]====
    }
    runs.delete(runId);
    return undefined;
  }));

  return { registered: true, tagTools, traceDir, contextEngineId: KEEPER_CONTEXT_ENGINE_ID, hooks: ['before_agent_run', 'tool_result_persist', 'before_tool_call', 'llm_input', 'llm_output', 'agent_end'] };
}

export { pruneDoc, KEEPER_CONTEXT_ENGINE_ID };