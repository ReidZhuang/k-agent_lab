#!/usr/bin/env python3
"""
对照组实验：用 key_findings_used 的引用替代完整历史 tool result

实验组（已跑）：完整历史 tool result 一直保留在上下文中
对照组（本脚本）：每轮收到引用后，将上一轮的完整结果替换为引用摘要

验证：回答质量是否一致？节省多少 tokens？
"""

import os, json, time, sys, requests, copy
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompts import (
    WEB_SEARCH_TOOL_WITH_REASONING, RESEARCH_SYSTEM_PROMPT,
    DEFAULT_MODEL, DEFAULT_MAX_TOKENS, API_BASE_URL,
)

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY: print("❌ 未设置 DEEPSEEK_API_KEY"); sys.exit(1)
client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# ══════════════════════════════════════════
# 真实数据获取（与实验组完全相同）
# ══════════════════════════════════════════
EMONEY_HEADERS = {'User-Agent': 'Mozilla/5.0'}

def safe_float(v, default=0):
    if v is None: return default
    try: return float(v)
    except: return default

def fetch_financial(secucode):
    r = requests.get(
        'https://datacenter.eastmoney.com/securities/api/data/get',
        params={'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
                'filter':f'(SECUCODE="{secucode}")','p':1,'ps':6,
                'st':'NOTICE_DATE','sr':-1},
        headers=EMONEY_HEADERS, timeout=15)
    return r.json().get('result',{}).get('data',[])

def fmt_report(rows, name):
    if not rows: return f"（无数据）"
    lines = [f"{name} 财务数据报告", "="*40]
    for row in rows[:4]:
        date = row.get('REPORT_DATE_NAME','?')
        def f(n):
            if n is None: return 'N/A'
            return f"{float(n)/1e8:.1f}亿"
        def fp(n):
            if n is None: return 'N/A'
            return f"{float(n):.2f}%"
        def fy(n):
            if n is None: return ''
            return f"(同比{float(n):.1f}%)"
        lines.append(f"\n── {date} ──")
        lines.append(f"营收: {f(row.get('TOTALOPERATEREVE'))} {fy(row.get('TOTALOPERATEREVETZ'))}")
        lines.append(f"净利: {f(row.get('PARENTNETPROFIT'))} {fy(row.get('PARENTNETPROFITTZ'))}")
        lines.append(f"扣非净利: {f(row.get('KCFJCXSYJLR'))}")
        lines.append(f"毛利率: {fp(row.get('XSMLL'))} | 净利率: {fp(row.get('XSJLL'))}")
        lines.append(f"EPS: {row.get('EPSXS','N/A')} | ROE: {fp(row.get('ROEJQ'))}")
        lines.append(f"总资产: {f(row.get('TOTAL_ASSETS_PK'))} | 净资产: {f(row.get('TOTAL_EQUITY_PK'))}")
        lines.append(f"资产负债率: {fp(row.get('ZCFZL'))}")
    lines.append(f"\n(来源:东方财富)")
    return "\n".join(lines)

def search_realtime(query):
    results = []
    if '宁德时代' in query or ('营收' in query and '比亚迪' not in query):
        results.append(fmt_report(fetch_financial('300750.SZ'), '宁德时代(300750)'))
    if '比亚迪' in query or ('对比' in query or '比较' in query):
        results.append(fmt_report(fetch_financial('002594.SZ'), '比亚迪(002594)'))
    if ('对比' in query or '比较' in query) and len(results) >= 2:
        catl = fetch_financial('300750.SZ')
        byd = fetch_financial('002594.SZ')
        if catl and byd:
            cr, br = catl[0], byd[0]
            ls = ["\n\n── 核心对比 ──"]
            ls.append(f"{'指标':<20} {'宁德时代':<20} {'比亚迪':<20}")
            for k, cn, bn in [('TOTALOPERATEREVE','营收(亿)','f'),('PARENTNETPROFIT','净利(亿)','f'),
                               ('XSMLL','毛利率(%)','p'),('XSJLL','净利率(%)','p'),
                               ('ROEJQ','ROE(%)','p'),('ZCFZL','负债率(%)','p')]:
                cv = safe_float(cr.get(k))/1e8 if cn.endswith('(亿)') else safe_float(cr.get(k))
                bv = safe_float(br.get(k))/1e8 if cn.endswith('(亿)') else safe_float(br.get(k))
                ls.append(f"{cn:<20} {cv:<20.2f} {bv:<20.2f}")
            results.append("\n".join(ls))
    if not results:
        results.append(fmt_report(fetch_financial('300750.SZ'), '宁德时代(300750)'))
    return "\n\n".join(results)

