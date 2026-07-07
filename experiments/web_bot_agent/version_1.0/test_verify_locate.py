"""验证：要点与 LLM 定位到的原文是否匹配"""
import os, asyncio
from core import split_paragraphs, build_point_locate_prompt, parse_point_locate_output, _call_llm

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "locate_verify")
os.makedirs(RESULTS_DIR, exist_ok=True)

async def main():
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    chunks = split_paragraphs(paragraphs)

    key_points = [
        "信创产业规模快速增长，预计2025年将突破2.2万亿元。",
        "国产化替代面临挑战，尤其在高端芯片和工业软件领域。",
        "报告基于对厂商、用户和开发者的调研数据进行分析。",
        "信创产业链已形成完整体系，呈现区域集聚特征。",
        "各核心领域的国产化替代率稳步提升，但生态建设仍需加强。",
        "信创产业在核心网设备、基站设备、云平台和运营支撑系统等领域实现较高替代率。",
        "开发者规模持续壮大，年轻开发者占比高，一线城市集中。",
        "国产开发工具链逐步完善，但高端工具与国际领先产品仍有差距。",
        "信创生态建设面临技术瓶颈、生态挑战和市场挑战。",
        "预计2025年信创市场规模将达2.2万亿元，2030年有望突破5万亿元。",
    ]
    kp_chunk_map = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    chunk_kp_indices = {0: [0,1,2,3,4], 1: [5,6,7,8,9]}

    rows = []

    for i, kp in enumerate(key_points):
        ci = kp_chunk_map[i]
        chunk = chunks[ci]
        pos = "开头" if ci == 0 else "结尾"

        # 只传本块涉及的要点作为上下文
        kp_in_chunk = [key_points[j] for j in chunk_kp_indices[ci]]
        local_idx = chunk_kp_indices[ci].index(i) + 1
        prompt = build_point_locate_prompt(chunk, kp, all_key_points=kp_in_chunk, target_index=local_idx)

        raw = await _call_llm(prompt)
        paras = parse_point_locate_output(raw)
        valid = [p for p in paras if 1 <= p <= len(chunk)]
        ok = bool(valid)

        if ok:
            found_text = '\n\n'.join(chunk[p-1] for p in valid)
            para_str = f"P{'-'.join(str(p) for p in valid)}" if len(valid) > 1 else f"P{valid[0]}"
        else:
            found_text = "（未找到）"
            para_str = "—"

        rows.append((i+1, kp, ci+1, pos, para_str, found_text, raw.strip(), ok))

    md_lines = ["# 要点与原文对比验证\n"]
    md_lines.append(f"验证文章: t_article_8000.txt | 分 {len(chunks)} 块 | 共 {len(key_points)} 个要点\n")

    found_count = 0
    for i, kp, ci, pos, para_str, found_text, raw_out, ok in rows:
        if ok:
            found_count += 1
        md_lines.append("---")
        md_lines.append(f"## 要点{i}: {kp}\n")
        md_lines.append(f"| 项目 | 值 |")
        md_lines.append(f"|---|---|")
        md_lines.append(f"| 所属块 | 块{ci}（{pos}） |")
        md_lines.append(f"| LLM定位 | {para_str} |")
        md_lines.append(f"| LLM原始输出 | `{raw_out}` |")
        md_lines.append(f"| 匹配原文 | {found_text} |")
        md_lines.append("")
        if ok:
            kws = [w for w in ["信创", "芯片", "开发", "替代", "产业", "市场", "生态", "人才", "工具"] if w in kp]
            match_score = sum(1 for kw in kws if kw in found_text) if kws else 1
            md_lines.append(f"✅ 匹配（关键词覆盖率 {match_score}/{len(kws)}）" if kws else "✅ 匹配")
        else:
            md_lines.append("❌ 未定位到段落")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("## 总结\n")
    md_lines.append(f"- 成功定位: {found_count}/{len(key_points)}")
    md_lines.append(f"- 未定位: {len(key_points) - found_count}/{len(key_points)}")

    report_path = os.path.join(RESULTS_DIR, "locate_verify_report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    print(f"报告已保存: {report_path}")
    print(f"成功定位: {found_count}/{len(key_points)}")

if __name__ == '__main__':
    asyncio.run(main())
