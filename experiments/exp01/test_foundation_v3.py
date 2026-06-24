#!/usr/bin/env python3
"""
Step 1 v3 — 超长文本 + 优先级分级 + 来源编号追踪

新增：
  1. 每条搜索结果标记为 [R{round}-{idx}]，如 R1-3
  2. key_findings_used 新增 source 字段（如 "R1-3"）
  3. 分析中追踪跨轮引用来源（哪些数据来自非上一轮）
  4. 最终汇总展示"引用来源分布"
"""

import os
import json
import time
import sys
import re
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

def print_separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def print_messages_summary(messages: list, label: str = "当前消息队列"):
    print(f"\n── {label} ──")
    print(f"  总消息数: {len(messages)}")
    total_in = 0
    for i, msg in enumerate(messages):
        role = msg["role"]
        content = msg.get("content", "")
        tc = msg.get("tool_calls")
        tcid = msg.get("tool_call_id")
        if role == "system":
            print(f"    [{i}] system ({count_chars(content)} chars)")
        elif role == "user":
            print(f"    [{i}] user ({count_chars(content)} chars): {content[:60].replace(chr(10),' ')}...")
        elif role == "assistant":
            if tc:
                print(f"    [{i}] assistant (tool_call: {[t['function']['name'] for t in tc]})")
            elif content:
                print(f"    [{i}] assistant ({count_chars(content)} chars, 最终回答)")
        elif role == "tool":
            print(f"    [{i}] tool (result: {count_chars(content)} chars, id={tcid[:18]}...)")
            total_in += count_chars(content)
    print(f"  累计 tool result: {total_in} chars")


def print_tool_definition(tool: dict):
    func = tool["function"]
    print(f"\n── 可用工具 ──")
    print(f"  名称: {func['name']}")
    for pname, pdef in func["parameters"]["properties"].items():
        ptype = pdef.get("type", "?")
        desc = pdef.get("description", "")[:80].replace("\n", " ")
        print(f"  参数: {pname} ({ptype}, required)")
        if pname == "key_findings_used":
            print(f"    └── items: {{content (str), source (R轮次-条目号), priority (critical|related)}}")
            print(f"    └── {desc}")
        else:
            print(f"    └── {desc}")


def print_llm_response(choice, response_usage=None):
    finish = choice.finish_reason
    msg = choice.message
    usage = response_usage
    in_tokens = usage.prompt_tokens if usage else "?"
    out_tokens = usage.completion_tokens if usage else "?"
    print(f"\n── LLM 响应 ──")
    print(f"  finish_reason: {finish}  |  tokens: in={in_tokens}, out={out_tokens}")
    if finish == "stop":
        text = (msg.content or "")[:500]
        print(f"  最终回答 (前500字):")
        for line in text.split("\n")[:8]:
            print(f"  │ {line}")
        print(f"  │ ... (共 {count_chars(msg.content or '')} 字)" if len(text) >= 500 else "")
        return
    if finish == "tool_calls" and msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"  tool_call: {tc.function.name}")
            try:
                args = json.loads(tc.function.arguments)
                # 精简显示：只显示 findings 数量和来源
                findings = args.get("key_findings_used", [])
                sources = [f.get("source","?") for f in findings] if findings else []
                print(f"  key_findings_used: {len(findings)} 条")
                print(f"  来源分布: {sources}")
                print(f"  查询: {args.get('query','')[:60]}")
            except json.JSONDecodeError:
                print(f"  arguments: {tc.function.arguments[:200]}")


def print_tool_result(search_text: str):
    snippets = extract_key_snippets(search_text)
    print(f"\n── 注入 tool result ──")
    print(f"  {len(snippets)} 条结果, {count_chars(search_text)} chars")
    for s in snippets[:4]:
        short = s["snippet"][:100] + "..."
        print(f"  {s['ref']}: {s['title'][:55]}")
        print(f"          {short}")
    if len(snippets) > 4:
        print(f"  ... 及另外 {len(snippets)-4} 条")


