// U5 tokenizer.js + counter.js 单元测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U5-1..6）+ 补充边界。
import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateTokens, correctionFactor, applyCorrection, messagesTokens } from '../src/tokenizer.js';
import { createTokenCounter, estimateInputTokens } from '../src/counter.js';

// ---------- 冒烟 ----------

test('T-U5-1 冒烟：非空文本估算>0；空文本/非字符串=0', () => {
  assert.ok(estimateTokens('比亚迪今日收涨10.0%') > 0);
  assert.equal(estimateTokens(''), 0);
  assert.equal(estimateTokens(null), 0);
  assert.equal(estimateTokens(undefined), 0);
});

// ---------- 常规 ----------

test('T-U5-2：同一文本重复计数稳定（确定性）', () => {
  const t = '公司近期发布2026年中报，营收同比增长12%，净利润+8.5%。';
  assert.equal(estimateTokens(t), estimateTokens(t));
  assert.equal(estimateTokens(t), estimateTokens(t));
});

test('T-U5-3：中文估算量级正确；usage 校正系数联动', () => {
  const est = estimateTokens('凯莱英收盘价161.61元，涨幅10.0%，总市值583亿');
  assert.ok(est > 10 && est < 200, `量级应合理，实际 ${est}`);
  // 实测 200 vs 估算 100 → 系数 2，后续估算放大
  const { factor } = correctionFactor(200, 100);
  assert.equal(factor, 2);
  assert.equal(applyCorrection(50, factor), 100);
  // 估算 0 而实测 >0 → punitive 标记，系数回落 1（防除零）
  assert.equal(correctionFactor(10, 0).punitive, true);
  assert.equal(correctionFactor(10, 0).factor, 1);
});

test('T-U5-4：estimate(压缩前) − estimate(压缩后) = 节省量，方向正确', () => {
  const before = ['甲：今天上涨1%。（数据块）', '提示：本条完全无用免责声明，删除。'];
  const after = ['甲：今天上涨1%。'];
  const saved = estimateTokens(before.join('')) - estimateTokens(after.join(''));
  assert.ok(saved > 0, '删除后估算必须减少');
});

test('T-U5-5：usage 缺失 → 记录走估算回退且标记 usage_unavailable', () => {
  const c = createTokenCounter();
  c.recordRound({ input: 100, output: 50, usage: null });
  const s = c.stats();
  assert.equal(s.usage_unavailable, true);
  assert.equal(s.input_total, 100);
  assert.equal(s.output_total, 50);
});

test('T-U5-6：累计器多轮：累加/均值/环比/usage 回填正确', () => {
  const c = createTokenCounter();
  c.recordRound({ input: 100, output: 30, usage: { prompt_tokens: 98, completion_tokens: 32 } });
  c.recordRound({ input: 200, output: 60, usage: null });                 // 缺 usage → 走高估回退
  c.recordRound({ input: 300, output: 90, usage: null });
  const s = c.stats();
  assert.equal(s.rounds, 3);
  assert.equal(s.input_total, 598, '第一轮应取实测 98，后两轮取估算');
  assert.equal(s.output_total, 182);
  assert.equal(s.total, 780);
  assert.equal(s.input_avg, 199);
  assert.equal(s.input_delta, 100, '环比 = 最新轮 - 上一轮');
  assert.equal(s.usage_rounds, 1);
  assert.equal(s.usage_unavailable, false, '存在 usage 轮则标记可用');
});

// ---------- 补充边界 ----------

test('T-U5-7：messagesTokens/estimateInputTokens 汇编估算', () => {
  const msgs = [{ role: 'user', content: '你好世界' }, { role: 'assistant', content: '上涨10%' }];
  assert.equal(messagesTokens(msgs), estimateInputTokens(msgs));
  assert.ok(messagesTokens(msgs) > 0);
  assert.equal(messagesTokens(null), 0);
  assert.equal(messagesTokens([]), 0);
});

test('T-U5-8：recordSaving 节省量不出现负数', () => {
  const c = createTokenCounter();
  assert.deepEqual(c.recordSaving({ before: 500, after: 300 }), { saved: 200, before: 500, after: 300 });
  assert.equal(c.recordSaving({ before: 10, after: 40 }).saved, 0, '压缩反而变大 → 记 0 并交事件层报警');
});

test('T-U5-9：stats 无轮次 → 安全返回', () => {
  const s = createTokenCounter().stats();
  assert.equal(s.rounds, 0);
});