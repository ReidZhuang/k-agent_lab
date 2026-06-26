#!/usr/bin/env python3
"""
Step 1 v4 — 「只能引用上一轮」约束验证 + 晚期首次引用检测

新增：
  1. 工具定义中明确限制：只能引用 [R{当前轮次-1}-N] 的内容
  2. 检测违规引用（越轮引用早期数据）
  3. 检测「晚期首次引用」——早期轮次从未引用、但后期翻出来的数据
  4. 每轮展示：本地发送内容概要 → LLM tool_call 返回的完整引用列表
"""

import os
import json
import time
import sys
import re
from collections import defaultdict
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
# 格式化
# ==============================================================
def sep(title):
    print(f"\n{'═' * 60}\n  {title}\n{'═' * 60}")

def msg_summary(messages):
    print(f"  消息队列: {len(messages)} 条")
    for i, m in enumerate(messages):
        r = m["role"]
        c = m.get("content", "")
        tc = m.get("tool_calls")
        tcid = m.get("tool_call_id")
        if r == "system":     print(f"    [{i}] system ({count_chars(c)}c)")
        elif r == "user":     print(f"    [{i}] user ({count_chars(c)}c): {c[:60].replace(chr(10),' ')}...")
        elif r == "assistant" and tc:
            print(f"    [{i}] assistant (tool_call)")
        elif r == "assistant" and c:
            print(f"    [{i}] assistant ({count_chars(c)}c, 最终回答)")
        elif r == "tool":     print(f"    [{i}] tool ({count_chars(c)}c, id={tcid[:16]}...)")

# ==============================================================
# 逐轮全量引用展示
# ==============================================================
def show_round_exchange(round_num, messages_before, llm_args, search_result):
    """展示一轮的完整交换内容"""
    print(f"\n  ┌─ 本轮发送给 LLM 的消息 ──────────────────────")
    msg_summary(messages_before)

    findings = llm_args.get("key_findings_used", [])
    gaps = llm_args.get("gaps_identified", "")
    strategy = llm_args.get("search_strategy", "")
    query = llm_args.get("query", "")

    print(f"\n  ├─ LLM 返回的 tool_call.arguments ────────────")
    print(f"     查询: {query}")
    print(f"     缺口: {gaps[:80]}")
    print(f"     策略: {strategy[:80]}")
    print(f"     引用 ({len(findings)} 条):")
    for i, f in enumerate(findings):
        c = f.get("content","")[:90]
        s = f.get("source","?")
        p = f.get("priority","?")
        print(f"       [{i}] src={s:6s} | {p:8s} | {c}")

    snippets = extract_key_snippets(search_result)
    print(f"\n  └─ 注入搜索结果 ({len(snippets)} 条, {count_chars(search_result)}c) ──")
    for s in snippets[:3]:
        print(f"      {s['ref']}: {s['title'][:60]}")
    if len(snippets) > 3:
        print(f"      ...及另外 {len(snippets)-3} 条")


def analyze_v4(findings, prev_result_text, current_round, citation_first_seen):
    """分析引用 + 越轮检测 + 晚期首次引用检测

    Args:
        findings: key_findings_used
        prev_result_text: 上一轮搜索结果全文
        current_round: 当前轮次
        citation_first_seen: dict, entry_key → first_seen_round (跨轮追踪)
    """
    if not findings:
        return None

    r1_lower = prev_result_text.lower()
    result = {
        "total": len(findings),
        "matched": 0, "partial": 0, "unmatched": 0,
        "by_priority": {"critical": 0, "related": 0},
        "by_source_round": {},
        "violations": [],         # 越轮引用（source_round < current_round - 1）
        "late_first_citations": [],  # 晚期首次引用
        "details": [],
    }

    for f in findings:
        content = f.get("content", "")
        source = f.get("source", "")
        priority = f.get("priority", "unknown")
        result["by_priority"][priority] = result["by_priority"].get(priority, 0) + 1

        # 解析来源编号
        src_match = re.match(r'^R(\d+)-\d+$', source)
        if src_match:
            src_round = int(src_match.group(1))
            result["by_source_round"][src_round] = result["by_source_round"].get(src_round, 0) + 1

            # ═══ 越轮检测 ═══
            if src_round < current_round - 1:
                result["violations"].append({
                    "source": source,
                    "content": content[:80],
                    "round": current_round,
                    "expected": f"R{current_round-1}-N",
                    "actual": source,
                })

            # ═══ 晚期首次引用检测 ═══
            entry_key = source  # e.g. "R1-3"
            if entry_key not in citation_first_seen:
                citation_first_seen[entry_key] = {
                    "first_seen": current_round,
                    "content_preview": content[:80],
                    "origin_round": src_round,
                }
            else:
                # 同一个 source 被再次引用，但可能是不同内容
                prev = citation_first_seen[entry_key]
                if current_round == prev["first_seen"]:
                    pass  # 同一轮多次引用同一个 source 正常
                else:
                    # 标记为「跨轮重复引用」
                    pass  # 这不是问题，用户关心的是"晚期首次引用"

        # 内容验证
        content_lower = content.lower().strip()
        detail = {"content": content[:120], "source": source, "priority": priority}
        if content_lower in r1_lower:
            detail["status"] = "✅"
            result["matched"] += 1
        else:
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


