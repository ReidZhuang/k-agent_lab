#!/usr/bin/env python3
"""
全量模式测试：critical + useful + related 所有层级保留

使用 v1.1 新版 prompts（三层五级分类 + 字符偏移标注）
后端：东方财富 API 实时数据
优先级模式：全量（不丢弃任何 priority 级别的引用）

对比 baseline：test_real_search.py（旧版 prompts）
后续对比：标准模式、精简模式
"""

import os, json, time, sys, requests, copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING, RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL, DEFAULT_MAX_TOKENS, API_BASE_URL,
)

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("❌ 未设置 DEEPSEEK_API_KEY")
    sys.exit(1)

client = __import__("openai").OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ═══════════════════════════════════════
# 东方财富 API（与 baseline 完全相同）
# ═══════════════════════════════════════

EMONEY_HEADERS = {"User-Agent": "Mozilla/5.0"}


def safe_float(v, default=0):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def fetch_financial(secucode):
    r = requests.get(
        "https://datacenter.eastmoney.com/securities/api/data/get",
        params={
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": 1,
            "ps": 6,
            "st": "NOTICE_DATE",
            "sr": -1,
        },
        headers=EMONEY_HEADERS,
        timeout=15,
    )
    return r.json().get("result", {}).get("data", [])


def fmt_report(rows, name):
    if not rows:
        return f"（{name} 暂无数据）"
    lines = [f"{name} 财务数据报告", "=" * 40]
    for row in rows[:4]:
        date = row.get("REPORT_DATE_NAME", "?")
        revenue = row.get("TOTALOPERATEREVE")
        revenue_tz = row.get("TOTALOPERATEREVETZ", "")
        profit = row.get("PARENTNETPROFIT")
        profit_tz = row.get("PARENTNETPROFITTZ", "")
        gross_margin = row.get("XSMLL", "")
        net_margin = row.get("XSJLL", "")
        eps = row.get("EPSXS", "")
        roe = row.get("ROEJQ", "")
        assets = row.get("TOTAL_ASSETS_PK", "")
        equity = row.get("TOTAL_EQUITY_PK", "")
        liability = row.get("ZCFZL", "")
        kcf_profit = row.get("KCFJCXSYJLR", "")

        lines.append(f"\n── {date} ──")

        def f(v):
            if v is None:
                return "N/A"
            try:
                return f"{float(v)/1e8:.1f}亿"
            except:
                return str(v)

        def fp(v):
            if v is None:
                return "N/A"
            try:
                return f"{float(v):.2f}%"
            except:
                return str(v)

        def fy(v):
            if v is None or v == "":
                return ""
            try:
                return f"(同比{float(v):.1f}%)"
            except:
                return str(v)

        lines.append(f"营业收入: {f(revenue)} {fy(revenue_tz)}")
        lines.append(f"净利润: {f(profit)} {fy(profit_tz)}")
        lines.append(f"扣非净利润: {f(kcf_profit)}")
        lines.append(f"毛利率: {fp(gross_margin)}")
        lines.append(f"净利率: {fp(net_margin)}")
        lines.append(f"每股收益: {eps if eps and eps != 'N/A' else 'N/A'}")
        lines.append(f"ROE: {fp(roe)}")
        lines.append(f"总资产: {f(assets)}")
        lines.append(f"净资产: {f(equity)}")
        lines.append(f"资产负债率: {fp(liability)}")
    lines.append(f"\n(数据来源: 东方财富数据中心, {time.strftime('%Y-%m-%d %H:%M')})")
    return "\n".join(lines)


def search_realtime(query):
    results = []
    if "宁德时代" in query and ("营收" in query or "财务" in query or "财报" in query):
        results.append(fmt_report(fetch_financial("300750.SZ"), "宁德时代(300750)"))
    if "比亚迪" in query and ("营收" in query or "财务" in query or "财报" in query):
        results.append(fmt_report(fetch_financial("002594.SZ"), "比亚迪(002594)"))
    if "对比" in query or "比较" in query:
        catl = fetch_financial("300750.SZ")
        byd = fetch_financial("002594.SZ")
        if catl and byd:
            results.append(fmt_report(catl, "宁德时代(300750)"))
            results.append(fmt_report(byd, "比亚迪(002594)"))
            cr, br = catl[0], byd[0]
            lines = [f"\n\n── 核心指标对比 ──",
                     f"{'指标':<20} {'宁德时代':<20} {'比亚迪':<20}"]
            for k, cn, mode in [
                ("TOTALOPERATEREVE", "营收(亿)", "f"),
                ("PARENTNETPROFIT", "净利润(亿)", "f"),
                ("XSMLL", "毛利率(%)", "p"),
                ("XSJLL", "净利率(%)", "p"),
                ("ROEJQ", "ROE(%)", "p"),
                ("ZCFZL", "负债率(%)", "p"),
            ]:
                cv = safe_float(cr.get(k)) / 1e8 if mode == "f" else safe_float(cr.get(k))
                bv = safe_float(br.get(k)) / 1e8 if mode == "f" else safe_float(br.get(k))
                lines.append(f"{cn:<20} {cv:<20.2f} {bv:<20.2f}")
            results.append("\n".join(lines))
    if not results:
        results.append(fmt_report(fetch_financial("300750.SZ"), "宁德时代(300750)"))
    return "\n\n".join(results)


# ═══════════════════════════════════════
# 主循环
# ═══════════════════════════════════════

