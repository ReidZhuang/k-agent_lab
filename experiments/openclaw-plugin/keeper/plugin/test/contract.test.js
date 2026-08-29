// U1 contract.js 单元测试 —— node --test
// 案例编号对应  docs/DEVELOPMENT_PLAN.md 第 4 节（T-U1-1..6）+ 补充边界。
import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeRowset, normalizeDiscard, genDocId, ROW_KINDS, DEFAULT_MAX_ROW_CHARS } from '../src/contract.js';

/** 构造一份合法行集样本；overrides 可改任意字段做破坏性测试。 */
function sample(overrides = {}) {
  const base = {
    tool: 'hithink-market-query',
    doc_id: 'doc_0',
    query: '比亚迪 近10日涨跌幅',
    fetched_at: '2026-08-27T10:00:00+08:00',
    sections: [
      {
        id: 's0',
        source: { name: '同花顺 i问财 · 盘面', url: '', check: '核对行情口径' },
        rows: [
          { n: 0, k: 'h', t: '比亚迪(002594) 盘面速览' },
          { n: 1, k: 'v', t: '2026-08-15 收盘 346.00 涨跌 +2.10% 换手 3.2%' },
        ],
      },
    ],
    _meta: { n_rows: 2, hint: '按 n 引用；下次查询时用 discard_lines 报告完全无用的行号' },
  };
  return JSON.parse(JSON.stringify({ ...base, ...overrides }));
}

// ---------- 冒烟 ----------

test('T-U1-1 冒烟：合法完整行集通过校验，字段齐全、n 连续', () => {
  const r = normalizeRowset(sample());
  assert.equal(r.ok, true);
  assert.equal(r.value.doc_id, 'doc_0');
  assert.equal(r.value.sections[0].rows.length, 2);
  assert.deepEqual(r.value.sections[0].rows.map((x) => x.n), [0, 1]);
});

// ---------- 常规 ----------

test('T-U1-2 冒烟：normalizeDiscard 去重/排序/剔除越界行号', () => {
  assert.deepEqual(normalizeDiscard([3, 1, 3, 99], 10), [1, 3]);
  assert.deepEqual(normalizeDiscard([4, 0, 2], 3), [0, 2]); // 4 越界被剔除
});

test('T-U1-3：discard_lines 传 null/undefined/字符串/数字 → 一律视为不删', () => {
  assert.deepEqual(normalizeDiscard(null, 5), []);
  assert.deepEqual(normalizeDiscard(undefined, 5), []);
  assert.deepEqual(normalizeDiscard('1,2', 5), []);
  assert.deepEqual(normalizeDiscard(42, 5), []);
  assert.deepEqual(normalizeDiscard([1.5, -1, '3', NaN], 5), []); // 非法成员忽略
});

test('T-U1-4：缺 sections 或 sections 为空 → 校验失败并给出可读错误', () => {
  const noSections = sample({ sections: undefined }); // 留空则继承原值，需显式删除
  delete noSections.sections;
  const r1 = normalizeRowset(noSections);
  assert.equal(r1.ok, false);
  assert.ok(r1.errors.some((e) => e.includes('sections')));

  const r2 = normalizeRowset(sample({ sections: [] }));
  assert.equal(r2.ok, false);
  assert.ok(r2.errors.some((e) => e.includes('sections must not be empty')));
});

test('T-U1-5：行号不连续（跳号）→ 校验失败', () => {
  const doc = sample();
  doc.sections[0].rows = [
    { n: 0, k: 'h', t: 'a' },
    { n: 2, k: 'v', t: 'b' },
  ];
  doc._meta.n_rows = 2;
  const r = normalizeRowset(doc);
  assert.equal(r.ok, false);
  assert.ok(r.errors.some((e) => e.includes('contiguous from 0')), JSON.stringify(r.errors));
});

test('T-U1-6：行类型 k 非法 → 校验失败', () => {
  const doc = sample();
  doc.sections[0].rows[1].k = 'z';
  const r = normalizeRowset(doc);
  assert.equal(r.ok, false);
  assert.ok(r.errors.some((e) => e.includes('.k must be one of')));
});

// ---------- 补充边界（常规/半极端） ----------

test('T-U1-7：行号重复（[0,0]）→ 校验失败', () => {
  const doc = sample();
  doc.sections[0].rows = [
    { n: 0, k: 'h', t: 'a' },
    { n: 0, k: 'v', t: 'b' },
  ];
  doc._meta.n_rows = 2;
  assert.equal(normalizeRowset(doc).ok, false);
});

test('T-U1-8：行号为负 / 非整数 → 校验失败', () => {
  const a = sample();
  a.sections[0].rows[1].n = -1;
  assert.equal(normalizeRowset(a).ok, false);
  const b = sample();
  b.sections[0].rows[1].n = 1.5;
  assert.equal(normalizeRowset(b).ok, false);
});

test('T-U1-9：rows 为空数组 / t 为空 → 校验失败', () => {
  const a = sample();
  a.sections[0].rows = [];
  assert.equal(normalizeRowset(a).ok, false);
  const b = sample();
  b.sections[0].rows[1].t = '';
  assert.equal(normalizeRowset(b).ok, false);
});

test('T-U1-10：_meta.n_rows 与实际行数不符 → 校验失败', () => {
  const doc = sample();
  doc._meta.n_rows = 99;
  const r = normalizeRowset(doc);
  assert.equal(r.ok, false);
  assert.ok(r.errors.some((e) => e.includes('mismatch actual row count')));
});

test('T-U1-11：doc_id 格式非法 → 校验失败；genDocId 生成稳定 id', () => {
  const doc = sample({ doc_id: 'foo' });
  assert.equal(normalizeRowset(doc).ok, false);
  assert.equal(genDocId(0), 'doc_0');
  assert.equal(genDocId(9), 'doc_9');
});

test('T-U1-12：非对象根（字符串/数组/null）→ 校验失败', () => {
  assert.equal(normalizeRowset('x').ok, false);
  assert.equal(normalizeRowset([]).ok, false);
  assert.equal(normalizeRowset(null).ok, false);
});

test('T-U1-13：常量约定（ROW_KINDS 冻结、默认 maxRowChars=400）', () => {
  assert.deepEqual([...ROW_KINDS], ['h', 'v', 't', 'u']);
  assert.throws(() => { 'use strict'; ROW_KINDS.push('x'); }, TypeError);
  assert.equal(DEFAULT_MAX_ROW_CHARS, 400);
});