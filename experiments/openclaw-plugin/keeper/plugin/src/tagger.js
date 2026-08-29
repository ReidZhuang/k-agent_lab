// ==========================================================================
// U2 tagger —— 原文 → JSON 行集（语义单元切分 + k 分类 + n 编号 + _meta）
// ==========================================================================
// 设计依据：PLUGIN_DESIGN_V2.md v2.1 §2.3
//   - "语义单元"切分是【本地确定性规则】，不是大模型语义——表格按行、散文按段→完整句。
//   - 不切半句：散文行的边界只允许落在句号/问号/感叹号/分号之后（或换行天然成句），
//     无标点残句与下一段拼接；若拼接后仍超过 maxRowChars，按"截断+…"策略收尾（见 truncate）。
//   - k 启发式：免责/仅供参考/版权→u（最高优先，即使含数字）；含数字→v；表头分隔线相邻→h；其余→t。
// 输出必过 U1 normalizeRowset 校验；无信息产出时返回 { ok:true, value:null }（约定：不产 doc）。
// ==========================================================================

import { genDocId, normalizeRowset, DEFAULT_MAX_ROW_CHARS } from './contract.js';

const HINT = '按 n 引用；下次查询时用 discard_lines 报告完全无用的行号';

/** 免责/仅供参考/版权 等无用行信号词（u 优先级最高） */
const U_SIGNALS = [
  /免责/,
  /仅供参考/,
  /风险提示/,
  /版权/,
  /著作权/,
  /侵删/,
  /如涉及侵权/,
  /如有雷同/,
  /不构成.{0,10}(投资)?建议/,
  /据此(操作|投资)/,
  /本文(内容|观点)?.{0,4}(仅供|不构成|不代表)/,
  /信息.{0,6}(来自|来源|整理自)/,
];

/** 表头分隔线样式：---- 、==== 、+---+ 、|----| 、"------- --------"（每列一截）等 */
export function isSeparatorLine(s) {
  const t = (s ?? '').trim().replace(/^[|｜+]+|[|｜+]+$/g, '').replace(/\s+/g, '');
  return t.length >= 3 && /^[-─━═=－]+$/.test(t);
}

/**
 * 判别某文本块是否"结构化块"（按行切才有语义单元）。
 * 触发任一：任一分隔线 / ≥2 行含 \t / ≥2 行含 | 或 ｜ / ≥2 列表项(- * ·) / ≥1 个 markdown 标题(#)。
 * 真实 i问财 盘面输出多为 `## 标题` + `key: value | key: value` 记录 + `- 列表` 形态，必须按行切。
 */
export function isTableLike(text) {
  const lines = (text ?? '').split('\n');
  if (lines.some(isSeparatorLine)) return true;
  if (lines.filter((l) => l.includes('\t')).length >= 2) return true;
  if (lines.filter((l) => /[｜|]/.test(l)).length >= 2) return true;
  if (lines.filter((l) => /^\s*[-*·•]\s/.test(l)).length >= 2) return true;
  if (lines.some((l) => /^\s*#{1,6}\s/.test(l))) return true;
  return false;
}

/** 单文本块 → 行（结构化模式：原样按行；行 = 一个语义单元） */
export function splitTable(text) {
  const rows = [];
  for (const raw of (text ?? '').split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    if (isSeparatorLine(line)) {
      // 分隔线不产出；其上一行(若为内容行)升级为表头 h
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].k === 't') rows[i].k = 'h';
        break;
      }
      continue;
    }
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (heading) {
      rows.push({ k: 'h', t: heading[1] }); // markdown 标题 → 表头性质
      continue;
    }
    rows.push({ k: classifyRow(line), t: line.replace(/^\s*[-*·•]\s+/, '') }); // 列表项去标记
  }
  return rows;
}

/** 按句子结束标点切开（标点随行走；无标点残句会留在最后一段） */
function splitByEnding(text) {
  const END = /[。！？!?；;]/;
  const out = [];
  let buf = '';
  for (const ch of text) {
    buf += ch;
    if (END.test(ch)) {
      out.push(buf);
      buf = '';
    }
  }
  if (buf) out.push(buf);
  return out;
}

/** 超长句截断策略（写死：尾部截断 + 省略号） */
export function truncate(s, max) {
  return s.length <= max ? s : s.slice(0, max - 1) + '…';
}

/**
 * 散文段 → 完整句行。
 * 无标点残句与下一片段拼接直至成句；拼接后仍超长则截断（不切半句的边界只在标点/截断策略处）。
 */
function splitProseParagraph(paragraph, maxRowChars) {
  const rows = [];
  let acc = '';
  for (const seg of splitByEnding(paragraph)) {
    acc += seg;
    if (acc.length >= maxRowChars || /[。！？!?；;]/.test(acc.slice(-1))) {
      rows.push(truncate(acc.trim(), maxRowChars));
      acc = '';
    }
  }
  if (acc.trim()) rows.push(truncate(acc.trim(), maxRowChars));
  return rows.filter((r) => r.length > 0);
}

