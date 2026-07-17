"""端到端全链路详细测试记录 — 每步输入输出"""
import json, os, sys, time
_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _QA_DIR)

from core.orchestrator import Orchestrator, agent_guide_parse, agent_router_select, enrich_route

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

def test_with_logs(query: str, run_coder: bool = True) -> dict:
    """执行测试并记录每一步的输入输出"""
    log = []
    log.append({"step": "start", "query": query})

    # ── Phase 1: agent_guide ──
    t0 = time.time()
    log.append({"step": "agent_guide", "action": "调用LLM解析NL", "input": query})
    guide = agent_guide_parse(query)
    t1 = time.time()
    guide_time = round(t1 - t0, 2)

    if "error" in guide:
        log.append({"step": "agent_guide", "output": guide, "error": guide["error"], "elapsed": guide_time})
        return {"query": query, "success": False, "log": log}

    requests = guide.get("requests", [])
    chain = guide.get("chain", False)
    log.append({
        "step": "agent_guide", "output": {
            "chain": chain, "requests_count": len(requests),
            "requests": [{"req_id": r["req_id"], "obj": r["obj"], "var": r["var"], "condition": r["condition"]} for r in requests]
        }, "elapsed": guide_time
    })

    # ── Phase 2-4: 逐 request ──
    processed = []
    chain_results = []

    for i, req in enumerate(requests):
        req_id = req.get("req_id", f"R_{i+1:03d}")
        req_log = []

        # Phase 2: agent_router
        t2 = time.time()
        req_log.append({"step": f"{req_id}_router", "action": "hybrid_query + LLM选字段",
                        "input": {"obj": req["obj"], "var": req["var"], "condition": req["condition"]}})
        router_result = agent_router_select(req)
        t3 = time.time()
        router_time = round(t3 - t2, 2)

        if "error" in router_result:
            req_log.append({"step": f"{req_id}_router", "output": {}, "error": router_result["error"], "elapsed": router_time})
            processed.append({"req_id": req_id, "success": False, "error": router_result["error"], "log": req_log})
            chain_results.append({"result": []})
            continue

        candidates_short = [{"id": c["id"], "name": c.get("name",""), "scope": c.get("scope",""), "protocol": c.get("protocol","")}
                          for c in router_result.get("candidates", [])[:5]]
        req_log.append({
            "step": f"{req_id}_router", "output": {
                "field_id": router_result["field_id"],
                "candidates_count": len(router_result.get("candidates", [])),
                "top5_candidates": candidates_short,
                "llm_raw": router_result.get("_raw", ""),
            }, "elapsed": router_time
        })

        # Phase 3: enrichment
        t4 = time.time()
        req_log.append({"step": f"{req_id}_enrich", "action": "Neo4j补全+实体解析+时间解析",
                        "input": {"field_id": router_result["field_id"], "obj": req.get("obj", [])}})
        enriched = enrich_route(router_result)
        t5 = time.time()
        enrich_time = round(t5 - t4, 2)

        if "error" in enriched:
            req_log.append({"step": f"{req_id}_enrich", "output": {}, "error": enriched["error"], "elapsed": enrich_time})
            processed.append({"req_id": req_id, "success": False, "error": enriched["error"], "log": req_log})
            chain_results.append({"result": []})
            continue

        ds = enriched.get("datasource", {})
        route = enriched.get("route", {})
        req_log.append({
            "step": f"{req_id}_enrich", "output": {
                "entity_value": route.get("entity_value", ""),
                "entity_type": route.get("entity_type", ""),
                "time_start": route.get("time_start", ""),
                "time_end": route.get("time_end", ""),
                "datasource_id": ds.get("id", ""),
                "protocol": ds.get("protocol", ""),
                "api_column": route.get("api_column", ""),
                "condition_text": route.get("condition_text", ""),
            }, "elapsed": enrich_time
        })

        # Phase 4: codegen (if requested)
        if run_coder:
            from core.coder import codegen_loop
            t6 = time.time()
            req_log.append({"step": f"{req_id}_coder", "action": "LLM代码生成+执行",
                            "input": {"prompt_dir": ds.get("id", ""), "protocol": ds.get("protocol", "")}})
            code_result = codegen_loop(enriched)
            t7 = time.time()
            coder_time = round(t7 - t6, 2)
            step_result = {
                "req_id": req_id,
                "success": code_result.get("success", False),
                "result": code_result.get("result", []),
                "output": code_result.get("output", ""),
                "error": code_result.get("error", ""),
            }
            req_log.append({
                "step": f"{req_id}_coder", "output": {
                    "success": code_result.get("success", False),
                    "result": code_result.get("result", []),
                    "error": code_result.get("error", "")[:200] if code_result.get("error") else "",
                }, "elapsed": coder_time
            })
        else:
            step_result = {
                "req_id": req_id, "success": True, "result": [],
                "output": "", "error": "",
            }

        step_result["log"] = req_log
        step_result["entity_value"] = route.get("entity_value", "")
        step_result["datasource"] = {"id": ds.get("id", ""), "protocol": ds.get("protocol", "")}
        step_result["field_id"] = route.get("field_id", "")
        processed.append(step_result)
        chain_results.append(step_result)

    # ── 汇总 ──
    success_count = sum(1 for p in processed if p["success"])
    result = {
        "query": query,
        "success": success_count > 0,
        "chain": chain,
        "summary": f"{success_count}/{len(processed)} requests succeeded",
        "requests": processed,
        "log": log,
    }
    return result


