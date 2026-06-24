#!/usr/bin/env python3
"""
真实搜索测试：使用东方财富 API 获取真实财务数据，跑 2-3 轮 agent loop

数据来源：datacenter.eastmoney.com（实时财务数据）
调用路径：OpenAI 兼容路径（DeepSeek API）
核心验证：tool_call arguments 中的 reasoning 提取
"""

import os, json, time, sys, requests
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING, RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL, DEFAULT_MAX_TOKENS, API_BASE_URL,
)

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY: print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ══════════════════════════════════════════════
# 真实数据获取（东方财富 API）
# ══════════════════════════════════════════════

EMONEY_HEADERS = {'User-Agent': 'Mozilla/5.0'}

def fetch_main_financial(secucode):
    """获取主要财务指标"""
    r = requests.get(
        'https://datacenter.eastmoney.com/securities/api/data/get',
        params={
            'type': 'RPT_F10_FINANCE_MAINFINADATA',
            'sty': 'ALL',
            'filter': f'(SECUCODE="{secucode}")',
            'p': 1, 'ps': 6,
            'st': 'NOTICE_DATE', 'sr': -1,
        },
        headers=EMONEY_HEADERS, timeout=15
    )
    return r.json().get('result', {}).get('data', [])


def format_financial_report(rows, company_name):
    """将财务数据格式化为报告"""
    if not rows:
        return f"（{company_name} 暂无数据）"

    lines = [f"{company_name} 财务数据报告", "=" * 40]

    for row in rows[:4]:
        date = row.get('REPORT_DATE_NAME', '?')
        revenue = row.get('TOTALOPERATEREVE')
        revenue_tz = row.get('TOTALOPERATEREVETZ', '')
        profit = row.get('PARENTNETPROFIT')
        profit_tz = row.get('PARENTNETPROFITTZ', '')
        gross_margin = row.get('XSMLL', '')
        net_margin = row.get('XSJLL', '')
        eps = row.get('EPSXS', '')
        roe = row.get('ROEJQ', '')
        assets = row.get('TOTAL_ASSETS_PK', '')
        equity = row.get('TOTAL_EQUITY_PK', '')
        liability_ratio = row.get('ZCFZL', '')
        kcf_profit = row.get('KCFJCXSYJLR', '')

        lines.append(f"\n── {date} ──")

        def fmt(n):
            if n is None or n == 'N/A': return 'N/A'
            try: return f"{float(n)/1e8:.1f}亿"
            except: return str(n)

        def fmt_pct(n):
            if n is None or n == '': return 'N/A'
            try: return f"{float(n):.2f}%"
            except: return str(n)

        def fmt_yoy(n):
            if n is None or n == '': return ''
            try: return f"(同比{float(n):.1f}%)"
            except: return str(n)

        lines.append(f"营业收入: {fmt(revenue)} {fmt_yoy(revenue_tz)}")
        lines.append(f"净利润: {fmt(profit)} {fmt_yoy(profit_tz)}")
        lines.append(f"扣非净利润: {fmt(kcf_profit)}")
        lines.append(f"毛利率: {fmt_pct(gross_margin)}")
        lines.append(f"净利率: {fmt_pct(net_margin)}")
        lines.append(f"每股收益: {eps if eps and eps != 'N/A' else 'N/A'}")
        lines.append(f"ROE: {fmt_pct(roe)}")
        lines.append(f"总资产: {fmt(assets)}")
        lines.append(f"净资产: {fmt(equity)}")
        lines.append(f"资产负债率: {fmt_pct(liability_ratio)}")

    lines.append(f"\n(数据来源: 东方财富数据中心, {time.strftime('%Y-%m-%d %H:%M')})")
    return "\n".join(lines)


