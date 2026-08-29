// U4 compressor.js 单元测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U4-1..9）+ 补充边界（T-U4-10..11）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { applyCompression, pruneDoc } from '../src/compressor.js';

/** 构造一行集消息序列里的 doc（两行） */
function doc(id, rows = 2) {
  const arr = [];
  for (let n = 0; n < rows; n++) arr.push({ n, k: rows > 1 && n === 0 ? 'h' : 'v', t: `行${n}` });
  return {
    tool: 't', doc_id: id, query: 'q', fetched_at: '',
    sections: [{ id: 's0', source: { name: 'src', url: '', check: '' }, rows: arr }],
    _meta: { n_rows: rows, hint: 'h' },
  };
}

const tool = (d) => ({ role: 'tool', doc: d });
const assistant = (lines, doc_id) => ({ role: 'assistant', discard: { ...(doc_id !== undefined ? { doc_id } : {}), lines } });

// ---------- 冒烟 ----------

test('T-U4-1 冒烟：单 doc + assistant(discard) → 删行、_pruned、原输入不动、返回事件', () => {
  const d0 = doc('doc_0');
  const input = [tool(d0), assistant([0])];
  const before = JSON.stringify(input);
  const { messages, events } = applyCompression(input);
  assert.equal(JSON.stringify(input), before, '输入消息数组不可被改动');
  const pruned = messages[0].doc;
  assert.equal(pruned._meta._pruned.n_del, 1);
  assert.equal(pruned.sections[0].rows.length, 1);
  assert.deepEqual(pruned.sections[0].rows.map((x) => x.n), [1], 'n 不变号');
  assert.equal(events[0].type, 'discard_applied');
  assert.equal(events.length, 1);
});

// ---------- 常规 ----------

test('T-U4-2：无 discard → 视图与输入一致、无事件', () => {
  const input = [tool(doc('doc_0')), { role: 'assistant', text: '看看' }];
  const { messages, events } = applyCompression(input);
  assert.deepEqual(JSON.parse(JSON.stringify(messages)), JSON.parse(JSON.stringify(input)));
  assert.equal(events.length, 0);
});

test('T-U4-3：旧 doc + 新 doc，discard 指向最新 → 只删最新那份，旧 doc 不动', () => {
  const d0 = doc('doc_0');
  const d1 = doc('doc_1');
  const { messages, events } = applyCompression([tool(d0), tool(d1), assistant([0])]);
  const oldDoc = messages[0].doc;
  const newDoc = messages[1].doc;
  assert.equal(oldDoc._meta._pruned, undefined, '旧 doc 不能被动');
  assert.equal(newDoc._meta._pruned.n_del, 1);
  assert.equal(events[0].type, 'discard_applied');
  assert.equal(events[0].doc_id, 'doc_1');
});

test('T-U4-4：连续三轮 doc0→dl1→doc1→dl2 → 两两独立消费', () => {
  const d0 = doc('doc_0', 3);
  const d1 = doc('doc_1', 4);
  const { messages, events } = applyCompression([tool(d0), assistant([0]), tool(d1), assistant([0, 2])]);
  assert.equal(events.length, 2, '两轮删除各成事件');
  assert.equal(events[0].doc_id, 'doc_0');
  assert.equal(events[0].n_del, 1);
  assert.equal(events[1].doc_id, 'doc_1');
  assert.equal(events[1].n_del, 2);
  assert.deepEqual(messages[0].doc.sections[0].rows.map((x) => x.n), [1, 2]);
  assert.deepEqual(messages[2].doc.sections[0].rows.map((x) => x.n), [1, 3]);
});

test('T-U4-5：discard 含不存在行号 → 忽略，只删存在的；n_left 按实际', () => {
  const d0 = doc('doc_0', 2);
  const { messages } = applyCompression([tool(d0), assistant([0, 99, -1])]);
  const m = messages[0].doc._meta._pruned;
  assert.equal(m.n_del, 1);
  assert.equal(m.n_left, 1);
});

test('T-U4-6：isError 工具结果夹在中间 → 不进入候选', () => {
  const d0 = doc('doc_0');
  const bad = { ...doc('doc_bad'), _meta: undefined };
  const { messages, events } = applyCompression([tool(d0), { role: 'tool', isError: true, doc: bad }, assistant([0])]);
  assert.equal(events[0].type, 'tool_result_error');
  assert.equal(events[1].type, 'discard_applied');
  assert.equal(events[1].doc_id, 'doc_0', '错误结果不被消费，discard 落到最近的正常 doc');
  assert.equal(messages[0].doc._meta._pruned.n_del, 1);
});