USER_QUERY = "请研究宁德时代的财务状况，然后与比亚迪进行对比分析。你可以多步搜索，每步基于上一步发现继续深入。目标：全面了解两者的盈利能力、成长性和财务健康状况。"
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
SAVE_PATH = os.path.join(RESULTS_DIR, f"full_mode_{time.strftime('%Y%m%d_%H%M%S')}.json")


def main():
    print(f"{'='*65}")
    print(f"  全量模式测试")
    print(f"  优先级: critical + useful + related（所有层级保留）")
    print(f"  后端: 东方财富 API（与 baseline 相同）")
    print(f"  提示词版本: v1.1（三层五级分类 + 字符偏移标注）")
    print(f"{'='*65}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    rounds_log = []
    final_answer = None
    round_num = 0

    while True:
        round_num += 1
        print(f"\n{'─'*60}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*60}")

        total_tool_chars = sum(
            len(m.get("content", "")) for m in messages if m["role"] == "tool"
        )
        print(f"  消息: {len(messages)} 条, tool result 累计 {total_tool_chars} chars")

        # ── API 调用 ──
        try:
            t_api = time.time()
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_full_mode"},
            )
            api_time = time.time() - t_api
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else "?"
        out_t = response.usage.completion_tokens if response.usage else "?"
        print(f"  tokens: in={in_t}, out={out_t}, finish={finish}, time={api_time:.1f}s")

        # ── 完成回答 ──
        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 完成回答 ({len(final_answer)} chars)")
            print(f"  ╔{'═'*60}╗")
            for line in final_answer.split("\n"):
                print(f"  ║ {line}")
            print(f"  ╚{'═'*60}╝")
            break

        # ── Tool Call ──
        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name != "web_search":
                continue

            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                continue

            query = args.get("query", "")
            findings = args.get("key_findings_used", [])
            if not findings:
                findings = []

            # 统计优先级分布
            c_count = sum(1 for f in findings if f.get("priority") == "critical")
            u_count = sum(1 for f in findings if f.get("priority") == "useful")
            r_count = sum(1 for f in findings if f.get("priority") == "related")
            unk_count = sum(1 for f in findings if f.get("priority") not in ("critical", "useful", "related"))

            print(f"\n  🔍 {query}")
            print(f"  📋 引用 {len(findings)} 条 (c:{c_count} u:{u_count} r:{r_count}")
            if unk_count:
                print(f"  ⚠️  未知优先级: {unk_count} 条")

            # 打印每条引用详情
            for i, f in enumerate(findings):
                c = f.get("content", "")[:80]
                s = f.get("source", "?")
                p = f.get("priority", "?")
                print(f"    [{i}] [{p}] src={s} | {c}")

            # ── 真实搜索 ──
            t0 = time.time()
            search_result = search_realtime(query)
            search_time = time.time() - t0
            print(f"  📦 返回 {len(search_result)} chars ({search_time:.1f}s)")

            # ── 记录本轮数据 ──
            round_entry = {
                "round": round_num,
                "query": query,
                "findings": copy.deepcopy(findings),
                "priority_counts": {"critical": c_count, "useful": u_count, "related": r_count},
                "search_result": search_result,
                "search_result_len": len(search_result),
                "prompt_tokens": in_t,
                "completion_tokens": out_t,
            }
            rounds_log.append(round_entry)

            # ── 注入 assistant 消息 ──
            asst_msg = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                ],
            }
            model_extra = getattr(msg, "model_extra", None) or {}
            if model_extra.get("reasoning_content"):
                asst_msg["reasoning_content"] = model_extra["reasoning_content"]
            messages.append(asst_msg)

            # ── 注入 tool result ──
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": search_result,
            })
            print(f"  ✅ 注入完成 ({len(messages)} 条消息)")

    # ══════════════════════════
    # 汇总 & 保存
    # ══════════════════════════

    # 统计所有轮次的优先级分布
    total_c = sum(e["priority_counts"]["critical"] for e in rounds_log)
    total_u = sum(e["priority_counts"]["useful"] for e in rounds_log)
    total_r = sum(e["priority_counts"]["related"] for e in rounds_log)
    total_findings = total_c + total_u + total_r

    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  Tool Call 轮次: {len(rounds_log)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'} ({len(final_answer or '')} chars)")
    print(f"  总引用: {total_findings} 条")
    print(f"    其中 critical: {total_c} 条 ({total_c/total_findings*100:.1f}%" if total_findings else "")
    print(f"         useful:   {total_u} 条 ({total_u/total_findings*100:.1f}%)" if total_findings else "")
    print(f"         related:  {total_r} 条 ({total_r/total_findings*100:.1f}%)" if total_findings else "")

    # 比对：baseline 跑了 10 轮，对照组 16 轮
    print(f"\n  📊 与 baseline 对比")
    print(f"  baseline (旧版prompts, 实验组): 10 轮, 最终 3,586 chars")
    print(f"  baseline (旧版prompts, 对照组): 16 轮, 最终 3,529 chars, 节省 19,676 tokens")

    # 保存
    output = {
        "test_name": "full_mode",
        "priority_mode": "critical+useful+related",
        "prompts_version": "v1.1",
        "model": DEFAULT_MODEL,
        "user_query": USER_QUERY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rounds": len(rounds_log),
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "final_answer_chars": len(final_answer or ""),
        "total_findings": total_findings,
        "priority_summary": {
            "critical": total_c,
            "useful": total_u,
            "related": total_r,
        },
        "rounds": rounds_log,
    }

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📝 已保存: {SAVE_PATH}")


if __name__ == "__main__":
    main()
