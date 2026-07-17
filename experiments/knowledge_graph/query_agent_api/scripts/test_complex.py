#!/usr/bin/env python3
"""Test 20 complex composite queries - chains, parallel, multi-object (5+)"""
import json, os, sys, re, time, glob
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _QA_DIR)
from core import build_prompt

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1", api_key="ollama")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

COMPLEX_TESTS = [
    # ── Chain型 (5条) ──
    ("CX-01", "宁德时代所在板块的龙头股的所属概念", True, 3, "3-level chain"),
    ("CX-02", "茅台所在行业的平均市盈率排名", True, 2, "chain: 行业→平均市盈率排名"),
    ("CX-03", "比亚迪所在的板块的龙头股的资金流向", True, 3, "chain: 板块→龙头股→资金流向"),
    ("CX-04", "药明康德所在行业的平均毛利率", True, 2, "chain: 行业→毛利率"),
    ("CX-05", "三一重工所属行业的龙头股的最新收盘价", True, 3, "chain: 行业→龙头股→收盘价"),

    # ── 同级并行多指标 (5条) ──
    ("CX-06", "宁德时代今天的成交量、换手率、振幅、成交额", False, 4, "4 parallel metrics"),
    ("CX-07", "上证指数今天的开盘价、收盘价、最高价、最低价、成交量", False, 5, "5 parallel metrics"),
    ("CX-08", "茅台今天的PE、PB、PS、ROE、营收增长率", False, 5, "5 financial metrics"),
    ("CX-09", "沪深300、上证50、中证500今天的涨跌幅", False, 3, "3 indexes"),
    ("CX-10", "招商银行今年的净利润、营业收入、ROE、不良率", False, 4, "4 financial"),

    # ── 5+个对象 (5条) ──
    ("CX-11", "宁德时代、比亚迪、长城汽车、上汽集团、广汽集团今天的涨跌幅", False, 1, "5 stocks, 1 metric"),
    ("CX-12", "贵州茅台、五粮液、泸州老窖、山西汾酒、洋河股份今天的股价", False, 1, "5 baijiu stocks, 1 metric"),
    ("CX-13", "工商银行、建设银行、农业银行、中国银行、招商银行今天的涨跌幅", False, 1, "5 banks, 1 metric"),
    ("CX-14", "宁德时代、阳光电源、隆基绿能、通威股份、TCL中环今天的换手率", False, 1, "5 solar stocks"),
    ("CX-15", "中国平安、中国人寿、中国太保、新华保险、中国人保今天的涨跌幅", False, 1, "5 insurance"),

    # ── 混合复杂 (5条) ──
    ("CX-16", "宁德时代所属板块的龙头股以及比亚迪今天的涨跌幅", True, 3, "chain + parallel mixed"),
    ("CX-17", "查一下茅台所在行业的平均PE和五粮液的PE", True, 3, "chain + independent"),
    ("CX-18", "沪深300、中证500、创业板指今天的涨跌幅和成交额", False, 6, "3 indexes * 2 metrics"),
    ("CX-19", "宁德时代、比亚迪、长城汽车所属行业的板块涨跌幅", True, 6, "3 entities each chain"),
    ("CX-20", "白酒板块、医药板块、新能源板块、银行板块、半导体板块今天的涨跌幅", False, 1, "5 sectors"),
]


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
        cp = re.compile(r"^res\d+$")
        if i == 0 and any(isinstance(o, str) and cp.match(o) for o in obj):
            errors.append(f"[{i}] 首个 req 不能有 resN")
        for o in obj:
            if isinstance(o, str) and cp.match(o):
                dep = int(o[3:])
                if dep >= len(reqs) or dep >= i:
                    errors.append(f"[{i}] res{dep} 不合法")
    return errors


system_prompt = build_prompt("agent_guide", {"parser_expert"})

print(f"{'='*70}")
print(f"  🧪 复合型 Query 测试（20条）")
print(f"  模型: {MODEL}")
print(f"{'='*70}")

