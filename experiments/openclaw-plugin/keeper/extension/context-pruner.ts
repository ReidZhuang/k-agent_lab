// ==========================================================================
// keeper context-pruner —— OpenClaw **extension**（不是 plugin！）删行视图压缩
// ==========================================================================
// ⚠️ 架构修正（2026-08-28，v2.2）：插件 API 的 api.on("context") 是死路——
//   插件 SDK 的 on() 走 registerTypedHook，只认 typed-hook 白名单（PLUGIN_HOOK_NAMES），
//   "context" 不在白名单 → 注册即被忽略（gateway 日志：unknown typed hook "context" ignored）。
//   context 是 **extension API** 的事件（sessions.js emitContext 遍历 ext.handlers.get("context")，
//   官方 contextPruning 同形态：api.on("context", (event, ctx) => ({ messages: next }))）。
//   因此 keeper 的删行环节落在 extension 文件里；插件(plugin)只保留 typed hooks
//   （打标/剥离/token 统计），两组件共享同一 trace.jsonl（观测层复用，删行计算零跨进程 IO）。
//
// 设计（对照 PLUGIN_DESIGN_V2.md §2.4 位置配对 / §7.3 插件落地接缝）：
//   - handler 从 event.messages（AgentMessage[]）里提取 keeper 行集(doc_id+n 行号)与模型的
//     discard_lines 申报（extractDocTexts / extractDiscards），applyCompression 只消费"最新未标记 doc"。
//   - 只改内存视图：返回 { messages: next }，不改盘上 transcript（盘上保留全文，可恢复）。
//   - 幂等：compressor 只消费未标记 doc（_meta._pruned 已压缩即跳过），transformContext 每轮从
//     原始消息重建视图，本 handler 是纯函数。
//   - 观测：view_before / view_after / discard_applied 事件**追加写进与插件相同的 trace.jsonl**
//     （createLogger 复用，与插件共享 traceDir），驾驶舱/效果对比据此统计。
// 本文件不 import openclaw/plugin-sdk，只 import 插件纯函数与 node:fs —— 无网关也能单测。
// ==========================================================================

import { compressView, extractDocTexts, extractDiscards } from '../plugin/src/assembly.js';
import { createLogger } from '../plugin/src/logger.js';
import { messagesTokens } from '../plugin/src/tokenizer.js';

const DEFAULT_TRACE_DIR = process.env.KEEPER_TRACE_DIR ?? 'keeper-logs';
// §6 数据基础：每轮把压缩前/后 messages 全量入库（方案 A/B 重放前提），与插件同约定。
const DEFAULT_PAYLOAD_MAX = 50_000;

/** 从 extension ctx 里拿 session 标识（view 压缩是 session 级操作，与插件的 turn 级 runId 并存） */
function sessionKeyOf(ctx) {
  try {
    const sm = ctx && ctx.sessionManager;
    if (sm && typeof sm.getSessionId === 'function') {
      const sid = sm.getSessionId();
      if (sid) return `session:${sid}`;
    }
  } catch { /* fallthrough */ }
  return 'extension:default';
}

/**
 * context 事件处理：event.messages → 压缩视图。
 * 纯函数（无外部状态），可单测；返回 { messages } 由 emitContext 链接收并替换待发消息。
 * @param {{messages: unknown[], type?: string}} event
 * @param {object} ctx extension context
 * @param {{traceDir?: string, persistViewPayloads?: boolean, logger?: object}} [opts] 测试注入
 */
export function pruneContextView(event, ctx, opts = {}) {
  const messages = event && event.messages;
  if (!Array.isArray(messages) || messages.length === 0) return undefined;
  const logger = opts.logger ?? null;
  const persistViewPayloads = opts.persistViewPayloads !== false;
  const sessionKey = sessionKeyOf(ctx);
  const before = messagesTokens(messages);
  const { messages: next, events } = compressView(messages);
  const after = messagesTokens(next);
  const saved = Math.max(0, before - after);
  const hit = events.some((e) => e.type === 'discard_applied');
  if (logger) {
    logger.log({
      type: 'view_before', runId: sessionKey, tokens: before, n_messages: messages.length,
      ...(persistViewPayloads ? { payload: JSON.stringify(messages) } : {}),
    });
    logger.log({
      type: 'view_after', runId: sessionKey, tokens: after, n_messages: next.length, saved, hit,
      ...(persistViewPayloads ? { payload: JSON.stringify(next) } : {}),
    });
    for (const ev of events) logger.log({ type: ev.type, runId: sessionKey, ...ev });
  }
  return { messages: next };
}

/**
 * extension 入口：OpenClaw 加载时调用 factory(api)，api.on("context") 挂删行。
 * 同步注册（createExtensionAPI.on 无任何异步要求；handler 内不 await）。
 */
export default function contextPruner(api) {
  const logger = createLogger({
    traceDir: process.env.KEEPER_TRACE_DIR ?? DEFAULT_TRACE_DIR,
    ...(process.env.KEEPER_PAYLOAD_MAX ? { payloadMax: Number(process.env.KEEPER_PAYLOAD_MAX) } : {}),
  });
  api.on('context', (event, ctx) => {
    try {
      return pruneContextView(event, ctx, { logger, persistViewPayloads: process.env.KEEPER_PERSIST_VIEW_PAYLOADS !== 'false' });
    } catch (e) {
      // 失败隔离：context 处理绝不让 agent loop 崩
      console.warn(`[keeper:context] ${e && e.message ? e.message : e}`);
      return undefined;
    }
  });
  return { registered: true, traceDir: logger.traceDir };
}

export { extractDocTexts, extractDiscards, compressView };