#!/usr/bin/env python3
"""Generate markdown report + run 20 condition-focused blind tests"""
import json, os, sys, re, time, glob
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _QA_DIR)
from core import build_prompt

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1", api_key="ollama")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# Load existing test results
all_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "guide_test_all_*.json")))
existing = {"summary": "N/A", "cases": []}
if all_files:
    with open(all_files[-1], encoding="utf-8") as f:
        existing = json.load(f)
    print(f"Loaded: {os.path.basename(all_files[-1])}")

BLIND_TESTS = [
    ("CT-01", "贵州茅台昨天下午的收盘价", False, 1),
    ("CT-02", "宁德时代年初至今的涨跌幅", False, 1),
    ("CT-03", "比亚迪最近5日的北向资金净买入", False, 1),
    ("CT-04", "药明康德昨日的成交量", False, 1),
    ("CT-05", "汇川技术上周五的收盘价", False, 1),
    ("CT-06", "中国平安本周以来的涨跌幅", False, 1),
    ("CT-07", "五粮液去年同期的营业收入", False, 1),
    ("CT-08", "贵州茅台近3个交易日的资金流向", False, 1),
    ("CT-09", "恒瑞医药盘中的实时股价", False, 1),
    ("CT-10", "隆基绿能前复权的收盘价", False, 1),
    ("CT-11", "招商银行今年一季度的净利润", False, 1),
    ("CT-12", "长江电力近10日的涨跌幅", False, 1),
    ("CT-13", "格力电器当日开盘价和收盘价", False, 2),
    ("CT-14", "美的集团最近一周的北向资金", False, 1),
    ("CT-15", "工商银行过去30个交易日的股价走势", False, 1),
    ("CT-16", "宁德时代今日最高涨幅超过5%了吗", False, 1),
    ("CT-17", "上证指数今年以来的表现", False, 1),
    ("CT-18", "中芯国际昨日和前日的资金流向对比", False, 2),
    ("CT-19", "工业富联三季度末的股东人数", False, 1),
    ("CT-20", "紫金矿业盘后的大单交易", False, 1),
]

def validate_output(data: dict) -> list[str]:
    errors = []
    if not isinstance(data, dict):
        return ["输出不是 dict"]
    reqs = data.get("requests", [])
    if not isinstance(reqs, list) or len(reqs) == 0:
        return ["requests 为空"]
    seen = set()
    for i, r in enumerate(reqs):
        if not isinstance(r, dict):
            errors.append(f"[{i}] 不是 dict")
            continue
        rid = r.get("req_id", "")
        if not re.match(r"^R_\d{3}$", rid):
            errors.append(f"[{i}] req_id: {rid}")
        elif rid in seen:
            errors.append(f"[{i}] 重复: {rid}")
        seen.add(rid)
        obj = r.get("obj", [])
        if not isinstance(obj, list) or len(obj) == 0:
            errors.append(f"[{i}] obj 为空")
        var = r.get("var", "")
        if not var or not isinstance(var, str):
            errors.append(f"[{i}] var 缺失")
        cond = r.get("condition", [])
        if not isinstance(cond, list) or len(cond) == 0:
            errors.append(f"[{i}] condition 为空")
        # chain ref validation
        cp = re.compile(r"^res\d+$")
        if i == 0 and any(isinstance(o, str) and cp.match(o) for o in obj):
            errors.append(f"[{i}] 首个 req 不能有 resN")
        for o in obj:
            if isinstance(o, str) and cp.match(o):
                dep = int(o[3:])
                if dep >= len(reqs) or dep >= i:
                    errors.append(f"[{i}] res{dep} 不合法")
    return errors

def extract_json(text: str) -> dict | None:
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return None

system_prompt = build_prompt("agent_guide", {"parser_expert"})

# Build report
lines = ["# agent_guide 测试报告\n", f"**模型**: {MODEL}", "**日期**: 2026-07-15\n"]
lines.append("## 原测试集 (14条)\n")
lines.append("| # | ID | Query | chain | Requests | 状态 |")
lines.append("|---|-----|-------|-------|----------|------|")
for i, tc in enumerate(existing["cases"], 1):
    icon = "❌" if tc["status"] == "FAIL" else ("⚠️" if tc["status"] == "PARTIAL" else "✅")
    if tc["status"] == "FAIL":
        lines.append(f"| {i} | {tc['id']} | {tc['query'][:40]} | ? | ? | {icon} |")
    else:
        o = tc["output"]
        lines.append(f"| {i} | {tc['id']} | {tc['query'][:40]} | {'true' if o.get('chain') else 'false'} | {len(o.get('requests',[]))} | {icon} |")

lines.append("\n---\n## 条件盲测 (20条)\n")
lines.append("| # | ID | Query | 期望 chain | 期望 count | 结果 chain | 结果 count | 状态 |")
lines.append("|---|-----|-------|-----------|-----------|-----------|-----------|------|")

results = []
for test_id, query, exp_chain, exp_count in BLIND_TESTS:
    print(f"  [{test_id}] {query}")
    t0 = time.time()
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
        temperature=0.1, max_tokens=2048,
    )
    raw = resp.choices[0].message.content or ""
    parsed = extract_json(raw)
    errors = validate_output(parsed) if parsed else ["无法提取 JSON"]
    elapsed = time.time() - t0

    row_idx = len(results) + 1
    if parsed and not errors:
        act_chain = parsed.get("chain", "?")
        act_count = len(parsed.get("requests", []))
        match = (act_chain == exp_chain and act_count == exp_count)
        status = "✅" if match else "⚠️"
        lines.append(f"| {row_idx} | {test_id} | {query[:35]} | {exp_chain} | {exp_count} | {act_chain} | {act_count} | {status} |")
        lines.append(f"\n**{test_id} 输出**:\n```json\n{json.dumps(parsed, ensure_ascii=False, indent=2)}\n```\n")
        results.append({"id": test_id, "query": query, "output": parsed, "status": "PASS" if match else "PARTIAL"})
    else:
        err = errors[0] if errors else "未知"
        lines.append(f"| {row_idx} | {test_id} | {query[:35]} | {exp_chain} | {exp_count} | - | - | ❌ {err} |")
        lines.append(f"\n**原始回复**:\n```\n{raw[:300]}\n```\n")
        results.append({"id": test_id, "query": query, "status": "FAIL", "error": err})
    print(f"     {status} ({elapsed:.1f}s)")

pass_count = sum(1 for r in results if r["status"] == "PASS")
lines.append(f"\n**汇总**: {pass_count}/{len(results)} 通过, {len(results)-pass_count} 失败\n")

with open(os.path.join(RESULTS_DIR, "guide_condition_report_20260715.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"\n报告: guide_condition_report_20260715.md")

with open(os.path.join(RESULTS_DIR, "guide_condition_test_20260715.json"), "w", encoding="utf-8") as f:
    json.dump({"model": MODEL, "cases": results}, f, ensure_ascii=False, indent=2)
print(f"JSON: guide_condition_test_20260715.json")
