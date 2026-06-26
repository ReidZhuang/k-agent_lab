"""本地 token 计算器

依靠本地数据（消息列表、回复文本），用 tiktoken 计算 token 消耗，
不依赖 API 返回的 usage 字段。

设计目标：
  - 透明：计数逻辑可审计，每步可验证
  - 一致：实验组和对照组用同一套公式，对比公平
  - 独立：纯本地计算，不依赖 API 响应

计数方法（两套可切换）：
  1. "json" 模式：将 messages JSON 序列化后对完整字符串计 token
     → 最透明，用户可直接看到被计数的文本
  2. "chat" 模式：模拟 API 的 chat 模板格式计 token
     → 每消息 4 overhead + role token + content token + tool_calls token
     → 更接近 API 实际计数

用法：
    calc = TokenCalculator()
    # 计算 prompt token
    result = calc.count_prompt(messages, mode="json")
    # 计算 completion token
    result = calc.count_completion(response_text)
    # 一次性统计（含分解）
    report = calc.full_report(messages, response_text)
"""

import json
import tiktoken


# ——— 默认编码 ———
# cl100k_base 是 GPT-4/GPT-3.5 使用的编码。
# DeepSeek 的编码与 cl100k_base 接近但不完全一致，
# 但对于实验组/对照组的公平对比来说一致性好于精确性。
_DEFAULT_ENCODING = "cl100k_base"


