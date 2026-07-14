#!/usr/bin/env python3
"""
agent_exp v6 — Prompt-Level Tool Calling

专为不支持原生 tool_calls 的模型（deepseek-r1:8b 等）设计。
不使用 API 的 tools 参数，而是把工具定义嵌入 system prompt，
LLM 在文字中输出 [TOOL_CALL] 标记，Python 解析执行。

结束条件同 v5：
  1. LLM 输出 [FINAL_ANSWER] → 显式确认完成
  2. 收敛检测：连续 3 轮路由结果（top field_id）未变化 → 终止
  3. 最大轮次 10 → 安全阀
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
MODEL = os.environ.get("OLLAMA_MODEL", "deepseek-r1:8b")
MAX_ROUNDS = 10
MAX_TOKENS = 4096  # deepseek 思链长，需要更多 tokens

# ── Tool 定义（嵌入 system prompt） ──

TOOL_DEFINITIONS = """
## 可用工具

你必须在每一轮回复中决定：调用工具 or 输出 [FINAL_ANSWER]。

### 工具调用规则
- 回复中用 [TOOL_CALL] 工具名(参数JSON) 来调用工具
- 每轮只调一个工具，等结果回来再决定下一步
- 绝对不要假设工具返回结果——必须实际调用工具
- 示例: [TOOL_CALL] route_query({"keywords": ["涨跌幅"], "entity_type": "stock_code", "entity_value": "300750.SZ"})

### route_query
执行路由查询，输入关键词返回匹配的 DataField。
参数: keywords(string[]), entity_type(""|"stock_code"|"sector_name"|"index_code"), entity_value(string), strict(bool)

### fetch_data
路由后取数。先 route_query 确定 field_id 再调此工具。
参数: field_id(string), entity_type(string), entity_value(string), time_start(string), time_end(string)

