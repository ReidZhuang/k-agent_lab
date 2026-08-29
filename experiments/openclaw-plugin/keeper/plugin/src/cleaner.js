// ==========================================================================
// U3 cleaner —— 从工具参数剥离辅助字段（discard_lines 等）
// ==========================================================================
// 设计依据：PLUGIN_DESIGN_V2.md —— 模型在工具调用的参数里带 discard_lines，
// 但这些字段不是真工具的合法参数，必须在调用前剥离（rest 发给真工具，aux 留给插件）。
// rest = 浅拷贝的新对象，**绝不改动调用方的原对象**。
// ==========================================================================

/** 会被剥离的辅助字段（可配置；默认集合） */
export const DEFAULT_AUX_KEYS = Object.freeze(['discard_lines']);

/**
 * 拆分参数：rest = 去掉辅助字段后的真工具参数；aux = 被剥离字段的 {字段名: 值}。
 * @param {object|null|undefined} params 工具参数（来自 before_tool_call 拦截）
 * @param {{auxKeys?: string[]}} [opts]
 * @returns {{rest: object, aux: object}}
 */
export function stripAuxParams(params, opts = {}) {
  const auxKeys = opts.auxKeys ?? DEFAULT_AUX_KEYS;
  if (params === null || params === undefined || typeof params !== 'object' || Array.isArray(params)) {
    // 非对象参数：无从剥离，原样返回（防御：不让插件在畸形输入上崩）
    return { rest: params, aux: {} };
  }
  const rest = { ...params };
  const aux = {};
  for (const key of auxKeys) {
    if (Object.prototype.hasOwnProperty.call(params, key)) {
      aux[key] = params[key];
      delete rest[key];
    }
  }
  return { rest, aux };
}