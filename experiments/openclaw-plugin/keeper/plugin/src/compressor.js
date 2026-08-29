// ==========================================================================
// U4 compressor —— 按 discard_lines 压缩"最新未标记文档"，产出压缩后视图 + 事件
// ==========================================================================
// 设计依据：PLUGIN_DESIGN_V2.md v2.1 §2.4（位置配对）
//   - 配对方向：assistant 消息里的 discard_lines 只"向后看"，消费【它之前最近一份】未标记 doc。
//   - newest-only：最新一份结果永不压缩；discard 只能筛"最新一份未标记文档"。
//   - 幂等：transformContext 每次从原始消息重建压缩视图，本函数纯函数、不改输入。
// 归一化消息形状（U7 适配层负责把 OpenClaw 真实消息映射到这里）：
//   { role:'user'|'tool', doc?:Rowset, isError?:boolean }         —— 载有行集的工具结果
//   { role:'assistant', discard?: { doc_id?:string, lines:number[] } } —— 模型申报删除
// ==========================================================================

/**
 * 从 doc 中删除指定行号（n 引用；不存在/非法行号忽略）。
 * 剩余行号【不变号】（契约：n 稳定不重编号）；_meta 追加 _pruned 记录。
 * 不改原 doc（返回深拷贝）。
 * @param {object} doc 合法行集（∅ 或已过 U1 校验）
 * @param {number[]} lines 要删的行号
 * @returns {{doc: object|null, removed: number[], removedRows: Array<{n,k,t}>, left: number}}
 */
export function pruneDoc(doc, lines) {
  const del = new Set(Array.isArray(lines) ? lines.filter((x) => Number.isInteger(x) && x >= 0) : []);
  const pruned = structuredClone(doc);
  const removed = [];
  const removedRows = []; // 被删行原文,供 trace/驾驶舱回显(旧 trace 未持久化该内容)
  for (const sec of pruned.sections) {
    const kept = [];
    for (const row of sec.rows) {
      if (del.has(row.n)) { removed.push(row.n); removedRows.push({ n: row.n, k: row.k, t: row.t }); continue; }
      kept.push(row);
    }
    sec.rows = kept;
  }
  removed.sort((a, b) => a - b);
  const n_rows = pruned.sections.reduce((s, sec) => s + sec.rows.length, 0);
  pruned._meta = {
    ...pruned._meta,
    n_rows,
    _pruned: { n_del: removed.length, n_left: n_rows, discarded: removed },
  };
  return { doc: pruned, removed, removedRows, left: n_rows };
}

/**
 * 一趟扫描：assistant 的 discard 消费其之前最近一份未痕迹 doc（newest-only 配对）。
 * 输出消息数组是【新构造的深拷贝】；产生事件供 U6 记录与驾驶舱展示。
 * @param {Array<{role?:string, doc?:object, isError?:boolean, discard?:object}>} messages 归一化消息
 * @returns {{messages: Array, events: Array<object>}}
 */
export function applyCompression(messages) {
  const out = Array.isArray(messages) ? structuredClone(messages) : [];
  const events = [];
  const pending = []; // 未消费文档的索引（按出现顺序；尾部 = 最新）
  for (let i = 0; i < out.length; i++) {
    const msg = out[i];
    if (msg && typeof msg === 'object' && msg.doc) {
      if (msg.isError) {
        events.push({ type: 'tool_result_error', at: i }); // 错误结果不进入候选
      } else if (msg.doc._meta && msg.doc._meta._pruned) {
        events.push({ type: 'doc_already_pruned', doc_id: msg.doc.doc_id, at: i }); // 上一轮产物，跳过
      } else {
        pending.push(i);
      }
      continue;
    }
    if (msg && typeof msg === 'object' && msg.discard) {
      const dl = msg.discard;
      if (!Array.isArray(dl.lines) || dl.lines.length === 0) {
        events.push({ type: 'discard_empty', at: i });
        continue;
      }
      if (pending.length === 0) {
        events.push({ type: 'compress_skip', reason: 'no_unconsumed_doc', at: i });
        continue;
      }
      // 命中目标：discard 显式指定 doc_id → 精确命中该未消费 doc（doc_id 全局唯一、memo 稳定，
      // 是比"最新"更强的句柄；已剪过 _pruned 的 doc 不进 pending，天然防重复删）。未指定 doc_id
      // → 退回最新一份未消费 doc。两种路径都一次性消费（splice），防同一 doc 被后续 discard 再消费。
      let idx;
      if (dl.doc_id !== undefined) {
        idx = pending.findIndex((p) => out[p].doc.doc_id === dl.doc_id);
        if (idx === -1) {
          // 指定了不存在/已消费的 doc_id → 拒绝消费（防幻指），记录事件
          events.push({ type: 'compress_skip', reason: 'doc_id_mismatch', doc_id: dl.doc_id, at: i });
          continue;
        }
      } else {
        idx = pending.length - 1; // 最新一份未消费文档
      }
      const target = out[pending[idx]];
      const { doc: pruned, removed, removedRows, left } = pruneDoc(target.doc, dl.lines);
      out[pending[idx]].doc = pruned;
      pending.splice(idx, 1);
      events.push({ type: 'discard_applied', doc_id: target.doc.doc_id, n_del: removed.length, n_left: left, lines: removed, removed_rows: removedRows, at: i });
    }
  }
  return { messages: out, events };
}