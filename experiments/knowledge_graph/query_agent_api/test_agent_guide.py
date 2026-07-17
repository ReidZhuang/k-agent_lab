#!/usr/bin/env python3
"""
test_agent_guide — agent_guide 的测试和调优工具

测试 agent_guide 的 query 解析能力：输入 NL query，输出结构化 dict，
然后校验格式是否正确，并人工评估语义准确性。

用法:
    # 测试单个 query
    python3 test_agent_guide.py "宁德时代今天的涨跌幅"

    # 测试全部预置用例
    python3 test_agent_guide.py --all

    # 保存中间结果到文件
    python3 test_agent_guide.py "宁德时代的涨跌幅" --save
"""
import json, os, sys, time, re, uuid
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_QA_DIR))

from core import build_prompt

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
MAX_RETRIES = 3  # 格式不合格时的重试次数

# ── 测试用例集 ──
TEST_CASES = [
    # 基础 - 单指标
    {
        "id": "TC-01",
        "query": "宁德时代今天的涨跌幅",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 多指标
    {
        "id": "TC-02",
        "query": "查询宁德时代今天的最高价和最低价",
        "expect_chain": False,
        "expect_count": 2,
    },
    # 多主体同指标
    {
        "id": "TC-03",
        "query": "我想知道比亚迪和宁德时代今天中午收盘的股价",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 同指标多条件（无交织）
    {
        "id": "TC-04",
        "query": "给我查一下宁德时代在今天收盘和上周收盘的换手率",
        "expect_chain": False,
        "expect_count": 2,
    },
    # 链式：所在板块
    {
        "id": "TC-05",
        "query": "宁德时代所在的版块今天的涨跌幅",
        "expect_chain": True,
        "expect_count": 2,
    },
    # 链式 + 多指标
    {
        "id": "TC-06",
        "query": "宁德时代所在的版块的涨跌幅和成交量",
        "expect_chain": True,
        "expect_count": 3,
    },
    # 直接指定板块（不需要 chain）
    {
        "id": "TC-07",
        "query": "电池板块今天的涨跌幅",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 指数查询
    {
        "id": "TC-08",
        "query": "查一下上证指数今天的涨跌幅和成交量",
        "expect_chain": False,
        "expect_count": 2,
    },
    # 比较式查询
    {
        "id": "TC-09",
        "query": "茅台和五粮液今天的股价谁高？",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 无时间条件
    {
        "id": "TC-10",
        "query": "宁德时代的涨跌幅",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 多级链式
    {
        "id": "TC-11",
        "query": "查一下宁德时代所在的板块的龙头股的涨跌幅",
        "expect_chain": True,
        "expect_count": 3,
    },
    # 不同条件
    {
        "id": "TC-12",
        "query": "最近一个月北向资金流向",
        "expect_chain": False,
        "expect_count": 1,
    },
    # 板块多指标
    {
        "id": "TC-13",
        "query": "宁德时代所在板块今天的涨跌幅和主力资金流入",
        "expect_chain": True,
        "expect_count": 3,
    },
    # 单指标 + 明确板块名 + 时间范围
    {
        "id": "TC-14",
        "query": "新能源汽车板块最近5天的涨跌幅",
        "expect_chain": False,
        "expect_count": 1,
    },
]

# ── 验证器 ──

def validate_output(data: dict) -> list[str]:
    """校验输出格式，返回错误列表（空 = 合格）"""
    errors = []

    if not isinstance(data, dict):
        return ["输出不是 dict 类型"]

    # requests
    requests = data.get("requests", [])
    if not isinstance(requests, list) or len(requests) == 0:
        errors.append("requests 不存在或为空列表")
        return errors

    # chain
    chain = data.get("chain", None)
    if chain not in (True, False):
        errors.append("chain 必须为 true 或 false")

    # 每个 request
    req_ids = set()
    for i, req in enumerate(requests):
        if not isinstance(req, dict):
            errors.append(f"requests[{i}] 不是 dict")
            continue

        # req_id
        rid = req.get("req_id", "")
        if not re.match(r'^R_\d{3}$', rid):
            errors.append(f"requests[{i}].req_id 格式不符: {rid}")
        elif rid in req_ids:
            errors.append(f"requests[{i}].req_id 重复: {rid}")
        req_ids.add(rid)

        # obj
        obj = req.get("obj", [])
        if not isinstance(obj, list) or len(obj) == 0:
            errors.append(f"requests[{i}].obj 不是非空列表")

        # var
        var = req.get("var", "")
        if not var or not isinstance(var, str):
            errors.append(f"requests[{i}].var 缺失或不是字符串")

        # condition
        cond = req.get("condition", [])
        if not isinstance(cond, list) or len(cond) == 0:
            errors.append(f"requests[{i}].condition 不是非空列表")

        # obj 中的 resN 合法性
        chain_pattern = re.compile(r'^res\d+$')
        has_chain_ref = any(isinstance(o, str) and chain_pattern.match(o) for o in obj)
        if has_chain_ref and i == 0:
            errors.append(f"requests[0].obj 引用了 resN，但首个 request 不能有依赖")

        # 如果链引用了不存在的 req_id 索引
        if has_chain_ref:
            for o in obj:
                if isinstance(o, str) and chain_pattern.match(o):
                    dep_idx = int(o[3:])
                    if dep_idx >= len(requests) or dep_idx >= i:
                        errors.append(f"res{dep_idx} 引用了不存在或尚未执行的 request")

    return errors


# ── LLM 调用 ──

def call_llm(system_prompt: str, query: str) -> tuple[str | None, dict]:
    """调用 LLM 并返回 (原始回复, 解析后的 dict)"""
    t0 = time.time()
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as e:
        return None, {"error": str(e)}

    elapsed = time.time() - t0
    content = resp.choices[0].message.content or ""
    usage = resp.usage

    info = {
        "elapsed": round(elapsed, 2),
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }
    return content, info


def extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象"""
    # 尝试 ```json ... ``` 块
    m = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试最外层的 {} 包裹
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def format_result(data: dict, tc: dict) -> str:
    """格式化测试结果供人工评判"""
    lines = []
    lines.append(f"  Query: {tc['query']}")
    lines.append(f"  期望: chain={tc['expect_chain']}, count={tc['expect_count']}")

    requests = data.get("requests", [])
    lines.append(f"  实际: chain={data.get('chain')}, count={len(requests)}")
    for i, req in enumerate(requests):
        lines.append(f"    R{i+1}: obj={req.get('obj')}, var={req.get('var')}, cond={req.get('condition')}")

    return "\n".join(lines)


# ── 主测试逻辑 ──

def test_single(query: str, tc: dict | None = None, save: bool = False) -> dict:
    """测试单个 query"""
    system_prompt = build_prompt("agent_guide", {"parser_expert"})
    result = {
        "query": query,
        "success": False,
        "errors": [],
        "llm_raw": "",
        "parsed": None,
        "info": {},
        "retry_count": 0,
    }

    for attempt in range(1 + MAX_RETRIES):
        if attempt > 0:
            print(f"    第 {attempt} 次重试...")

        raw, info = call_llm(system_prompt, query)
        result["llm_raw"] = raw or ""
        result["info"] = info

        if raw is None:
            result["errors"].append(f"LLM 调用失败: {info.get('error')}")
            break

        parsed = extract_json(raw)
        if parsed is None:
            result["errors"].append(f"第 {attempt+1} 次: 无法从回复中提取 JSON")
            continue

        errors = validate_output(parsed)
        if errors:
            result["errors"].extend([f"第 {attempt+1} 次: {e}" for e in errors])
            continue

        # 成功
        result["success"] = True
        result["parsed"] = parsed
        result["retry_count"] = attempt
        break

    if save:
        ts = time.strftime("%Y%m%d_%H%M%S")
        rid = uuid.uuid4().hex[:8]
        path = os.path.join(RESULTS_DIR, f"guide_test_{ts}_{rid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"  已保存: {path}")

    return result


def run_all():
    """运行所有测试用例"""
    print(f"{'='*70}")
    print(f"  🧪 agent_guide 全量测试")
    print(f"  模型: {MODEL}")
    print(f"  用例数: {len(TEST_CASES)}")
    print(f"{'='*70}\n")

    pass_count = 0
    fail_count = 0
    detail = []

    for tc in TEST_CASES:
        print(f"\n{'─'*50}")
        print(f"  [{tc['id']}] {tc['query']}")
        print(f"{'─'*50}")

        result = test_single(tc["query"], tc)
        parsed = result["parsed"]

        # 基本格式通过
        if parsed:
            print(f"  ✅ 格式通过 (retry={result['retry_count']}, "
                  f"{result['info'].get('prompt_tokens','?')} tokens)")
            print(format_result(parsed, tc))
            # 检查期望值
            chain_match = parsed.get("chain") == tc["expect_chain"]
            count_match = len(parsed.get("requests", [])) == tc["expect_count"]
            if chain_match and count_match:
                print(f"  ✅ 期望匹配 ✓")
                pass_count += 1
            else:
                print(f"  ⚠️ 期望不匹配 (仅参考, 需人工判断)")
                pass_count += 0.5
            detail.append({
                "id": tc["id"],
                "query": tc["query"],
                "status": "PASS" if (chain_match and count_match) else "PARTIAL",
                "output": parsed,
            })
        else:
            print(f"  ❌ 失败")
            for e in result["errors"][:3]:
                print(f"     - {e}")
            fail_count += 1
            detail.append({
                "id": tc["id"],
                "query": tc["query"],
                "status": "FAIL",
                "errors": result["errors"],
            })

    # 汇总
    print(f"\n{'='*70}")
    print(f"  汇总: {pass_count}/{len(TEST_CASES)} 通过, {fail_count} 失败")
    print(f"{'='*70}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"guide_test_all_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "summary": f"{pass_count}/{len(TEST_CASES)}", "cases": detail},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"  详细结果: {path}")

    return pass_count, fail_count


def interactive_mode():
    """交互式测试"""
    print("Agent Guide 交互测试模式（输入 q 退出）")
    print("=" * 50)
    while True:
        try:
            query = input("\nQuery > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query or query.lower() == "q":
            break

        result = test_single(query)
        if result["success"]:
            print("\n  ✅ 结果:")
            print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))
            print(f"  (tokens: {result['info'].get('prompt_tokens','?')} in, "
                  f"{result['info'].get('completion_tokens','?')} out)")
        else:
            print(f"\n  ❌ 格式错误 ({result['info'].get('elapsed','?')}s):")
            for e in result["errors"][:3]:
                print(f"     {e}")
            print(f"\n  LLM 原始回复 (前300字):")
            print(f"  {result['llm_raw'][:300]}")


if __name__ == "__main__":
    if "--all" in sys.argv:
        run_all()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        query = sys.argv[1]
        save = "--save" in sys.argv
        result = test_single(query, save=save)
        if result["success"]:
            print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))
        else:
            print(f"❌ 失败: ")
            for e in result["errors"]:
                print(f"   {e}")
            print(f"\nLLM 原始回复 (前500字):")
            print(result["llm_raw"][:500])
    else:
        interactive_mode()
