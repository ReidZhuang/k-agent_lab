#!/usr/bin/env python3
"""
实验组 — v1.3 行号标记系统 + 上下文压缩
每轮收到 LLM 引用后，压缩上一轮的 tool result 为精炼 markdown 格式
"""

import os, json, time, sys, requests, copy, re

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

EMONEY_HEADERS = {"User-Agent": "Mozilla/5.0"}

def safe_float(v, default=0):
    if v is None: return default
    try: return float(v)
    except: return default

def fetch_financial(secucode):
    r = requests.get(
        "https://datacenter.eastmoney.com/securities/api/data/get",
        params={
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{secucode}")',
            "p": 1, "ps": 6, "st": "NOTICE_DATE", "sr": -1,
        },
        headers=EMONEY_HEADERS, timeout=15,
    )
    return r.json().get("result", {}).get("data", [])

def fmt_report(rows, name):
    if not rows: return f"（{name} 暂无数据）"
    lines = [f"{name} 财务数据报告", "=" * 40]
    for row in rows[:4]:
        date = row.get("REPORT_DATE_NAME", "?")
        revenue = row.get("TOTALOPERATEREVE")
        revenue_tz = row.get("TOTALOPERATEREVETZ", "")
        profit = row.get("PARENTNETPROFIT")
        profit_tz = row.get("PARENTNETPROFITTZ", "")
        def f(v):
            if v is None: return "N/A"
            try: return f"{float(v)/1e8:.1f}亿"
            except: return str(v)
        def fp(v):
            if v is None: return "N/A"
            try: return f"{float(v):.2f}%"
            except: return str(v)
        def fy(v):
            if v is None or v == "": return ""
            try: return f"(同比{float(v):.1f}%)"
            except: return str(v)
        lines.append(f"\n── {date} ──")
        lines.append(f"营业收入: {f(revenue)} {fy(revenue_tz)}")
        lines.append(f"净利润: {f(profit)} {fy(profit_tz)}")
        lines.append(f"扣非净利润: {f(row.get('KCFJCXSYJLR', ''))}")
        lines.append(f"毛利率: {fp(row.get('XSMLL', ''))}")
        lines.append(f"净利率: {fp(row.get('XSJLL', ''))}")
        lines.append(f"每股收益: {row.get('EPSXS') or 'N/A'}")
        lines.append(f"ROE: {fp(row.get('ROEJQ', ''))}")
        lines.append(f"总资产: {f(row.get('TOTAL_ASSETS_PK', ''))}")
        lines.append(f"净资产: {f(row.get('TOTAL_EQUITY_PK', ''))}")
        lines.append(f"资产负债率: {fp(row.get('ZCFZL', ''))}")
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
            items = [f"\n\n── 核心指标对比 ──",
                     f"{'指标':<20} {'宁德时代':<20} {'比亚迪':<20}"]
            for k, cn, mode in [
                ("TOTALOPERATEREVE","营收(亿)","f"),("PARENTNETPROFIT","净利润(亿)","f"),
                ("XSMLL","毛利率(%)","p"),("XSJLL","净利率(%)","p"),
                ("ROEJQ","ROE(%)","p"),("ZCFZL","负债率(%)","p"),
            ]:
                cv = safe_float(cr.get(k))/1e8 if mode=="f" else safe_float(cr.get(k))
                bv = safe_float(br.get(k))/1e8 if mode=="f" else safe_float(br.get(k))
                items.append(f"{cn:<20} {cv:<20.2f} {bv:<20.2f}")
            results.append("\n".join(items))
    if not results:
        results.append(fmt_report(fetch_financial("300750.SZ"), "宁德时代(300750)"))
    return "\n\n".join(results)

# ═══════════════════════════════════════
# 行号标记系统
# ═══════════════════════════════════════

def inject_line_tags(raw_text):
    if not raw_text: return "", {}
    raw_lines = raw_text.split("\n")
    tagged_lines = []
    line_map = {}
    line_no = 0
    for raw_line in raw_lines:
        remaining = raw_line
        while len(remaining) > 100:
            part = remaining[:100]
            tagged_lines.append(f"{line_no}~ {part}")
            line_map[line_no] = part
            remaining = remaining[100:]
            line_no += 1
        tagged_lines.append(f"{line_no}~ {remaining}")
        line_map[line_no] = remaining
        line_no += 1
    return "\n".join(tagged_lines), line_map

def parse_line_ref(lines_str):
    if not lines_str: return []
    result = []
    for part in lines_str.split(","):
        part = part.strip()
        if not part: continue
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                result.extend(range(int(a.strip()), int(b.strip()) + 1))
            except: continue
        else:
            try: result.append(int(part))
            except: continue
    return sorted(set(result))

def reconstruct_content(lines_str, line_map):
    nums = parse_line_ref(lines_str)
    segs = []
    for n in nums:
        if n in line_map:
            segs.append(line_map[n])
    return "\n".join(segs)

