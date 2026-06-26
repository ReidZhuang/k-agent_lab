#!/usr/bin/env python3
"""
对照组 — 纯 OpenClaw agent，无引用系统、无行号、无压缩

架构特点：
  - system prompt = SOUL.md + AGENTS.md（无技能列表、无 PREFERENCES.md）
  - tool = 最简单的 web_search，仅 query 参数
  - 搜索结果原文返回，不打行号
  - 消息列表只增长，不修改，不压缩

使用方式：
  DEEPSEEK_API_KEY=xxx python control.py
"""

import os, sys, json, time, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.prompt_assembler import build_prompt
from core.tools import WEB_SEARCH_TOOL_PLAIN
from core.token_calculator import TokenCalculator
from core.search import (
    API_KEY, DEFAULT_MODEL, DEFAULT_MAX_TOKENS, API_BASE_URL,
    USER_QUERY, RESULTS_DIR, search_realtime,
)

client = __import__("openai").OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

_RUN_ID = uuid.uuid4().hex[:12]
_calc = TokenCalculator()


def main():
    run_id = _RUN_ID
    print(f"{'='*65}")
    print(f"  对照组（含 PREFERENCES.md）— 无引用、无行号、无压缩")
    print(f"  Run ID: {run_id}")
    print(f"{'='*65}")

    base_prompt = build_prompt("control")
    prefs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent", "PREFERENCES.md")
    with open(prefs_path, "r", encoding="utf-8") as f:
        prefs_content = f.read().strip()
    messages = [
        {"role": "system", "content": base_prompt + "\n\n" + prefs_content},
        {"role": "user", "content": USER_QUERY},
    ]

    rounds_log = []
    final_answer = None
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_local_prompt_tokens = 0
    total_local_completion_tokens = 0

    while True:
        round_num = len(rounds_log) + 1
        print(f"\n{'─'*60}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*60}")

        tool_chars = sum(len(m.get("content", "")) for m in messages if m["role"] == "tool")
        print(f"  消息: {len(messages)} 条, tool result 累计 {tool_chars} chars")

        try:
            t_api = time.time()
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_PLAIN],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": f"exp02_control_plain_{run_id}"},
            )
            api_time = time.time() - t_api
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else 0
        out_t = response.usage.completion_tokens if response.usage else 0
        total_prompt_tokens += in_t
        total_completion_tokens += out_t

        # ── 本地 token 计数（主用） ──
        response_text_for_counting = msg.content or ""
        if getattr(msg, "model_extra", None) and msg.model_extra.get("reasoning_content"):
            response_text_for_counting += msg.model_extra["reasoning_content"]
        if msg.tool_calls:
            for tc in msg.tool_calls:
                response_text_for_counting += json.dumps(
                    {"name": tc.function.name, "arguments": tc.function.arguments},
                    ensure_ascii=False,
                )
        local_prompt = _calc.count_prompt(messages)["total_tokens"]
        local_completion = _calc.count_completion(response_text_for_counting)["total_tokens"]
        total_local_prompt_tokens += local_prompt
        total_local_completion_tokens += local_completion

        print(f"  tokens: API(in={in_t},out={out_t}) 本地(in={local_prompt},out={local_completion}) | finish={finish} time={api_time:.1f}s")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 完成回答 ({len(final_answer)} chars)")
            break

        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name != "web_search":
                continue

            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                continue

            query = args.get("query", "")
            print(f"\n  🔍 {query}")

            # ── 原始搜索，无行号标记 ──
            t0 = time.time()
            search_result = search_realtime(query)
            search_time = time.time() - t0
            print(f"  📦 原始 {len(search_result)} chars ({search_time:.1f}s)")

            round_entry = {
                "round": round_num,
                "query": query,
                "search_result": search_result,
                "search_result_len": len(search_result),
                "prompt_tokens": in_t,
                "completion_tokens": out_t,
                "local_prompt_tokens": local_prompt,
                "local_completion_tokens": local_completion,
                "tool_chars_before": tool_chars,
            }
            rounds_log.append(round_entry)

            # ── 注入 assistant message ──
            asst_msg = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }],
            }
            model_extra = getattr(msg, "model_extra", None) or {}
            if model_extra.get("reasoning_content"):
                asst_msg["reasoning_content"] = model_extra["reasoning_content"]
            messages.append(asst_msg)

            # ── 注入完整 tool result（原文，无压缩） ──
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": search_result})
            print(f"  ✅ 注入完成 ({len(messages)} 条消息)")

    # ══════════════════════════
    # 汇总
    # ══════════════════════════
    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  Tool Call 轮次: {len(rounds_log)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'} ({len(final_answer or '')} chars)")
    print(f"  总消耗(API): {total_prompt_tokens} in + {total_completion_tokens} out tokens")
    print(f"  总消耗(本地): {total_local_prompt_tokens} in + {total_local_completion_tokens} out tokens")

    output = {
        "test_name": "control_exp02_with_prefs",
        "run_id": run_id,
        "arch": "openclaw_style_control_with_prefs",
        "model": DEFAULT_MODEL,
        "user_query": USER_QUERY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rounds": len(rounds_log),
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "final_answer_chars": len(final_answer or ""),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_local_prompt_tokens": total_local_prompt_tokens,
        "total_local_completion_tokens": total_local_completion_tokens,
        "rounds": rounds_log,
    }

    save_path = os.path.join(RESULTS_DIR, f"control_with_prefs_{time.strftime('%Y%m%d_%H%M%S')}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📝 已保存: {save_path}")


if __name__ == "__main__":
    main()
