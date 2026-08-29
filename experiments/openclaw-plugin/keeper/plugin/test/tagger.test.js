// U2 tagger.js 单元测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U2-1..6）+ 补充边界（T-U2-7..10）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { tag, classifyRow, isTableLike, isSeparatorLine, truncate, jsonRows } from '../src/tagger.js';
import { normalizeRowset } from '../src/contract.js';

const SRC = { name: '同花顺 i问财 · 盘面', url: '', check: '核对行情口径' };

// ---------- 冒烟 ----------

test('T-U2-1 冒烟：典型表格 → 每数据行一行、n 连续、k 合理、过 U1 校验', () => {
  const r = tag({
    tool: 'hithink-market-query',
    query: '比亚迪 近10日涨跌幅',
    fetched_at: '2026-08-27T10:00:00+08:00',
    blocks: [{
      source: SRC,
      text: '证券简称 收盘价 涨跌幅\n------- -------- ------\n比亚迪 346.00 +2.10%\n宁德时代 245.10 +0.85%',
    }],
  });
  assert.equal(r.ok, true);
  const doc = r.value;
  assert.deepEqual(doc.sections[0].rows.map((x) => x.n), [0, 1, 2]);
  assert.equal(doc.sections[0].rows[0].k, 'h');          // 表头（分隔线上方）
  assert.equal(doc.sections[0].rows[1].k, 'v');          // 数据行含数字
  assert.equal(doc._meta.n_rows, 3);
  assert.equal(normalizeRowset(doc).ok, true);            // 产出即合法行集
});

// ---------- 常规 ----------

test('T-U2-2：长散文 → 按段/完整句切，无任何半句行', () => {
  const r = tag({
    tool: 'x',
    blocks: [{
      source: SRC,
      text: '公司近期发布2026年中报，营收同比+12%。整体经营稳健。\n\n风险提示：以上信息仅供参考。',
    }],
  });
  assert.equal(r.ok, true);
  const rows = r.value.sections[0].rows;
  assert.ok(rows.length >= 2);
  for (const row of rows) {
    assert.ok(/[。！？！？；;…]$/.test(row.t) || row.t.length < 400,
      `半句行不允许: ${JSON.stringify(row.t)}`);
  }
  const kinds = rows.map((x) => x.k);
  assert.ok(kinds.includes('u'), '风险提示行应标 u');
  assert.ok(kinds.includes('v'), '含数字句应标 v');
});

test('T-U2-3：空文本/全空行 → 不产 doc（value=null），不报错', () => {
  const r = tag({ tool: 'x', blocks: [{ source: SRC, text: '   \n\n  ' }] });
  assert.equal(r.ok, true);
  assert.equal(r.value, null);
});

test('T-U2-4：多个文本块（表格+备注）→ 各成 section，行号跨 section 连续', () => {
  const r = tag({
    tool: 'x',
    blocks: [
      { source: SRC, text: '证券 收盘价\n---- ----\n比亚迪 346' },
      { source: { name: '备注', check: '' }, text: '备注：以上数据截至当日收盘。' },
    ],
  });
  assert.equal(r.ok, true);
  const doc = r.value;
  assert.equal(doc.sections.length, 2);
  const all = doc.sections.flatMap((s) => s.rows.map((x) => x.n));
  assert.deepEqual(all, all.map((_, i) => i), '跨 section 行号必须连续 0..N-1');
});

test('T-U2-5：超长单行(>maxRowChars) → 截断策略生效（尾部截断+省略号）', () => {
  const long = 'A'.repeat(600);
  const r = tag({ tool: 'x', blocks: [{ source: SRC, text: long }] }, { maxRowChars: 100 });
  assert.equal(r.ok, true);
  const row = r.value.sections[0].rows[0];
  assert.ok(row.t.length <= 100);
  assert.equal(row.t.slice(-1), '…');
  assert.equal(truncate('短', 100), '短');
});

test('T-U2-6：免责/仅供参考/版权信号词行 → k=u', () => {
  assert.equal(classifyRow('以上内容仅供参考，不构成投资建议。'), 'u');
  assert.equal(classifyRow('风险提示：投资有风险。'), 'u');
  assert.equal(classifyRow('本报告版权归某某所有。'), 'u');
});

// ---------- 补充边界 ----------

test('T-U2-7：散文中途换行(无空行) → 残句与后句合并为完整句，不切半句', () => {
  const r = tag({
    tool: 'x',
    blocks: [{ source: SRC, text: '比亚迪发布了业绩预告，\n净利润同比增长12%。' }],
  });
  assert.equal(r.ok, true);
  const rows = r.value.sections[0].rows;
  assert.equal(rows.length, 1, '残句必须与后句合并为一行');
  assert.ok(rows[0].t.includes('净利润同比增长12%'));
  assert.ok(rows[0].t.endsWith('。'));
});

test('T-U2-8：分隔线不产出行，仅升级表头', () => {
  const t = '名称 值\n---- --\n干 50\n';
  const raw = tag({ tool: 'x', blocks: [{ source: SRC, text: t }] });
  assert.equal(raw.ok, true);
  const rows = raw.value.sections[0].rows;
  assert.equal(rows.length, 2, '分隔线不应产出行');
});

test('T-U2-9：u 优先级高于含数字（免责行带年份仍是 u）', () => {
  assert.equal(classifyRow('2026年半年度报告，仅供参考，不构成投资建议。'), 'u');
});

test('T-U2-10：同段落多完句 → 每句一行、n 连续、k 合理', () => {
  const r = tag({
    tool: 'x',
    blocks: [{ source: SRC, text: '今日沪指收涨。成交额1.2万亿。北向资金净流入。' }],
  });
  assert.equal(r.ok, true);
  const rows = r.value.sections[0].rows;
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((x) => x.n), [0, 1, 2]);
  assert.deepEqual(rows.map((x) => x.k), ['t', 'v', 't']); // 净流入句无数字 → t
});

