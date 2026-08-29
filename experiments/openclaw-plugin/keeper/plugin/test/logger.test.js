// U6 logger.js 单元测试 —— node --test
// 案例编号对应 DEVELOPMENT_PLAN.md §4（T-U6-1..5）+ 补充边界。
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createLogger } from '../src/logger.js';

async function freshDir(prefix = 'keeper-log-') {
  const d = await mkdtemp(path.join(tmpdir(), prefix));
  return d;
}

// ---------- 冒烟 ----------

test('T-U6-1 冒烟：写一条事件 → trace.jsonl 产生且可反序列化', async () => {
  const dir = await freshDir();
  const lg = await createLogger({ traceDir: dir, runId: 'r1' });
  await lg.log({ type: 'tagger_doc', doc_id: 'doc_0', n_rows: 5 });
  const raw = await readFile(path.join(dir, 'trace.jsonl'), 'utf8');
  const ev = JSON.parse(raw.trim());
  assert.equal(ev.type, 'tagger_doc');
  assert.equal(ev.doc_id, 'doc_0');
  assert.ok(ev.ts, '事件应带时间戳');
  await rm(dir, { recursive: true, force: true });
});

// ---------- 常规 ----------

test('T-U6-2：目录不存在 → 自动创建', async () => {
  const base = await freshDir();
  const dir = path.join(base, 'a', 'b', 'c');
  const lg = await createLogger({ traceDir: dir });
  await lg.log({ type: 'x' });
  const raw = await readFile(path.join(dir, 'trace.jsonl'), 'utf8');
  assert.equal(JSON.parse(raw.trim()).type, 'x');
  await rm(base, { recursive: true, force: true });
});

test('T-U6-3：批量写入顺序与内容正确', async () => {
  const dir = await freshDir();
  const lg = await createLogger({ traceDir: dir });
  for (let i = 0; i < 5; i++) await lg.log({ type: 'ev', i });
  const raw = await readFile(path.join(dir, 'trace.jsonl'), 'utf8');
  const lines = raw.trim().split('\n').map(JSON.parse);
  assert.deepEqual(lines.map((l) => l.i), [0, 1, 2, 3, 4]);
  await rm(dir, { recursive: true, force: true });
});

test('T-U6-4：写失败（目标路径下存在同名文件）→ 不抛、降级警告、插件不崩', async () => {
  const base = await freshDir();
  const blocker = path.join(base, 'afile');
  await writeFile(blocker, 'i am a file', 'utf8'); // 让 afile/logs 的 mkdir 失败
  const dir = path.join(blocker, 'logs');
  const lg = await createLogger({ traceDir: dir });
  try {
    await lg.log({ type: 'x' }); // 不应 throw
    await lg.log({ type: 'y' });
    assert.ok(true, '未抛出异常');
  } catch (e) {
    assert.fail(`日志写入在损坏目标上不应抛异常: ${e.message}`);
  }
  await rm(base, { recursive: true, force: true });
});

test('T-U6-5：payload 过大 → 写 trace_payloads/<id>.json，trace.jsonl 只留引用', async () => {
  const dir = await freshDir();
  const lg = await createLogger({ traceDir: dir, payloadMax: 100 });
  const big = 'A'.repeat(500);
  await lg.log({ type: 'payload_big', payload: big });
  await lg.log({ type: 'payload_small', payload: 'short' });
  const raw = await readFile(path.join(dir, 'trace.jsonl'), 'utf8');
  const lines = raw.trim().split('\n').map(JSON.parse);
  assert.ok(lines[0].payload_ref, '大 payload 应被外联引用');
  assert.equal(lines[0].payload, undefined);
  assert.equal(lines[1].payload, 'short');
  const files = await readdir(path.join(dir, 'trace_payloads'));
  assert.equal(files.length, 1);
  const stored = await readFile(path.join(dir, 'trace_payloads', files[0]), 'utf8');
  assert.equal(stored, big);
  await rm(dir, { recursive: true, force: true });
});

// ---------- 补充边界 ----------

test('T-U6-6：finalize 写 run_stats.json（事件总量+按类型+起止）', async () => {
  const dir = await freshDir();
  const lg = await createLogger({ traceDir: dir, runId: 'r9' });
  await lg.log({ type: 'a' });
  await lg.log({ type: 'b' });
  await lg.log({ type: 'a' });
  const stats = await lg.finalize();
  assert.equal(stats.runId, 'r9');
  assert.equal(stats.events_total, 3);
  assert.deepEqual(stats.events_by_type, { a: 2, b: 1 });
  const fromDisk = JSON.parse(await readFile(path.join(dir, 'run_stats.json'), 'utf8'));
  assert.deepEqual(fromDisk.events_by_type, { a: 2, b: 1 });
  await rm(dir, { recursive: true, force: true });
});

test('T-U6-7：非对象/空事件 → 忽略且不崩', async () => {
  const dir = await freshDir();
  const lg = await createLogger({ traceDir: dir });
  await lg.log(null);
  await lg.log(undefined);
  await lg.log('str');
  await lg.log({ type: 'ok' });
  const raw = await readFile(path.join(dir, 'trace.jsonl'), 'utf8');
  assert.equal(raw.trim().split('\n').length, 1);
  await rm(dir, { recursive: true, force: true });
});