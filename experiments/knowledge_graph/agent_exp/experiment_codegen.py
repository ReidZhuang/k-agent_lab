#!/usr/bin/env python3
"""
experiment_codegen — 取数代码生成 Agent 实验

测试方式：给定 field_id + 实体，用 agent_coder/ 的 prompt 引导 LLM
迭代生成取数代码，compile() 检查语法，executor 执行，出错则修复重试。

结束条件：
  1. 代码成功执行 → [FINAL_ANSWER]
  2. 连续 3 次修复失败 → [FINAL_ANSWER] 说明错误
"""
import json, os, sys, time, re, traceback
from openai import OpenAI

_EXP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_EXP_DIR))

from core import build_prompt
from irkg.sql_gen import build_sql_prompt, parse_llm_output, merge_with_template
from irkg.types import RouteCondition, RouteResult, FieldInfo
from irkg.graph import GraphQuerier
from scripts.executor import execute_code

RESULTS_DIR = os.path.join(_EXP_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
MAX_ROUNDS = 5  # 含重试


def build_coder_system() -> str:
    """组装 codegen agent 的 system prompt"""
    return build_prompt({"code_expert"}, agent_dir=os.path.join(_EXP_DIR, "agent_coder"))


def build_codegen_task(field_id: str, entity_type: str = "",
                       entity_value: str = "",
                       time_start: str = "", time_end: str = "") -> tuple[str, str, RouteResult | None]:
    """构造代码生成任务的 prompt，返回 (prompt, ds_protocol, route_result)"""
    graph = GraphQuerier()

    field_node = graph.get_field_by_id(field_id)
    if not field_node:
        return f"错误: 字段 {field_id} 不在知识图谱中", "", None

    ds = graph.get_datasource(field_id)
    if not ds:
        return f"错误: 字段 {field_id} 没有关联数据源", "", None

    cond = RouteCondition(
        entity_type=entity_type, entity_value=entity_value,
        time_range_start=time_start, time_range_end=time_end,
    )

    result = RouteResult(intent_type="fact", conditions=cond, concept_id="", datasource=ds)
    result.fields.append(FieldInfo(
        id=field_id,
        standard_name=field_node.standard_name,
        description=field_node.description,
        data_type=field_node.data_type,
        unit=field_node.unit,
        api_column=field_node.api_column,
        granularity=field_node.granularity,
        refresh_time=field_node.refresh_time,
    ))

    task_prompt = build_sql_prompt(result)
    return task_prompt, ds.protocol or "", result


def parse_python_code(text: str) -> str | None:
    """从 LLM 回复中提取 ```python 代码块"""
    m = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def syntax_check(code: str) -> str | None:
    """compile() 语法检查，通过返回 None，失败返回错误信息"""
    try:
        compile(code, '<codegen>', 'exec')
        return None
    except SyntaxError as e:
        return f"语法错误: 行{e.lineno}: {e.msg}\n{e.text}"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 experiment_codegen.py <field_id> [entity_value]")
        print("示例: python3 experiment_codegen.py FIELD_QUOTE_PCT_CHG 300750.SZ")
        sys.exit(1)

    field_id = sys.argv[1]
    entity_value = sys.argv[2] if len(sys.argv) > 2 else "300750.SZ"
    entity_type = sys.argv[3] if len(sys.argv) > 3 else "stock_code"

    run_id = os.urandom(4).hex()
    print(f"{'='*70}")
    print(f"  🧪 取数代码生成 Agent 实验")
    print(f"  模型: {MODEL}  RunID: {run_id}")
    print(f"  Field: {field_id}  Entity: {entity_value}")
    print(f"{'='*70}")

    # 1. 组装 system prompt
    system_prompt = build_coder_system()
    print(f"\n🔧 System prompt ({len(system_prompt)} chars)\n")

    # 2. 构造 task prompt
    task_prompt, protocol, route_result = build_codegen_task(
        field_id, entity_type=entity_type, entity_value=entity_value,
    )
    if route_result is None:
        print(f"❌ {task_prompt}")
        sys.exit(1)
    print(f"📋 Task prompt ({len(task_prompt)} chars)")
    print(f"   数据源: {route_result.datasource.id} 协议: {protocol}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"以下是生成代码需要的关键信息\n\n{task_prompt}"},
    ]

    round_log = []
    final_answer = None
    stop_reason = ""
    error_count = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n{'─'*50}")
        print(f"  🔄 Round {round_num}/{MAX_ROUNDS}")
        print(f"{'─'*50}")

        t0 = time.time()
        try:
            resp = _client.chat.completions.create(
                model=MODEL, messages=messages,
                temperature=0.1, max_tokens=1024,
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
        print(f"  ⏱  {elapsed:.1f}s | in={usage.prompt_tokens if usage else '?'} out={usage.completion_tokens if usage else '?'}")

        if msg.content:
            preview = msg.content.strip()[:300]
            print(f"  💬 回复 ({len(msg.content)} chars):\n     {preview[:200]}...")

        # [FINAL_ANSWER]
        if "[FINAL_ANSWER]" in (msg.content or ""):
            final_answer = msg.content
            stop_reason = "final_answer"
            print(f"\n  ✅ [FINAL_ANSWER]")
            break

        # 解析代码
        code = parse_python_code(msg.content or "")
        if not code:
            print(f"  ⚠️  未找到代码块")
            error_count += 1
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({"role": "user", "content": "请将代码放在 ```python 代码块中。重新生成。"})
            continue

        print(f"  📝 代码 ({len(code)} chars):\n{code[:200]}...")

        # compile() 语法检查
        syntax_err = syntax_check(code)
        if syntax_err:
            print(f"  ❌ 语法检查失败:\n     {syntax_err}")
            error_count += 1
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": f"代码语法错误:\n{syntax_err}\n\n修正后重新生成。"
            })
            continue

        print(f"  ✅ 语法检查通过")

        # 注入协议模板 + 执行
        full_code = merge_with_template(code, protocol)
        exec_result = execute_code(full_code)

        if exec_result["success"]:
            result_data = exec_result.get("result", [])
            if result_data:
                print(f"  ✅ 执行成功: _result = {result_data}")
                final_answer = f"取数成功: {result_data}"
            else:
                print(f"  ✅ 执行成功:\n     {exec_result['output'][:200]}")
                final_answer = f"取数成功:\n{exec_result['output']}"
            stop_reason = "exec_success"
            break
        else:
            err_msg = exec_result.get("error", "未知错误")
            print(f"  ❌ 执行失败:\n     {err_msg[:200]}")
            error_count += 1
            if error_count >= 3:
                print(f"\n  ⏹  连续 {error_count} 次失败，终止")
                final_answer = f"取数失败（已重试{error_count}次）:\n{err_msg}"
                stop_reason = "max_retries"
                break

            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": f"代码执行报错:\n{err_msg}\n\n分析错误原因并修复代码。"
            })

    # 汇总
    print(f"\n{'='*70}")
    print(f"  📋 实验汇总")
    print(f"{'='*70}")
    print(f"  Field: {field_id}")
    print(f"  实体: {entity_value}")
    print(f"  模型: {MODEL}")
    print(f"  停止原因: {stop_reason}")
    print(f"  错误次数: {error_count}")
    print(f"  最终结果: {'有 ✅' if final_answer else '无 ❌'}")

    if final_answer:
        out = re.sub(r'\[/?FINAL_ANSWER\]', '', final_answer).strip()
        print(f"\n  📄 输出:\n  {out[:500]}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    output = {
        "field_id": field_id,
        "entity_value": entity_value,
        "model": MODEL,
        "protocol": protocol,
        "stop_reason": stop_reason,
        "error_count": error_count,
        "has_result": bool(final_answer),
        "result": final_answer,
    }
    save_path = os.path.join(RESULTS_DIR, f"codegen_{ts}_{run_id}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  💾 已保存: {save_path}")


if __name__ == "__main__":
    main()
