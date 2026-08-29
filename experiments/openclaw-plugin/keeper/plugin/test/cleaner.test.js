// U3 cleaner.js 单元测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U3-1..4）+ 补充边界。
import test from 'node:test';
import assert from 'node:assert/strict';
import { stripAuxParams, DEFAULT_AUX_KEYS } from '../src/cleaner.js';

// ---------- 冒烟 ----------

test('T-U3-1 冒烟：参数含 discard_lines → rest 无该字段、aux 保留其值', () => {
  const params = { query: '比亚迪', days: 10, discard_lines: [0, 2] };
  const { rest, aux } = stripAuxParams(params);
  assert.equal('discard_lines' in rest, false);
  assert.deepEqual(rest, { query: '比亚迪', days: 10 });
  assert.deepEqual(aux, { discard_lines: [0, 2] });
});

// ---------- 常规 ----------

test('T-U3-2：参数不含 discard_lines → rest 原样、aux 为空', () => {
  const params = { query: '宁德时代' };
  const { rest, aux } = stripAuxParams(params);
  assert.deepEqual(rest, { query: '宁德时代' });
  assert.deepEqual(aux, {});
});

test('T-U3-3：discard_lines 为 null → 照常剥离（值进 aux）', () => {
  const { rest, aux } = stripAuxParams({ q: 'x', discard_lines: null });
  assert.deepEqual(rest, { q: 'x' });
  assert.deepEqual(aux, { discard_lines: null });
});

test('T-U3-4：嵌套其他参数不受影响；原对象不被改动', () => {
  const params = { query: 'A', filter: { market: 'sz' }, discard_lines: [1] };
  const before = JSON.stringify(params);
  stripAuxParams(params);
  assert.equal(JSON.stringify(params), before, '原对象必须原样');
  const { rest } = stripAuxParams(params);
  assert.deepEqual(rest.filter, { market: 'sz' });
});

// ---------- 补充边界 ----------

test('T-U3-5：非对象参数（null/undefined/数组/字符串）→ 防御性原样返回', () => {
  assert.deepEqual(stripAuxParams(null), { rest: null, aux: {} });
  assert.deepEqual(stripAuxParams(undefined), { rest: undefined, aux: {} });
  assert.deepEqual(stripAuxParams([1, 2]), { rest: [1, 2], aux: {} });
  assert.deepEqual(stripAuxParams('x'), { rest: 'x', aux: {} });
});

test('T-U3-6：auxKeys 可配置；DEFAULT_AUX_KEYS 常量冻结', () => {
  const params = { q: 'x', doc_id: 'doc_0', discard_lines: [0] };
  const { rest, aux } = stripAuxParams(params, { auxKeys: ['doc_id'] });
  assert.equal('doc_id' in rest, false);
  assert.deepEqual(aux, { doc_id: 'doc_0' });
  assert.equal('discard_lines' in rest, true, '未配置的字段不应被剥离');
  assert.deepEqual([...DEFAULT_AUX_KEYS], ['discard_lines']);
  assert.throws(() => { 'use strict'; DEFAULT_AUX_KEYS.push('x'); }, TypeError);
});