# ══════════════════════════════════════════
# 核心：引用压缩逻辑
# ══════════════════════════════════════════

def compress_to_citations(full_text: str, cited_contents: list) -> str:
    """将完整搜索结果压缩为仅保留被引用部分的摘要

    Args:
        full_text: 完整的 tool result 原文
        cited_contents: key_findings_used 中的 content 列表

    Returns:
        压缩后的文本（仅保留被引用片段）
    """
    if not cited_contents:
        return "(本轮内容未产生引用)"

    parts = []
    seen = set()
    for content in cited_contents:
        if not content or content in seen:
            continue
        seen.add(content)
        if content in full_text:
            parts.append(content)

    if not parts:
        # fallback: 返回原文前500字
        return full_text[:500] + "\n...(截断)"

    return "\n\n".join([f"> 引用: {p}" for p in parts])


def replace_previous_tool_result(messages, round_num, compression_map):
    """将消息队列中上一轮的完整 tool result 替换为引用摘要

    Args:
        messages: 当前消息队列
        round_num: 当前轮次
        compression_map: {round: {"full": ..., "short": ..., "savings": ...}}
    """
    if round_num <= 1:
        return

    prev_round = round_num - 1
    if prev_round not in compression_map:
        return

    short_text = compression_map[prev_round]["short"]
    replaced = 0

    # 从后往前查找并替换上一轮的 tool result
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg["role"] == "tool":
            # 检查这个 tool result 是否是上一轮的
            if msg.get("_round") == prev_round:
                original_len = len(msg.get("content", ""))
                msg["content"] = short_text
                new_len = len(short_text)
                compression_map[prev_round]["replaced"] = True
                compression_map[prev_round]["original_len"] = original_len
                compression_map[prev_round]["compressed_len"] = new_len
                compression_map[prev_round]["savings"] = original_len - new_len
                replaced += 1
                break

    return replaced


# ══════════════════════════════════════════
# Main
# ══════════════════════════════════════════

USER_QUERY = "请研究宁德时代的财务状况，然后与比亚迪进行对比分析。你可以多步搜索，每步基于上一步发现继续深入。目标：全面了解两者的盈利能力、成长性和财务健康状况。"
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", f"control_{time.strftime('%Y%m%d_%H%M%S')}.json")