### 重要
- 思考要简洁。想清楚后直接输出 [TOOL_CALL] 开始调用
- 不要替系统执行查询——你不调工具就不可能有数据返回
"""

TOOL_CALL_PATTERN = re.compile(
    r'\[TOOL_CALL\]\s*(\w+)\(([^)]*)\)',
    re.IGNORECASE,
)


def build_system_prompt() -> str:
    """组装 system prompt：角色定义 + 路由知识 + 工具定义"""
    base = build_prompt({"route_expert"})
    return base + "\n" + TOOL_DEFINITIONS


def extract_field_ids(result_text: str) -> list[str]:
    return re.findall(r'FIELD_[A-Z_]+', result_text)


def fmt_route_result(route_out: dict) -> str:
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


def parse_tool_call(text: str) -> tuple[str, dict] | None:
    """从 LLM 回复中解析 [TOOL_CALL] 标记

    Returns:
        (tool_name, args_dict) or None
    """
    # 先移除 <think> 块
    text_clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    match = TOOL_CALL_PATTERN.search(text_clean)
    if not match:
        return None

    tool_name = match.group(1).lower()
    args_str = match.group(2).strip()

    try:
        args = json.loads(args_str) if args_str else {}
    except json.JSONDecodeError:
        # 尝试补全：单引号→双引号，key 加引号
        try:
            args_str_fixed = args_str.replace("'", '"')
            args = json.loads(args_str_fixed)
        except json.JSONDecodeError:
            return None

    return tool_name, args


def main():
    user_query = sys.argv[1] if len(sys.argv) > 1 else "宁德时代今天上午的涨跌幅如何？"
    run_id = uuid.uuid4().hex[:8]

    print(f"{'='*70}")
    print(f"  🧪 路由解析 Agent v6 — Prompt-Level Tool Calling")
    print(f"  模型: {MODEL}   RunID: {run_id}")
    print(f"  Query: {user_query}")
    print(f"{'='*70}")

    # System prompt
    system_prompt = build_system_prompt()
    system_len = len(system_prompt)
    print(f"\n🔧 System prompt: {system_len} chars")

    # Router
    route_tool = get_route_tool()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    rounds_log = []
    field_history: list[str] = []
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
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=MAX_TOKENS,
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

        # ── 打印 LLM 思考/回复 ──
        if msg.content:
            # 检查是否有 think 块
            think_match = re.search(r'<think>(.*?)</think>', msg.content, re.DOTALL)
            if think_match:
                print(f"\n  🤔 思考:")
                think_text = think_match.group(1)
                for line in think_text.strip().split("\n")[:6]:
                    print(f"     {line}")
                if len(think_text.split("\n")) > 6:
                    print(f"     ...（{len(think_text)} chars）")

            # 打印回复（不含 think 块）
            reply = re.sub(r'<think>.*?</think>', '', msg.content, flags=re.DOTALL).strip()
            if reply:
                print(f"\n  💬 回复 ({len(reply)} chars):")
                for line in reply.split("\n")[:5]:
                    print(f"     {line}")
                if len(reply.split("\n")) > 5:
                    print(f"     ...")
        else:
            print(f"  💬 回复: (空)")

        # ── 条件 1: [FINAL_ANSWER] ──
        if "[FINAL_ANSWER]" in (msg.content or ""):
            final_answer = msg.content
            stop_reason = "final_answer_tag"
            print(f"\n  ✅ [FINAL_ANSWER] 显式确认，终止")
            break

        # ── 解析工具调用 ──
        parsed = parse_tool_call(msg.content or "")

        # ── 条件 2: finish=length（思链过长截断） ──
        if finish == "length":
            if parsed:
                print(f"\n  📐 finish=length，但已检测到工具调用，执行")
            else:
                print(f"\n  ✂️  思链过长截断（{len(msg.content or '')} chars），强制要求工具调用")
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({
                    "role": "user",
                    "content": "思考已截断。直接输出 [TOOL_CALL] 调用工具，不要继续思考。",
                })
                continue

        # ── 条件 3: finish=stop 且无工具调用 ──
        if finish == "stop" and not parsed:
            if msg.content:
                final_answer = msg.content
                stop_reason = "stop_no_tool"
                print(f"\n  ⏹  finish=stop，无工具调用，视为最终回答")
            else:
                stop_reason = "stop_empty"
                print(f"\n  ⚠️  finish=stop 且内容为空")
            break

        # ── 条件 4: 仍无工具调用 ──
        if not parsed:
            print(f"\n  ⚠️  未检测到 [TOOL_CALL]（finish={finish}），继续引导")
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": "请调用工具。输出一行 [TOOL_CALL] 工具名({\"参数\": \"值\"}) 来调用，不要替系统模拟执行。",
            })
            continue

        tool_name, tool_args = parsed
        print(f"\n  🛠  TOOL CALL: {tool_name}")
        print(f"      args: {json.dumps(tool_args, ensure_ascii=False)}")

        # ── 执行工具 ──
        t_route = time.time()
        result_text = ""
        fields_count = 0
        field_ids = []

        if tool_name == "route_query":
            route_out = route_tool.query(
                keywords=tool_args.get("keywords", []),
                intent_type=tool_args.get("intent_type", "fact"),
                entity_type=tool_args.get("entity_type", ""),
                entity_value=tool_args.get("entity_value", ""),
                time_start=tool_args.get("time_start", ""),
                time_end=tool_args.get("time_end", ""),
                strict=tool_args.get("strict", False),
            )
            result_text = fmt_route_result(route_out)
            fields_count = route_out["fields_count"]
            field_ids = extract_field_ids(result_text)
            route_time = time.time() - t_route
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

        elif tool_name == "fetch_data":
            result_text = route_tool.fetch(
                field_id=tool_args.get("field_id", ""),
                entity_type=tool_args.get("entity_type", ""),
                entity_value=tool_args.get("entity_value", ""),
                time_start=tool_args.get("time_start", ""),
                time_end=tool_args.get("time_end", ""),
            )
            route_time = time.time() - t_route
            print(f"     📤 取数完成 ({route_time:.2f}s)")

        else:
            result_text = f"错误: 未知工具 {tool_name}"
            route_time = time.time() - t_route
            print(f"     ❌ 未知工具: {tool_name}")

        # 记录日志
        rounds_log.append({
            "round": round_num,
            "tool": tool_name,
            "tool_args": tool_args,
            "fields_count": fields_count,
            "field_ids": field_ids,
        })

        # ── 注入 assistant 回复 + tool result ──
        messages.append({"role": "assistant", "content": msg.content or ""})
        messages.append({"role": "user", "content": f"工具返回:\n{result_text}"})

        # 路由无匹配提示
        if tool_name == "route_query" and fields_count == 0:
            print(f"\n  ⚠️  无匹配")
            messages.append({
                "role": "user",
                "content": "没有匹配到任何字段，请换关键词重试，或输出 [FINAL_ANSWER] 告知用户该指标不存在。",
            })

        # fetch_data 完成后引导回答
        if tool_name == "fetch_data":
            messages.append({
                "role": "user",
                "content": "根据以上数据，回答用户的原始问题。完成后输出 [FINAL_ANSWER]。",
            })

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
    save_path = os.path.join(RESULTS_DIR, f"agent_pt_{ts}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  💾 JSON: {save_path}")

    log_path = os.path.join(RESULTS_DIR, f"agent_pt_{ts}_{run_id}.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent 路由解析日志（Prompt-Level Tool Calling）\n\n")
        f.write(f"- **查询**: {user_query}\n- **模型**: {MODEL}\n- **时间**: {ts}\n- **停止原因**: {stop_reason}\n- **工具调用**: {len(rounds_log)} 轮\n\n---\n\n")
        for r in rounds_log:
            f.write(f"## Round {r['round']}\n\n")
            f.write(f"**工具**: {r['tool']}\n\n")
            f.write(f"**参数**:\n```json\n{json.dumps(r['tool_args'], ensure_ascii=False, indent=2)}\n```\n\n")
            f.write(f"**结果**: {r['fields_count']} 个字段: {r['field_ids']}\n\n---\n\n")
        if final_answer:
            f.write(f"## 最终决策\n\n")
            f.write(f"**停止原因**: {stop_reason}\n\n")
            f.write(f"{final_answer}\n")
    print(f"  📝 Log: {log_path}")


if __name__ == "__main__":
    main()
