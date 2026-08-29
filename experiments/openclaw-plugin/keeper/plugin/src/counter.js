// ==========================================================================
// U5 counter —— 运行期 token 累计（逐轮记录 → 汇总/均值/环比/usage 回填）
// ==========================================================================
import { estimateTokens, messageTokens } from './tokenizer.js';

/**
 * 创建运行期 token 计数器。每轮调用 recordRound()，结束时取 stats()。
 * usage 存在时用实测；缺失时用估算并标 usage_unavailable。
 */
export function createTokenCounter() {
  const rounds = [];
  let usageRounds = 0;

  function recordRound({ input, output, usage }) {
    const u = usage ?? null;
    const hasUsage = Boolean(u && (u.prompt_tokens !== undefined || u.total_tokens !== undefined));
    if (hasUsage) usageRounds++;
    rounds.push({
      input: hasUsage && u.prompt_tokens !== undefined ? u.prompt_tokens : input,
      output: hasUsage && u.completion_tokens !== undefined ? u.completion_tokens : output,
      input_est: input ?? 0,
      output_est: output ?? 0,
      usage: u ?? null,
      usage_unavailable: !hasUsage,
    });
    return { ok: true, round: rounds.length };
  }

  /** 记录"压缩前后"的节省量（供驾驶舱 Token 面板逐轮展示） */
  function recordSaving({ before, after }) {
    return { saved: Math.max(0, before - after), before, after };
  }

  function stats() {
    if (rounds.length === 0) return { rounds: 0 };
    const inputTotal = rounds.reduce((s, r) => s + r.input, 0);
    const outputTotal = rounds.reduce((s, r) => s + r.output, 0);
    const n = rounds.length;
    const last = rounds[n - 1];
    const prev = n >= 2 ? rounds[n - 2] : null;
    return {
      rounds: n,
      input_total: inputTotal,
      output_total: outputTotal,
      total: inputTotal + outputTotal,
      input_avg: Math.round(inputTotal / n),
      output_avg: Math.round(outputTotal / n),
      usage_rounds: usageRounds,
      usage_unavailable: usageRounds === 0,
      // 环比：最新一轮相对上一轮的输入增/减
      input_delta: prev ? last.input - prev.input : null,
      latest_round: last,
    };
  }

  return { recordRound, recordSaving, stats };
}

/** 便捷：估算一个消息数组的输入规模（供 recordRound 传 input 前使用） */
export { estimateTokens, messageTokens };
export function estimateInputTokens(messages) {
  return messages.reduce((s, m) => s + messageTokens(m), 0);
}