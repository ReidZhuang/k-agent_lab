// ==========================================================================
// U5 tokenizer —— 本地、确定性、零依赖的 token 估算
// ==========================================================================
// 目的：不做真实 tokenizer（无依赖性），用一个**透明规则**给文本/消息算口数：
//   - 中日韩字符：1 字符 ≈ 1 token
//   - 拉丁/数字连串（单词/数字/百分比）：每 ≈4 字符折算 1 token（向上取整）
//   - 其它标点/空白：不计（透明性优先；相对差值即"节省量"仍是单调一致的）
// 当 provider 回传 usage 时，用 correctionFactor 把估算校正到实测口径（见 counter.js）。
// ==========================================================================

const CJK_RE = /[一-鿿㐀-䶿぀-ヿ가-힯、-〿！-～]/g;
const LATIN_RE = /[A-Za-z0-9][A-Za-z0-9._%+\-/：:]*/g;

/**
 * 文本 → 估算 token 数（确定性：同一输入恒同输出）。
 * @param {string} text
 * @returns {number}
 */
export function estimateTokens(text) {
  if (typeof text !== 'string' || text.length === 0) return 0;
  let n = (text.match(CJK_RE) ?? []).length;
  for (const run of (text.match(LATIN_RE) ?? [])) n += Math.ceil(run.length / 4);
  return n;
}

/** 单条消息 → 估算 token（序列化后统计） */
export function messageTokens(msg) {
  if (msg === null || msg === undefined) return 0;
  return estimateTokens(typeof msg === 'string' ? msg : JSON.stringify(msg));
}

/** 消息数组 → 估算 token（逐条累加） */
export function messagesTokens(messages) {
  if (!Array.isArray(messages)) return 0;
  let n = 0;
  for (const m of messages) n += messageTokens(m);
  return n;
}

/**
 * 估算归一化系数：当拿到实测 usage 时，factor = 实测/估算，用于把后续估折算到实测口径。
 * @param {number} usageTokens provider 实测 token 数
 * @param {number} estimateTokens_ 同内容本地估算
 * @returns {{factor: number, punitive: boolean}} punitive=true 表示估算为 0 而实测 >0（防除零）
 */
export function correctionFactor(usageTokens, estimateTokens_) {
  if (usageTokens === 0 || !estimateTokens_) return { factor: 1, punitive: estimateTokens_ === 0 && usageTokens > 0 };
  return { factor: usageTokens / estimateTokens_, punitive: false };
}

/** 估算值 × 校正系数（保底为原估算） */
export function applyCorrection(estimate, factor) {
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  return Math.max(estimate, Math.round(estimate * f));
}