#!/usr/bin/env python3
"""
Step 1 — 基础验证：LLM 是否能在 tool_call 中引用上一轮返回的真实数据

测试流程：
  第1轮: LLM 调用 web_search → 我们执行 DuckDuckGo 搜索 → 结果注入
  第2轮: LLM 再次调用 web_search → 我们捕获 reasoning_analysis.key_findings_used
  分析:  key_findings_used 中的条目是否真实存在于第1轮搜索结果中

如果此测试失败，整个研究方向不成立。
"""

import os
import json
import time
import sys
from openai import OpenAI

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING,
    RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL,
    API_BASE_URL,
)
from search_backend import web_search, extract_key_snippets

# ---- 配置 ----
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("❌ 错误: 未设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULT_DIR, exist_ok=True)

TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")

# 用户查询 —— 明确要求两步搜索，增加多轮可能性
USER_QUERY = (
    "请分两步研究宁德时代：\n"
    "第一步：搜索其2024年财报核心数据（营收、净利润、增长率等）；\n"
    "第二步：基于第一步的发现，深入搜索其储能业务的增长情况——这一步你必须引用第一步找到的具体数据。\n"
    "注意：不要同时搜索，一步一步来。"
)

# ---- 辅助函数 ----


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_round_header(round_num: int, title: str):
    print(f"\n{'-'*50}")
    print(f"  🔄 第 {round_num} 轮: {title}")
    print(f"{'-'*50}")


def analyze_references(findings: list[str], round1_results: str, snippets: list[dict]) -> dict:
    """分析 key_findings_used 中的条目是否真实存在于上一轮结果中

    Args:
        findings: LLM 输出的 key_findings_used 列表
        round1_results: 第1轮搜索返回的原始文本
        snippets: 从 round1_results 提取的结构化片段

    Returns:
        分析结果 dict
    """
    analysis = {
        "total": len(findings),
        "matched": 0,
        "partial": 0,
        "unmatched": 0,
        "details": [],
    }

    # 将第1轮结果转成小写用于匹配
    r1_lower = round1_results.lower()

    for finding in findings:
        finding_lower = finding.lower()
        detail = {"finding": finding, "status": "", "evidence": ""}

        # 尝试精确匹配
        if finding_lower in r1_lower:
            detail["status"] = "✅ 精确匹配"
            detail["evidence"] = "原文包含完全相同的文本片段"
            analysis["matched"] += 1
        else:
            # 尝试关键词匹配：提取数字+单位组合和关键名词
            import re

            # 找数字组合（如 "3600亿元", "22%"）
            numbers = re.findall(r'[\d,.]+[万亿%倍千百万亿]*', finding)
            # 找关键名词（如 "营收", "净利润", "装机量"）
            key_nouns = re.findall(r'[营收净利储能电池动力装机同比增\d]+', finding)

            matched_terms = []
            unmatched_terms = []

            for num in numbers:
                if num in r1_lower or num.replace(",", "") in r1_lower.replace(",", ""):
                    matched_terms.append(num)
                else:
                    unmatched_terms.append(num)

            for noun in key_nouns:
                if noun in r1_lower:
                    if noun not in matched_terms:
                        matched_terms.append(noun)

            if matched_terms and not unmatched_terms:
                detail["status"] = "✅ 精确匹配"
                detail["evidence"] = f"关键词全部命中: {matched_terms}"
                analysis["matched"] += 1
            elif matched_terms and unmatched_terms:
                detail["status"] = "⚠️ 部分匹配"
                detail["evidence"] = (
                    f"命中: {matched_terms} | 未命中: {unmatched_terms}"
                )
                analysis["partial"] += 1
            else:
                detail["status"] = "❌ 未匹配"
                detail["evidence"] = "无法在上一轮结果中找到对应内容"
                analysis["unmatched"] += 1

        analysis["details"].append(detail)

    return analysis


def print_analysis(analysis: dict):
    """打印分析结果"""
    print(f"\n  📊 引用分析:")
    print(f"     总条目: {analysis['total']}")
    print(f"     精确匹配: {analysis['matched']}")
    print(f"     部分匹配: {analysis['partial']}")
    print(f"     未匹配: {analysis['unmatched']}")

    if analysis["total"] > 0:
        accuracy = (analysis["matched"] + analysis["partial"] * 0.5) / analysis["total"]
        print(f"     加权准确率: {accuracy:.0%}")

    for d in analysis["details"]:
        print(f"     {d['status']}: {d['finding'][:60]}")
        print(f"       证据: {d['evidence']}")


def save_round_data(round_num: int, data: dict):
    """保存每轮数据到 JSON"""
    filepath = os.path.join(RESULT_DIR, f"foundation_round{round_num}_{TIMESTAMP}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📝 已保存: {os.path.basename(filepath)}")


# ---- 主线流程 ----

def main():
    print_header("Step 1: 基础验证 —— LLM 能否引用上一轮 tool result 的真实数据")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"  时间: {TIMESTAMP}")
    print(f"\n  📋 假设验证链:")
    print(f"      Round 1: LLM 搜索 → 我们注入真实搜索结果")
    print(f"      Round 2: LLM 再次搜索 → 捕获其 reasoning_analysis")
    print(f"      分析:  Round 2 引用的数据是否真实存在于 Round 1 结果中")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    round_data = {}  # 记录所有轮次数据
    final_answer = None

    # ---- Agent Loop ----
    for round_num in range(1, 5):  # 最多 4 轮
        print_round_header(round_num, "LLM 决策中...")

        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=2000,
                parallel_tool_calls=False,  # 强制顺序执行，避免并行调用
                extra_body={"user_id": "exp01_foundation_test"},
            )
        except Exception as e:
            print(f"  ❌ API 调用异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        usage = response.usage

        # Token 用量（OpenAI SDK 格式: prompt_tokens / completion_tokens）
        in_tokens = usage.prompt_tokens if usage else "?"
        out_tokens = usage.completion_tokens if usage else "?"
        print(f"  📊 Tokens: in={in_tokens}, out={out_tokens}, 状态={finish}")

        # ---- 情况 1: LLM 决定停止 ----
        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✋ LLM 决定停止，给出最终回答")
            print(f"  回答(前200字): {final_answer[:200]}")
            round_data[round_num] = {"role": "final_answer", "content": final_answer}
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
            except json.JSONDecodeError:
                print(f"  ❌ 无法解析 arguments: {tc.function.arguments[:100]}")
                continue

            query = args.get("query", "")
            reasoning = args.get("reasoning_analysis", {})

            print(f"  🔍 搜索: {query}")
            if reasoning:
                findings = reasoning.get("key_findings_used", [])
                gaps = reasoning.get("gaps_identified", "")
                strategy = reasoning.get("search_strategy", "")
                print(f"  💭 引用发现: {json.dumps(findings, ensure_ascii=False)[:200]}")
                if gaps:
                    print(f"  💭 识别缺口: {gaps[:100]}")
                if strategy:
                    print(f"  💭 搜索策略: {strategy[:100]}")

            # ---- 执行搜索 ----
            print(f"  ⏳ 正在搜索...", end=" ", flush=True)
            search_result = web_search(query, max_results=5)
            snippets = extract_key_snippets(search_result)
            print(f"获得 {len(snippets)} 条结果 ({len(search_result)} chars)")

            # ---- 记录本轮数据 ----
            round_data[round_num] = {
                "role": "tool_call",
                "query": query,
                "reasoning_analysis": reasoning,
                "search_result_length": len(search_result),
                "search_result_snippets": len(snippets),
                "search_result_preview": search_result[:300],
            }

            # ---- 分析阶段（核心！）----
            # 第2轮及以上：检查 reasoning 是否引用了上一轮的真实数据
            if round_num >= 2:
                prev_data = round_data.get(round_num - 1, {})
                prev_result_text = prev_data.get("_full_result", "")

                # 保存本轮结果供下一轮分析
                round_data[round_num]["_full_result"] = search_result

                if findings and findings != ["initial_search"]:
                    print(f"\n  🔬 ==== 核心分析: 第{round_num}轮引用是否真实 ====")
                    analysis = analyze_references(
                        findings, prev_result_text,
                        extract_key_snippets(prev_result_text)
                    )
                    print_analysis(analysis)
                    round_data[round_num]["reference_analysis"] = analysis
                else:
                    print(f"\n  ⚠️ 第{round_num}轮未提供具体引用 (findings={findings})")
                    print(f"     → 可能原因: LLM 在第一轮就完成了，或者 reasoning 字段为空")
            else:
                # 第1轮：保存结果供第2轮分析
                round_data[round_num]["_full_result"] = search_result

            # ---- 注入 tool result ----
            # 注入 assistant message（含 tool_call）
            messages.append({
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
            })

            # 注入 tool result
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": search_result,
            })

            # 保存本轮的完整消息快照
            save_round_data(round_num, {
                "query": query,
                "reasoning_analysis": reasoning,
                "search_result_length": len(search_result),
                "messages_count": len(messages),
                "token_usage": {"input": in_tokens, "output": out_tokens},
            })

    # ---- 最终汇总 ----
    print_header("Step 1 测试完成 —— 汇总")
    print(f"  总轮次: {len([k for k in round_data if isinstance(k, int)])}")
    print(f"  Tool Call 轮次: {len([k for k, v in round_data.items() if isinstance(k, int) and v.get('role') == 'tool_call'])}")

    # 如果执行到第2+轮，汇总引用分析
    all_analyses = []
    for rn, rd in round_data.items():
        if isinstance(rn, int) and "reference_analysis" in rd:
            all_analyses.append(rd["reference_analysis"])

    if all_analyses:
        print(f"\n  📊 全局引用分析:")
        for i, a in enumerate(all_analyses):
            print(f"     第{2+i}轮: 准确率 {a['matched']}/{a['total']} "
                  f"(精确), +{a['partial']}/{a['total']} (部分)")
            if a['total'] > 0:
                acc = (a['matched'] + a['partial'] * 0.5) / a['total']
                print(f"             加权准确率: {acc:.0%}")

        # 总体结论
        total_matched = sum(a["matched"] for a in all_analyses)
        total_partial = sum(a["partial"] for a in all_analyses)
        total_all = sum(a["total"] for a in all_analyses)
        if total_all > 0:
            overall_acc = (total_matched + total_partial * 0.5) / total_all
            print(f"\n  🏆 总体判定:")
            if overall_acc >= 0.7:
                print(f"     ✅ 通过: 加权准确率 {overall_acc:.0%} ≥ 70%")
                print(f"     → Direction 1 基础假设成立，LLM 确实能在 tool_call 中引用真实数据")
            elif overall_acc >= 0.4:
                print(f"     ⚠️ 部分通过: 加权准确率 {overall_acc:.0%}")
                print(f"     → 引用存在但不稳定，需要优化 tool 设计或 prompt 约束")
            else:
                print(f"     ❌ 不通过: 加权准确率 {overall_acc:.0%} < 40%")
                print(f"     → LLM 无法可靠引用上一轮数据，本方向需要重新审视")
    else:
        print(f"\n  ⚠️ 没有收集到第2+轮的引用数据（LLM 可能1轮就结束了）")
        print(f"  → 需要调整 prompt 鼓励更多轮次，或以当前结果评估")

    # 保存完整记录
    summary_path = os.path.join(RESULT_DIR, f"foundation_summary_{TIMESTAMP}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "test": "foundation_test",
            "timestamp": TIMESTAMP,
            "model": DEFAULT_MODEL,
            "rounds": {str(k): v for k, v in round_data.items()},
            "final_answer": final_answer,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 完整记录已保存: {os.path.basename(summary_path)}")


if __name__ == "__main__":
    main()
