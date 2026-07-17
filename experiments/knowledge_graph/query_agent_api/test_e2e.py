#!/usr/bin/env python3
"""test_e2e — 端到端全链路测试

测试 orchestrator 的端到端能力：NL query → 路由 → 补全 → 代码生成 → 执行

执行方式:
    # 快速模式（只跑 guide + router，不跑 coder）
    python3 test_e2e.py --fast

    # 全链路（跑全部 coder）
    python3 test_e2e.py

    # 单条测试
    python3 test_e2e.py "宁德时代今天的涨跌幅"
"""
import json, os, sys, time

_QA_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _QA_DIR)

from core.orchestrator import Orchestrator, agent_guide_parse, agent_router_select, enrich_route
from core.entity_resolver import get_resolver
from core.time_parser import parse_conditions_list

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ============================================================
# 测试用例集
# ============================================================
# mode: "guide"=仅验证 guide 解析, "route"=guide+router, "full"=全链路

TEST_CASES = [
    # ── 基础单指标（A类：Tushare） ──
    {
        "id": "E2E-01", "query": "宁德时代今天的涨跌幅",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 1,
    },
    {
        "id": "E2E-02", "query": "贵州茅台今天的成交量",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 1,
    },
    # ── 多指标 ──
    {
        "id": "E2E-03", "query": "宁德时代今天的最高价和最低价",
        "expect": {"chain": False, "min_requests": 2},
        "mode": "full",
        "priority": 1,
    },
    # ── 多主体同指标 ──
    {
        "id": "E2E-04", "query": "宁德时代和比亚迪今天的股价",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "route",
        "priority": 2,
    },
    # ── 板块（B类：Akshare） ──
    {
        "id": "E2E-05", "query": "电池板块今天的涨跌幅",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 1,
    },
    # ── 指数 ──
    {
        "id": "E2E-06", "query": "上证指数今天的涨跌幅",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 1,
    },
    # ── 链式：宁德时代所在板块的涨跌幅 ──
    {
        "id": "E2E-07", "query": "宁德时代所在的板块今天的涨跌幅",
        "expect": {"chain": True, "min_requests": 2},
        "mode": "route",
        "priority": 1,
    },
    # ── 换手率（带参数） ──
    {
        "id": "E2E-08", "query": "宁德时代最近5天的换手率",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 财务指标 ──
    {
        "id": "E2E-09", "query": "贵州茅台今天的市盈率",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 沪深300 ──
    {
        "id": "E2E-10", "query": "沪深300今天的涨跌幅",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 资金流向 ──
    {
        "id": "E2E-11", "query": "宁德时代今天的大单资金流向",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "route",
        "priority": 3,
    },
    # ── Tencent 实时行情（需要 sz300750 格式） ──
    {
        "id": "E2E-12", "query": "宁德时代今天的股价",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 1,
    },
    # ── 多条件：同指标不同时间 ──
    {
        "id": "E2E-13", "query": "宁德时代在今天收盘和上周收盘的换手率",
        "expect": {"chain": False, "min_requests": 2},
        "mode": "route",
        "priority": 3,
    },
    # ── 板块多指标（链式） ──
    {
        "id": "E2E-14", "query": "宁德时代所在板块今天的涨跌幅和成交量",
        "expect": {"chain": True, "min_requests": 3},
        "mode": "route",
        "priority": 3,
    },
    # ── 北向资金 ──
    {
        "id": "E2E-15", "query": "最近一个月北向资金流向",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 恒生指数 ──
    {
        "id": "E2E-16", "query": "恒生指数今天的收盘价",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "route",
        "priority": 3,
    },
    # ── 财务深度：招商银行的ROE ──
    {
        "id": "E2E-17", "query": "招商银行最近一个季度的ROE",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 价格比较 ──
    {
        "id": "E2E-18", "query": "茅台和五粮液今天的股价谁高？",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "route",
        "priority": 3,
    },
    # ── 多级链式 ──
    {
        "id": "E2E-19", "query": "查一下宁德时代所在的板块的龙头股的涨跌幅",
        "expect": {"chain": True, "min_requests": 3},
        "mode": "guide",
        "priority": 3,
    },
    # ── 创业板指 ──
    {
        "id": "E2E-20", "query": "创业板指今天的成交量",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 2,
    },
    # ── 财务报表（HTML Scrape） ──
    {
        "id": "E2E-21", "query": "宁德时代最近一个季度的营业收入",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "route",
        "priority": 3,
    },
    # ── PMI 宏观数据 ──
    {
        "id": "E2E-22", "query": "中国最新的综合PMI",
        "expect": {"chain": False, "min_requests": 1},
        "mode": "full",
        "priority": 3,
    },
]


# ============================================================
# 测试执行
# ============================================================

def run_test(tc: dict, run_coder: bool = True) -> dict:
    """执行单个测试用例"""
    query = tc["query"]
    mode = tc.get("mode", "full")

    t0 = time.time()

    if mode == "guide":
        # 仅 guide 解析
        result = agent_guide_parse(query)
        elapsed = time.time() - t0
        success = "error" not in result
        return {
            "id": tc["id"], "query": query, "mode": mode,
            "success": success, "elapsed": round(elapsed, 2),
            "guide": result, "error": result.get("error", ""),
        }

    elif mode == "route":
        # guide + router（不含 coder）
        orch = Orchestrator()
        result = orch.answer(query, verbose=False, run_coder=False)
        elapsed = time.time() - t0
        return {
            "id": tc["id"], "query": query, "mode": mode,
            "success": result.get("success", False),
            "elapsed": round(elapsed, 2),
            "chain": result.get("chain", False),
            "requests": result.get("requests", []),
            "error": result.get("error", ""),
        }

    else:
        # 全链路
        orch = Orchestrator()
        result = orch.answer(query, verbose=False, run_coder=run_coder)
        elapsed = time.time() - t0
        return {
            "id": tc["id"], "query": query, "mode": mode,
            "success": result.get("success", False),
            "elapsed": round(elapsed, 2),
            "chain": result.get("chain", False),
            "requests": result.get("requests", []),
            "error": result.get("error", ""),
        }


def print_result(r: dict):
    """格式输出测试结果"""
    status = "✅" if r["success"] else "❌"
    mode_map = {"guide": "仅解析", "route": "路由", "full": "全链路"}
    mode_label = mode_map.get(r["mode"], r["mode"])

    print(f"  {status} [{r['id']}] {r['query']}")
    print(f"     模式={mode_label}, 耗时={r['elapsed']}s")

    if not r["success"]:
        print(f"     错误: {r.get('error', '')[:100]}")
        return

    if r.get("mode") == "guide":
        guide = r.get("guide", {})
        print(f"     chain={guide.get('chain','?')}, requests={len(guide.get('requests',[]))}")
        for req in guide.get("requests", [])[:2]:
            print(f"       {req.get('req_id')}: obj={req.get('obj')}, var={req.get('var')}, cond={req.get('condition')}")
    else:
        chain = r.get("chain", False)
        reqs = r.get("requests", [])
        print(f"     chain={chain}, requests={len(reqs)}")
        for req in reqs[:3]:
            status = "✅" if req.get("success") else "❌"
            field = req.get("field_id", "")
            if r["mode"] == "full":
                result_val = req.get("result", [])
                print(f"       {status} {req.get('req_id')}: {field} → {result_val}")
            else:
                entity = req.get("entity_value", "")
                ds = req.get("datasource", {}).get("id", "")
                ts = req.get("time_start", "")
                print(f"       {status} {req.get('req_id')}: {field} entity={entity} ds={ds} time={ts}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="端到端全链路测试")
    parser.add_argument("query", nargs="?", help="单条查询测试")
    parser.add_argument("--fast", action="store_true", help="只跑路由验证（不含取数执行）")
    parser.add_argument("--priority", type=int, default=1, help="最低优先级（1=最高, 3=最低）")
    args = parser.parse_args()

    # ── 单条测试 ──
    if args.query:
        print(f"{'='*60}")
        print(f"  单条测试: {args.query}")
        print(f"{'='*60}")

        orch = Orchestrator()
        t0 = time.time()
        result = orch.answer(args.query, verbose=True, run_coder=not args.fast)
        elapsed = time.time() - t0

        print(f"\n总耗时: {elapsed:.1f}s")
        print(f"结果: {'✅ 成功' if result.get('success') else '❌ 失败'}")
        if result.get("requests"):
            for r in result["requests"]:
                s = "✅" if r["success"] else "❌"
                print(f"  {s} [{r['req_id']}] field={r.get('field_id','')} result={r.get('result', [])}")
        return

    # ── 批量测试 ──
    cases = [c for c in TEST_CASES if c["priority"] <= (args.priority or 3)]

    # fast 模式：跳过 full
    if args.fast:
        cases = [c for c in cases if c["mode"] != "full"]

    print(f"{'='*70}")
    print(f"  🧪 端到端全链路测试")
    print(f"  模式: {'快速(不含取数)' if args.fast else '全链路'}")
    print(f"  用例: {len(cases)} 条（优先级 ≤ {args.priority})")
    print(f"{'='*70}")

    results = []
    pass_count = 0
    fail_count = 0

    for tc in cases:
        print(f"\n{'─'*60}")
        retry_count = 0
        run_coder = not args.fast and tc["mode"] == "full"

        while retry_count < 3:
            result = run_test(tc, run_coder=run_coder)

            if result["success"]:
                pass_count += 1
                print_result(result)
                results.append(result)
                break

            # 对于 full 模式，网络错误可以重试
            if "Connection" in result.get("error", "") or "Timeout" in result.get("error", ""):
                retry_count += 1
                print(f"  ⚠️ [{tc['id']}] 网络错误，第 {retry_count} 次重试...")
                time.sleep(3)
                continue

            fail_count += 1
            print_result(result)
            results.append(result)
            break
        else:
            fail_count += 1
            print_result(result)
            results.append(result)

    # ── 汇总 ──
    print(f"\n{'='*70}")
    print(f"  测试完成")

    # 按模式统计
    by_mode = {}
    for r in results:
        mode = r.get("mode", "full")
        by_mode.setdefault(mode, {"total": 0, "pass": 0})
        by_mode[mode]["total"] += 1
        if r["success"]:
            by_mode[mode]["pass"] += 1

    for mode, stats in by_mode.items():
        mode_label = {"guide": "解析验证", "route": "路由验证", "full": "全链路"}.get(mode, mode)
        print(f"  【{mode_label}】{stats['pass']}/{stats['total']} 通过")

    print(f"\n  总计: {pass_count}/{len(cases)} 成功, {fail_count} 失败")
    print(f"{'='*70}")

    # 保存结果
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"e2e_test_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            "fast": args.fast,
            "cases": results,
            "summary": f"{pass_count}/{len(cases)}",
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"  详细结果: {path}")


if __name__ == "__main__":
    main()
