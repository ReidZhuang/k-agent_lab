#!/usr/bin/env python3
"""
大规模测试：超长文本（20-30KB/轮）× 至少6轮 × 无编号

核心问题：去掉编号后，「只能引用上一轮」的约束是否仍然有效？
"""

import os, json, time, sys, re
from collections import defaultdict
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING, RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL, DEFAULT_MAX_TOKENS, MAX_ROUNDS, API_BASE_URL,
)
from search_backend import web_search, count_chars

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULT_DIR, exist_ok=True)
TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")

USER_QUERY = (
    "请通过至少6轮搜索深入研究宁德时代，每轮基于上一轮发现继续深入：\n"
    "第1轮：搜索2024年财报核心数据；\n"
    "第2轮：深入储能业务；\n"
    "第3轮：对比比亚迪电池业务；\n"
    "第4轮：分析行业竞争格局；\n"
    "第5轮：分析下一代电池技术；\n"
    "第6轮：分析政策与地缘政治影响。\n"
    "每步必须引用上一步的具体原文数据，不能回翻更早轮次的内容。"
)


def sep(t):
    print(f"\n{'═'*60}\n  {t}\n{'═'*60}")


def show_round(round_num, msgs_before, args, search_text):
    print(f"\n  ┌─ 本轮发送 ({len(msgs_before)}条) ─────────────────")
    for i, m in enumerate(msgs_before):
        r, c = m["role"], m.get("content","")
        tc = m.get("tool_calls")
        if r == "system": print(f"  [{i}] system")
        elif r == "user":  print(f"  [{i}] user ({count_chars(c)}c)")
        elif r == "assistant" and tc: print(f"  [{i}] assistant (tool_call)")
        elif r == "tool":  print(f"  [{i}] tool ({count_chars(c)}c)")
    print(f"  内容规模: {sum(count_chars(m.get('content','')) for m in msgs_before if m['role']=='tool')} chars tools")

    findings = args.get("key_findings_used", [])
    print(f"\n  ├─ LLM 返回引用 ({len(findings)}条) ──────────────")
    for i, f in enumerate(findings):
        c = f.get("content","")[:80]
        s = f.get("source","?")
        p = f.get("priority","?")
        print(f"  [{i}] {p:8s} src={s:12s} | {c}")

    print(f"\n  └─ 注入新数据 ({count_chars(search_text)} chars) ──")
    # Show first 3 lines as preview
    for line in search_text.strip().split("\n")[:3]:
        print(f"  {line[:80]}")
    print(f"  ... ({count_chars(search_text)} chars total)")


def check_content_existence(text: str, needle: str) -> dict:
    """检查 needle 是否存在于 text 中"""
    needle_clean = needle.lower().strip()
    if needle_clean in text.lower():
        return {"found": True, "method": "exact"}
    # 关键词匹配
    nums = re.findall(r'[\d,.]+[万亿%倍千百万亿元GWh]*', needle)
    if nums:
        matched = sum(1 for n in nums if n.lower() in text.lower())
        if matched >= len(nums) * 0.6:
            return {"found": True, "method": "keyword", "matched_nums": matched, "total_nums": len(nums)}
    return {"found": False, "method": "none"}


