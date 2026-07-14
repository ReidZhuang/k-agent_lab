#!/usr/bin/env python3
"""Phase 8: 端到端测试 — 路由→LLM→执行 全链路评估"""
import sys, os, json, time, requests
sys.path.insert(0, "/home/stockagent/project_space/research/experiments/knowledge_graph")
sys.path.insert(0, "/home/stockagent/project_space/research/experiments/knowledge_graph/scripts")

from irkg import Router, RouteCondition
from irkg.sql_gen import build_sql_prompt, parse_llm_output
from executor import execute_code

os.environ["TUSHARE_TOKEN"] = "87d2631fc1363cace10f99f1ee6112f2b56f0f98370eac2860e7e956"
ROUTER = Router()
ROUTER.build(alias_csv_path="/home/stockagent/project_space/research/experiments/knowledge_graph/data/datafield_new_alias_all.txt")
OLLAMA = "http://localhost:11434/api/generate"

results = []

def llm_generate(prompt, model):
    t0 = time.time()
    resp = requests.post(OLLAMA, json={
        "model": model, "prompt": prompt,
        "stream": False, "temperature": 0.1, "num_predict": 512,
    }, timeout=180)
    t = time.time() - t0
    data = resp.json()
    output = data.get("response", "")
    tokens = data.get("eval_count", 0)
    return output, t, tokens

def test_scenario(name, keywords, model, intent="fact", **cond_kw):
    cond = RouteCondition(**cond_kw) if cond_kw else RouteCondition()
    route = ROUTER.route(keywords, intent_type=intent, conditions=cond)
    prompt = build_sql_prompt(route)
    output, llm_time, tokens = llm_generate(prompt, model)
    code = parse_llm_output(output)
    exec_result = execute_code(code) if code else {"success": False, "error": "No code generated"}
    
    result = {
        "name": name,
        "model": model,
        "route_ok": len(route.fields) > 0,
        "datasource": route.datasource.id if route.datasource else "?",
        "concept": route.concept_id,
        "prompt_len": len(prompt),
        "llm_time_s": round(llm_time, 1),
        "llm_tokens": tokens,
        "has_sql_keywords": any(kw in code for kw in ["SELECT ", "FROM ", "WHERE "]),
        "has_python_call": any(x in code for x in ["pro.", "ak.", "lk.", "requests."]),
        "exec_ok": exec_result["success"],
        "exec_output": exec_result.get("output", "")[:200],
        "exec_error": exec_result.get("error", "")[:200],
        "code_len": len(code),
    }
    results.append(result)
    return result

def print_result(r):
    status = "✅" if (r["exec_ok"] or not r["has_sql_keywords"]) else "❌"
    flag_sql = " [SQL!]" if r["has_sql_keywords"] else ""
    flag_py = " [py]" if r["has_python_call"] else ""
    print(f'{status} {r["name"]:25s} | LLM:{r["llm_time_s"]:4.1f}s {r["llm_tokens"]:4d}tok | '
          f'DS:{r["datasource"]:25s} | exe:{r["exec_ok"]}{flag_sql}{flag_py}')

# ===== 测试场景 =====
MODEL_Q3 = "glm4:9b-chat-q3_K_M"

print("=" * 60)
print("Phase 8 端到端测试 — q3_K_M")
print("=" * 60)

# 1. 简单事实查询
test_scenario("PE_TTM(茅台)", ["PE_TTM"], MODEL_Q3,
              entity_type="stock_code", entity_value="600519.SH")
test_scenario("毛利率(宁德)", ["毛利率"], MODEL_Q3,
              entity_type="stock_code", entity_value="300750.SZ")
test_scenario("市场热度", ["市场热度"], MODEL_Q3)

# 2. 带时间范围的财务
test_scenario("毛利率+净利率", ["毛利率", "净利率"], MODEL_Q3, intent="analysis",
              entity_type="stock_code", entity_value="300750.SZ",
              time_range_start="20240101", time_range_end="20240630")

# 3. 指数/板块行情
test_scenario("指数涨跌幅", ["指数涨跌幅"], MODEL_Q3)
test_scenario("板块涨跌幅", ["板块涨跌幅"], MODEL_Q3)

# 4. 新字段测试
test_scenario("买1价(新浪盘口)", ["买1价"], MODEL_Q3)
test_scenario("港股PE", ["港股PE"], MODEL_Q3)
test_scenario("同花顺概念", ["同花顺概念板块名"], MODEL_Q3)
test_scenario("管理层姓名", ["管理层姓名"], MODEL_Q3)

# 5. 带实体的复杂查询
test_scenario("茅台财务摘要", ["ROE", "毛利率", "净利率"], MODEL_Q3, intent="analysis",
              entity_type="stock_code", entity_value="600519.SH",
              time_range_start="20240101", time_range_end="20240630")

# 6. 广告诉
test_scenario("涨停家数", ["涨停家数"], MODEL_Q3)

# ===== 结果汇总 =====
print(f"\n{'='*60}")
print("测试结果汇总")
print(f"{'='*60}")
print(f"{'场景':30s} {'时间':6s} {'Token':6s} {'执行':6s} {'SQL?':5s} {'DS':25s}")
print("-" * 80)
for r in results:
    exe = "OK" if r["exec_ok"] else "NO"
    sql = "Y" if r["has_sql_keywords"] else "N"
    print(f'{r["name"]:30s} {r["llm_time_s"]:4.1f}s {r["llm_tokens"]:4d}   {exe:6s} {sql:5s} {r["datasource"]:25s}')

# 统计
total = len(results)
exec_ok = sum(1 for r in results if r["exec_ok"])
sql_fail = sum(1 for r in results if r["has_sql_keywords"])
avg_time = sum(r["llm_time_s"] for r in results) / total if total > 0 else 0
avg_tokens = sum(r["llm_tokens"] for r in results) / total if total > 0 else 0

print(f"\n{'='*60}")
print(f"统计: {total} 场景")
print(f"  执行成功: {exec_ok}/{total}")
print(f"  SQL关键字污染: {sql_fail}/{total}")
print(f"  平均LLM时间: {avg_time:.1f}s")
print(f"  平均Token数: {avg_tokens:.0f}")
print(f"{'='*60}")
