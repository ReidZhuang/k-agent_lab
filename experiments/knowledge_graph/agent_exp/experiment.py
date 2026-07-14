#!/usr/bin/env python3
"""
agent_exp v5 — 路由解析 Agent 实验

结束条件（任一满足即止）：
  1. LLM 输出 [FINAL_ANSWER] → 显式确认完成
  2. 路由返回 1 个 field + LLM 验证通过 → 收敛终止
  3. 收敛检测：连续 3 轮路由结果（top field_id）未变化 → 死循环终止
  4. 最大轮次 10 → 安全阀

结构化验证：
  LLM 自己验证——看到单字段的结果 + 原始 query → 回答"是/否"
  Python 不做任何 domain→entity 的硬编码判断

数据流追踪：
  每轮注入 tool result 时会打印完整内容，看到底什么数据进了下一轮 LLM
"""
import json, os, sys, time, uuid, re
from openai import OpenAI

_EXP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_EXP_DIR))

from core import build_prompt
from core.route_tool import get_route_tool

RESULTS_DIR = os.path.join(_EXP_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
MAX_ROUNDS = 10


def extract_field_ids(result_text: str) -> list[str]:
    """从路由结果文本中提取所有 field_id"""
    return re.findall(r'FIELD_[A-Z_]+', result_text)


def fmt_route_result(route_out: dict) -> str:
    """路由结果 → LLM 可读文本"""
    lines = [f"【路由结果】共匹配到 {route_out['fields_count']} 个 DataField"]
    if route_out["fields_count"] == 0:
        return "\n".join(lines)
    for i, f_text in enumerate(route_out["fields"]):
        lines.append(f"\n── Field #{i+1} ──")
        lines.append(f_text)
    if route_out["concept_id"]:
        lines.append(f"\n📌 主概念：{route_out['concept_id']}（{route_out['concept_name']}）")
    if route_out["datasource_id"]:
        lines.append(f"🔌 主数据源：{route_out['datasource_id']} | 协议={route_out['datasource_protocol']}")
    return "\n".join(lines)


def main():
    user_query = sys.argv[1] if len(sys.argv) > 1 else "宁德时代今天上午的涨跌幅如何？"
    run_id = uuid.uuid4().hex[:8]

    print(f"{'='*70}")
    print(f"  🧪 路由解析 Agent 实验 v5")
    print(f"  模型: {MODEL}   RunID: {run_id}")
    print(f"  Query: {user_query}")
    print(f"{'='*70}")

    # System
    system_prompt = build_prompt({"route_expert"})
    print(f"\n🔧 System prompt: {len(system_prompt)} chars")

    # Router + 取数工具
    route_tool = get_route_tool()
    tools = [route_tool.to_openai_tool(), route_tool.to_fetch_tool_schema()]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    rounds_log = []
    field_history: list[str] = []  # 用于收敛检测
    final_answer = None
    stop_reason = ""

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n{'─'*60}")
        print(f"  🔄 Round {round_num}/{MAX_ROUNDS}")
        print(f"{'─'*60}")

        # ── 调用 LLM ──
        t0 = time.time()
        try:
            resp = _client.chat.completions.create(
                model=MODEL, messages=messages, tools=tools,
                temperature=0.1, max_tokens=2048,
            )
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            stop_reason = f"api_error: {e}"
            break

        elapsed = time.time() - t0
        choice = resp.choices[0]
        msg = choice.message
        finish = choice.finish_reason
        usage = resp.usage
        print(f"  ⏱  {elapsed:.1f}s | in={usage.prompt_tokens if usage else '?'} out={usage.completion_tokens if usage else '?'} | finish={finish}")

        if msg.content:
            clines = msg.content.strip().split("\n")
            print(f"\n  💬 思考:")
            for line in clines[:6]:
                print(f"     {line}")
            if len(clines) > 6:
                print(f"     ...（共 {len(msg.content)} chars）")

        # ── 条件 1: [FINAL_ANSWER] 显式确认 ──
        if "[FINAL_ANSWER]" in (msg.content or ""):
            final_answer = msg.content
            stop_reason = "final_answer_tag"
            print(f"\n  ✅ [FINAL_ANSWER] 显式确认，终止")
            break

        # ── 条件 2/3: tool_calls ──
        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                print(f"  ❌ 参数 JSON 解析失败")
                continue

            print(f"\n  🛠  CALL: {fn_name}")
            print(f"      {json.dumps(fn_args, ensure_ascii=False, indent=6)}")

            t_route = time.time()

            if fn_name == "route_query":
                route_out = route_tool.query(
                    keywords=fn_args.get("keywords", []),
                    intent_type=fn_args.get("intent_type", "fact"),
                    entity_type=fn_args.get("entity_type", ""),
                    entity_value=fn_args.get("entity_value", ""),
                    time_start=fn_args.get("time_start", ""),
                    time_end=fn_args.get("time_end", ""),
                    strict=fn_args.get("strict", False),
                )
                route_time = time.time() - t_route
                result_text = fmt_route_result(route_out)
                fields_count = route_out["fields_count"]
                field_ids = extract_field_ids(result_text)
                print(f"     📤 {fields_count} 个字段 ({route_time:.2f}s): {field_ids}")

                # ── 收敛检测 ──
                if field_ids:
                    field_history.append(field_ids[0])
                    if len(field_history) >= 3 and len(set(field_history[-3:])) == 1:
                        print(f"\n  ⏹  收敛检测：连续 3 轮 top field = {field_history[-1]}，终止")
                        final_answer = f"路由收敛于 {field_history[-1]}"
                        stop_reason = "convergence"
                        break
                else:
                    field_history.append("__empty__")

                # ── 单字段引导验证 ──
                if fields_count == 1:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"找到唯一匹配。你可调用 fetch_data 直接取数查看实际数据，"
                            f"或确认结果后输出 [FINAL_ANSWER]。"
                        )
                    })

            elif fn_name == "fetch_data":
                result_text = route_tool.fetch(
                    field_id=fn_args.get("field_id", ""),
                    entity_type=fn_args.get("entity_type", ""),
                    entity_value=fn_args.get("entity_value", ""),
                    time_start=fn_args.get("time_start", ""),
                    time_end=fn_args.get("time_end", ""),
                )
                route_time = time.time() - t_route
                print(f"     📤 取数完成 ({route_time:.2f}s)")
                # 引导 LLM 回答用户
                messages.append({
                    "role": "user",
                    "content": f"{result_text}\n\n根据以上数据，回答用户的原始问题。完成后输出 [FINAL_ANSWER]。"
                })

            # 记录
            rounds_log.append({
                "round": round_num,
                "route_args": fn_args,
                "fields_count": fields_count,
                "field_ids": field_ids,
                "concept": route_out["concept_name"],
                "datasource": route_out["datasource_id"],
                "injected_tool_result": result_text,
            })

            # ── 注入 assistant + tool result ──
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": fn_name, "arguments": tc.function.arguments}}
                ],
            })
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})

            # 无匹配时提示换关键词
            if fn_name == "route_query" and fields_count == 0:
                print(f"\n  ⚠️  无匹配，建议 LLM 换关键词")
                messages.append({
                    "role": "user",
                    "content": "没有匹配到任何字段，请换一组关键词重试。"
                })
            # 多个字段 → 什么都不做，LLM 自然会判断并继续

        elif finish == "stop":
            # LLM 主动停止但没有 [FINAL_ANSWER]
            # 可能是回答了但没标记，也可能是中途跑偏
            if msg.content:
                final_answer = msg.content
                stop_reason = "stop_no_tag"
                print(f"\n  ⏹  finish=stop，但无 [FINAL_ANSWER] 标记，视为最终回答")
            else:
                print(f"\n  ⚠️  finish=stop 且内容为空，可能异常")
                stop_reason = "stop_empty"
            break
        else:
            print(f"\n  ⚠️  未预期的 finish={finish}")
            stop_reason = f"unexpected_finish:{finish}"
            break

    # ── 汇总 ──
    print(f"\n{'='*70}")
    print(f"  📋 实验汇总")
    print(f"{'='*70}")
    print(f"  查询: {user_query}")
    print(f"  模型: {MODEL}")
    print(f"  停止原因: {stop_reason}")
    print(f"  路由调用轮次: {len(rounds_log)}")
    print(f"  最终决策: {'有 ✅' if final_answer else '未确认 ❌'}")

    if final_answer:
        text = re.sub(r'\[/?FINAL_ANSWER\]', '', final_answer).strip()
        print(f"\n  📄 最终输出 ({len(text)} chars):")
        print(f"  {text[:800]}")

    # 保存
    ts = time.strftime("%Y%m%d_%H%M%S")
    output = {
        "query": user_query,
        "model": MODEL,
        "run_id": run_id,
        "timestamp": ts,
        "total_route_calls": len(rounds_log),
        "stop_reason": stop_reason,
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "rounds": rounds_log,
    }
    save_path = os.path.join(RESULTS_DIR, f"agent_route_{ts}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  💾 JSON: {save_path}")

    log_path = os.path.join(RESULTS_DIR, f"agent_route_{ts}_{run_id}.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent 路由解析日志\n\n")
        f.write(f"- **查询**: {user_query}\n- **模型**: {MODEL}\n- **时间**: {ts}\n- **停止原因**: {stop_reason}\n- **路由调用**: {len(rounds_log)} 轮\n\n---\n\n")
        for r in rounds_log:
            f.write(f"## Round {r['round']}\n\n")
            f.write(f"**ROUTE 参数**:\n```json\n{json.dumps(r['route_args'], ensure_ascii=False, indent=2)}\n```\n\n")
            f.write(f"**结果**: {r['fields_count']} 个字段: {r['field_ids']}\n\n")
            f.write(f"**注入 tool result**:\n```\n{r['injected_tool_result']}\n```\n\n")
            f.write(f"概念: {r['concept']} | 数据源: {r['datasource']}\n\n---\n\n")
        if final_answer:
            f.write(f"## 最终决策\n\n")
            f.write(f"**停止原因**: {stop_reason}\n\n")
            f.write(f"{final_answer}\n")
    print(f"  📝 Log: {log_path}")


if __name__ == "__main__":
    main()