def main():
    print(f"{'='*60}")
    print(f"  大规模测试: 超长文本 × 至少6轮 × 无编号")
    print(f"  每轮内容: 16-26KB，无编号标记")
    print(f"  约束: 只能引用上一轮结果")
    print(f"{'='*60}")

    messages = [{"role":"system","content":RESEARCH_SYSTEM_PROMPT},
                {"role":"user","content":USER_QUERY}]

    all_results = []          # 每轮的数据
    all_violations = []
    priority_stats = {"critical": 0, "related": 0}
    final_answer = None

    for round_num in range(1, MAX_ROUNDS+1):
        sep(f"第 {round_num} 轮")
        msgs_before = list(messages)

        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL, messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto", max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_v5_test"},
            )
        except Exception as e:
            print(f"\n  ❌ API异常: {e}"); break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else "?"
        out_t = response.usage.completion_tokens if response.usage else "?"
        print(f"  in={in_t}, out={out_t}, finish={finish}")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"  ✅ 完成 ({count_chars(final_answer)}c)"); break

        if finish == "length":
            print(f"  ⚠️ 截断，继续下一轮"); continue

        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name != "web_search": continue

            try: args = json.loads(tc.function.arguments)
            except: continue

            query = args.get("query","")
            findings = args.get("key_findings_used",[])
            search_result = web_search(query, round_num=round_num)

            show_round(round_num, msgs_before, args, search_result)
            print(f"  🔍 {query}")

            # ---- 引用分析（无编号，基于内容检查） ----
            round_info = {"round": round_num, "n_findings": len(findings),
                          "n_violations": 0, "violations": [], "priority_dist": {}}

            if round_num >= 2:
                prev_text = ""
                # 找到上一轮的 tool result
                for m in reversed(messages):
                    if m["role"] == "tool" and m.get("_round") == round_num - 1:
                        prev_text = m.get("content", "")
                        break
                # 如果找不到，从 all_results 取
                if not prev_text and all_results:
                    prev_text = all_results[-1].get("raw_text", "")

                prev_all_text = prev_text

                print(f"\n  ── 引用验证 ──")
                for fi, f in enumerate(findings):
                    content = f.get("content","")
                    priority = f.get("priority","?")
                    source = f.get("source","?")
                    priority_stats[priority] = priority_stats.get(priority, 0) + 1

                    # 检查是否存在于上一轮结果中
                    result = check_content_existence(prev_all_text, content)

                    if result["found"]:
                        status = f"✅ {result['method']}"
                    else:
                        # 检查是否存在于更早轮次
                        found_earlier = False
                        for ri in range(len(all_results)-1, -1, -1):
                            er = check_content_existence(all_results[ri].get("raw_text",""), content)
                            if er["found"]:
                                found_earlier = True
                                all_violations.append({
                                    "round": round_num, "content": content[:80],
                                    "found_in_round": all_results[ri]["round"],
                                    "expected_round": round_num - 1,
                                })
                                round_info["n_violations"] += 1
                                round_info["violations"].append({
                                    "content": content[:80],
                                    "found_in_round": all_results[ri]["round"],
                                })
                                status = f"⛔ 来自第{all_results[ri]['round']}轮(非上轮)"
                                break
                        if not found_earlier:
                            status = "❌ 未匹配任何轮次"

                    pdist = round_info["priority_dist"]
                    pdist[priority] = pdist.get(priority, 0) + 1

                    print(f"  [{fi}] {status:40s} | {priority:8s} | {content[:60]}")

                total_ok = sum(1 for f in findings if
                              check_content_existence(prev_all_text, f.get("content",""))["found"])
                print(f"\n  结果: {total_ok}/{len(findings)} 来自上一轮, "
                      f"{round_info['n_violations']} 次越轮违规")
                if findings:
                    print(f"  critical={pdist.get('critical',0)}, related={pdist.get('related',0)}")
            else:
                print(f"\n  ── 第一轮，无引用验证 ──")

            # ---- 注入 ----
            messages.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}],
            })
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": search_result,
                "_round": round_num,
            })

            # 记录本轮数据供后续验证
            all_results.append({
                "round": round_num, "raw_text": search_result,
                "findings": findings, "analysis": round_info,
            })

            print(f"  ✅ 消息队列: {len(messages)} 条")

    # 如果没到6轮tool call，继续
    tool_rounds = len(all_results)
    print(f"\n  Tool call 完成: {tool_rounds} 轮")

    # ---- 汇总 ----
    sep("汇总")
    print(f"  Tool Call 轮次: {tool_rounds}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'}")

    # 逐轮准确率
    print(f"\n📊 逐轮引用统计:")
    print(f"  {'轮次':<6} {'引用数':<8} {'越轮违规':<10} {'critical':<10} {'related':<10}")
    print(f"  {'─'*40}")
    for r in all_results:
        a = r["analysis"]
        p = a.get("priority_dist", {})
        print(f"  第{r['round']:<2}轮 {a['n_findings']:<8} {a['n_violations']:<10} "
              f"{p.get('critical',0):<10} {p.get('related',0):<10}")

    # 全局优先级
    print(f"\n  全局优先级分布: critical={priority_stats.get('critical',0)}, "
          f"related={priority_stats.get('related',0)}")

    # 违规汇总
    if all_violations:
        print(f"\n⛔ 越轮违规 ({len(all_violations)} 次):")
        for v in all_violations:
            print(f"  第{v['round']}轮引用了第{v['found_in_round']}轮的数据")
            print(f"    → {v['content']}")
    else:
        print(f"\n✅ 所有引用均来自上一轮，无越轮违规")

    # 总结
    total_ok = sum(1 for v in all_violations if v)
    total_citations = sum(a["n_findings"] for a in [r["analysis"] for r in all_results if r["round"] > 1])
    print(f"\n  🏆 总结: 共{total_citations}条引用, {len(all_violations)}次违规 "
          f"({(1-len(all_violations)/total_citations)*100:.0f}%合规)" if total_citations > 0 else "")

    summary_path = os.path.join(RESULT_DIR, f"v5_summary_{TIMESTAMP}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "test": "foundation_v5_large",
            "rounds": tool_rounds,
            "n_citations": total_citations,
            "n_violations": len(all_violations),
            "priority_stats": priority_stats,
            "violations": all_violations,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 {summary_path}")


if __name__ == "__main__":
    main()