class TokenCalculator:
    """本地 token 计算器。"""

    def __init__(self, model: str = "deepseek-v4-flash",
                 encoding_name: str = _DEFAULT_ENCODING):
        self.model = model
        self.encoding_name = encoding_name
        self.encoding = tiktoken.get_encoding(encoding_name)

    # ──────────────────────────
    # 底层：文本 → token 数
    # ──────────────────────────

    def count_text(self, text: str) -> int:
        """返回 text 的 token 数（核心方法）。"""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    # ──────────────────────────
    # prompt 计数（两套模式）
    # ──────────────────────────

    def count_prompt(self, messages: list[dict],
                     mode: str = "json") -> dict:
        """计算 prompt token 消耗。

        Args:
            messages: 要发送的消息列表
            mode: "json" — JSON 序列化整个 messages 后计数（推荐）
                  "chat" — 逐消息模拟 chat 模板计数

        Returns:
            {"total_tokens": int, "mode": str, "details": list[dict], ...
             "json_serialized": str (仅 json mode)}
        """
        if mode == "json":
            return self._count_prompt_json(messages)
        elif mode == "chat":
            return self._count_prompt_chat(messages)
        else:
            raise ValueError(f"未知 mode: {mode}，可选: json, chat")

    def _count_prompt_json(self, messages: list[dict]) -> dict:
        """JSON 序列化后对整个文本计 token。

        将 messages 序列化为 JSON（无空格、无缩进），
        然后对整个 JSON 字节文本计 token。
        这相当于把"你实际发送给 API 的文本"做 token 计算。

        注意：真实 API 调用的 token 计算方式不是直接对 JSON 文本
        做 tokenization，而是对 chat template 做。但 JSON 模式的优势
        在于完全透明——用户看到的就是被计数的文本。
        """
        serialized = json.dumps(messages, ensure_ascii=False,
                                indent=None, separators=(",", ":"))
        total = self.count_text(serialized)

        # 分解：只对 tool 和已注入 system 的消息做 content 分解
        msg_details = []
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "") or ""
            content_tokens = self.count_text(content)
            entry = {
                "role": role,
                "content_tokens": content_tokens,
                "tool_call_count": len(msg.get("tool_calls") or []),
            }
            msg_details.append(entry)

        return {
            "mode": "json",
            "total_tokens": total,
            "serialized_length": len(serialized),
            "message_count": len(messages),
            "details": msg_details,
            "json_serialized": serialized,  # 方便调试查看
        }

    def _count_prompt_chat(self, messages: list[dict]) -> dict:
        """模拟 chat template 计 token。

        公式（对照 OpenAI 公开的计数方式）：
          每消息 4 token（模拟 <|im_start|>role\n 和 <|im_end|>\n）+
          role 字符串 + content 字符串 +
          name 字段（+1 token）+
          tool_calls JSON 序列化

          额外 +3 token 用于回复起始的 <|im_start|>assistant

        这个模式更接近 API 实际计数，但不如 json 模式透明。
        """
        total = 0
        details = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""

            overhead = 4  # 模拟 role marker + format overhead
            role_t = self.count_text(role)
            content_t = self.count_text(content)
            name_t = 0
            tool_t = 0

            # name 字段
            if "name" in msg:
                name_t += 1 + self.count_text(msg["name"])

            # tool_calls 字段
            for tc in msg.get("tool_calls") or []:
                tc_str = json.dumps(tc, ensure_ascii=False,
                                    indent=None, separators=(",", ":"))
                tool_t += self.count_text(tc_str)

            msg_total = overhead + role_t + content_t + name_t + tool_t
            total += msg_total
            details.append({
                "role": role,
                "role_tokens": role_t,
                "content_tokens": content_t,
                "name_extra": name_t,
                "tool_calls_tokens": tool_t,
                "overhead": overhead,
                "total": msg_total,
            })

        # 回复起始标记
        priming = 3
        total += priming

        return {
            "mode": "chat",
            "total_tokens": total,
            "priming": priming,
            "message_count": len(messages),
            "details": details,
        }

    # ──────────────────────────
    # completion 计数
    # ──────────────────────────

    def count_completion(self, text: str) -> dict:
        """计算 completion token 消耗。

        Args:
            text: assistant 回复的完整文本（含 content + tool_calls 的 JSON）

        Returns:
            {"total_tokens": int, "text_length": int}
        """
        tokens = self.count_text(text or "")
        return {
            "total_tokens": tokens,
            "text_length": len(text or ""),
        }

    # ──────────────────────────
    # 完整统计 + 对比
    # ──────────────────────────

    def full_report(self, messages: list[dict],
                    response_text: str,
                    mode: str = "json",
                    api_usage: dict | None = None) -> dict:
        """一次计算 prompt + completion 的完整报告。

        Args:
            messages: 发送的消息列表
            response_text: assistant 回复文本
            mode: "json" 或 "chat"
            api_usage: API 返回的 usage dict（可选），用于对比

        Returns:
            包含 prompt、completion、total、对比的完整 dict
        """
        prompt = self.count_prompt(messages, mode=mode)
        completion = self.count_completion(response_text)
        total = prompt["total_tokens"] + completion["total_tokens"]

        result = {
            "model": self.model,
            "encoding": self.encoding_name,
            "mode": mode,
            "prompt": prompt,
            "completion": completion,
            "total_tokens": total,
        }

        if api_usage:
            api_prompt = api_usage.get("prompt_tokens", 0)
            api_completion = api_usage.get("completion_tokens", 0)
            api_total = api_usage.get("total_tokens", 0)
            result["api_usage"] = {
                "prompt_tokens": api_prompt,
                "completion_tokens": api_completion,
                "total_tokens": api_total,
            }
            result["diff"] = {
                "prompt": prompt["total_tokens"] - api_prompt,
                "completion": completion["total_tokens"] - api_completion,
                "total": total - (api_total or api_prompt + api_completion),
            }

        return result

    # ──────────────────────────
    # 格式化输出
    # ──────────────────────────

    def format_one_line(self, report: dict) -> str:
        """一行概要。"""
        p = report["prompt"]["total_tokens"]
        c = report["completion"]["total_tokens"]
        parts = [f"prompt={p}", f"completion={c}", f"total={p+c}"]

        if "api_usage" in report:
            api = report["api_usage"]
            diff = report["diff"]
            pd = diff["prompt"]
            cd = diff["completion"]
            api_parts = [f"API(p={api['prompt_tokens']},c={api['completion_tokens']})"]
            if pd or cd:
                api_parts.append(f"Δ(p={pd:+d},c={cd:+d})")
            parts.append(" vs " + " ".join(api_parts))

        return " | ".join(parts)

    def format_verbose(self, report: dict) -> str:
        """详细分解（多行文本）。"""
        lines = []
        lines.append(f"📊 Token 消耗报告 ({report['mode']} mode)")
        lines.append(f"   模型: {report['model']} | 编码: {report['encoding']}")
        lines.append("")

        # prompt 分解
        prompt = report["prompt"]
        lines.append(f"┌─ Prompt ({prompt['total_tokens']} tokens, {prompt['message_count']} msg)")
        for i, d in enumerate(prompt.get("details", [])):
            if prompt["mode"] == "chat":
                ct = d["content_tokens"]
                extra_parts = []
                if d.get("tool_calls_tokens"):
                    extra_parts.append(f"tc={d['tool_calls_tokens']}")
                if d.get("name_extra"):
                    extra_parts.append(f"name+{d['name_extra']}")
                extra = f" ({','.join(extra_parts)})" if extra_parts else ""
                lines.append(f"  ├─ [{i}] {d['role']}: content={ct}{extra} → msg={d['total']}")
            else:
                lines.append(f"  ├─ [{i}] {d['role']}: content_tokens={d['content_tokens']}")
        lines.append(f"  └─ {prompt['message_count']} 条消息 = {prompt['total_tokens']} tokens")

        # completion
        comp = report["completion"]
        lines.append(f"┌─ Completion ({comp['total_tokens']} tokens, {comp['text_length']} chars)")
        lines.append(f"  └─ {comp['total_tokens']} tokens")

        # total
        lines.append(f"└─ 总计: {report['total_tokens']} tokens")

        # API 对比
        if "api_usage" in report:
            api = report["api_usage"]
            diff = report["diff"]
            lines.append("")
            lines.append("  API 对比:")
            lines.append(f"    本地:   prompt={prompt['total_tokens']:>6}  completion={comp['total_tokens']:>6}  total={report['total_tokens']:>6}")
            lines.append(f"    API:    prompt={api['prompt_tokens']:>6}  completion={api['completion_tokens']:>6}  total={api['total_tokens']:>6}")
            lines.append(f"    差异:   prompt={diff['prompt']:+d}  completion={diff['completion']:+d}  total={diff['total']:+d}")

        return "\n".join(lines)


# ──────────────────────────────────
# 便捷函数（不用实例化也能用）
# ──────────────────────────────────

def quick_count_prompt(messages: list[dict]) -> int:
    """快速计算 prompt token 数（json 模式）。"""
    return TokenCalculator().count_prompt(messages)["total_tokens"]


def quick_count_completion(text: str) -> int:
    """快速计算 completion token 数。"""
    return TokenCalculator().count_completion(text)["total_tokens"]


def human_readable(tokens: int) -> str:
    """将 token 数转为可读格式。"""
    if tokens < 1000:
        return f"{tokens} tok"
    elif tokens < 100000:
        return f"{tokens/1000:.1f}k tok"
    else:
        return f"{tokens/1000:.0f}k tok"