def main():
    print(f"{'='*60}")
    print(f"  对照组实验：引用压缩")
    print(f"  配置与实验组完全相同，唯一差异：用引用摘要替代历史完整 tool result")
    print(f"{'='*60}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    compression_map = {}       # round → {full, short, savings, replaced}
    total_future_savings = 0   # 累计未来节省
    round_data = []
    final_answer = None

    round_num = 0
    while True:
        round_num += 1
        print(f"\n{'─'*50}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*50}")

        # 累计已压缩的 tool result 总字符
        total_tool_chars = sum(len(m.get('content','')) for m in messages if m['role']=='tool')
        print(f"  消息: {len(messages)} 条, tool result累计: {total_tool_chars} chars")

        # 打印上下文结构：哪些轮次是完整/压缩状态
        for i, m in enumerate(messages):
            if m['role'] == 'tool':
                rnd = m.get('_round', '?')
                c_len = len(m.get('content',''))
                status = "FULL" if rnd in compression_map and not compression_map.get(rnd,{}).get('replaced') else "SHORT" if rnd in compression_map else "FULL"
                print(f"    [{i}] tool(R{rnd}, {c_len}c, {status})")
            elif m['role'] == 'assistant':
                tc = m.get('tool_calls')
                print(f"    [{i}] assistant({'tool_call' if tc else 'text'})")

        # ── API 调用 ──
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL, messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING],
                tool_choice="auto", max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_control"},
            )
        except Exception as e:
            print(f"  ❌ API: {e}"); break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else "?"
        out_t = response.usage.completion_tokens if response.usage else "?"
        print(f"  tokens: in={in_t}, out={out_t}, finish={finish}")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ 完成回答 ({len(final_answer)} chars)")
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

            query = args.get("query","")
            findings = args.get("key_findings_used", [])
            cited_contents = [f.get("content","") for f in findings] if findings else []

            print(f"\n  🔍 {query}")
            print(f"  📋 引用 {len(findings)} 条")

            # ── 真实搜索（与实验组相同）──
            t0 = time.time()
            search_result = search_realtime(query)
            print(f"  📦 返回 {len(search_result)} chars ({time.time()-t0:.1f}s)")

            # ── 压缩上一轮 tool result ──
            if round_num >= 2:
                prev_round = round_num - 1
                if prev_round in compression_map:
                    prev_full = compression_map[prev_round].get("full", "")
                    prev_short = compress_to_citations(prev_full, cited_contents)

                    # 记录压缩结果
                    compression_map[prev_round]["short"] = prev_short
                    compression_map[prev_round]["cited_contents"] = cited_contents

                    # 替换消息队列中的完整内容
                    replace_previous_tool_result(messages, round_num, compression_map)

                    savings = compression_map[prev_round].get("savings", 0)
                    future_savings = savings * 10
                    total_future_savings += future_savings if savings > 0 else 0

                    orig = compression_map[prev_round].get('original_len','?')
                    comp_len = compression_map[prev_round].get('compressed_len','?')
                    print(f"  ✂️  压缩第{prev_round}轮: {orig} → {comp_len} chars, 节省{savings} chars")
                else:
                    print(f"  ⚠️ 第{prev_round}轮无搜索结果可压缩")

            # ── 记录本轮数据 ──
            round_data.append({"round": round_num, "query": query, "findings": findings, "result_len": len(search_result)})

            # ── 保存完整结果供压缩 ──
            compression_map[round_num] = {
                "full": search_result,
                "short": None,
                "savings": 0,
                "replaced": False,
                "original_len": len(search_result),
                "compressed_len": None,
            }

            # ── 注入 assistant 消息 ──
            asst_msg = {
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}],
            }
            model_extra = getattr(msg, 'model_extra', None) or {}
            if model_extra.get('reasoning_content'):
                asst_msg['reasoning_content'] = model_extra['reasoning_content']
            messages.append(asst_msg)

            # ── 注入 tool result（标记轮次）──
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": search_result,
                "_round": round_num,
            })
            print(f"  ✅ 注入完成 ({len(messages)} 条消息)")

    # ══════════════════════
    # 汇总
    # ══════════════════════
    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  Tool Call 轮次: {len(round_data)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'}")

    # 实际节省计算
    print(f"\n📊 压缩统计:")
    print(f"  {'轮次':<6} {'压缩前':<10} {'压缩后':<10} {'单轮节省':<10} {'实际剩余轮次':<12} {'未来节省':<10}")
    print(f"  {'─'*56}")
    actual_total_savings = 0
    for r in sorted(compression_map.keys()):
        info = compression_map[r]
        if info.get("replaced") and info.get("savings", 0) > 0:
            # 计算实际剩余轮次：从压缩发生那一刻起，到结束的轮次数
            compression_happened_at = r + 1  # 在第 r+1 轮被压缩
            remaining_actual = len(round_data) - r  # 剩余的 tool call 轮次
            future_save = info["savings"] * remaining_actual
            actual_total_savings += future_save
            print(f"  第{r:<2}轮 {info['original_len']:<10} {info['compressed_len']:<10} {info['savings']:<10} {remaining_actual:<12} {future_save:<10}")
    print(f"  {'─'*56}")
    print(f"  {'总计':<6} {'':<10} {'':<10} {'':<10} {'':<12} {actual_total_savings:<10}")

    print(f"\n  🏆 总节省: {actual_total_savings} chars ≈ {actual_total_savings//4} tokens (估算)")

    # 保存
    with open(SAVE_PATH, "w") as f:
        json.dump({
            "test": "control_compression",
            "rounds": len(round_data),
            "has_final_answer": bool(final_answer),
            "total_savings_chars": actual_total_savings,
            "total_savings_tokens_est": actual_total_savings // 4,
            "compression_details": {str(k): v for k, v in compression_map.items()},
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📝 {SAVE_PATH}")


if __name__ == "__main__":
    main()
