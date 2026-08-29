#!/usr/bin/env node
// ==========================================================================
// U8 dashboard —— 零依赖 Node 服务：驾驶舱数据源（静态页 + runs 列表 + SSE 事件流）
// ==========================================================================
// 用法： node scripts/dashboard.mjs [--port 4399] [--logs <keeper-logs-dir>]
//   GET /                    → scripts/dashboard/index.html（U9 驾驶舱前端）
//   GET /api/runs            → { runs: [{id, events, statsFile, updatedAt}] }
//   GET /api/events?run=<id> → SSE：先回放该 run 全部已有事件，再轮询尾随新行
// 数据源：<logs>/<run>/trace.jsonl（每行一个 JSON 事件，U6 写的）
// ==========================================================================

import { createServer } from 'node:http';
import { readFile, readdir, stat } from 'node:fs/promises';
import { createReadStream, watch } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_LOGS = path.join(__dirname, 'logs');
const DEFAULT_PORT = 4399;
const INDEX_PATH = path.join(__dirname, 'dashboard', 'index.html');
const POLL_MS = 800;

function parseArgs(argv) {
  const out = { port: DEFAULT_PORT, logs: DEFAULT_LOGS };
  for (let i = 0; i < argv.length; i += 2) {
    if (argv[i] === '--port') out.port = Number(argv[i + 1]);
    if (argv[i] === '--logs') out.logs = path.resolve(argv[i + 1]);
  }
  return out;
}

/** 列出 run 目录（含 trace.jsonl 的目录） */
export async function listRuns(logsDir) {
  let entries;
  try {
    entries = await readdir(logsDir, { withFileTypes: true });
  } catch {
    return [];
  }
  const runs = [];
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    const tracePath = path.join(logsDir, e.name, 'trace.jsonl');
    try {
      const st = await stat(tracePath);
      runs.push({ id: e.name, events: st.size === 0 ? 0 : await countLines(tracePath), updatedAt: st.mtime.toISOString() });
    } catch {
      /* 无 trace.jsonl 的目录不算 run */
    }
  }
  return runs.sort((a, b) => (a.id < b.id ? 1 : -1));
}

async function countLines(file) {
  const buf = await readFile(file, 'utf8');
  if (!buf.trim()) return 0;
  return buf.trim().split('\n').length;
}

/**
 * 打开一个 run 的事件流：先把历史事件全部取出，再持续读出新增行。
 * @returns {{history: object[], tail:(cb:(ev:object)=>void)=>Promise<()=>Promise<void>>, close:()=>void}}
 */
export function openRunStream(logsDir, runId) {
  const tracePath = path.join(logsDir, runId, 'trace.jsonl');
  let lastSize = 0;
  let stopped = false;
  let timer = null;

  return {
    async readHistory() {
      try {
        const buf = await readFile(tracePath, 'utf8');
        lastSize = Buffer.byteLength(buf, 'utf8');
        return buf.split('\n').filter((l) => l.trim()).map((l) => safeParse(l)).filter(Boolean);
      } catch {
        lastSize = 0;
        return [];
      }
    },
    tail(cb) {
      return new Promise((resolve) => {
        const tick = async () => {
          if (stopped) return resolve();
          let buf = '';
          try {
            buf = await readFile(tracePath, 'utf8');
          } catch {
            return;
          }
          const size = Buffer.byteLength(buf, 'utf8');
          if (size > lastSize) {
            const newPart = buf.slice(lastSize);
            for (const line of newPart.split('\n')) {
              if (!line.trim()) continue;
              const ev = safeParse(line);
              if (ev) cb(ev);
            }
            lastSize = size;
          }
        };
        timer = setInterval(tick, POLL_MS);
      });
    },
    close() {
      stopped = true;
      if (timer) clearInterval(timer);
    },
  };
}

function safeParse(line) {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

export function createDashboardServer({ logsDir, indexPath = INDEX_PATH } = {}) {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host ?? 'localhost'}`);
    try {
      if (url.pathname === '/api/runs') {
        const runs = await listRuns(logsDir);
        return json(res, 200, { runs });
      }
      if (url.pathname === '/api/events') {
        const run = url.searchParams.get('run');
        if (!run || /[^A-Za-z0-9_.-]/.test(run)) return json(res, 400, { error: 'bad run id' });
        return sse(req, res, logsDir, run);
      }
      if (url.pathname === '/' || url.pathname === '/index.html') {
        try {
          const html = await readFile(indexPath, 'utf8');
          res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
          return res.end(html);
        } catch {
          return json(res, 500, { error: `index.html not found at ${indexPath}` });
        }
      }
      return json(res, 404, { error: 'not found' });
    } catch (e) {
      console.error('[dashboard] ', e.message);
      return json(res, 500, { error: e.message });
    }
  });
  return server;
}

function json(res, code, obj) {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

async function sse(req, res, logsDir, runId) {
  res.writeHead(200, {
    'content-type': 'text/event-stream; charset=utf-8',
    'cache-control': 'no-cache',
    connection: 'keep-alive',
  });
  const stream = openRunStream(logsDir, runId);
  try {
    const history = await stream.readHistory();
    for (const ev of history) writeEvent(res, ev);
    res.write(': connected\n\n');
  } catch (e) {
    console.error('[dashboard] sse init fail', e.message);
  }
  req.on('close', () => stream.close());
  await stream.tail((ev) => writeEvent(res, ev));
  res.end();
}

function writeEvent(res, ev) {
  res.write(`data: ${JSON.stringify(ev)}\n\n`);
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  const { port, logs } = parseArgs(process.argv.slice(2));
  createDashboardServer({ logsDir: logs }).listen(port, () => {
    console.log(`[dashboard] http://127.0.0.1:${port}  logs=${logs}`);
  });
}