results = []
for test_id, query, exp_chain, exp_count, desc in COMPLEX_TESTS:
    print(f"\n{'─'*50}")
    print(f"  [{test_id}] {desc}")
    print(f"  Q: {query}")
    print(f"  期望: chain={exp_chain}, count={exp_count}")

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

    act_chain = None
    act_count = None
    if parsed and not errors:
        act_chain = parsed.get("chain", "?")
        act_count = len(parsed.get("requests", []))
        match = (act_chain == exp_chain and act_count == exp_count)
        if match:
            status = "✅"
        else:
            status = "⚠️ count/chain 不符"
        print(f"  结果: chain={act_chain}, count={act_count} ({elapsed:.1f}s) {status}")
        for i, r in enumerate(parsed.get("requests", [])):
            obj_str = r.get("obj", [])
            print(f"    R{i+1}: obj={obj_str}")
            print(f"           var={r.get('var')}, cond={r.get('condition')}")
    else:
        err = errors[0] if errors else "未知错误"
        status = f"❌ {err}"
        print(f"  失败 ({elapsed:.1f}s): {err}")

    results.append({
        "id": test_id, "query": query, "desc": desc,
        "exp_chain": exp_chain, "exp_count": exp_count,
        "act_chain": act_chain, "act_count": act_count,
        "output": parsed if (parsed and not errors) else None,
        "raw_snippet": raw[:400],
        "status": status,
    })

# Summary
print(f"\n{'='*70}")
print(f"  汇总:")
pass_count = sum(1 for r in results if r["status"] == "✅")
warn_count = sum(1 for r in results if "⚠️" in r["status"])
fail_count = sum(1 for r in results if "❌" in r["status"])
print(f"  ✅ 完全匹配: {pass_count}")
print(f"  ⚠️ 部分匹配: {warn_count}")
print(f"  ❌ 失败: {fail_count}")
print(f"{'='*70}")

# Save
with open(os.path.join(RESULTS_DIR, "guide_complex_test_20260715.json"), "w", encoding="utf-8") as f:
    json.dump({"model": MODEL, "cases": results}, f, ensure_ascii=False, indent=2)
print(f"\n已保存: guide_complex_test_20260715.json")

# Generate markdown report
lines = []
lines.append("# agent_guide 复合型 Query 测试报告\n")
lines.append(f"**模型**: {MODEL}")
lines.append(f"**日期**: 2026-07-15\n")
lines.append(f"**汇总**: ✅{pass_count} / ⚠️{warn_count} / ❌{fail_count}\n")
lines.append("| # | ID | 类别 | Query | 期望 chain | 期望 count | 结果 chain | 结果 count | 状态 |")
lines.append("|---|-----|------|-------|-----------|-----------|-----------|-----------|------|")

for i, r in enumerate(results, 1):
    icon = "✅" if r["status"] == "✅" else ("⚠️" if "⚠️" in r["status"] else "❌")
    cat = r["desc"].split(":")[0] if ":" in r["desc"] else r["desc"]
    act_ch = str(r["act_chain"]) if r["act_chain"] is not None else "?"
    act_ct = str(r["act_count"]) if r["act_count"] is not None else "?"
    lines.append(f"| {i} | {r['id']} | {cat} | {r['query'][:30]} | {r['exp_chain']} | {r['exp_count']} | {act_ch} | {act_ct} | {icon} |")

lines.append("\n---\n## 详细输出\n")
for r in results:
    lines.append(f"### {r['id']}: {r['query']}\n")
    lines.append(f"**类别**: {r['desc']}  ")
    lines.append(f"**状态**: {r['status']}\n")
    if r["output"]:
        lines.append("```json")
        lines.append(json.dumps(r["output"], ensure_ascii=False, indent=2))
        lines.append("```\n")
    else:
        lines.append(f"**原始回复**:\n```\n{r['raw_snippet']}\n```\n")

with open(os.path.join(RESULTS_DIR, "guide_complex_report_20260715.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"报告: guide_complex_report_20260715.md")
