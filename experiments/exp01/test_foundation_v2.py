#!/usr/bin/env python3
"""
Step 1 v2 — 超长文本 + 优先级分级 + 全量日志

增强点：
  1. 数据集 6-9KB/轮，模拟真实搜索的信息量
  2. key_findings_used 改为 {content, priority} 结构，critical/related 两档
  3. 循环最多 10 轮，充分展示多轮引用链
  4. 打印每次发送给 LLM 和 LLM 返回的完整内容
"""

import os
import json
import time
import sys
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING,
    RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    MAX_ROUNDS,
    API_BASE_URL,
)
from search_backend import web_search, extract_key_snippets, count_chars

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("❌ 错误: 未设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULT_DIR, exist_ok=True)
TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")

USER_QUERY = (
    "请分多步深入研究宁德时代：\n"
    "第一步：搜索其2024年财报核心数据（营收、净利润、增长、各业务板块）；\n"
    "第二步：基于第一步发现，深入搜索其储能业务的增长情况与毛利率；\n"
    "第三步：搜索比亚迪电池业务，与宁德时代做对比分析；\n"
    "第四步：基于以上对比，分析行业竞争格局和未来展望。\n"
    "注意：一步一步来，每步必须引用上一步搜索到的具体原文数据。"
)


# ==============================================================
# 格式化打印
# ==============================================================

def box(text: str, char: str = "─"):
    lines = text.split("\n")
    width = max(len(l) for l in lines) if lines else 40
    width = min(width, 120)
    return f" {char * (width+2)}\n│ {text} │\n {char * (width+2)}"


def print_separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def print_messages_summary(messages: list, label: str = "当前消息队列"):
    """打印消息队列的摘要"""
    print(f"\n── {label} ──")
    print(f"  总消息数: {len(messages)}")
    total_in = 0
    total_out = 0
    for i, msg in enumerate(messages):
        role = msg["role"]
        content = msg.get("content", "")
        tc = msg.get("tool_calls")
        tcid = msg.get("tool_call_id")

        if role == "system":
            print(f"    [{i}] system ({count_chars(content)} chars, {len(content.split())} tokens)")
        elif role == "user":
            content_preview = content[:60].replace("\n", " ") if content else ""
            print(f"    [{i}] user ({count_chars(content)} chars): {content_preview}...")
        elif role == "assistant":
            if tc:
                names = [t["function"]["name"] for t in tc]
                print(f"    [{i}] assistant (tool_call: {names})")
            elif content:
                print(f"    [{i}] assistant ({count_chars(content)} chars, 最终回答)")
                total_out += count_chars(content)
            else:
                print(f"    [{i}] assistant (空)")
        elif role == "tool":
            tool_len = count_chars(content) if content else 0
            print(f"    [{i}] tool (result: {tool_len} chars, id={tcid[:12]}...)")
            total_in += tool_len
    print(f"  tool result 总计: {total_in} chars | LLM 输出总计: {total_out} chars")


def print_tool_definition(tool: dict):
    """打印 tool 定义的关键部分"""
    func = tool["function"]
    print(f"\n── 可用工具 ──")
    print(f"  名称: {func['name']}")
    print(f"  描述: {func['description'][:200].replace(chr(10), ' ')}")
    params = func["parameters"]["properties"]
    for pname, pdef in params.items():
        ptype = pdef.get("type", "?")
        print(f"  参数: {pname} ({ptype}, required)")
        desc = pdef.get("description", "")[:100].replace("\n", " ")
        if pname == "key_findings_used":
            items = pdef.get("items", {})
            item_props = items.get("properties", {})
            print(f"    └── items: {{content (str), priority (critical|related)}}")
            print(f"    └── {desc}")
        else:
            print(f"    └── {desc}")


def print_llm_response(choice, response_usage=None):
    """打印 LLM 响应的完整内容"""
    finish = choice.finish_reason
    msg = choice.message
    usage = response_usage

    in_tokens = usage.prompt_tokens if usage else "?"
    out_tokens = usage.completion_tokens if usage else "?"
    print(f"\n── LLM 响应 ──")
    print(f"  finish_reason: {finish}")
    print(f"  tokens: in={in_tokens}, out={out_tokens}")

    if finish == "stop":
        text = (msg.content or "")[:500]
        print(f"  最终回答 (前500字):")
        print(f"  ┌─{'─' * 60}")
        for line in text.split("\n"):
            print(f"  │ {line}")
        print(f"  └─{'─' * 60}")
        if msg.content and len(msg.content) > 500:
            print(f"  ... (共 {count_chars(msg.content)} 字)")
        return

    if finish == "tool_calls" and msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"  tool_call id: {tc.id[:20]}...")
            print(f"  function: {tc.function.name}")
            try:
                args = json.loads(tc.function.arguments)
                print(f"  arguments (pretty):")
                print(json.dumps(args, ensure_ascii=False, indent=4))
            except json.JSONDecodeError:
                print(f"  arguments (raw): {tc.function.arguments[:300]}")


