// ==========================================================================
// Keeper ContextEngine —— 插件 API 可达的"视图压缩"接缝（context-engine slot）
// ==========================================================================
// 架构实证（2026-08-29，v2.3 修正"extension 路线作废"）：
//   1. extension api.on("context") 在网关嵌入式路径完全失效：
//      embedded resource loader 硬编码 noExtensions:true（createEmbeddedAgentResourceLoader
//      给 DefaultResourceLoader 传 { noExtensions, noSkills, ... }）→ 文件系统 extension
//      在网关进程里【从不加载】，settings.json extensions 条目同样被忽略。
//   2. 官方上下文修剪 = 内建工厂注入形态（buildEmbeddedExtensionFactories →
//      buildContextPruningFactory），且仅 cache-ttl 供应商（Anthropic/Google prompt cache）
//      可用；deepseek-v4-flash 走 opencode-go → isCacheTtlEligibleProvider=false →
//      官方 config.contextPruning 模式在本栈恒为空操作（连 factory 都不实例化）。
//   3. OpenClaw 提供**插件可达**的 ContextEngine 槽位（等价于"注册内建工厂"的插件版）：
//        - 注册：OpenClawPluginApi.registerContextEngine(id, factory)（同步，registry 全局
//          singleton，非 bundled-only，id 不得为预留值 "legacy"）。
//        - 选中：config.plugins.slots.contextEngine = "<id>" 显式插槽覆盖 → resolveContextEngine
//          （registry-CMq-i5MO.js）按其解析；非默认引擎 factory/契约失败 → 记录 + quarantine → 静默回退 legacy。
//        - 调用：selection 嵌入式 run loop 每轮迭代 `if (activeContextEngine) assemble(...)`
//          （selection-DrXxngyT.js:12397，不 gate ownsCompaction），assembled.messages !==
//          activeSession.messages 时替换 agent.state.messages = 压缩视图 → 发给模型的 prompt
//          就是修剪后的消息。等价 api.on("context") 的"只改发给模型的内存视图，不动盘上 transcript"。
//        - 契约（describeResolvedContextEngineContractError）：info{id,name} + ingest + assemble + compact。
// 本引擎 ownsCompaction:true → selection:12010 安装 installContextEngineLoopHook（transformContext
// 包装, 每轮模型调用都走）→ assemble 每轮执行（含 v2.4 liveTagger 实时打标）。
// assemble 幂等：每轮从原始消息重建视图（liveTagger 只改返回视图, 不动入参/盘上 transcript）；
// compressor 只消费未 _pruned 的最新 doc；compact() 返回 not-compacted 安全（宿主只看 result.compacted）。
// 失败隔离：assemble 内 try/catch → 原样返回；宿主另有 try/catch fallback（log.warn → pipeline messages）。
// 本文件纯逻辑，不 import openclaw/plugin-sdk（与 assembly/compressor 同层），可单测。
// ==========================================================================

import { compressView } from './assembly.js';
import { messagesTokens } from './tokenizer.js';

export const KEEPER_CONTEXT_ENGINE_ID = 'keeper';

const NOOP = () => {};

/**
 * 创建 keeper ContextEngine 实例。
 * @param {{logger?:object, persistViewPayloads?:boolean, liveTagger?:Function}} [opts]
 *   观测注入（复用插件同一 trace.jsonl）；liveTagger 由 assembly 注入：把门控 toolResult 改写为
 *   keeper 行集（v2.4 关键修复 —— 模型从此真正看到行号契约才能申报 discard_lines）。
 * @returns {object} 满足 ContextEngine 契约的对象
 */