test('T-U2-11：blocks 缺失/空/文本为空 → ok=false 或 value=null（不崩）', () => {
  assert.equal(tag({ tool: 'x', blocks: [] }).ok, false);
  assert.equal(tag({ tool: 'x' }).ok, false);
  const r = tag({ tool: 'x', blocks: [{ source: SRC, text: '' }] });
  assert.equal(r.ok, true);               // 空文本=无信息 → value=null 而非报错
  assert.equal(r.value, null);
});

test('T-U2-13（真实形态校准）：## 标题 + key:value 管道记录 + 列表项 → 每行一个语义单元', () => {
  const kvLine = '收盘价: 161.61 | 涨跌幅: 10.0% | 开盘: 155.55 | 最高: 161.61 | 最低: 155.55 | 昨收: 146.92 | 成交额: 9.1亿元 | 换手率: 1.79% | 量比: 0.67 | 振幅: 4.12% | 外盘/内盘: 21587/35313 | 动态PE: 47.9 | PB: 3.33 | 总市值: 583.06亿 | 流通市值: 512.37亿 | 涨停价: 161.61 | 跌停价: 132.23';
  const r = tag({
    tool: 'hithink-market-query',
    blocks: [{
      source: SRC,
      text: `## 【今日收盘 凯莱英 (002821.SZ)情况】(快照时间: 2026-08-04 18:08:51)\n${kvLine}\n形态: 收于全天高位附近(强势收盘)\n- 市场热度: 52（高）\n- 成交额: 2.38万亿（+4259亿）\n- 上涨占比: 69.00% | 赚钱效应: 86%`,
    }],
  });
  assert.equal(r.ok, true);
  const rows = r.value.sections[0].rows;
  assert.equal(rows.length, 6, `应产出 6 行（标题/记录/形态/3 列表项），实际 ${rows.length}`);
  assert.equal(rows[0].k, 'h');                                        // ## 标题 → h
  assert.ok(rows[0].t.startsWith('【今日收盘 凯莱英'), '标题应去掉 ## 前缀');
  assert.equal(rows[1].k, 'v');                                        // kv 记录行含数字 → v
  assert.equal(rows[1].t, kvLine);                                     // 记录保持整行不拆
  assert.ok(rows[1].t.length < 400, 'DEFAULT_MAX_ROW_CHARS 应容纳整条记录');
  assert.equal(rows[3].k, 'v');
  assert.ok(!/^-\s/.test(rows[5].t), '列表项应去掉 - 标记');
  assert.equal(normalizeRowset(r.value).ok, true);
});

test('T-U2-12：isTableLike/isSeparatorLine 判定正确', () => {
  assert.equal(isTableLike('a\n----\nb'), true);
  assert.equal(isTableLike('a\t1\nb\t2'), true);
  assert.equal(isTableLike('a｜1\nb｜2'), true);
  assert.equal(isTableLike('这是散文。第一句。第二句。'), false);
  assert.equal(isSeparatorLine('-----'), true);
  assert.equal(isSeparatorLine('|----|'), true);
  assert.equal(isSeparatorLine('普通行'), false);
});

test('T-U2-13（v2.4.1）：exec JSON 信封解包 → datas 数组每个元素一行（语义原子, 保结构）', () => {
  const envelope = JSON.stringify({
    success: true,
    query: '航天宏图 688017 近10个交易日 涨跌幅 换手率 成交额 收盘价',
    code_count: 2, returned_count: 2, page: '1', limit: '10', has_more: false,
    chunks_info: '["航天宏图,688017,近10个交易日,涨跌幅 (2)"]',
    datas: [
      { 股票代码: '688017.SH', 股票简称: '绿的谐波', 最新价: '292.0', 最新涨跌幅: -2.439 },
      { 股票代码: '300750.SZ', 股票简称: '宁德时代', 最新价: '250.1', 最新涨跌幅: 0.85 },
    ],
  });
  const rows = jsonRows(envelope, 400);
  assert.equal(rows.length, 2, 'datas 两个元素 → 两行');
  assert.match(rows[0].t, /688017/, '行0 保留元素内容（股票代码在内）');
  assert.match(rows[1].t, /宁德时代/, '行1 保留元素内容');
  assert.equal(rows[0].k, 'v', '含数字 → value 行');
  // tag() 入口：整份信封 → rows = 2, n_rows=2（不再单行 400 截断）
  const r = tag({ tool: 'exec', blocks: [{ source: { name: 'exec', check: 'keeper-tagged' }, text: envelope }] }, { seq: 0 });
  assert.equal(r.ok, true);
  assert.equal(r.value._meta.n_rows, 2, 'doc 行数 = 数组元素数');
  assert.equal(r.value.sections[0].rows.length, 2);
  assert.ok(r.value.sections[0].rows.every((row) => row.t.length > 40), '元素整体保留, 未被 400 截断');
});

test('T-U2-14（v2.4.1）：非 JSON / JSON 无数组字段 → jsonRows 返回 null, 走原 prose 逻辑', () => {
  assert.equal(jsonRows('这是普通散文。没有 JSON。', 400), null);
  assert.equal(jsonRows('{\n  "success": true,\n  "query": "x"\n}', 400), null, '无数据数组 → null');
  // tag() 对纯 JSON 对象（无数组字段）→ 退化单行（原行为不变）
  const r = tag({ tool: 'exec', blocks: [{ source: { name: 'x', check: 'y' }, text: '{"success": true, "query": "x"}' }] }, { seq: 0 });
  assert.equal(r.ok, true);
  assert.equal(r.value._meta.n_rows, 1);
});