def print_tool_result(search_text: str):
    """打印即将注入的 tool result"""
    snippets = extract_key_snippets(search_text)
    print(f"\n── 注入 tool result ──")
    print(f"  {len(snippets)} 条结果, {count_chars(search_text)} chars")
    for s in snippets:
        # 截断显示
        short_snippet = s["snippet"][:150] + "..." if len(s["snippet"]) > 150 else s["snippet"]
        print(f"\n  [{s['idx']}] {s['title'][:70]}")
        print(f"      {short_snippet}")


def print_references(findings: list, prev_result_text: str):
    """打印并分析引用

    Args:
        findings: [{content, priority}, ...] 或旧版字符串列表
        prev_result_text: 上一轮的 tool result 全文
    """
    if not findings:
        print("  ⚠️ 本轮未引用任何数据")
        return

    is_old_format = isinstance(findings[0], str) if findings else False
    r1_lower = prev_result_text.lower()

    print(f"\n── 引用分析 (key_findings_used) ──")
    print(f"  总条目: {len(findings)}")

    matched = 0
    partial = 0
    unmatched = 0
    by_priority = {"critical": 0, "related": 0, "unknown": 0}

    for i, f in enumerate(findings):
        if is_old_format:
            content = f
            priority = "unknown"
        else:
            content = f.get("content", "")
            priority = f.get("priority", "unknown")

        by_priority[priority] = by_priority.get(priority, 0) + 1
        content_preview = content[:120].replace("\n", " ")

        # 验证
        content_lower = content.lower().strip()
        if content_lower in r1_lower:
            status = "✅"
            matched += 1
            evidence = "原文包含"
        else:
            # 关键词匹配
            import re
            numbers = re.findall(r'[\d,.]+[万亿%倍千百万亿元GWh]*', content)
            matched_terms = [n for n in numbers if n.lower() in r1_lower]
            unmatched_terms = [n for n in numbers if n.lower() not in r1_lower]

            if matched_terms and not unmatched_terms:
                status = "✅"
                matched += 1
                evidence = f"数字匹配: {matched_terms}"
            elif matched_terms:
                status = "⚠️"
                partial += 1
                evidence = f"部分匹配: +{matched_terms} / -{unmatched_terms}"
            else:
                status = "❌"
                unmatched += 1
                evidence = "原文未找到"

        print(f"\n  [{i}] {status} {priority.upper():8s} | {content_preview}")
        print(f"       {evidence}")

    total = len(findings)
    acc = (matched + partial * 0.5) / total if total > 0 else 0
    print(f"\n  汇总: 精确{matched} + 部分{partial} + 未匹配{unmatched} = {total}")
    print(f"  优先级分布: critical={by_priority.get('critical',0)}, "
          f"related={by_priority.get('related',0)}")
    print(f"  加权准确率: {acc:.0%}")

    return {
        "total": total,
        "matched": matched,
        "partial": partial,
        "unmatched": unmatched,
        "by_priority": by_priority,
        "accuracy": acc,
        "details": [
            {"content": f.get("content","") if not is_old_format else f,
             "priority": f.get("priority","unknown") if not is_old_format else "unknown",
             "status": status}
            for f, status in zip(findings, ["matched"]*matched + ["partial"]*partial + ["unmatched"]*unmatched)
        ] if not is_old_format else []
    }


# ==============================================================
# 主流程
# ==============================================================

