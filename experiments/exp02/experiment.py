#!/usr/bin/env python3
"""
实验组 — OpenClaw 架构 + 行号标记 + 上下文压缩

架构特点：
  - system prompt 由 prompt_assembler 从 .md 文件动态组装
  - tool definition 精简（~100 chars），详细规则在 SKILL.md
  - Round 1 不带 skill 规则，Round 2 注入
  - 压缩逻辑同 v1.3

使用方式：
  DEEPSEEK_API_KEY=xxx python experiment.py
"""

import os, sys, json, time, copy, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.prompt_assembler import build_prompt
from core.tools import WEB_SEARCH_TOOL
from core.tagger import inject_line_tags, reconstruct_content, format_compressed_citation
from core.token_calculator import TokenCalculator
from core.search import (
    API_KEY, DEFAULT_MODEL, DEFAULT_MAX_TOKENS, API_BASE_URL,
    USER_QUERY, RESULTS_DIR, search_realtime,
)

client = __import__("openai").OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

_RUN_ID = uuid.uuid4().hex[:12]
_calc = TokenCalculator()
_INTERACTION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interactions")


def _strip_line_tags(text: str) -> str:
    """移除行首的「数字~+空格」标记和 CITATION_BLOCK 包裹标记，还原为纯文本。"""
    import re
    text = re.sub(r"^\d+~\s?", "", text, flags=re.MULTILINE)
    return text.replace("<<<CITATION_BLOCK>>>", "").replace("<<<END_CITATION_BLOCK>>>", "")