test('T-U4-7：幂等 —— 同一原始输入重复压缩输出一致；压缩结果是固定点(再压不变)', () => {
  const input = [tool(doc('doc_0', 3)), assistant([1]), tool(doc('doc_1', 2)), assistant([0])];
  const r1 = applyCompression(input);
  const r2 = applyCompression(input);                       // 同输入重新压缩
  assert.deepEqual(JSON.parse(JSON.stringify(r2.messages)), JSON.parse(JSON.stringify(r1.messages)));
  assert.deepEqual(JSON.parse(JSON.stringify(r2.events)), JSON.parse(JSON.stringify(r1.events)));
  const r3 = applyCompression(r1.messages);                 // 对压缩结果再压 = 固定点
  assert.deepEqual(JSON.parse(JSON.stringify(r3.messages)), JSON.parse(JSON.stringify(r1.messages)),
    '压缩视图再压缩必须保持不变');
});

test('T-U4-8：删行后剩余行号不变号', () => {
  const d0 = doc('doc_0', 5);
  const { doc: pruned } = pruneDoc(d0, [0, 4]);
  assert.deepEqual(pruned.sections[0].rows.map((x) => x.n), [1, 2, 3]);
  assert.equal(pruned._meta.n_rows, 3);
});

test('T-U4-9：已带 _pruned 的 doc（上轮产物）→ 不再被新 discard 消费', () => {
  const d0 = doc('doc_0');
  const d0b = { ...d0, _meta: { ...d0._meta, _pruned: { n_del: 1, n_left: 1, discarded: [0] } } };
  const { messages, events } = applyCompression([tool(d0b), assistant([1])]);
  assert.deepEqual(messages[0].doc._meta._pruned, d0b._meta._pruned, '已标记 doc 不应再被改');
  assert.equal(events[0].type, 'doc_already_pruned');
  assert.equal(events[1].type, 'compress_skip');
  assert.equal(events[1].reason, 'no_unconsumed_doc');
});

// ---------- 补充边界 ----------

test('T-U4-10（v2.4.2）：discard 显式指定非最新未消费 doc_id → 精确命中该 doc（resume 多 doc 窗口）', () => {
  const d0 = doc('doc_0');
  const d1 = doc('doc_1');
  const { messages, events } = applyCompression([tool(d0), tool(d1), assistant([0], 'doc_0')]);
  assert.equal(events[0].type, 'discard_applied');
  assert.equal(events[0].doc_id, 'doc_0', '按显式 doc_id 命中旧 doc');
  assert.ok(messages[0].doc._meta._pruned, '旧 doc 被删行');
  assert.equal(messages[1].doc._meta._pruned, undefined, '其他 doc 不动');
});

test('T-U4-13（v2.4.2）：显式 doc_id 指向已消费/不存在 → 拒绝；未指定 doc_id 仍走最新', () => {
  const d0 = doc('doc_0');
  const d1 = doc('doc_1');
  const r1 = applyCompression([tool(d0), tool(d1), assistant([0], 'doc_0'), assistant([0], 'doc_0')]);
  // 第一条显式 doc_0 消费最新也已消费?——顺序：doc_0 先被消费 → 第二条 doc_0 已不在 pending → 拒绝
  assert.equal(r1.events.filter((e) => e.type === 'discard_applied').length, 1, '同 doc_id 只消费一次');
  assert.equal(r1.events[1].type, 'compress_skip');
  assert.equal(r1.events[1].reason, 'doc_id_mismatch');
  // 未指定 doc_id（undefined）→ 退回最新未消费 doc
  const r2 = applyCompression([tool(d0), tool(d1), assistant([0], undefined)]);
  assert.equal(r2.events[0].doc_id, 'doc_1', '未指定时消费最新 doc_1');
});

test('T-U4-11：discard 空数组/非消息输入 → 防御性处理', () => {
  assert.deepEqual(applyCompression([]).messages, []);
  assert.deepEqual(applyCompression(null).messages, []);
  const r = applyCompression([tool(doc('doc_0')), assistant([])]);
  assert.equal(r.events[0].type, 'discard_empty');
  assert.equal(r.messages[0].doc._meta._pruned, undefined);
});

test('T-U4-12（§9.4）：并行展开的连续两条 discard → 逐个消费"最新未标注 doc"', () => {
  const d0 = doc('doc_0');
  const d1 = doc('doc_1');
  // 两条 discard 在同一 assistant（U7 展开为两条独立归一化条），顺序配对：
  // discard1 → 最新 doc_1；discard2 → 其次 doc_0
  const r = applyCompression([tool(d0), tool(d1), assistant([0]), assistant([1])]);
  assert.equal(r.events.filter((e) => e.type === 'discard_applied').length, 2);
  assert.equal(r.messages[1].doc._meta._pruned.n_del, 1, 'discard1 消费最新 doc');
  assert.equal(r.messages[0].doc._meta._pruned.n_del, 1, 'discard2 消费其次 doc');

  // 只有一份 doc + 两条 discard → 第二条无 doc 可消费 → skip
  const r2 = applyCompression([tool(d0), assistant([0]), assistant([0])]);
  assert.equal(r2.messages[0].doc._meta._pruned.n_del, 1);
  assert.equal(r2.events[1].type, 'compress_skip');
  assert.equal(r2.events[1].reason, 'no_unconsumed_doc');
});