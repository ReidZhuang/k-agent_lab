// U7 assembly.js 单元/装配测试 + Cluster E 伪 loop —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U7-1..5）+ Cluster E（T-CE-1..）。
// 不 import openclaw：用 mock api（createKeeper 的 on() 均可注入）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createKeeper, compressView, extractDiscards, extractDocTexts, encodeDoc, KEEPER_PREFIX } from '../src/assembly.js';
import { tag } from '../src/tagger.js';

function mockApi(pluginConfig = {}) {
  const handlers = {};
  return {
    pluginConfig,
    on(name, fn) { (handlers[name] ??= []).push(fn); },
    handlers,
    async fire(name, event, ctx = {}) {
      let last;
      for (const fn of handlers[name] ?? []) last = await fn(event, { runId: 'r', ...ctx });
      return last;
    },
  };
}

async function freshTraceCfg(t) {
  const dir = await mkdtemp(path.join(tmpdir(), 'keeper-u7-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return { traceDir: dir, trace: true };
}

const SRC = { name: '同花顺 i问财 · 盘面', check: 'keeper-tagged' };
function makeDoc(text, seq = 0) {
  return tag({ tool: 'hithink-market-query', blocks: [{ source: SRC, text }] }, { seq }).value;
}

// ---------- 冒烟 ----------

test('T-U7-1：enabled=false → 不注册，createKeeper 返回 registered:false', async () => {
  const api = mockApi({ enabled: false });
  const k = await createKeeper(api);
  assert.equal(k.registered, false);
  assert.equal(Object.keys(api.handlers).length, 0);
});

test('T-U7-2：enabled=true → typed hooks 全部注册（context 已迁往 extension，见 context-pruner.test.js）', async () => {
  const api = mockApi({ enabled: true, trace: false });
  const k = await createKeeper(api);
  assert.equal(k.registered, true);
  for (const name of ['tool_result_persist', 'before_tool_call', 'llm_input', 'llm_output', 'agent_end']) {
    assert.ok(Array.isArray(api.handlers[name]), `缺钩子 ${name}`);
  }
  assert.ok(!Array.isArray(api.handlers['context']), '插件侧不应再注册 context（extension 负责，注册即被忽略）');
});

// ---------- 常规 ----------

test('T-U7-3：tagTools 命中/不命中（命中→改写为 __keeper1__ 行集；不命中→原样）', async () => {
  const api = mockApi({ enabled: true, trace: false, tagTools: ['hithink-market-query'] });
  await createKeeper(api);
  const raw = '证券 收盘价\n---- ----\n比亚迪 346.00';
  const hit = await api.fire('tool_result_persist', {
    toolName: 'hithink-market-query',
    message: { role: 'toolResult', content: [{ type: 'text', text: raw }] },
  });
  assert.ok(hit.message.content[0].text.startsWith(KEEPER_PREFIX), '命中的工具结果应被改写为行集');
  const doc = JSON.parse(hit.message.content[0].text.slice(KEEPER_PREFIX.length));
  assert.equal(doc.tool, 'hithink-market-query');
  assert.equal(doc._meta.n_rows, 2);

  const miss = await api.fire('tool_result_persist', {
    toolName: 'web_search',
    message: { role: 'toolResult', content: [{ type: 'text', text: raw }] },
  });
  assert.equal(miss, undefined, '未命中工具应保持原样（不返回改写）');
});

test('T-U7-4：某钩子抛错 → 不崩、其它钩子照常（失败隔离）', async () => {
  const api = mockApi({ enabled: true, trace: false });
  await createKeeper(api);
  const evil = {};
  Object.defineProperty(evil, 'params', { get() { throw new Error('boom'); } });
  let res;
  try { res = await api.fire('before_tool_call', evil); } catch (e) { assert.fail(`不应上抛: ${e.message}`); }
  assert.equal(res, undefined);
  // 其它钩子仍可用
  const k2 = await api.fire('llm_output', { usage: { prompt_tokens: 10, completion_tokens: 5 } });
  assert.equal(k2, undefined);
});

test('T-U7-5：traceDir 配置生效 → trace.jsonl 写到指定目录', async (t) => {
  const td = await freshTraceCfg(t);
  const api = mockApi({ enabled: true, ...td });
  await createKeeper(api);
  await api.fire('llm_output', { sessionId: 's1', usage: { prompt_tokens: 10, completion_tokens: 5 } });
  await api.fire('agent_end', { sessionId: 's1' });
  const raw = await readFile(path.join(td.traceDir, 'trace.jsonl'), 'utf8');
  const evs = raw.trim().split('\n').map(JSON.parse);
  assert.ok(evs.some((e) => e.type === 'token_round'));
  assert.ok(evs.some((e) => e.type === 'run_finalized'));
  const stats = JSON.parse(await readFile(path.join(td.traceDir, 'run_stats.json'), 'utf8'));
  assert.ok(stats.events_total >= 2);
});

// ---------- Cluster E 伪 loop（T-CE-1） ----------

test('T-CE-1：伪 loop 全链路 —— persist打标 → 剥离 → token → 汇总（压缩环节在 extension 侧，见 context-pruner.test.js EXT-3..6）', async (t) => {
  const td = await freshTraceCfg(t);
  const api = mockApi({ enabled: true, ...td });
  await createKeeper(api);

  // 1) persist：hithink 结果 → 行集（5 行：h + v + v + u 免责 + u 版权）
  const rawText0 = '## 比亚迪盘面\n收盘价: 346.00 | 涨跌幅: +2.1% | 换手率: 3.2%\n收盘价: 345.20 | 涨跌幅: -0.2% | 换手率: 2.7%\n仅供参考，不构成投资建议。\n版权声明：本页信息归同花顺所有。';
  const p0 = await api.fire('tool_result_persist', {
    sessionId: 's1', toolName: 'hithink-market-query',
    message: { role: 'toolResult', toolName: 'hithink-market-query', content: [{ type: 'text', text: rawText0 }] },
  });
  assert.ok(p0);
  const doc0 = extractDocTexts(p0.message.content)[0];
  assert.equal(doc0._meta.n_rows, 5, '行集应含 5 行');

  // 2) before_tool_call：剥离 discard_lines（压缩环节已迁往 extension，见 context-pruner.test.js）
  const stripped = await api.fire('before_tool_call', {
    sessionId: 's1', toolName: 'hithink-market-query', toolCallId: 'c1',
    params: { query: '比亚迪', days: 10, discard_lines: [0, 3, 4] },
  });
  assert.equal('discard_lines' in stripped.params, false);
  assert.deepEqual(stripped.params, { query: '比亚迪', days: 10 });

  // 3) llm_output → token_round 记录
  await api.fire('llm_output', { sessionId: 's1', usage: { prompt_tokens: 1555, completion_tokens: 333 } });

  // 4) agent_end → run_finalized + run_stats
  await api.fire('agent_end', { sessionId: 's1' });
  const raw = await readFile(path.join(td.traceDir, 'trace.jsonl'), 'utf8');
  const evs = raw.trim().split('\n').map(JSON.parse);
  const types = evs.map((e) => e.type);
  assert.ok(types.includes('tagger_doc'), 'persist 打标事件');
  assert.ok(types.includes('assistant_discard'), '剥离申报事件');
  assert.ok(types.includes('token_round'), 'token 事件');
  assert.ok(types.includes('run_finalized'));
  assert.ok(!types.includes('view_before') && !types.includes('view_after'), '插件侧不再产出视图事件（extension 职责）');
});

// T-CE-2 / T-CE-3 / T-CE-4 已迁往 context-pruner.test.js：
//   它们此前用插件侧 api.on("context") 验证视图压缩（payload 入库/外联/双 discard 配对）。
//   v2.2 架构修正后 context 属 extension 事件（插件 SDK 的 on("context") 注册即被忽略），
//   对应用例移到 extension 的 pruneContextView 直接单测 —— 语义不变，载体更正。

// ---------- 补充：插件侧适配器/压缩视图单元（不依赖 context hook 的部分） ----------

test('T-CE-5（Cluster C 联动）：llm_output → token_round 逐轮累计与 run_stats 汇总一致', async (t) => {
  const td = await freshTraceCfg(t);
  const api = mockApi({ enabled: true, ...td });
  await createKeeper(api);
  await api.fire('llm_output', { sessionId: 's1', usage: { prompt_tokens: 1000, completion_tokens: 200 } });
  await api.fire('llm_output', { sessionId: 's1', usage: { prompt_tokens: 1500, completion_tokens: 300 } });
  await api.fire('agent_end', { sessionId: 's1' });

  // 1) token_round 事件值应与 TokenCounter 逐轮累计一致（U5 数字经 U6 事件落 trace）
  const evs = (await readFile(path.join(td.traceDir, 'trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const rounds = evs.filter((e) => e.type === 'token_round');
  assert.equal(rounds.length, 2);
  assert.equal(rounds[0].round, 1);
  assert.equal(rounds[0].input, 1000);
  assert.equal(rounds[0].output, 200);
  assert.equal(rounds[0].input_total, 1000);
  assert.equal(rounds[0].output_total, 200);
  assert.equal(rounds[0].total, 1200);
  assert.equal(rounds[1].round, 2);
  assert.equal(rounds[1].input, 1500);
  assert.equal(rounds[1].output, 300);
  assert.equal(rounds[1].input_total, 2500); // 前后两轮 input 累计
  assert.equal(rounds[1].output_total, 500);
  assert.equal(rounds[1].total, 3000);

  // 2) run_stats：events_by_type 求和 == events_total（U6 汇总 = 各事件求和）
  const stats = JSON.parse(await readFile(path.join(td.traceDir, 'run_stats.json'), 'utf8'));
  const sum = Object.values(stats.events_by_type).reduce((a, b) => a + b, 0);
  assert.equal(sum, stats.events_total);
  assert.equal(stats.events_by_type['token_round'], 2);
  assert.equal(stats.events_by_type['run_finalized'], 1);
});

test('T-U7-6：compressView 对无 keeper 标记的消息保持原样', () => {
  const msgs = [
    { role: 'user', content: 'hi' },
    { role: 'toolResult', isError: false, content: [{ type: 'text', text: '普通结果' }] },
    { role: 'assistant', content: [{ type: 'text', text: '看看' }] },
  ];
  const { messages, events } = compressView(msgs);
  assert.equal(events.length, 0);
  assert.deepEqual(messages[1].content[0].text, '普通结果');
});

test('T-U7-7：extractDiscards 从 toolCall arguments 提取多 discard', () => {
  const m = { role: 'assistant', content: [
    { type: 'toolCall', id: 'a', name: 't1', arguments: { discard_lines: [1] } },
    { type: 'toolCall', id: 'b', name: 't2', arguments: { x: 1 } },
    { type: 'toolCall', id: 'c', name: 't1', arguments: { discard_lines: [2], doc_id: 'doc_0' } },
  ] };
  const ds = extractDiscards(m);
  assert.equal(ds.length, 2);
  assert.equal(ds[0].toolCallId, 'a');
  assert.equal(ds[1].doc_id, 'doc_0');
});

test('T-CE-6：生命线日志齐全 —— run_start / tagger_skip / llm_input 在新节点落 trace', async (t) => {
  const td = await freshTraceCfg(t);
  const api = mockApi({ enabled: true, ...td });
  await createKeeper(api);

  // 1) before_agent_run → run_start（run 起点：tagTools 白名单/配置快照）
  await api.fire('before_agent_run', { sessionId: 's1' });
  // 2) 空内容 toolResult（无信息）→ tagger_skip，不产 tagger_doc
  await api.fire('tool_result_persist', {
    sessionId: 's1', toolName: 'hithink-market-query',
    message: { role: 'toolResult', content: [{ type: 'text', text: '' }] },
  });
  // 3) llm_input → 每轮输入消息数 + 估算 token
  await api.fire('llm_input', { sessionId: 's1', messages: [{ role: 'user', content: 'hi' }, { role: 'assistant', content: [{ type: 'text', text: 'ok' }] }] });
  await api.fire('agent_end', { sessionId: 's1' });

  const evs = (await readFile(path.join(td.traceDir, 'trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const types = evs.map((e) => e.type);

  assert.ok(types.includes('run_start'), 'run_start 应落 trace');
  const rs = evs.find((e) => e.type === 'run_start');
  assert.deepEqual(rs.tagTools, ['hithink-market-query']);

  assert.ok(types.includes('tagger_skip'), '无信息 toolResult 应记录 tagger_skip');
  assert.ok(!types.includes('tagger_doc'), '空内容不产 doc，不应有 tagger_doc');
  const ts = evs.find((e) => e.type === 'tagger_skip');
  assert.equal(ts.reason, 'no_info');

  assert.ok(types.includes('llm_input'), 'llm_input 应落 trace');
  const li = evs.find((e) => e.type === 'llm_input');
  assert.equal(li.n_messages, 2);
  assert.ok(li.est_tokens > 0);
});

test('T-CE-7：exec 登记管线 —— before_tool_call 登记 toolCallId→runId，persist 反查配对产 doc；未命中静默', async (t) => {
  const td = await freshTraceCfg(t);
  const api = mockApi({ enabled: true, ...td });
  await createKeeper(api);

  // 1) exec 跑 hithink cli.py → before_tool_call 登记 toolCallId=t1 → persist 按 t1 反查配对产 tagger_doc
  //    （persist 事件无 runId，仅 toolCallId 跨钩子可靠；反查命中即配对，与 runKey 无关）
  await api.fire('before_tool_call', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't1',
    params: { command: 'python3 ~/stock_research_agent/skills/hithink-market-query/scripts/cli.py --query "平安银行 涨跌幅 换手率"' },
  });
  await api.fire('tool_result_persist', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't1',
    message: { role: 'toolResult', content: [{ type: 'text', text: '| 交易日 | 涨跌幅 |\n| 08-27 | +1.20% |\n| 08-28 | +0.52% |' }] },
  });

  // 2) exec 普通命令（无 hithink）→ 不登记 → persist 静默不产 doc
  await api.fire('before_tool_call', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't2',
    params: { command: 'ls -la /tmp' },
  });
  await api.fire('tool_result_persist', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't2',
    message: { role: 'toolResult', content: [{ type: 'text', text: 'drwxrwxrwt tmp 文件列表' }] },
  });

  // 3) 中间插一个非 exec persist：登记表按 toolCallId 隔离，不消费 t3 登记；t3 的 exec persist 反查仍命中产 doc
  await api.fire('before_tool_call', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't3',
    params: { command: 'python3 cli.py --query "中国平安 最新价"' },
  });
  await api.fire('tool_result_persist', {
    sessionId: 's1', runId: 's1', toolName: 'read', toolCallId: 'r1',
    message: { role: 'toolResult', content: [{ type: 'text', text: 'data/foo.csv' }] },
  });
  await api.fire('tool_result_persist', {
    sessionId: 's1', runId: 's1', toolName: 'exec', toolCallId: 't3',
    message: { role: 'toolResult', content: [{ type: 'text', text: '| 最新价 |\n| 49.30 |' }] },
  });

  await api.fire('agent_end', { sessionId: 's1' });

  const evs = (await readFile(path.join(td.traceDir, 'trace.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const types = evs.map((e) => e.type);
  assert.equal(types.filter((x) => x === 'exec_tool_match').length, 2, '两条 exec+hithink 命令都应登记 exec_tool_match');
  assert.equal(types.filter((x) => x === 'tagger_doc').length, 2, 't1 与 t3 的 exec 结果各自产 doc（toolCallId 隔离配对，互不干扰）');
  const docs = evs.filter((e) => e.type === 'tagger_doc');
  assert.ok(docs.every((d) => d.n_rows >= 1), '表格文本应解析出行集');
  assert.equal(types.filter((x) => x === 'tagger_skip').length, 0, '未命中不产 skip（静默）');
});

// ---------- v2.4：live 视图实时打标 + discard 闭环（Task 4 验收路径） ----------

test('T-U7-8（v2.4）：liveTagger 装配 → 真实调用路径下模型视图拿到 keeper 行集, 再按 discard_lines 压缩', async () => {
  const api = mockApi({ enabled: true, trace: false, tagTools: ['hithink-market-query'] });
  api.registerContextEngine = (id, factoryFn) => { api.contextEngineFactory = factoryFn; };
  await createKeeper(api);
  assert.ok(api.contextEngineFactory, 'registerContextEngine 应被调用');
  const engine = api.contextEngineFactory();

  const raw = '证券 收盘价 涨跌幅\n---- ---- ----\n比亚迪 346.00 +1.2%\n宁德时代 250.10 -0.4%';
  // 同一次工具调用：先登记 exec（before_tool_call, 真实网关顺序）→ persist 产 doc（盘上 archive）
  // → live 视图复用同一 doc；live doc 记忆化的兜底门控 = docsByTcId.has(tcId)
  const tcId = 'call_smoke8_1';
  await api.fire('before_tool_call', {
    sessionId: 's1', runId: 'r1', toolName: 'exec', toolCallId: tcId,
    params: { command: 'python cli.py query 航天宏图' },
  });
  const persist = await api.fire('tool_result_persist', {
    toolName: 'exec', runId: 'r1', toolCallId: tcId,
    message: { role: 'toolResult', content: [{ type: 'text', text: raw }] },
  });
  assert.ok(persist, 'persist 应改写');
  const persistDoc = JSON.parse(persist.message.content[0].text.slice(KEEPER_PREFIX.length));

  // 下一次模型调用 → assemble（live 视图仍是原始 JSON toolResult, 与盘上 archive 一致）
  const providerMessages = [
    { role: 'user', content: [{ type: 'text', text: '分析比亚迪' }] },
    { role: 'assistant', content: [{ type: 'text', text: '查一下' }, { type: 'toolCall', id: tcId, name: 'exec', arguments: { command: 'python cli.py query' } }] },
    { role: 'toolResult', toolName: 'exec', toolCallId: tcId, isError: false, content: [{ type: 'text', text: raw }] },
  ];
  const a1 = await engine.assemble({ sessionKey: 's1', messages: providerMessages, tokenBudget: 40000 });
  assert.notEqual(a1.messages, providerMessages, 'live 视图应被替换（新数组）, 模型才见到行集');
  const liveDocs = a1.messages.flatMap((m) => extractDocTexts(m.content));
  assert.equal(liveDocs.length, 1, 'live 视图应含 1 份 keeper doc');
  assert.equal(liveDocs[0].doc_id, persistDoc.doc_id, 'live 与 persist 两路 doc_id 一致（同一 toolCallId 同一 doc）');
  assert.equal(liveDocs[0].sections[0].rows.length, 3, '行集行号完整（表头+2 数据行）, 模型可按 n 申报');

  // 模型申报 discard_lines（读 SKILL 后发出的下一个 toolCall 参数）→ 下一轮 assemble 应压缩
  const withDiscard = [...a1.messages];
  withDiscard.push({
    role: 'assistant',
    content: [{ type: 'text', text: '涨跌幅列没用的行要删' }, { type: 'toolCall', id: 'call_smoke8_2', name: 'exec', arguments: { command: 'python cli.py query', discard_lines: [1], doc_id: liveDocs[0].doc_id } }],
  });
  withDiscard.push({ role: 'toolResult', toolName: 'exec', toolCallId: 'call_smoke8_2', isError: false, content: [{ type: 'text', text: '后续结果' }] });
  const a2 = await engine.assemble({ sessionKey: 's1', messages: withDiscard, tokenBudget: 40000 });
  const afterDocs = a2.messages.flatMap((m) => extractDocTexts(m.content));
  assert.equal(afterDocs.filter((d) => d.doc_id === liveDocs[0].doc_id).length, 1, '压缩后 doc 仍在（保留 _pruned 版本）');
  const pruned = afterDocs.find((d) => d.doc_id === liveDocs[0].doc_id);
  assert.ok(pruned._meta._pruned, '应带 _pruned 记录');
  assert.equal(pruned._meta._pruned.n_del, 1, '删掉 1 行');
  assert.equal(pruned._meta._pruned.n_left, 2, '剩表头+1 行');
  assert.ok(pruned.sections[0].rows.every((r) => r.n !== 1), '行号 1 已被删');
});

test('T-U7-9（v2.4.2）：resume 历史 exec 结果 —— 无 live 登记/无 memo, 靠 command 重建 cmdHit 打标；非取数命令不动', async () => {
  const api = mockApi({ enabled: true, trace: false, tagTools: ['hithink-market-query'] });
  api.registerContextEngine = (id, factoryFn) => { api.contextEngineFactory = factoryFn; };
  await createKeeper(api);
  const engine = api.contextEngineFactory();
  const raw = '日期 收盘价 涨跌幅\n---- ---- ----\n2026-08-29 346.00 +1.2%\n2026-08-28 250.10 -0.4%';

  // 模拟 resume：历史消息直接进入 providerMessages, 没有任何 before_tool_call / persist 事件
  const tcId = 'call_resume_1';
  const hitMessages = [
    { role: 'user', content: [{ type: 'text', text: '继续分析' }] },
    { role: 'assistant', content: [{ type: 'text', text: '取数' }, { type: 'toolCall', id: tcId, name: 'exec', arguments: { command: 'python cli.py query 航天宏图' } }] },
    { role: 'toolResult', toolName: 'exec', toolCallId: tcId, isError: false, content: [{ type: 'text', text: raw }] },
  ];
  const a1 = await engine.assemble({ sessionKey: 's1', messages: hitMessages, tokenBudget: 40000 });
  assert.notEqual(a1.messages, hitMessages, '历史 exec 结果应被 live 改写（新数组）');
  const docs = extractDocTexts(a1.messages[2].content);
  assert.equal(docs.length, 1, '历史 exec 结果产出 1 份 doc');
  assert.equal(docs[0].sections[0].rows.length, 3, '行集行号完整');

  // 反向用例：非取数命令（git status）不得打标
  const negTc = 'call_resume_2';
  const negMessages = [
    { role: 'user', content: [{ type: 'text', text: '继续' }] },
    { role: 'assistant', content: [{ type: 'toolCall', id: negTc, name: 'exec', arguments: { command: 'git status' } }] },
    { role: 'toolResult', toolName: 'exec', toolCallId: negTc, isError: false, content: [{ type: 'text', text: raw }] },
  ];
  const a2 = await engine.assemble({ sessionKey: 's1', messages: negMessages, tokenBudget: 40000 });
  assert.equal(a2.messages, negMessages, '非取数命令保持原样（原数组引用）');

  // OpenAI tool_calls[] 形态兜底：arguments 为 JSON 字符串
  const openaiTc = 'call_resume_3';
  const openaiMessages = [
    { role: 'user', content: [{ type: 'text', text: '继续' }] },
    { role: 'assistant', content: '取数', tool_calls: [{ id: openaiTc, type: 'function', function: { name: 'exec', arguments: '{"command":"python cli.py query 宁德时代"}' } }] },
    { role: 'toolResult', toolName: 'exec', toolCallId: openaiTc, isError: false, content: [{ type: 'text', text: raw }] },
  ];
  const a3 = await engine.assemble({ sessionKey: 's1', messages: openaiMessages, tokenBudget: 40000 });
  assert.notEqual(a3.messages, openaiMessages, 'OpenAI tool_calls 形态也应命中 cmdHit');
});