def _line_data_in_context(line, context):
    """检查本行的数值数据是否已被 context 覆盖。

    提取行中所有数值（含百分比），逐项检查 context 中是否包含。
    允许 ±1 字符差异（如 context 中的 +52.4% 对应行中的 52.4%）。
    如果所有数值都在 context 中出现 → 行可省略。
    如果行中没有数值（如标题行）→ 保留。
    """
    if not line or not context:
        return False

    # 提取数值：数字+小数点+百分比符号，如 1291.3、52.4%、24.91
    values = re.findall(r'\d+\.?\d*%?', line)
    if not values:
        return False  # 纯文字行，不省略

    for v in values:
        # 完全匹配
        if v in context:
            continue
        # 去掉百分号匹配（行有%但context可能没写）
        v_stripped = v.rstrip('%')
        if v_stripped != v and v_stripped in context:
            continue
        # 带 +/- 前缀匹配（行有+52.4%但context写52.4% 或反之）
        if f'+{v}' in context or f'-{v}' in context:
            continue
        # 去掉末尾 .0
        if v.endswith('.0') and v[:-2] in context:
            continue
        return False  # 该数值在 context 中没有找到 → 行需要保留

    return True


def format_compressed_citation(findings, line_map):
    """将引用结果压缩为 markdown 格式

    每条引用输出：
    ### 重要性: critical
    ### summary: context
    ### content:
    （未包含在 summary 中的原文行）

    优化：如果某行数据已出现在 context 中，则省略该行。
    """
    parts = []
    for f in findings:
        line_ref = f.get("content", "")
        priority = f.get("priority", "")
        context = f.get("context", "")
        cited_text = reconstruct_content(line_ref, line_map)

        # 逐行检查：数据是否已被 context 覆盖
        kept_lines = []
        for cl in cited_text.split("\n"):
            if not _line_data_in_context(cl, context):
                kept_lines.append(cl)

        kept_text = "\n".join(kept_lines).strip()
        if kept_text:
            block = f"### 重要性: {priority}\n### summary: {context}\n### content:\n{kept_text}"
        else:
            # 所有行都被 context 覆盖，省略 content 部分
            block = f"### 重要性: {priority}\n### summary: {context}"
        parts.append(block)
    return "\n\n".join(parts)

# ═══════════════════════════════════════
# 主循环
# ═══════════════════════════════════════

USER_QUERY = "请研究宁德时代的财务状况，然后与比亚迪进行对比分析。你可以多步搜索，每步基于上一步发现继续深入。目标：全面了解两者的盈利能力、成长性和财务健康状况。"
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
SAVE_PATH = os.path.join(RESULTS_DIR, f"experiment_{time.strftime('%Y%m%d_%H%M%S')}.json")

