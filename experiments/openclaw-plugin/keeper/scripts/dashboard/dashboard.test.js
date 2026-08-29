// U8 dashboard.mjs 集成测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U8-1..5）。
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, mkdir, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createDashboardServer, listRuns } from '../dashboard.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_LOGS = path.join(__dirname, 'logs');

function listen(srv) {
  return new Promise((res, rej) => {
    srv.once('error', rej);
    srv.listen(0, '127.0.0.1', () => res(srv.address().port));
  });
}
function close(srv) {
  return new Promise((res) => {
    // keep-alive 空闲连接会让 server.close() 死等 → 强制断开（Node 18.2+）
    if (srv.closeAllConnections) srv.closeAllConnections();
    srv.close(() => res());
  });
}

async function readSSE(url, { maxMs = 4000 } = {}) {
  const ctrl = new AbortController();
  const res = await fetch(url, { signal: ctrl.signal });
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', events = [];
  const t0 = Date.now();
  try {
    while (Date.now() - t0 < maxMs) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        let connected = false;
        for (const line of frame.split('\n')) {
          if (line.startsWith('data: ')) events.push(JSON.parse(line.slice(6)));
          if (line.startsWith(': connected')) connected = true;
        }
        if (connected) { ctrl.abort(); return { events }; }
      }
    }
  } catch { /* abort 引发的读取中断：正常结束 */ }
  ctrl.abort();
  return { events };
}

// ---------- 冒烟 ----------

test('T-U8-1 冒烟：/api/runs 返回样本 run 列表', async () => {
  const srv = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const port = await listen(srv);
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/runs`);
    const { runs } = await r.json();
    const sample = runs.find((x) => x.id === 'sample');
    assert.ok(sample, '应有 sample run');
    assert.ok(sample.events >= 12, `sample 事件数 ${sample.events}`);
  } finally {
    await close(srv);
  }
});

// ---------- 常规 ----------

test('T-U8-2：SSE 先回放已有全部事件，顺序正确', async () => {
  const srv = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const port = await listen(srv);
  try {
    const { events } = await readSSE(`http://127.0.0.1:${port}/api/events?run=sample`);
    assert.equal(events[0].type, 'run_start');
    assert.ok(events.length >= 12, `回放事件数 ${events.length}`);
    assert.equal(events.at(-1).type, 'run_finalized', '顺序应与 trace.jsonl 一致');
    const types = events.map((e) => e.type);
    assert.ok(types.includes('discard_applied') && types.includes('tagger_doc') && types.includes('token_round'));
  } finally {
    await close(srv);
  }
});

test('T-U8-3：无日志目录 → /api/runs 返回空列表（不报错）', async () => {
  const none = path.join(await mkdtemp(path.join(tmpdir(), 'keeper-none-')), 'nope');
  const srv = createDashboardServer({ logsDir: none });
  const port = await listen(srv);
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/runs`);
    assert.equal(r.status, 200);
    assert.deepEqual((await r.json()).runs, []);
    const bad = await fetch(`http://127.0.0.1:${port}/api/events?run=x`);
    assert.equal(bad.status, 200, '未知 run 应回放空流而不是报错');
  } finally {
    await close(srv);
  }
});

// ---------- 补充边界 ----------

test('T-U8-4：端口占用 → 明确报错而非静默', async () => {
  const s1 = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const port = await listen(s1);
  const s2 = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const err = await new Promise((res) => {
    s2.once('error', (e) => res(e));
    s2.listen(port, '127.0.0.1');
  });
  assert.ok(err && err.code === 'EADDRINUSE', `应报 EADDRINUSE，实际 ${err && err.code}`);
  await close(s1);
});

test('T-U8-6（U9 冒烟）：GET / 返回驾驶舱页面且含关键元素', async () => {
  const srv = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const port = await listen(srv);
  try {
    const r = await fetch(`http://127.0.0.1:${port}/`);
    assert.equal(r.status, 200);
    const html = await r.text();
    assert.match(html, /keeper 驾驶舱/);
    assert.match(html, /runSel/);
    assert.match(html, /api\/events/);
  } finally {
    await close(srv);
  }
});

test('T-U8-5：run 切换 → 加载对应 trace（两个 run 内容不同）', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'keeper-runs-'));
  await mkdir(path.join(dir, 'run_a'), { recursive: true });
  await mkdir(path.join(dir, 'run_b'), { recursive: true });
  await writeFile(path.join(dir, 'run_a', 'trace.jsonl'), JSON.stringify({ type: 'aaa' }) + '\n', 'utf8');
  await writeFile(path.join(dir, 'run_b', 'trace.jsonl'), JSON.stringify({ type: 'bbb' }) + '\n', 'utf8');
  const srv = createDashboardServer({ logsDir: dir });
  const port = await listen(srv);
  try {
    const a = await readSSE(`http://127.0.0.1:${port}/api/events?run=run_a`);
    const b = await readSSE(`http://127.0.0.1:${port}/api/events?run=run_b`);
    assert.equal(a.events[0].type, 'aaa');
    assert.equal(b.events[0].type, 'bbb');
    const runs = await listRuns(dir);
    assert.equal(runs.length, 2);
  } finally {
    await close(srv);
    await rm(dir, { recursive: true, force: true });
  }
});

test('T-U8-7（U9）：/api/payload 外联报文读取（ref 不带 .json 也能取到）', async () => {
  const srv = createDashboardServer({ logsDir: SAMPLE_LOGS });
  const port = await listen(srv);
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/payload?run=sample&file=pay_sample_0`);
    assert.equal(r.status, 200, 'ref 不带 .json → 应自动补全后缀命中');
    const txt = await r.text();
    assert.ok(txt.includes('doc_id') && txt.includes('rows'), '应返回行集报文');
    const bad = await fetch(`http://127.0.0.1:${port}/api/payload?run=sample&file=../%2e%2e%2fetc/passwd`);
    assert.ok([400, 404].includes(bad.status), `路径穿越应被拒，实际 ${bad.status}`);
  } finally {
    await close(srv);
  }
});