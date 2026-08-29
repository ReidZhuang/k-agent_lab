// ==========================================================================
// U1 contract —— JSON 行集契约的类型校验与规范化（纯函数，零依赖）
//
// 被 U2 tagger / U3 cleaner / U4 compressor / U5 token 共用。
// 契约详见 docs/PLUGIN_DESIGN_V2.md §2（v2.1）。
//
// 行集文档形状：
//   {
//     tool, doc_id, query, fetched_at,
//     sections: [ { id, source:{name,url,check}, rows: [ {n,k,t} ] } ],
//     _meta: { n_rows, hint, _pruned? }
//   }
// 行号 n：0 起、全文唯一、连续；k ∈ {h,v,t,u}；永不重编号。
// ==========================================================================

export const ROW_KINDS = Object.freeze(['h', 'v', 't', 'u']);

/** tagger 散文长段的再切阈值（字符）；见 PLUGIN_DESIGN_V2.md §2.1 本地切分规则。 */
export const DEFAULT_MAX_ROW_CHARS = 400;

/** 生成稳定 doc_id：doc_<seq>（seq 由 tagger 按取数顺序递增）。 */
export function genDocId(seq) {
  return `doc_${seq}`;
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

/**
 * 校验并规范化一份行集文档。
 * @param {unknown} obj
 * @returns {{ok:true, value:object} | {ok:false, errors:string[]}}
 */
export function normalizeRowset(obj) {
  const errors = [];

  if (!isPlainObject(obj)) {
    return { ok: false, errors: ['root must be an object'] };
  }

  // doc_id
  if (typeof obj.doc_id !== 'string' || !/^doc_\d+$/.test(obj.doc_id)) {
    errors.push(`doc_id must be a string like "doc_0", got ${JSON.stringify(obj.doc_id)}`);
  }

  // sections / rows
  const allRows = [];
  if (!Array.isArray(obj.sections)) {
    errors.push('sections must be an array');
  } else if (obj.sections.length === 0) {
    errors.push('sections must not be empty');
  } else {
    obj.sections.forEach((sec, i) => {
      const p = `sections[${i}]`;
      if (!isPlainObject(sec)) { errors.push(`${p} must be an object`); return; }
      if (typeof sec.id !== 'string' || sec.id.length === 0) errors.push(`${p}.id must be a non-empty string`);
      if (!isPlainObject(sec.source) || typeof sec.source.name !== 'string' || sec.source.name.length === 0) {
        errors.push(`${p}.source.name must be a non-empty string`);
      }
      if (typeof sec.source.check !== 'string') errors.push(`${p}.source.check must be a string`);
      if (!Array.isArray(sec.rows) || sec.rows.length === 0) {
        errors.push(`${p}.rows must be a non-empty array`);
        return;
      }
      sec.rows.forEach((r, j) => {
        const q = `${p}.rows[${j}]`;
        if (!isPlainObject(r)) { errors.push(`${q} must be an object`); return; }
        if (!Number.isInteger(r.n) || r.n < 0) errors.push(`${q}.n must be a non-negative integer`);
        if (!ROW_KINDS.includes(r.k)) errors.push(`${q}.k must be one of ${ROW_KINDS.join('/')}, got ${JSON.stringify(r.k)}`);
        if (typeof r.t !== 'string' || r.t.length === 0) errors.push(`${q}.t must be a non-empty string`);
        allRows.push(r);
      });
    });

    // 全局行号：唯一、连续、从 0 起（跨 section 不重复）
    if (allRows.length > 0 && errors.length === 0) {
      const sorted = allRows.map((r) => r.n).sort((a, b) => a - b);
      for (let i = 0; i < sorted.length; i++) {
        if (sorted[i] !== i) {
          errors.push(`row numbers must be unique and contiguous from 0 (violation at position ${i}: value ${sorted[i]})`);
          break;
        }
      }
    }
  }

  // _meta（可选；若给了则一致性检查）
  if (obj._meta !== undefined) {
    if (!isPlainObject(obj._meta)) {
      errors.push('_meta must be an object');
    } else if (obj._meta.n_rows !== undefined) {
      const actual = obj.sections && Array.isArray(obj.sections)
        ? obj.sections.reduce((sum, s) => sum + (Array.isArray(s.rows) ? s.rows.length : 0), 0)
        : 0;
      if (obj._meta.n_rows !== actual) {
        errors.push(`_meta.n_rows (${obj._meta.n_rows}) mismatch actual row count (${actual})`);
      }
    }
  }

  if (errors.length > 0) return { ok: false, errors };
  return { ok: true, value: obj };
}

/**
 * 规范化 discard_lines：只保留"存在的行号"，去重、升序；非法输入视为不删。
 * @param {unknown} dl  模型投递的 discard_lines
 * @param {number} maxN 该文档总行数（合法行号为 [0, maxN-1]）
 * @returns {number[]}
 */
export function normalizeDiscard(dl, maxN) {
  if (!Array.isArray(dl)) return [];
  const out = [];
  for (const x of dl) {
    if (Number.isInteger(x) && x >= 0 && x < maxN && !out.includes(x)) out.push(x);
  }
  return out.sort((a, b) => a - b);
}