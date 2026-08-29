// extension/context-pruner.ts 单元/集成测试 —— node --test
// 对应 DEVELOPMENT_PLAN.md §4（T-CE-2 视图 payload 入库、T-CE-3 payload 外联、T-CE-4 双 discard 配对）
// + v2.2 架构修正后的 extension 语义（event.messages → 压缩视图，事件落同一 trace.jsonl）。
// 不 import openclaw：直接 import 纯函数 pruneContextView 与 createLogger（无网关可单测）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import contextPrunerDefault, { pruneContextView } from '../../extension/context-pruner.ts';
import { createLogger } from '../src/logger.js';
import { encodeDoc, extractDocTexts } from '../src/assembly.js';
import { tag } from '../src/tagger.js';

const SRC = { name: '同花顺 i问财 · 盘面', check: 'keeper-tagged' };
function makeDoc(text, seq = 0) {
  return tag({ tool: 'hithink-market-query', blocks: [{ source: SRC, text }] }, { seq }).value;
}
function trMsg(doc) {
  return { role: 'toolResult', isError: false, content: [{ type: 'text', text: encodeDoc(doc) }] };
}
function asstMsg(discards) {
  return {
    role: 'assistant',
    content: discards.map((d, i) => ({
      type: 'toolCall', id: `c${i}`, name: 'hithink-market-query', arguments: d,
    })),
  };
}
async function freshTraceCfg(t) {
  const dir = await mkdtemp(path.join(tmpdir(), 'keeper-ext-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return { traceDir: dir, logger: createLogger({ traceDir: dir }) };
}

// ---------- 冒烟 ----------

test('EXT-1：空/非数组 messages → 返回 undefined（不处理，不落事件）', async () => {
  assert.equal(pruneContextView({ messages: [] }, {}), undefined);
  assert.equal(pruneContextView(undefined, {}), undefined);
  assert.equal(pruneContextView({ messages: 'nope' }, {}), undefined);
});

test('EXT-2：无 keeper 标记的消息 → 原样返回，无 discard 事件', async () => {
  const msgs = [
    { role: 'user', content: 'hi' },
    { role: 'toolResult', isError: false, content: [{ type: 'text', text: '普通结果' }] },
    { role: 'assistant', content: [{ type: 'text', text: '看看' }] },
  ];
  const r = pruneContextView({ messages: msgs }, {});
  assert.ok(r && Array.isArray(r.messages));
  assert.equal(r.messages[1].content[0].text, '普通结果');
});

// ---------- T-CE-2 / T-CE-3 语义（视图 payload 入库 / 外联） ----------

test('EXT-3（原 T-CE-2）：view_before/view_after 落同一 trace，payload 含该轮 messages 全量', async (t) => {
  const { traceDir, logger } = await freshTraceCfg(t);
  const doc = makeDoc('## 比亚迪盘面\n收盘价: 346.00 | 涨跌幅: +2.1% | 换手率: 3.2%\n收盘价: 345.20 | 涨跌幅: -0.2% | 换手率: 2.7%\n仅供参考，不构成投资建议。\n版权声明：本页信息归同花顺所有。');
  const msgs = [trMsg(doc), asstMsg([{ query: 'q', discard_lines: [0, 3, 4] }])];
  pruneContextView({ messages: msgs }, { sessionManager: { getSessionId: () => 's1' } }, { logger });
  const evs = (await readFile(path.join(traceDir, 'trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const vb = evs.find((e) => e.type === 'view_before');
  const va = evs.find((e) => e.type === 'view_after');
  assert.ok(vb && typeof vb.payload === 'string', 'view_before 应带压缩前 messages 全量');
  assert.ok(va && typeof va.payload === 'string');
  const parsed = JSON.parse(vb.payload);
  assert.equal(parsed.length, 2);
  assert.equal(parsed[0].role, 'toolResult');
  // runId 从 ctx.sessionManager 推导（与插件 turn 级 runId 并存）
  assert.equal(vb.runId, 'session:s1');
  assert.ok(va.saved > 0, '压缩后应省 token');
  assert.ok(evs.some((e) => e.type === 'discard_applied'), 'discard_applied 应落 trace');
});

test('EXT-4（原 T-CE-2 变体）：persistViewPayloads=false → view 事件不带 payload', async (t) => {
  const { logger } = await freshTraceCfg(t);
  const doc = makeDoc('## 比亚迪盘面\n收盘价: 346.00');
  const msgs = [trMsg(doc), asstMsg([{ query: 'q', discard_lines: [0] }])];
  pruneContextView({ messages: msgs }, { sessionManager: { getSessionId: () => 's1' } }, { logger, persistViewPayloads: false });
  const vb = await readFile(logger.tracePath, 'utf8');
  const ev = vb.trim().split('\n').map(JSON.parse).find((e) => e.type === 'view_before');
  assert.ok(!('payload' in ev), 'persistViewPayloads=false → 不写 payload');
});

test('EXT-5（原 T-CE-3）：payload 超阈值 → 外联 trace_payloads/ 留 payload_ref', async (t) => {
  const dir = await mkdtemp(path.join(tmpdir(), 'keeper-ext-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const logger = createLogger({ traceDir: dir, payloadMax: 40 });
  const big = { role: 'toolResult', isError: false, content: [{ type: 'text', text: 'x'.repeat(200) }] };
  pruneContextView({ messages: [big] }, {}, { logger });
  const evs = (await readFile(path.join(dir, 'trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const vb = evs.find((e) => e.type === 'view_before');
  assert.ok(vb && typeof vb.payload_ref === 'string', '应外联 payload_ref');
  assert.ok(!('payload' in vb));
  const stored = JSON.parse(await readFile(path.join(dir, 'trace_payloads', `${vb.payload_ref}.json`), 'utf8'));
  assert.equal(stored.length, 1);
  assert.equal(stored[0].content[0].text.length, 200);
});

// ---------- T-CE-4 语义（双 discard 配对） ----------

test('EXT-6（原 T-CE-4）：同一 assistant 两条并行 toolCall discard → 顺序逐个消费最新未标注 doc', async (t) => {
  const { logger } = await freshTraceCfg(t);
  const d1 = makeDoc('证券 收盘价\n---- ----\n比亚迪 346.00', 0);
  const d2 = makeDoc('证券 收盘价\n---- ----\n宁德时代 201.50', 1);
  const msgs = [
    trMsg(d1),
    trMsg(d2),
    asstMsg([{ query: 'q', discard_lines: [0] }, { query: 'q', discard_lines: [0] }]),
  ];
  const r = pruneContextView({ messages: msgs }, { sessionManager: { getSessionId: () => 's1' } }, { logger });
  assert.ok(r && r.messages);
  const out1 = extractDocTexts(r.messages[0].content)[0];
  const out2 = extractDocTexts(r.messages[1].content)[0];
  assert.ok(out2._meta._pruned, '最新 doc 被第一条 discard 消费');
  assert.ok(out1._meta._pruned, '其次 doc 被第二条 discard 消费');
  assert.equal(out2._meta._pruned.n_del, 1);
  assert.equal(out1._meta._pruned.n_del, 1);
});

// ---------- extension 入口冒烟 ----------

test('EXT-7：default export 可挂 context handler（factory 形态，mock api）', () => {
  const calls = [];
  const api = {
    on(name, fn) { calls.push([name, fn]); },
  };
  const r = contextPrunerDefault(api);
  assert.ok(r && r.registered === true);
  assert.ok(calls.some(([name]) => name === 'context'), '应挂 context 事件');
});