def analyze_findings(findings: list, prev_result_text: str, current_round: int) -> dict:
    """分析引用：内容验证 + 来源编号验证 + 跨轮引用检测"""
    if not findings:
        print("  ⚠️ 本轮未引用数据")
        return {"total": 0, "matched": 0, "partial": 0, "unmatched": 0,
                "by_priority": {}, "by_source_round": {}, "cross_round_refs": [],
                "source_format_errors": [], "accuracy": 0}

    r1_lower = prev_result_text.lower()
    result = {
        "total": len(findings),
        "matched": 0,
        "partial": 0,
        "unmatched": 0,
        "by_priority": {"critical": 0, "related": 0, "unknown": 0},
        "by_source_round": {},  # source round → count
        "cross_round_refs": [],  # 跨轮引用记录
        "source_format_errors": [],  # 来源编号格式错误
        "details": [],
    }

    for f in findings:
        content = f.get("content", "") if isinstance(f, dict) else f
        source = f.get("source", "") if isinstance(f, dict) else ""
        priority = f.get("priority", "unknown") if isinstance(f, dict) else "unknown"

        result["by_priority"][priority] = result["by_priority"].get(priority, 0) + 1

        # ---- 验证来源编号 ----
        source_match = re.match(r'^R(\d+)-\d+$', source)
        if source_match:
            src_round = int(source_match.group(1))
            result["by_source_round"][src_round] = result["by_source_round"].get(src_round, 0) + 1
            # 跨轮检测：引用的是非上一轮的数据
            if src_round < current_round - 1:
                result["cross_round_refs"].append({
                    "source": source,
                    "content_preview": content[:80],
                    "referenced_from_round": current_round,
                    "actual_source_round": src_round,
                })
        else:
            if source:
                result["source_format_errors"].append(source)

        # ---- 验证内容 ----
        content_lower = content.lower().strip()
        detail = {"content": content[:120], "source": source, "priority": priority}

        if content_lower in r1_lower:
            detail["status"] = "✅"
            result["matched"] += 1
        else:
            # 关键词匹配
            numbers = re.findall(r'[\d,.]+[万亿%倍千百万亿元GWhkWhWh]*', content)
            matched_terms = [n for n in numbers if n.lower() in r1_lower]
            unmatched_terms = [n for n in numbers if n.lower() not in r1_lower]
            if matched_terms and not unmatched_terms:
                detail["status"] = "✅"
                result["matched"] += 1
            elif matched_terms:
                detail["status"] = "⚠️"
                result["partial"] += 1
            else:
                detail["status"] = "❌"
                result["unmatched"] += 1
        result["details"].append(detail)

    result["accuracy"] = (result["matched"] + result["partial"] * 0.5) / result["total"] if result["total"] else 0
    return result


def print_analysis(result: dict):
    print(f"\n── 引用分析 (key_findings_used) ──")
    print(f"  总条目: {result['total']}")
    for i, d in enumerate(result["details"]):
        icon = d["status"]
        print(f"  [{i}] {icon} {d['priority'].upper():8s} | src={d['source']:8s} | {d['content'][:70]}")
    print(f"  汇总: 精确{result['matched']} + 部分{result['partial']} + 未匹配{result['unmatched']} = {result['total']}")
    print(f"  优先级: critical={result['by_priority'].get('critical',0)}, related={result['by_priority'].get('related',0)}")
    if result["by_source_round"]:
        srcs = sorted(result["by_source_round"].items())
        print(f"  来源轮次分布: {', '.join(f'R{k}={v}' for k, v in srcs)}")
    if result["cross_round_refs"]:
        print(f"  ⚠️ 跨轮引用 ({len(result['cross_round_refs'])} 次):")
        for c in result["cross_round_refs"]:
            print(f"     第{c['referenced_from_round']}轮引用了 {c['source']} → {c['content_preview'][:60]}")
    if result["source_format_errors"]:
        print(f"  ❌ 来源编号格式错误: {result['source_format_errors']}")
    print(f"  加权准确率: {result['accuracy']:.0%}")


# ==============================================================
# 主流程
# ==============================================================

