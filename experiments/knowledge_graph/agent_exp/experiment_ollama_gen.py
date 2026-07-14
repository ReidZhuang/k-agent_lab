#!/usr/bin/env python3
"""
agent_exp v7 — Ollama Generate API (绕过 chat API 模板渲染问题)

专为 ollama 模板渲染有问题的模型设计（如 glm4:9b-chat）。
直接使用 /api/generate 端点，手动构造 prompt 文本，
解析 LLM 输出中的工具调用标记。

支持模型：
  - glm4:9b-chat-* 系列
  - deepseek-r1:8b（含 <think> 块处理）

结束条件：
  1. [FINAL_ANSWER] → 显式确认
  2. 收敛检测：连续 3 轮 top field 相同
  3. 最大轮次 10
"""
import json, os, sys, time, uuid, re
import requests

_EXP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_EXP_DIR))

from core import build_prompt
from core.route_tool import get_route_tool

RESULTS_DIR = os.path.join(_EXP_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "glm4:9b-chat-q4_K_M")
MAX_ROUNDS = 10
MAX_TOKENS = 2048

# ── 工具定义（嵌入 prompt） ──

TOOL_DEFS = """
## 可用工具

每次只能调用一个工具，写出函数名和参数，然后停止。系统会执行并返回结果。
绝对不要替系统模拟结果。不要写出你期望的返回——你没有权限访问数据，必须通过工具调用。

调用格式：函数名(参数名=值, ...)
例如：route_query(keywords=["涨跌幅"], entity_type="stock_code", entity_value="300750.SZ")

### route_query
作用：匹配知识图谱中的 DataField
参数：keywords(list[str]), entity_type(str), entity_value(str), strict(bool)

### fetch_data
作用：根据 field_id 获取真实数据
参数：field_id(str), entity_value(str), time_start(str), time_end(str)

规则：
- 看到"工具返回:"之前，不要做任何分析
- 确认得到数据后，输出 [FINAL_ANSWER]
"""


def call_llm(prompt_text: str) -> str:
    """调用 ollama /api/generate"""
    resp = requests.post(f"{OLLAMA_BASE}/api/generate", json={
        "model": MODEL,
        "prompt": prompt_text,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": MAX_TOKENS},
    }, timeout=180)
    data = resp.json()
    return data.get("response", "")


def parse_tool_call(text: str) -> tuple[str, dict] | None:
    """从 LLM 回复中解析工具调用

    支持格式（按优先级）：
      1. [TOOL_CALL] fn({...})
      2. fn(key=val, key=val)  — GLM 常用格式，可能包裹在代码块中
      3. fn_name\\n{json_args}
      4. {"name": "fn", "parameters": {...}}
    """
    if not text:
        return None

    # 格式1: [TOOL_CALL]
    m = re.search(r'\[TOOL_CALL\]\s*(\w+)\s*\(\s*(\{.*?\})\s*\)', text, re.DOTALL)
    if m:
        try:
            return m.group(1).lower(), json.loads(m.group(2))
        except json.JSONDecodeError:
            pass

    # 格式2: fn(key=val, ...) — GLM 风格
    # 可能在 ``` 代码块中
    blocks = re.findall(r'```(?:\w*)\s*(.*?)```', text, re.DOTALL)
    for block in blocks:
        m = re.search(r'(route_query|fetch_data)\s*\((.+?)\)', block, re.DOTALL)
        if m:
            args = _parse_glm_args(m.group(2))
            if args is not None:
                return m.group(1).lower(), args
    # 也在正文中查找
    for text_to_search in [text]:
        m = re.search(r'(route_query|fetch_data)\s*\((.+?)\)', text_to_search, re.DOTALL)
        if m:
            args = _parse_glm_args(m.group(2))
            if args is not None:
                return m.group(1).lower(), args

    # 格式3: fn_name\\n{json_args}
    m = re.search(r'(?:^|\n)(route_query|fetch_data)\s*\n\s*(\{.*?\})(?:\n|$)', text, re.DOTALL)
    if m:
        try:
            return m.group(1).lower(), json.loads(m.group(2))
        except json.JSONDecodeError:
            pass

    # 格式4: JSON function call
    m = re.search(r'\{"name"\s*:\s*"(route_query|fetch_data)"', text)
    if m:
        try:
            # 查找完整 JSON 对象
            start = text.index('{"name"', text.index(m.group(0)))
            end = start
            depth = 0
            for i, c in enumerate(text[start:]):
                if c == '{': depth += 1
                if c == '}': depth -= 1
                if depth == 0: end = start + i + 1; break
            obj = json.loads(text[start:end])
            fn_name = obj.get("name", "").lower()
            params = obj.get("parameters") or obj.get("arguments") or {}
            return fn_name, params
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _parse_glm_args(args_str: str) -> dict | None:
    """解析 GLM 风格参数：key=val, key=["a","b"], key=True"""
    args = {}
    # 保护字符串和列表内容，避免内部逗号干扰拆分
    # 先替换 [...] 和 "..." 为占位符
    placeholders = {}
    def _protect(m):
        idx = len(placeholders)
        placeholders[f'__ARR_{idx}__'] = m.group(0)
        return f'__ARR_{idx}__'
    # 保护 [...] 列表
    s = re.sub(r'\[.*?\]', _protect, args_str)
    # 保护 "..." 字符串
    s = re.sub(r'"[^"]*"', _protect, s)

    pairs = [p.strip() for p in s.split(',') if p.strip()]
    for pair in pairs:
        if '=' not in pair:
            continue
        key, val = pair.split('=', 1)
        key = key.strip()
        val = val.strip()
        # 还原占位符
        for ph, orig in placeholders.items():
            val = val.replace(ph, orig)
        # 解析值
        try:
            args[key] = json.loads(val)
        except (json.JSONDecodeError, ValueError):
            # 字符串
            args[key] = val.strip('\'"')
    return args if args else None


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