def main():
    print(f"{'=' * 66}")
    print(f"  Step 1 v2: 超长文本 + 优先级分级引用验证")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"  最大轮次: {MAX_ROUNDS}")
    print(f"  搜索数据: 3 组预取数据, 每组 6-9KB")
    print(f"{'=' * 66}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    round_data = {}
    final_answer = None
    all_analyses = []

    # 打印初始状态
    print_messages_summary(messages, "初始消息队列")
    print_tool_definition(WEB_SEARCH_TOOL_WITH_REASONING)

    # ---- Agent Loop ----
    for round_num in range(1, MAX_ROUNDS + 1):
        print_separator(f"第 {round_num} 轮")

        # 打印本轮要发送的消息
        print_messages_summary(messages, f"发送给 LLM 的消息 ({len(messages)} 条)")

        # ---- 调用 LLM ----
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_v2_test"},
            )
        except Exception as e:
            print(f"\n  ❌ API 调用异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message

        # 打印 LLM 响应
        print_llm_response(choice, response_usage=response.usage)

        # ---- 情况 1: LLM 停止 ----
        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 决定停止，研究工作完成")
            round_data[round_num] = {"role": "final_answer", "content_len": len(final_answer)}
            break

        # ---- 情况 2: LLM 调用工具 ----
        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]

            if tc.function.name != "web_search":
                print(f"  ⚠️ 未知工具调用: {tc.function.name}")
                continue

            # 解析 arguments
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError as e:
                print(f"  ❌ arguments 解析失败: {e}")
                continue

            query = args.get("query", "")
            # 扁平化参数：key_findings_used / gaps_identified / search_strategy 都是顶层参数
            findings = args.get("key_findings_used", [])
            gaps = args.get("gaps_identified", "")
            strategy = args.get("search_strategy", "")
            # 为保持向后兼容，也支持嵌套格式
            if not findings and "reasoning_analysis" in args:
                ra = args["reasoning_analysis"]
                if isinstance(ra, dict):
                    findings = ra.get("key_findings_used", findings)
                    gaps = ra.get("gaps_identified", gaps)
                    strategy = ra.get("search_strategy", strategy)
                elif isinstance(ra, str):
                    try:
                        ra_p = json.loads(ra)
                        findings = ra_p.get("key_findings_used", findings)
                    except: pass

            # ---- 执行搜索 ----
            print(f"\n  🔍 执行搜索: {query}")
            search_result = web_search(query, max_results=10)
            snippets = extract_key_snippets(search_result)
            print(f"  📦 返回 {len(snippets)} 条结果, {count_chars(search_result)} chars")

            # ---- 记录本轮数据 ----
            round_data[round_num] = {
                "role": "tool_call",
                "query": query,
                "key_findings_used": findings,
                "gaps_identified": gaps,
                "search_strategy": strategy,
                "search_result_length": count_chars(search_result),
                "search_result_snippets": len(snippets),
            }

            # ---- 打印 tool result（全量）----
            print_tool_result(search_result)

            # ---- 引用分析 ----
            if round_num >= 2:
                prev_data = round_data.get(round_num - 1, {})
                prev_result_text = prev_data.get("_full_result", "")

                round_data[round_num]["_full_result"] = search_result

                if findings:
                    analysis = print_references(findings, prev_result_text)
                    if analysis:
                        round_data[round_num]["reference_analysis"] = analysis
                        all_analyses.append(analysis)
                else:
                    print("\n  ⚠️ 本轮未提供引用！")
            else:
                round_data[round_num]["_full_result"] = search_result

            # ---- 注入 tool result ----
            assistant_msg = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                ],
            }
            messages.append(assistant_msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": search_result,
            })
            print(f"\n  ✅ 已注入 tool result (消息队列现在 {len(messages)} 条)")

            # 每轮结束保存
            save_path = os.path.join(RESULT_DIR, f"v2_round{round_num}_{TIMESTAMP}.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "round": round_num,
                    "query": query,
                    "key_findings_used": findings,
                    "gaps_identified": gaps,
                    "search_strategy": strategy,
                    "search_result_length": count_chars(search_result),
                }, f, ensure_ascii=False, indent=2)
            # (don't print save message to keep output clean)

    # ---- 最终汇总 ----
    print_separator("测试完成 —— 汇总")

    n_tool_rounds = len([k for k, v in round_data.items()
                         if isinstance(k, int) and v.get("role") == "tool_call"])
    print(f"  总轮次: {len([k for k in round_data if isinstance(k, int)])}")
    print(f"  Tool Call 轮次: {n_tool_rounds}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无（LLM 未输出最终回答）'}")

    if all_analyses:
        print(f"\n📊 全部引用分析汇总:")
        print(f"  {'轮次':<6} {'精确':<8} {'部分':<8} {'未匹配':<8} {'准确率':<8} {'critical':<10} {'related':<10}")
        print(f"  {'─'*60}")
        for i, a in enumerate(all_analyses):
            acc = a.get("accuracy", 0)
            print(f"  第{i+2:<2}轮 {a['matched']:<8} {a['partial']:<8} {a['unmatched']:<8} "
                  f"{acc:.0%}     {a['by_priority'].get('critical',0):<10} "
                  f"{a['by_priority'].get('related',0):<10}")

        matched = sum(a["matched"] for a in all_analyses)
        partial = sum(a["partial"] for a in all_analyses)
        total = sum(a["total"] for a in all_analyses)
        overall_acc = (matched + partial * 0.5) / total if total > 0 else 0

        print(f"\n  🏆 总体判定:")
        if overall_acc >= 0.7:
            print(f"     ✅ 通过: 加权准确率 {overall_acc:.0%} ≥ 70%")
            print(f"     → LLM 能在超长文本中准确引用上一轮数据，优先级判断可用")
        elif overall_acc >= 0.4:
            print(f"     ⚠️ 部分通过: 加权准确率 {overall_acc:.0%}")
        else:
            print(f"     ❌ 不通过: 加权准确率 {overall_acc:.0%}")
    else:
        print("\n  ⚠️ 没有收集到跨轮引用数据")

    # 保存完整记录
    summary_path = os.path.join(RESULT_DIR, f"v2_summary_{TIMESTAMP}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "test": "foundation_v2",
            "timestamp": TIMESTAMP,
            "model": DEFAULT_MODEL,
            "n_rounds": n_tool_rounds,
            "has_final_answer": bool(final_answer),
            "analyses": all_analyses,
            "final_answer_preview": (final_answer or "")[:500],
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 完整记录: {summary_path}")


if __name__ == "__main__":
    main()
