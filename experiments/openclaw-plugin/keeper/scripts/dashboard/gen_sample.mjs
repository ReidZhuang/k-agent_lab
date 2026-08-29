#!/usr/bin/env node
// 生成驾驶舱演示样本 run：模拟一轮 agent loop 的全部事件类型（含 tagger/discard/token/前后对比）
// 产物：scripts/dashboard/logs/<run>/trace.jsonl [+ run_stats.json + trace_payloads/pay_sample_*.json]
// 用法： node scripts/dashboard/gen_sample.mjs [runid]
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const runId = process.argv[2] ?? 'sample';
const dir = path.join(__dirname, 'logs', runId);
const payDir = path.join(dir, 'trace_payloads');
await mkdir(payDir, { recursive: true });

const ts = '2026-08-26T15:04:00.000Z';
// 时间戳递增辅助
const t = (i) => new Date(Date.parse(ts) + i * 1500).toISOString();

const doc0 = {
  tool: 'hithink-market-query',
  doc_id: 'doc_0',
  query: '比亚迪 近10日涨跌幅',
  fetched_at: '2026-08-26T15:03:50+08:00',
  sections: [
    {
      id: 's0',
      source: { name: '同花顺 i问财 · 盘面', url: '', check: '核对行情口径' },
      rows: [
        { n: 0, k: 'h', t: '日期 | 收盘价 | 涨跌幅 | 换手率' },
        { n: 1, k: 'v', t: '08-22 | 336.10 | +1.20% | 2.9%' },
        { n: 2, k: 'v', t: '08-23 | 341.00 | +1.46% | 3.1%' },
        { n: 3, k: 'v', t: '08-26 | 346.00 | +1.47% | 3.2%' },
        { n: 4, k: 'v', t: '08-27 | 345.20 | -0.23% | 2.7%' },
        { n: 5, k: 'u', t: '数据来源：同花顺，仅供参考，不构成投资建议。' },
        { n: 6, k: 'u', t: '版权归同花顺所有，如有转载请联系授权。' },
      ],
    },
  ],
  _meta: { n_rows: 7, hint: '按 n 引用；用 discard_lines 报告完全无用的行号' },
};

const events = [
  { ts: t(0), type: 'run_start', run: runId, version: '0.1.0' },
  { ts: t(1), type: 'tool_call', via: 'cleaner', tool: 'hithink-market-query', args: { query: '比亚迪 近10日涨跌幅', days: 10 } },
  { ts: t(2), type: 'tagger_doc', doc_id: 'doc_0', n_rows: 7, n_sections: 1, n_chars: 612 },
  { ts: t(3), type: 'view_before', view: 'context-assembled', tokens: 1280, n_chars: 5400, n_messages: 6 },
  { ts: t(4), type: 'token_round', round: 1, input: 1280, output: 210, usage: { prompt_tokens: 1255, completion_tokens: 198 }, saved: 0 },
  { ts: t(5), type: 'assistant_discard', tool_calls: 1, doc_id: 'doc_0', discard_lines: [0, 5, 6] },
  { ts: t(6), type: 'discard_applied', doc_id: 'doc_0', n_del: 3, n_left: 4, lines: [0, 5, 6] },
  { ts: t(7), type: 'view_after', view: 'compressed', tokens: 1024, n_chars: 4120, n_messages: 6, saved: 256 },
  { ts: t(8), type: 'token_round', round: 2, input: 1560, output: 330, usage: null, saved: 256, usage_note: 'usage 缺失，走本地估算' },
  { ts: t(9), type: 'tool_result_error', tool: 'web_search', at: 9, note: '搜索失败，不计入候选' },
  { ts: t(10), type: 'discard_empty', at: 10 },
  { ts: t(11), type: 'payload_doc', payload_ref: 'pay_sample_0', doc_id: 'doc_1', n_rows: 12 },
  { ts: t(12), type: 'run_finalized', events_total: 12, warn_fallbacks: 0 },
];

let file = '';
for (const ev of events) file += JSON.stringify(ev) + '\n';
await writeFile(path.join(dir, 'trace.jsonl'), file, 'utf8');
await writeFile(path.join(payDir, 'pay_sample_0.json'), JSON.stringify(doc0, null, 1), 'utf8');
await writeFile(path.join(dir, 'run_stats.json'), JSON.stringify({
  runId, started_at: events[0].ts, ended_at: events.at(-1).ts,
  events_total: events.length,
  events_by_type: events.reduce((m, e) => ((m[e.type] = (m[e.type] ?? 0) + 1), m), {}),
  warn_fallbacks: 0, degraded: false,
}, null, 2) + '\n', 'utf8');

console.log(`[gen_sample] 已生成 ${dir}`);