def print_result(result: dict):
    """格式化输出详细日志"""
    q = result["query"]
    s = "✅" if result["success"] else "❌"
    print(f"\n{'='*70}")
    print(f"  {s} 查询: {q}")
    print(f"  chain: {result.get('chain', False)}")
    print(f"  {result.get('summary', '')}")
    print(f"{'='*70}")

    for req in result.get("requests", []):
        req_id = req.get("req_id", "?")
        s = "✅" if req["success"] else "❌"
        print(f"\n  ┌─ {s} [{req_id}]")

        for entry in req.get("log", []):
            step = entry.get("step", "")
            action = entry.get("action", "")
            inp = entry.get("input", "")
            out = entry.get("output", "")
            err = entry.get("error", "")
            elapsed = entry.get("elapsed", "")

            print(f"  │  ├─ {step}")
            if inp:
                if isinstance(inp, str):
                    print(f"  │  │  输入: {inp}")
                else:
                    inp_str = json.dumps(inp, ensure_ascii=False)
                    print(f"  │  │  输入: {inp_str[:120]}")
            if out:
                out_str = json.dumps(out, ensure_ascii=False) if isinstance(out, dict) else str(out)
                print(f"  │  │  输出: {out_str[:200]}")
            if err:
                print(f"  │  │  ❌ 错误: {err[:150]}")
            if elapsed:
                print(f"  │  │  耗时: {elapsed}s")

        if req.get("success"):
            print(f"  │  └─ 结果: {req.get('result', [])}")
        else:
            print(f"  │  └─ ❌ {req.get('error', '')[:100]}")

    print()


def run_all():
    """运行所有测试用例并保存详细报告"""
    from test_e2e import TEST_CASES

    report = {
        "timestamp": time.strftime("%Y%m%d_%H%M%S"),
        "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
        "tests": [],
    }

    for tc in TEST_CASES:
        if tc.get("mode") == "guide":
            continue  # 跳过仅解析模式
        print(f"\n{'#'*70}")
        print(f"#  [{tc['id']}] {tc['query']}")
        print(f"#  模式: {'全链路' if tc.get('mode')=='full' else '路由验证'}")
        print(f"{'#'*70}")

        run_coder = tc.get("mode") == "full"
        result = test_with_logs(tc["query"], run_coder=run_coder)
        print_result(result)

        report["tests"].append({
            "id": tc["id"],
            "query": tc["query"],
            "mode": tc.get("mode", "full"),
            "success": result["success"],
            "chain": result.get("chain", False),
            "summary": result.get("summary", ""),
            "requests": [
                {
                    "req_id": r["req_id"],
                    "success": r["success"],
                    "result": r.get("result", []),
                    "error": r.get("error", ""),
                    "entity_value": r.get("entity_value", ""),
                    "field_id": r.get("field_id", ""),
                    "datasource": r.get("datasource", {}),
                    "log": r.get("log", []),
                }
                for r in result.get("requests", [])
            ],
        })

    # ── 保存 ──
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"e2e_detail_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # ── 汇总 ──
    print(f"\n{'='*70}")
    print(f"  详细测试报告")
    print(f"{'='*70}")

    for t in report["tests"]:
        s = "✅" if t["success"] else "❌"
        print(f"  {s} [{t['id']}] {t['query']}")
        print(f"     chain={t['chain']}, {t['summary']}")
        for r in t.get("requests", []):
            rs = "✅" if r["success"] else "❌"
            ds = r.get("datasource", {}).get("id", "")
            ev = r.get("entity_value", "")
            fid = r.get("field_id", "")
            rv = r.get("result", [])
            print(f"     {rs} {r['req_id']}: field={fid} entity={ev} ds={ds} result={rv}")

    print(f"\n  保存至: {path}")


if __name__ == "__main__":
    run_all()