def print_analysis_v4(result, round_num):
    print(f"\n  ── 引用分析 (第{round_num}轮) ──")
    print(f"  总条目: {result['total']}, 准确率: {result['accuracy']:.0%}")
    for i, d in enumerate(result["details"]):
        print(f"    {d['status']} src={d['source']:6s} | {d['priority']:8s} | {d['content'][:80]}")

    if result["violations"]:
        print(f"\n  ⛔ 越轮引用违规 ({len(result['violations'])} 次):")
        for v in result["violations"]:
            print(f"     第{v['round']}轮引用 {v['source']}（应只引用 {v['expected']}）→ {v['content'][:60]}")
    else:
        print(f"\n  ✅ 所有引用符合'只能引用上一轮'规则")

    print(f"  来源轮次分布: {dict(sorted(result['by_source_round'].items()))}")
    print(f"  优先级: critical={result['by_priority'].get('critical',0)}, related={result['by_priority'].get('related',0)}")


# ==============================================================
# Main
# ==============================================================
def main():
    print(f"{'=' * 60}")
    print(f"  Step 1 v4: 「只能引用上一轮」约束验证")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"{'=' * 60}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    round_data = {}
    final_answer = None
    all_analyses = []
    citation_first_seen = {}     # entry_key → {first_seen, content, origin_round}
    violation_log = []           # 所有越轮违规
    late_citation_log = []       # 所有晚期首次引用

    # 初始打印
    print(f"\n── 初始消息 ──")
    msg_summary(messages)
    print(f"\n── 工具定义中的引用约束 ──")
    desc = WEB_SEARCH_TOOL_WITH_REASONING["function"]["description"]
    print(f"  {desc[:200]}")
    print(f"  ...")
    # 提取约束部分
    constraint = desc[desc.find("⚠️ 引用范围限制"):desc.find("⚠️ 未在")]
    print(f"  {constraint}")

    for round_num in range(1, MAX_ROUNDS + 1):
        sep(f"第 {round_num} 轮")

        # 保存本轮发送前的消息快照
        msgs_before = list(messages)

        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_v4_test"},
            )
        except Exception as e:
            print(f"  ❌ API异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else "?"
        out_t = response.usage.completion_tokens if response.usage else "?"
        print(f"  tokens: in={in_t}, out={out_t}, finish={finish}")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"  ✅ LLM 决定停止 ({count_chars(final_answer)}字)")
            round_data[round_num] = {"role": "final_answer"}
            break

        if finish == "length":
            print(f"  ⚠️ 达到 max_tokens 上限，继续下一轮")
            continue

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

            # 搜索
            search_result = web_search(query, round_num=round_num)
            snippets = extract_key_snippets(search_result)

            # ═══ 全量交换展示 ═══
            show_round_exchange(round_num, msgs_before, args, search_result)

            # 记录
            round_data[round_num] = {
                "role": "tool_call",
                "query": query,
                "key_findings_used": findings,
                "search_result_len": count_chars(search_result),
            }

            # ═══ 分析 ═══
            if round_num >= 2:
                prev_data = round_data.get(round_num - 1, {})
                prev_result_text = prev_data.get("_full_result", "")
                round_data[round_num]["_full_result"] = search_result

                if findings:
                    analysis = analyze_v4(
                        findings, prev_result_text, round_num, citation_first_seen
                    )
                    if analysis:
                        print_analysis_v4(analysis, round_num)
                        round_data[round_num]["reference_analysis"] = analysis
                        all_analyses.append(analysis)

                        # 收集违规和晚期引用
                        if analysis["violations"]:
                            violation_log.extend(analysis["violations"])

                        # 检测晚期首次引用
                        for d in analysis["details"]:
                            source = d["source"]
                            if source in citation_first_seen:
                                info = citation_first_seen[source]
                                if info["first_seen"] == round_num:
                                    # 这个 source 在当前轮才被首次引用
                                    late_citation_log.append({
                                        "source": source,
                                        "first_seen_round": round_num,
                                        "origin_round": int(re.search(r'R(\d+)', source).group(1)) if re.search(r'R(\d+)', source) else 0,
                                        "content": d["content"][:80],
                                    })
                else:
                    print(f"  ⚠️ 本轮未提供引用")
            else:
                round_data[round_num]["_full_result"] = search_result

            # 注入上下文
            messages.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }],
            })
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": search_result,
            })

    # ═══════════════════════════════
    # 汇总
    # ═══════════════════════════════
    sep("汇总")

    n_tool = len([k for k, v in round_data.items() if isinstance(k, int) and v.get("role") == "tool_call"])
    print(f"  Tool Call 轮次: {n_tool}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'}")

    if all_analyses:
        # 准确率表
        print(f"\n📊 逐轮引用准确率:")
        print(f"  {'轮次':<6} {'引用数':<8} {'精确':<8} {'部分':<8} {'未匹配':<8} {'准确率':<8}")
        print(f"  {'─'*46}")
        for i, a in enumerate(all_analyses):
            r = i + 2
            print(f"  第{r:<2}轮 {a['total']:<8} {a['matched']:<8} {a['partial']:<8} {a['unmatched']:<8} {a['accuracy']:.0%}")

        tot_m = sum(a["matched"] for a in all_analyses)
        tot_p = sum(a["partial"] for a in all_analyses)
        tot_t = sum(a["total"] for a in all_analyses)
        print(f"\n  🏆 全局准确率: {tot_m}/{tot_t} 精确 + {tot_p}/{tot_t} 部分 = {(tot_m+tot_p*0.5)/tot_t:.0%}")

        # ═══ 越轮违规汇总 ═══
        if violation_log:
            print(f"\n⛔ 越轮引用违规 (共 {len(violation_log)} 次):")
            for v in violation_log:
                print(f"  第{v['round']}轮引用了 {v['source']}（应只引用 {v['expected']}）")
                print(f"    → {v['content']}")
        else:
            print(f"\n✅ 所有引用均遵守'只能引用上一轮'规则，无越轮违规")

        # ═══ 晚期首次引用检测 ═══
        if late_citation_log:
            # 去重：同一个 source 只显示一次
            seen_sources = set()
            unique_late = []
            for c in late_citation_log:
                if c["source"] not in seen_sources:
                    seen_sources.add(c["source"])
                    unique_late.append(c)

            if unique_late:
                print(f"\n📋 晚期首次引用（早期完全忽略、后期才翻出来引用的数据）:")
                # 按来源轮次排序
                unique_late.sort(key=lambda x: x["origin_round"])
                for c in unique_late:
                    rounds_late = c["first_seen_round"] - c["origin_round"]
                    print(f"  {c['source']}（源自第{c['origin_round']}轮）→ "
                          f"第{c['first_seen_round']}轮才首次引用（晚了{rounds_late}轮）")
                    print(f"    内容: {c['content']}")
        else:
            print(f"\n👌 没有检测到晚期首次引用，所有数据均在下一轮被及时引用")

        # 来源轮次分布
        src_dist = defaultdict(int)
        for a in all_analyses:
            for src_round, cnt in a.get("by_source_round", {}).items():
                src_dist[src_round] += cnt
        print(f"\n📊 引用来源轮次分布:")
        for src_round in sorted(src_dist):
            print(f"  R{src_round}: {src_dist[src_round]} 次")

    # 保存
    summary_path = os.path.join(RESULT_DIR, f"v4_summary_{TIMESTAMP}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "test": "foundation_v4",
            "timestamp": TIMESTAMP,
            "model": DEFAULT_MODEL,
            "rounds": n_tool,
            "analyses": all_analyses,
            "violations": violation_log,
            "late_citations": late_citation_log,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 {summary_path}")


if __name__ == "__main__":
    main()