def search_realtime(query):
    """将用户搜索意图映射到真实的财务数据"""
    results = []

    if '宁德时代' in query and ('营收' in query or '财报' in query or '财务' in query):
        data = fetch_main_financial('300750.SZ')
        results.append(format_financial_report(data, '宁德时代(300750)'))

    if '比亚迪' in query and ('营收' in query or '财报' in query or '财务' in query):
        data = fetch_main_financial('002594.SZ')
        results.append(format_financial_report(data, '比亚迪(002594)'))

    if '对比' in query or '比较' in query:
        catl = fetch_main_financial('300750.SZ')
        byd = fetch_main_financial('002594.SZ')
        if catl and byd:
            results.append(format_financial_report(catl, '宁德时代(300750)'))
            results.append(format_financial_report(byd, '比亚迪(002594)'))

            # Add comparison section
            cr = catl[0]
            br = byd[0]
            lines = ["\n\n── 核心指标对比 ──", f"{'指标':<20} {'宁德时代':<20} {'比亚迪':<20}"]
            try:
                def safe_float(v, default=0):
                    if v is None: return default
                    try: return float(v)
                    except: return default
                crv = safe_float(cr.get('TOTALOPERATEREVE')) / 1e8
                brv = safe_float(br.get('TOTALOPERATEREVE')) / 1e8
                lines.append(f"{'营收(亿)':<20} {crv:<20.1f} {brv:<20.1f}")
                crp = safe_float(cr.get('PARENTNETPROFIT')) / 1e8
                brp = safe_float(br.get('PARENTNETPROFIT')) / 1e8
                lines.append(f"{'净利润(亿)':<20} {crp:<20.1f} {brp:<20.1f}")
                lines.append(f"{'毛利率(%)':<20} {safe_float(cr.get('XSMLL')):<20.2f} {safe_float(br.get('XSMLL')):<20.2f}")
                lines.append(f"{'ROE(%)':<20} {safe_float(cr.get('ROEJQ')):<20.2f} {safe_float(br.get('ROEJQ')):<20.2f}")
            except: pass
            results.append("\n".join(lines))

    if '储能' in query or '毛利率' in query:
        data = fetch_main_financial('300750.SZ')
        report = format_financial_report(data, '宁德时代(300750)')
        # Add margin analysis note
        margin = data[0].get('XSMLL', 'N/A')
        if isinstance(margin, float): margin = f"{margin:.2f}"
        report += f"\n\n【毛利率分析】根据最新数据，宁德时代毛利率约{margin}%。储能业务详细毛利率数据未在本次API返回中，建议参考年报。"
        results.append(report)

    if not results:
        data = fetch_main_financial('300750.SZ')
        results.append(format_financial_report(data, '宁德时代(300750)'))

    return "\n\n".join(results)


# ══════════════════════════════════════════════
# Agent Loop
# ══════════════════════════════════════════════

USER_QUERY = "请研究宁德时代的财务状况，然后与比亚迪进行对比分析。你可以多步搜索，每步基于上一步发现继续深入。目标：全面了解两者的盈利能力、成长性和财务健康状况。"

def main():
    print(f"{'='*60}")
    print(f"  真实搜索测试: 东方财富 API × 2轮 agent loop")
    print(f"  数据: 实时财务数据")
    print(f"  模型: {DEFAULT_MODEL}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    round_data = {}
    final_answer = None
    round_num = 0

    while True:
        round_num += 1
        print(f"\n{'─'*50}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*50}")

        # Print message summary
        total_tool_chars = sum(len(m.get('content','')) for m in messages if m['role']=='tool')
        print(f"  消息队列: {len(messages)} 条 (tool result 累计 {total_tool_chars} chars)")

        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={
                    "user_id": "exp01_real_test",
                },
            )
        except Exception as e:
            print(f"  ❌ API异常: {e}"); break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else "?"
        out_t = response.usage.completion_tokens if response.usage else "?"
        print(f"  tokens: in={in_t}, out={out_t}, finish={finish}")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 完成回答 ({len(final_answer)} chars)")
            print(f"  ╔{'═'*60}╗")
            for line in final_answer.split("\n"):
                print(f"  ║ {line}")
            print(f"  ╚{'═'*60}╝")
            break

        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name != "web_search": continue

            try: args = json.loads(tc.function.arguments)
            except: continue

            query = args.get("query", "")
            findings = args.get("key_findings_used", [])

            print(f"\n  🔍 LLM 查询: {query}")
            print(f"  📋 引用 ({len(findings)} 条):")
            for f in findings:
                c = f.get("content","")[:60]
                s = f.get("source","?")
                p = f.get("priority","?")
                print(f"     [{p}] src={s} | {c}")

            # ═══ 真实搜索 ═══
            print(f"  ⏳ 正在获取真实数据...")
            t0 = time.time()
            search_result = search_realtime(query)
            print(f"  📦 返回 {len(search_result)} chars (耗时{time.time()-t0:.1f}s)")
            print(f"  ├─ 内容预览:")
            for line in search_result.split("\n")[:5]:
                print(f"  │ {line}")

            # 记录
            round_data[round_num] = {
                "query": query,
                "findings": findings,
                "result_len": len(search_result),
            }

            # 保存完整 assistant 消息（含可能存在的 reasoning_content）
            asst_msg = {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }],
            }
            # DeepSeek 可能在 response 中返回 reasoning_content，需要回传
            model_extra = getattr(msg, 'model_extra', None) or {}
            if model_extra.get('reasoning_content'):
                asst_msg['reasoning_content'] = model_extra['reasoning_content']
            messages.append(asst_msg)
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": search_result,
            })
            print(f"  ✅ 注入完成 ({len(messages)} 条消息, 其中 reasoning={bool(model_extra.get('reasoning_content'))})")

    # 汇总
    print(f"\n{'='*60}")
    print(f"  测试完成")
    print(f"  Tool Call 轮次: {len(round_data)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'}")

    if not final_answer and round_data:
        print(f"\n  各轮查询:")
        for r, d in round_data.items():
            print(f"  第{r}轮: {d['query']}")
            print(f"         引用 {len(d['findings'])} 条, 返回 {d['result_len']} chars")


if __name__ == "__main__":
    main()