def main():
    user_query = sys.argv[1] if len(sys.argv) > 1 else "宁德时代今天上午的涨跌幅如何？"
    run_id = uuid.uuid4().hex[:8]

    print(f"{'='*70}")
    print(f"  🧪 路由解析 Agent v7 — Ollama Generate API")
    print(f"  模型: {MODEL}   RunID: {run_id}")
    print(f"  Query: {user_query}")
    print(f"{'='*70}")

    # 组装 prompt
    system_base = build_prompt({"route_expert"})
    full_prompt = system_base + "\n" + TOOL_DEFS
    print(f"\n🔧 System prompt: {len(full_prompt)} chars")

    route_tool = get_route_tool()

    # 维护对话历史（文本格式）
    history_parts = [full_prompt, f"\n用户: {user_query}"]
    rounds_log = []
    field_history: list[str] = []
    final_answer = None
    stop_reason = ""

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n{'─'*60}")
        print(f"  🔄 Round {round_num}/{MAX_ROUNDS}")
        print(f"{'─'*60}")

        current_prompt = "\n\n".join(history_parts)

        # ── 调用 LLM ──
        t0 = time.time()
        try:
            response = call_llm(current_prompt)
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            stop_reason = f"api_error: {e}"
            break

        elapsed = time.time() - t0
        print(f"  ⏱  {elapsed:.1f}s | response={len(response)} chars")

        # 打印回复
        if response:
            # 截断显示
            lines = response.strip().split("\n")
            print(f"\n  💬 回复 ({len(response)} chars):")
            for line in lines[:6]:
                print(f"     {line}")
            if len(lines) > 6:
                print(f"     ...")
        else:
            print(f"  💬 回复: (空)")

        # ── 解析工具调用（先于 FINAL_ANSWER 检查，防模型同时输出两者） ──
        parsed = parse_tool_call(response)

        # ── [FINAL_ANSWER] 检查：仅在无工具调用时视为终止 ──
        if "[FINAL_ANSWER]" in response and not parsed:
            final_answer = response
            stop_reason = "final_answer_tag"
            print(f"\n  ✅ [FINAL_ANSWER] 显式确认，终止")
            break
        if not parsed:
            print(f"\n  ⏹  无工具调用，视为最终回答")
            final_answer = response
            stop_reason = "no_tool_call"
            break

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

            # 收敛检测
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

        rounds_log.append({
            "round": round_num,
            "tool": tool_name,
            "tool_args": tool_args,
            "fields_count": fields_count,
            "field_ids": field_ids,
        })

        # ── 注入历史 ──
        history_parts.append(f"助手: {response}")
        history_parts.append(f"系统: 工具返回:\n{result_text}")

        # fetch 后引导
        if tool_name == "fetch_data":
            history_parts.append("系统: 根据以上数据回答用户问题，然后输出 [FINAL_ANSWER]。")

    # ── 汇总 ──
    print(f"\n{'='*70}")
    print(f"  📋 实验汇总")
    print(f"{'='*70}")
    print(f"  查询: {user_query}")
    print(f"  模型: {MODEL}")
    print(f"  停止原因: {stop_reason}")
    print(f"  工具调用: {len(rounds_log)} 轮")
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
        "total_calls": len(rounds_log),
        "stop_reason": stop_reason,
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "rounds": rounds_log,
    }
    save_path = os.path.join(RESULTS_DIR, f"agent_og_{ts}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  💾 JSON: {save_path}")

    log_path = os.path.join(RESULTS_DIR, f"agent_og_{ts}_{run_id}.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Agent 路由解析日志（Ollama Generate API）\n\n")
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