def _save_interaction(run_id: str, round_num: int, phase: str, data: object):
    """保存完整交互数据到 interaction 目录。"""
    os.makedirs(_INTERACTION_DIR, exist_ok=True)
    path = os.path.join(_INTERACTION_DIR, f"{run_id}_R{round_num}_{phase}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_human_readable(run_id: str, message_snapshots: list, rounds_log: list, final_answer: str):
    """实验结束后生成可读的请求原文和回复原文 TXT 文件。"""
    from core.tagger import format_compressed_citation
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

    # ── 重建 messages 最终状态（含压缩），用于快照 ──
    # 用 snapshots 列表来重建：snapshot[0] 是 R1 发送前

    # ── 文件 1: request_messages ──
    lines = []
    lines.append(f"════════════════════════════════════════")
    lines.append(f"  实验组交互全录 — 每轮 API 调用前快照")
    lines.append(f"  Run ID: {run_id}")
    lines.append(f"════════════════════════════════════════\n")

    for rn, msgs in message_snapshots:
        lines.append(f"{'='*70}")
        lines.append(f"  Round {rn} — 发送前 messages（{len(msgs)} 条）")
        lines.append(f"{'='*70}\n")

        for idx, msg in enumerate(msgs):
            role = msg["role"]
            if role == "system":
                label = f"message[{idx}] role=system [系统指令]"
            elif role == "user":
                label = f"message[{idx}] role=user [用户提问]"
            elif role == "assistant":
                tc = msg.get("tool_calls", [])
                if tc:
                    try:
                        q = json.loads(tc[0]["function"]["arguments"]).get("query", "")[:35]
                    except Exception:
                        q = "?"
                    label = f"message[{idx}] role=assistant [工具调用: {q}]"
                else:
                    label = f"message[{idx}] role=assistant [回复]"
            elif role == "tool":
                c = msg["content"]
                if not c.strip():
                    label = f"message[{idx}] role=tool [已清空]"
                elif "### 重要性:" in c[:80]:
                    label = f"message[{idx}] role=tool [已压缩]"
                else:
                    lc = len([l for l in c.split("\n") if l.strip() and l[0].isdigit() and "~" in l[:6]])
                    if lc:
                        label = f"message[{idx}] role=tool [带行号] ({lc} 行)"
                    else:
                        label = f"message[{idx}] role=tool [已压缩]"

            lines.append(f"── {label} ──\n")
            if role == "assistant":
                lines.append(f"content: {msg.get('content', '')}")
                for t in msg.get("tool_calls", []):
                    lines.append("tool_calls:")
                    lines.append(json.dumps(t["function"], ensure_ascii=False, indent=2))
            else:
                lines.append(msg["content"])
            lines.append("")

    lines.append(f"{'='*70}")
    lines.append(f"  Final Answer — LLM 最终回答")
    lines.append(f"{'='*70}\n")
    lines.append(final_answer)
    lines.append("")

    req_path = os.path.join(results_dir, f"{run_id}_request_messages.txt")
    with open(req_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── 文件 2: llm_responses ──
    lines2 = []
    lines2.append(f"════════════════════════════════════════")
    lines2.append(f"  实验组 LLM 回复全录")
    lines2.append(f"  Run ID: {run_id}")
    lines2.append(f"════════════════════════════════════════\n")

    for r in rounds_log:
        rn = r["round"]
        findings = r.get("findings", [])
        lines2.append(f"{'='*70}")
        lines2.append(f"  Round {rn} — LLM 回复（finish=tool_calls）")
        lines2.append(f"{'='*70}\n")
        lines2.append("【工具调用 web_search】")
        lines2.append(f"  参数 query: {r['query']}")
        if findings:
            lines2.append(f"  参数 key_findings_used:")
            for fi, f in enumerate(findings):
                lines2.append(f"    [{fi}]")
                lines2.append(f"         content:  {f.get('content', '')}")
                lines2.append(f"         priority: {f.get('priority', '')}")
                lines2.append(f"         context:  {f.get('context', '')}")
        else:
            lines2.append(f"  参数 key_findings_used: (无)")
        lines2.append("")

    lines2.append(f"{'='*70}")
    lines2.append(f"  Final Answer — LLM 回复（finish=stop）")
    lines2.append(f"  回答长度: {len(final_answer)} chars")
    lines2.append(f"{'='*70}\n")
    lines2.append(final_answer)
    lines2.append("")

    resp_path = os.path.join(results_dir, f"{run_id}_llm_responses.txt")
    with open(resp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines2))

    print(f"\n📄 交互输出:")
    print(f"   {req_path}")
    print(f"   {resp_path}")


def main():
    run_id = _RUN_ID
    print(f"{'='*65}")
    print(f"  实验组 — OpenClaw 架构 + 行号标记 + 压缩")
    print(f"  Run ID: {run_id}")
    print(f"{'='*65}")

    loaded_skills: set[str] = set()
    messages = [
        {"role": "system", "content": build_prompt("full", loaded_skills=set())},
        {"role": "user", "content": USER_QUERY},
    ]

    rounds_log = []
    final_answer = None
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_local_prompt_tokens = 0
    total_local_completion_tokens = 0
    total_saved_chars = 0
    message_snapshots = []  # (round_num, messages_snapshot_before_api)

    last_line_map = None  # 上一次注入的 tool result 的 line_map

    while True:
        round_num = len(rounds_log) + 1
        print(f"\n{'─'*60}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*60}")

        tool_chars = sum(len(m.get("content", "")) for m in messages if m["role"] == "tool")
        print(f"  消息: {len(messages)} 条, tool result 累计 {tool_chars} chars")
        print(f"  已加载技能: {loaded_skills}")

        # 每次调用前更新 system prompt（Round 1 有技能列表，Round 2+ 追加已激活的技能正文）
        messages[0]["content"] = build_prompt("full", loaded_skills=loaded_skills)

        # 保存本轮请求原文
        _save_interaction(run_id, round_num, "request", {
            "messages": messages,
            "model": DEFAULT_MODEL,
            "max_tokens": DEFAULT_MAX_TOKENS,
        })

        # 快照：发送前的 messages 状态（用于生成可读交互文件）
        message_snapshots.append((round_num, copy.deepcopy(messages)))

        try:
            t_api = time.time()
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": f"exp02_experiment_{run_id}"},
            )
            api_time = time.time() - t_api
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message

        # 保存本轮 LLM 回复原文
        response_dict = {
            "finish_reason": finish,
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in (msg.tool_calls or [])
            ],
        }
        model_extra = getattr(msg, "model_extra", None) or {}
        if model_extra.get("reasoning_content"):
            response_dict["reasoning_content"] = model_extra["reasoning_content"]
        _save_interaction(run_id, round_num, "response", response_dict)
        # ── API token 计数（参考） ──
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
            findings = args.get("key_findings_used", []) or []

            c_count = sum(1 for f in findings if f.get("priority") == "critical")
            u_count = sum(1 for f in findings if f.get("priority") == "useful")
            r_count = sum(1 for f in findings if f.get("priority") == "related")

            print(f"\n  🔍 {query}")
            print(f"  📋 引用 {len(findings)} 条 (c:{c_count} u:{u_count} r:{r_count})")

            # ── 检查是否为 null 占位引用（无引用） ──
            is_null_citations = all(
                f.get("content") is None for f in findings
            ) if findings else True

            # ── 压缩上一轮的 tool result（每轮必须处理，确保旧内容无行号） ──
            saved_chars_this = 0
            if round_num >= 2 and last_line_map is not None:
                old_content = messages[2 * round_num - 1].get("content", "")

                if not findings or is_null_citations:
                    # 无引用：清空旧 tool 上下文
                    messages[2 * round_num - 1]["content"] = ""
                    saved_chars_this = len(old_content)
                    total_saved_chars += saved_chars_this
                    print(f"  🔧 无引用，清空第 {round_num-1} 轮 tool 上下文 (省 {saved_chars_this} chars)")
                else:
                    compressed = format_compressed_citation(findings, last_line_map)
                    COMPRESSED_MARK = "[已压缩]\n"

                    if len(compressed) < len(old_content):
                        compressed_marked = COMPRESSED_MARK + compressed
                        messages[2 * round_num - 1]["content"] = compressed_marked
                        saved_chars_this = len(old_content) - len(compressed_marked)
                        total_saved_chars += saved_chars_this
                        print(f"  🔧 压缩第 {round_num-1} 轮: {len(old_content)} → {len(compressed_marked)} chars (省 {saved_chars_this})")
                    else:
                        # 即使压缩不省字符，也必须剥离行号，确保旧数据无法被引用
                        stripped = _strip_line_tags(old_content)
                        stripped_marked = COMPRESSED_MARK + stripped
                        messages[2 * round_num - 1]["content"] = stripped_marked
                        saved_chars_this = len(old_content) - len(stripped_marked)
                        total_saved_chars += saved_chars_this
                        print(f"  🔧 跳过压缩第 {round_num-1} 轮，已剥离行号 (省 {saved_chars_this} chars)")

            # ── 打印引用详情 ──
            for i, f in enumerate(findings):
                line_ref = f.get("content", "")
                p = f.get("priority", "?")
                ctx = f.get("context", "")
                reconstructed = reconstruct_content(line_ref, last_line_map) if last_line_map else ""
                preview = reconstructed[:80] if reconstructed else "(无内容)"
                p_icon = {"critical": "🔴", "useful": "🟡", "related": "🟢"}.get(p, "⚪")
                print(f"    {p_icon} [{i}] [{p}] content={line_ref}")
                print(f"          ctx={ctx}")
                print(f"          → {preview}")

            # ── 真实搜索 ──
            t0 = time.time()
            search_result = search_realtime(query)
            search_time = time.time() - t0

            tagged_result, line_map = inject_line_tags(search_result)
            print(f"  📦 原始 {len(search_result)} chars → 标记后 {len(tagged_result)} chars ({search_time:.1f}s)")
            print(f"     共 {max(line_map.keys())+1 if line_map else 0} 行")

            # ── 记录本轮 ──
            round_entry = {
                "round": round_num,
                "query": query,
                "findings": copy.deepcopy(findings),
                "priority_counts": {"critical": c_count, "useful": u_count, "related": r_count},
                "raw_search_result": search_result,
                "tagged_search_result": tagged_result,
                "line_map": {str(k): v for k, v in line_map.items()},
                "search_result_len": len(tagged_result),
                "prompt_tokens": in_t,
                "completion_tokens": out_t,
                "local_prompt_tokens": local_prompt,
                "local_completion_tokens": local_completion,
                "tool_chars_before": tool_chars,
                "compressed_saved_chars": saved_chars_this,
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

            # ── 注入 tool message ──
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tagged_result})
            print(f"  ✅ 注入完成 ({len(messages)} 条消息)")

            # ── 激活 skill（后续轮次带完整规则） ──
            loaded_skills.add("cite-and-compress")
            last_line_map = line_map

    # ══════════════════════════
    # 汇总
    # ══════════════════════════
    total_c = sum(e["priority_counts"]["critical"] for e in rounds_log)
    total_u = sum(e["priority_counts"]["useful"] for e in rounds_log)
    total_r = sum(e["priority_counts"]["related"] for e in rounds_log)
    total_f = total_c + total_u + total_r

    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  Tool Call 轮次: {len(rounds_log)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'} ({len(final_answer or '')} chars)")
    print(f"  总引用: {total_f} (c:{total_c} u:{total_u} r:{total_r})")
    print(f"  总消耗(API): {total_prompt_tokens} in + {total_completion_tokens} out tokens")
    print(f"  总消耗(本地): {total_local_prompt_tokens} in + {total_local_completion_tokens} out tokens")
    print(f"  压缩节省: {total_saved_chars} chars")

    output = {
        "test_name": "experiment_exp02",
        "run_id": run_id,
        "arch": "openclaw_style",
        "model": DEFAULT_MODEL,
        "user_query": USER_QUERY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rounds": len(rounds_log),
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "final_answer_chars": len(final_answer or ""),
        "total_findings": total_f,
        "priority_summary": {"critical": total_c, "useful": total_u, "related": total_r},
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_local_prompt_tokens": total_local_prompt_tokens,
        "total_local_completion_tokens": total_local_completion_tokens,
        "total_saved_chars": total_saved_chars,
        "rounds": rounds_log,
    }

    save_path = os.path.join(RESULTS_DIR, f"experiment_{time.strftime('%Y%m%d_%H%M%S')}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📝 已保存: {save_path}")

    # 生成可读交互原文文件
    if final_answer:
        _save_human_readable(run_id, message_snapshots, rounds_log, final_answer)


if __name__ == "__main__":
    main()