def main():
    print(f"{'='*65}")
    print(f"  实验组 — 行号标记 + 上下文压缩")
    print(f"  后端: 东方财富 API")
    print(f"{'='*65}")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    rounds_log = []
    final_answer = None
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_saved_chars = 0

    while True:
        round_num = len(rounds_log) + 1
        print(f"\n{'─'*60}")
        print(f"  第 {round_num} 轮")
        print(f"{'─'*60}")

        tool_chars = sum(len(m.get("content","")) for m in messages if m["role"]=="tool")
        print(f"  消息: {len(messages)} 条, tool result 累计 {tool_chars} chars")

        try:
            t_api = time.time()
            response = client.chat.completions.create(
                model=DEFAULT_MODEL, messages=messages,
                tools=[WEB_SEARCH_TOOL_WITH_REASONING], tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                parallel_tool_calls=False,
                extra_body={"user_id": "exp01_experiment"},
            )
            api_time = time.time() - t_api
        except Exception as e:
            print(f"  ❌ API 异常: {e}")
            break

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message
        in_t = response.usage.prompt_tokens if response.usage else 0
        out_t = response.usage.completion_tokens if response.usage else 0
        total_prompt_tokens += in_t
        total_completion_tokens += out_t
        print(f"  tokens: in={in_t}, out={out_t}, finish={finish}, time={api_time:.1f}s")

        if finish == "stop":
            final_answer = msg.content or ""
            print(f"\n  ✅ LLM 完成回答 ({len(final_answer)} chars)")
            break

        if finish == "tool_calls" and msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name != "web_search": continue

            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                continue

            query = args.get("query", "")
            findings = args.get("key_findings_used", []) or []

            c_count = sum(1 for f in findings if f.get("priority")=="critical")
            u_count = sum(1 for f in findings if f.get("priority")=="useful")
            r_count = sum(1 for f in findings if f.get("priority")=="related")

            print(f"\n  🔍 {query}")
            print(f"  📋 引用 {len(findings)} 条 (c:{c_count} u:{u_count} r:{r_count})")

            # ── 如果已有上一轮数据，先压缩上一轮的 tool result ──
            saved_chars_this = 0
            if round_num >= 2 and findings:
                # 上一轮的数据在 rounds_log[-1]
                prev_round_data = rounds_log[-1]
                # line_map 在 JSON 中 key 是字符串，转 int
                prev_line_map = {int(k): v for k, v in prev_round_data["line_map"].items()}
                # 上一轮的 tool message 位于 messages[2*round_num - 1]
                # 因为: system(0)+user(1)+asst*N+tool*N，第N轮的tool在 2*N+1
                # 第 round_num-1 轮的 tool 在 2*(round_num-1)+1 = 2*round_num-1
                prev_tool_idx = 2 * round_num - 1

                old_content = messages[prev_tool_idx].get("content", "")
                compressed = format_compressed_citation(findings, prev_line_map)

                # 优化2：压缩后不比原文小 → 放弃压缩，保留原文
                if len(compressed) < len(old_content):
                    messages[prev_tool_idx]["content"] = compressed
                    saved_chars_this = len(old_content) - len(compressed)
                    total_saved_chars += saved_chars_this
                    print(f"  🔧 压缩第 {round_num-1} 轮: {len(old_content)} → {len(compressed)} chars (省 {saved_chars_this})")
                else:
                    saved_chars_this = 0
                    print(f"  🔧 跳过压缩第 {round_num-1} 轮: 压缩后 {len(compressed)} ≥ 原文 {len(old_content)} chars, 保留原文")

            # ── 打印引用详情 ──
            for i, f in enumerate(findings):
                line_ref = f.get("content","")
                p = f.get("priority","?")
                ctx = f.get("context","")
                # 还原时用上一轮的 line_map（不是刚才压缩用的，是上上轮的）
                if round_num >= 2:
                    prev_lm = {int(k): v for k, v in rounds_log[-1]["line_map"].items()}
                    reconstructed = reconstruct_content(line_ref, prev_lm)
                else:
                    reconstructed = ""
                preview = reconstructed[:80] if reconstructed else "(无内容)"
                p_icon = {"critical":"🔴","useful":"🟡","related":"🟢"}.get(p,"⚪")
                print(f"    {p_icon} [{i}] [{p}] content={line_ref}")
                print(f"          ctx={ctx}")
                print(f"          → {preview}")

            # ── 真实搜索 ──
            t0 = time.time()
            search_result = search_realtime(query)
            search_time = time.time() - t0

            tagged_result, line_map = inject_line_tags(search_result)
            print(f"  📦 原始 {len(search_result)} chars → 标记后 {len(tagged_result)} chars ({search_time:.1f}s)")
            print(f"     共 {max(line_map.keys())+1 if line_map else 0} 行")

            round_entry = {
                "round": round_num,
                "query": query,
                "findings": copy.deepcopy(findings),
                "priority_counts": {"critical":c_count,"useful":u_count,"related":r_count},
                "raw_search_result": search_result,
                "tagged_search_result": tagged_result,
                "line_map": {str(k): v for k, v in line_map.items()},  # JSON safe
                "search_result_len": len(tagged_result),
                "prompt_tokens": in_t,
                "completion_tokens": out_t,
                "tool_chars_before": tool_chars,
                "compressed_saved_chars": saved_chars_this,
            }
            rounds_log.append(round_entry)

            asst_msg = {
                "role": "assistant", "content": msg.content,
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }]
            }
            model_extra = getattr(msg, "model_extra", None) or {}
            if model_extra.get("reasoning_content"):
                asst_msg["reasoning_content"] = model_extra["reasoning_content"]
            messages.append(asst_msg)

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tagged_result})
            print(f"  ✅ 注入完成 ({len(messages)} 条消息)")

    # ══════════════════════════
    # 汇总
    # ══════════════════════════

    total_c = sum(e["priority_counts"]["critical"] for e in rounds_log)
    total_u = sum(e["priority_counts"]["useful"] for e in rounds_log)
    total_r = sum(e["priority_counts"]["related"] for e in rounds_log)
    total_f = total_c + total_u + total_r

    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  Tool Call 轮次: {len(rounds_log)}")
    print(f"  最终回答: {'有 ✅' if final_answer else '无'} ({len(final_answer or '')} chars)")
    print(f"  总引用: {total_f} (c:{total_c} u:{total_u} r:{total_r})")
    print(f"  总消耗: {total_prompt_tokens} in + {total_completion_tokens} out tokens")
    print(f"  压缩节省: {total_saved_chars} chars")

    output = {
        "test_name": "experiment",
        "prompts_version": "v1.3",
        "model": DEFAULT_MODEL,
        "user_query": USER_QUERY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rounds": len(rounds_log),
        "has_final_answer": bool(final_answer),
        "final_answer": final_answer,
        "final_answer_chars": len(final_answer or ""),
        "total_findings": total_f,
        "priority_summary": {"critical": total_c, "useful": total_u, "related": total_r},
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_saved_chars": total_saved_chars,
        "rounds": rounds_log,
    }

    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📝 已保存: {SAVE_PATH}")

if __name__ == "__main__":
    main()
