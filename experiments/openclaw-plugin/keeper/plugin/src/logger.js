// ==========================================================================
// U6 logger —— trace 事件落盘（trace.jsonl + run_stats.json + 大 payload 外联）
// ==========================================================================
// 设计：U6 的 trace = "恢复源"（原文+删除记录），也是驾驶舱(Step2)与效果对比(Step5/6)的数据基础。
//   - trace.jsonl   每行一个 JSON 事件，顺序即发生顺序（追加写，低延迟）。
//   - trace_payloads/  事件含大 payload 时外联写入 <id>.json，trace.jsonl 只留 {payload_ref}。
//   - run_stats.json flush 时汇总：事件总量 / 按类型计数 / 起止时间。
// 失败不回抛：任何 IO 失败 → console.warn 降级（插件不允许因日志而崩）。
// ==========================================================================

import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export const DEFAULT_PAYLOAD_MAX = 50_000; // 字符阈值：超过则外联

let seq = 0;
function nextPayloadId(eventIndex) {
  seq += 1;
  return `pay_${Date.now()}_${eventIndex}_${seq}`;
}

/**
 * 创建 logger。
 * ⚠️ **必须同步**：OpenClaw 插件 register 要求同步（见 docs/LOGGING.md 与 index.js），
 * 因此目录创建与所有文件 IO 一律用同步 fs。每次调用 event 写入量小（每轮几个事件），
 * 追加写（appendFileSync）延迟可忽略；失败同样降级 console，不让插件崩。
 * @param {{traceDir?:string, runId?:string, payloadMax?:number}} [opts]
 * @returns {{log:(event:object)=>void, finalize:()=>object,
 *                    warnFallbacks:()=>number, counts:()=>object,
 *                    traceDir:string, tracePath:string, payloadDir:string}}
 */
export function createLogger(opts = {}) {
  const traceDir = opts.traceDir ?? '.';
  const runId = opts.runId ?? `run_${Date.now()}`;
  const payloadMax = opts.payloadMax ?? DEFAULT_PAYLOAD_MAX;
  const tracePath = path.join(traceDir, 'trace.jsonl');
  const statsPath = path.join(traceDir, 'run_stats.json');
  const payloadDir = path.join(traceDir, 'trace_payloads');
  const byType = {};
  const startedAt = new Date().toISOString();
  let total = 0;
  let eventIndex = 0;
  let warnFallbacks = 0;
  let degraded = false;

  try {
    mkdirSync(traceDir, { recursive: true }); // 目录不存在自动建（T-U6-2）
    mkdirSync(payloadDir, { recursive: true });
  } catch (e) {
    degraded = true;
    warnFallbacks += 1;
    console.warn('[keeper:logger] 目录创建失败，日志降级 console：', e.message);
  }

  async function log(event) {
    if (event === null || typeof event !== 'object') {
      console.warn('[keeper:logger] 忽略非对象事件');
      return;
    }
    eventIndex += 1;
    total += 1;
    byType[event.type] = (byType[event.type] ?? 0) + 1;
    let line;
    try {
      const ev = { ts: new Date().toISOString(), ...event };
      if (typeof ev.payload === 'string' && ev.payload.length > payloadMax) {
        const id = nextPayloadId(eventIndex);
        writeFileSync(path.join(payloadDir, `${id}.json`), ev.payload, 'utf8');
        delete ev.payload;
        ev.payload_ref = id;
      }
      line = JSON.stringify(ev);
    } catch (e) {
      // 结构/序列化失败 → 降级，不让插件崩
      warnFallbacks += 1;
      console.warn('[keeper:logger] 事件序列化失败：', e.message);
      return;
    }
    try {
      appendFileSync(tracePath, line + '\n', 'utf8');
    } catch (e) {
      warnFallbacks += 1;
      console.warn('[keeper:logger] trace 写入失败：', e.message);
    }
  }

  async function finalize() {
    const stats = {
      runId,
      started_at: startedAt,
      ended_at: new Date().toISOString(),
      events_total: total,
      events_by_type: byType,
      warn_fallbacks: warnFallbacks,
      degraded,
    };
    try {
      writeFileSync(statsPath, JSON.stringify(stats, null, 2), 'utf8');
    } catch (e) {
      warnFallbacks += 1;
      console.warn('[keeper:logger] run_stats 写入失败：', e.message);
    }
    return stats;
  }

  return {
    log,
    finalize,
    warnFallbacks: () => warnFallbacks,
    counts: () => ({ total, byType: { ...byType } }),
    traceDir,
    tracePath,
    payloadDir,
  };
}