export function createKeeperContextEngine(opts = {}) {
  const logger = opts.logger ?? null;
  const persistViewPayloads = opts.persistViewPayloads !== false;
  const liveTagger = typeof opts.liveTagger === 'function' ? opts.liveTagger : null;

  const sessionRunId = (params) => {
    const key = (params && params.sessionKey) || (params && params.sessionId) || 'unknown';
    return `session:${key}`;
  };
  const stamp = () => ({ ts: new Date().toISOString() });

  return {
    info: {
      id: KEEPER_CONTEXT_ENGINE_ID,
      name: 'keeper 语料语义压缩（discard_lines 行级视图压缩）',
      version: '2.4.2',
      // ownsCompaction:true 是"每轮视图压缩"接缝的钥匙 —— selection:12010 用它 gate
      // installContextEngineLoopHook（transformContext 包装, 每轮模型调用都走). 之前为 false ⇒
      // 只有一次性 session-resume 接缝(12397), 全新会话下 0 条消息⇒永不压缩。compact() 返回
      // not-compacted 安全：宿主只读 result.compacted 决定 adopt, 不压缩就原样继续。
      ownsCompaction: true,
      turnMaintenanceMode: 'foreground',
    },
    /** 每轮迭代：对将发给模型的 messages 做行级修剪。幂等、纯计算、可安全降级。 */
    async assemble(params) {
      const messages = params && params.messages;
      if (!Array.isArray(messages) || messages.length === 0) {
        return { messages: Array.isArray(messages) ? messages : [], estimatedTokens: 0 };
      }
      const runId = sessionRunId(params);
      const before = messagesTokens(messages);
      // ====[KEEPER-LOG: view_before begin]====
      try {
        if (logger) {
          logger.log({
            type: 'view_before', runId, tokens: before, n_messages: messages.length,
            ...(persistViewPayloads ? { payload: JSON.stringify(messages) } : {}),
          });
        }
      } catch (e) {
        console.warn(`[keeper:context-engine] view_before log failed: ${e.message}`);
      }
      // ====[KEEPER-LOG: view_before end]====
      // ---- v2.4: 实时打标（liveTagger）→ 模型真实看到 keeper 行集 ----
      // 之前 tagger 改写只落盘（persist 路径），发给模型的内存视图仍是原始 JSON ⇒ 模型不知道行号
      // 契约 ⇒ 从不 discard_lines。这里在 assemble 内直接改写 messages：liveTagger 返回新数组且
      // selection 只在 !== 入参时替换模型视图 ⇒ 行集进入 prompt；与盘上 archive 共用同一份 doc
      // （assembly 内按 toolCallId 记忆化, 两路 doc_id 一致）。
      let tagged = messages;
      let rewrote = 0;
      if (liveTagger) {
        try {
          const tr = liveTagger(messages, { runId });
          if (tr && Array.isArray(tr.messages) && tr.messages !== messages) {
            tagged = tr.messages;
            rewrote = tr.rewrote ?? 0;
          }
        } catch (e) {
          // 失败隔离：打标失败 → 原样走压缩, 绝不让模型调用崩
          console.warn(`[keeper:context-engine] liveTagger failed: ${e.message}`);
        }
      }
      let next = messages;
      let events = [];
      try {
        const r = compressView(tagged);
        next = r.messages;
        events = r.events;
      } catch (e) {
        // 失败隔离：压缩失败 → 原样返回，绝不让模型调用崩
        console.warn(`[keeper:context-engine] compressView failed: ${e.message}`);
        return { messages, estimatedTokens: before };
      }
      const after = messagesTokens(next);
      const saved = Math.max(0, before - after);
      const hit = events.some((ev) => ev.type === 'discard_applied');
      // ====[KEEPER-LOG: view_after + 压缩事件透传 begin]====
      try {
        if (logger) {
          logger.log({
            type: 'view_after', runId, tokens: after, n_messages: next.length, saved, hit,
            ...(persistViewPayloads ? { payload: JSON.stringify(next) } : {}),
          });
          for (const ev of events) logger.log({ type: ev.type, runId, ...ev, ...stamp() });
        }
      } catch (e) {
        console.warn(`[keeper:context-engine] view_after log failed: ${e.message}`);
      }
      // ====[KEEPER-LOG: view_after + 压缩事件透传 end]====
      // 命中删除或用 liveTagger 改写了视图 → 返回新数组（selection 在 !== 时替换模型视图；
      // 未命中未改写 → 返回原数组引用，省一次赋值）
      if (!hit && rewrote === 0) return { messages, estimatedTokens: before };
      return { messages: next, estimatedTokens: after };
    },
    /** 契约占位：keeper 不维护引擎侧存储（压缩从当轮 messages 就地计算）。 */
    async ingest() {
      return { ingested: true };
    },
    async ingestBatch() {
      return { ingestedCount: 0 };
    },
    /** 不行：keeper 的行级压缩在 assemble 内联完成，运行时 compaction 路径照旧（ownsCompaction=false）。 */
    async compact() {
      return { ok: true, compacted: false, reason: 'keeper 行级压缩在 assemble 内联完成，不参与运行时 compaction' };
    },
    async afterTurn() {},
    async maintain() {
      return { changed: false, bytesFreed: 0, rewrittenEntries: 0 };
    },
    async dispose() {},
  };
}