def main():
    print(f"{'=' * 66}")
    print(f"  Step 1 v3: 超长文本 + 优先级 + 来源编号追踪")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"  最大轮次: {MAX_ROUNDS}")
    print(f"{'=' * 66}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    round_data = {}
    final_answer = None
    all_analyses = []
    source_round_distribution = {}  # 全局来源轮次统计

    # 初始打印
    print_messages_summary(messages, "初始消息队列")
    print_tool_definition(WEB_SEARCH_TOOL_WITH_REASONING)
    print(f"\n⚠️  tool definition 中要求 LLM 标注每条引用的来源编号 [R轮次-条目号]")

    for round_num in range(1, MAX_ROUNDS + 1):
        print_separator(f"第 {round_num} 轮")
        print_messages_summary(messages, f"发送给 LLM 的消息 ({len(messages)} 条)")

        # ---- API 调用 ----
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_v3_test"},
            )
        except Exception as e:
            print(f"\n  ❌ API 调用异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        print_llm_response(choice, response.usage)

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 决定停止")
            round_data[round_num] = {"role": "final_answer", "content_len": len(final_answer)}
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
            findings = args.get("key_findings_used", [])
            gaps = args.get("gaps_identified", "")
            strategy = args.get("search_strategy", "")

            # ---- 执行搜索（传递 round_num 以生成编号）----
            print(f"\n  🔍 搜索: {query}")
            search_result = web_search(query, round_num=round_num)
            snippets = extract_key_snippets(search_result)
            print(f"  📦 返回 {len(snippets)} 条结果, {count_chars(search_result)} chars")

            # ---- 记录 ----
            round_data[round_num] = {
                "role": "tool_call",
                "query": query,
                "key_findings_used": findings,
                "gaps_identified": gaps,
                "search_strategy": strategy,
                "search_result_length": count_chars(search_result),
                "search_result_snippets": len(snippets),
            }

            # ---- 打印 tool result ----
            print_tool_result(search_result)

            # ---- 引用分析 ----
            if round_num >= 2:
                prev_data = round_data.get(round_num - 1, {})
                prev_result_text = prev_data.get("_full_result", "")
                round_data[round_num]["_full_result"] = search_result

                if findings:
                    analysis = analyze_findings(findings, prev_result_text, round_num)
                    print_analysis(analysis)
                    round_data[round_num]["reference_analysis"] = analysis
                    all_analyses.append(analysis)

                    # 更新全局来源轮次分布
                    for src_round, count in analysis.get("by_source_round", {}).items():
                        source_round_distribution[src_round] = \
                            source_round_distribution.get(src_round, 0) + count
                else:
                    print("\n  ⚠️ 本轮未提供引用")
            else:
                round_data[round_num]["_full_result"] = search_result

            # ---- 注入上下文 ----
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }],
            })
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": search_result,
            })
            print(f"  ✅ 注入完成 (消息队列: {len(messages)} 条)")

    # ==============================================================
    # 最终汇总
    # ==============================================================
    print_separator("汇总")
    n_tool = len([k for k, v in round_data.items() if isinstance(k, int) and v.get("role") == "tool_call"])
    print(f"  总轮次: {len(round_data)}")
    print(f"  Tool Call: {n_tool}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'}")

    if all_analyses:
        print(f"\n📊 逐轮引用准确率:")
        print(f"  {'轮次':<6} {'引用数':<8} {'精确':<8} {'部分':<8} {'未匹配':<8} {'准确率':<8} {'critical':<10} {'related':<10}")
        print(f"  {'─'*60}")
        for i, a in enumerate(all_analyses):
            r = i + 2
            print(f"  第{r:<2}轮 {a['total']:<8} {a['matched']:<8} {a['partial']:<8} {a['unmatched']:<8} "
                  f"{a['accuracy']:.0%}     {a['by_priority'].get('critical',0):<10} {a['by_priority'].get('related',0):<10}")

        # 全局引用准确率
        tot_m = sum(a["matched"] for a in all_analyses)
        tot_p = sum(a["partial"] for a in all_analyses)
        tot_t = sum(a["total"] for a in all_analyses)
        overall_acc = (tot_m + tot_p * 0.5) / tot_t if tot_t else 0
        print(f"\n  🏆 全局准确率: {overall_acc:.0%} ({tot_m}+{tot_p}/{tot_t})")

        # 全局来源轮次分布
        if source_round_distribution:
            print(f"\n📊 全局引用来源轮次分布:")
            for src_round in sorted(source_round_distribution):
                print(f"  R{src_round} 轮的数据被后续引用: {source_round_distribution[src_round]} 次")

        # 跨轮引用汇总
        all_cross = []
        for a in all_analyses:
            all_cross.extend(a.get("cross_round_refs", []))
        if all_cross:
            print(f"\n⚠️ 跨轮引用汇总 ({len(all_cross)} 次):")
            for c in all_cross:
                print(f"  第{c['referenced_from_round']}轮 → {c['source']} ({c['content_preview'][:60]})")

        # 来源格式错误汇总
        all_fmt_errors = []
        for a in all_analyses:
            all_fmt_errors.extend(a.get("source_format_errors", []))
        if all_fmt_errors:
            print(f"\n❌ 来源编号格式错误: {all_fmt_errors}")
        else:
            print(f"\n✅ 所有来源编号格式正确")

        if overall_acc >= 0.7:
            verdict = f"✅ 通过 ({overall_acc:.0%} ≥ 70%)"
        elif overall_acc >= 0.4:
            verdict = f"⚠️ 部分通过 ({overall_acc:.0%})"
        else:
            verdict = f"❌ 不通过 ({overall_acc:.0%})"
        print(f"\n  判定: {verdict}")
    else:
        print("\n  ⚠️ 没有跨轮引用数据")

    # 保存
    summary_path = os.path.join(RESULT_DIR, f"v3_summary_{TIMESTAMP}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "test": "foundation_v3",
            "timestamp": TIMESTAMP,
            "model": DEFAULT_MODEL,
            "rounds": n_tool,
            "analyses": all_analyses,
            "source_round_distribution": source_round_distribution,
            "cross_round_refs": all_cross,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 完整记录: {summary_path}")


if __name__ == "__main__":
    main()