// JSON 信封解包（v2.4.1）：exec 取数结果 = 外层 JSON 信封（{success, query, datas:[...], ...}）。
// 直接把整份 JSON 走散文/表格→ 1 行（DEFAULT_MAX_ROW_CHARS=400 截断 → 模型只看得到前 400 字符，
// 且单行无可删粒度 ⇒ discard_applied 恒 0）。解包后每个数组元素 = 一行（语义原子，保结构整体）。
// 不是 JSON / 无数据数组 → 返回 null，调用方走原 prose/table 逻辑（幂等不误伤既有输入）。
const JSON_ARRAY_KEYS = ['datas', 'data', 'rows', 'items', 'list', 'results', 'records', 'values'];
export function jsonRows(text, maxRowChars) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    return null;
  }
  let arr = null;
  if (Array.isArray(parsed)) arr = parsed;
  else if (parsed && typeof parsed === 'object') {
    for (const k of JSON_ARRAY_KEYS) {
      if (Array.isArray(parsed[k]) && parsed[k].length > 0) {
        arr = parsed[k];
        break;
      }
    }
  }
  if (!arr || arr.length === 0) return null;
  // JSON 行保结构：元素整体保留（cap 高于散文上限，防 400 字符截断切字段）；仅远超 cap 才截尾
  const cap = Math.max(maxRowChars, 1200);
  return arr
    .filter((el) => el !== null && el !== undefined)
    .map((el) => {
      const s = typeof el === 'string' ? el : JSON.stringify(el);
      return truncate(s, cap);
    })
    .map((s) => ({ k: classifyRow(s), t: s }));
}

/** 散文模式：按空行分段 → 段内按完整句切行 */
function proseRows(text, maxRowChars) {
  const paragraphs = (text ?? '').split(/\n\s*\n+/) // 空行分段
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
  const rows = [];
  for (const para of paragraphs) {
    for (const seg of splitProseParagraph(para, maxRowChars)) {
      rows.push({ k: classifyRow(seg), t: seg });
    }
  }
  return rows;
}

/** k 启发式分类（顺序即优先级：u > v > h > t） */
export function classifyRow(t) {
  const s = (t ?? '').trim();
  if (!s) return 't';
  if (U_SIGNALS.some((re) => re.test(s))) return 'u'; // 免责/仅供参考/版权，最高优先
  if (/\d/.test(s)) return 'v';
  if (isSeparatorLine(s)) return 'h';
  return 't';
}

/**
 * 入口：文本块数组 → JSON 行集文档。
 * @param {{tool?:string, doc_id?:string, query?:string, fetched_at?:string,
 *          blocks:{id?:string, source?:{name?:string,url?:string,check?:string}, text:string}[]}} input
 * @param {{maxRowChars?:number, seq?:number}} [opts] seq 用于 doc_id 自增
 */
export function tag(input, opts = {}) {
  const maxRowChars = opts.maxRowChars ?? DEFAULT_MAX_ROW_CHARS;
  const seq = opts.seq ?? 0;
  if (!input || typeof input !== 'object' || !Array.isArray(input.blocks) || input.blocks.length === 0) {
    return { ok: false, errors: ['input.blocks must be a non-empty array'] };
  }
  const errors = [];
  const sections = [];
  let n = 0;
  input.blocks.forEach((blk, i) => {
    const p = `blocks[${i}]`;
    if (!blk || typeof blk.text !== 'string') {
      errors.push(`${p}.text must be a string`);
      return;
    }
    if (!blk.text.trim()) return; // 空文本 = 无信息 → 跳过（不产 section，不报错）
    const rawRows = isTableLike(blk.text) ? splitTable(blk.text)
    : (jsonRows(blk.text, maxRowChars) ?? proseRows(blk.text, maxRowChars));
    if (rawRows.length === 0) return; // 该块无信息 → 不产 section
    sections.push({
      id: blk.id ?? `s${i}`,
      source: {
        name: blk.source?.name ?? '未知来源',
        url: blk.source?.url ?? '',
        check: blk.source?.check ?? '',
      },
      rows: rawRows.map((r) => ({ n: n++, k: r.k, t: r.t })),
    });
  });
  if (errors.length > 0) return { ok: false, errors };
  if (sections.length === 0 || n === 0) return { ok: true, value: null }; // 无信息不产 doc
  const doc = {
    tool: input.tool ?? 'tool',
    doc_id: genDocId(seq),
    query: input.query ?? '',
    fetched_at: input.fetched_at ?? '',
    sections,
    _meta: { n_rows: n, hint: HINT },
  };
  const norm = normalizeRowset(doc);
  if (!norm.ok) return { ok: false, errors: ['tagger output failed contract: ' + norm.errors.join('; ')] };
  return { ok: true, value: doc };
}