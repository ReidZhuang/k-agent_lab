"""测试批量要点定位：同块多点合并一次LLM调用"""
import os, time, asyncio, re
from collections import defaultdict
from core import _call_llm, split_paragraphs

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "batch_locate_test")
os.makedirs(RESULTS_DIR, exist_ok=True)

async def main():
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    chunks = split_paragraphs(paragraphs)

    # 模拟的 key_points（来自 summary_chunk_merge 测试的实际输出）
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
    # 块1产前5个，块2产后5个
    kp_chunk_map = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]

    print(f'文章: {len(paragraphs)}段, 分{len(chunks)}块')
    print(f'要点总数: {len(key_points)}个')
    print()

    scenarios = [
        ("场景A_同块多点", [2, 4, 5]),
        ("场景B_跨块多点", [2, 7, 5]),
    ]

    for scene_name, point_indices in scenarios:
        print(f'=== {scene_name} ===')
        print(f'请求要点: {point_indices}')

        chunk_groups = defaultdict(list)
        for pi in point_indices:
            idx = pi - 1
            ci = kp_chunk_map[idx]
            chunk_groups[ci].append((idx, key_points[idx]))

        print(f'分组: {dict(chunk_groups)}')
        print()

        for chunk_idx, items in chunk_groups.items():
            chunk = chunks[chunk_idx]
            pos = "开头" if chunk_idx == 0 else "结尾"
            safe_name = scene_name.replace(' ', '_').replace(':', '')

            lines = ["下面有几个要点，请判断每个要点对应下方【原文段落】中的哪一段（或哪几段连续段落）。"]
            lines.append("")
            lines.append("要点列表：")
            for orig_idx, kp in items:
                lines.append(f"{orig_idx+1}. {kp}")
            lines.append("")
            lines.append("【原文段落】")
            lines.append('\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(chunk)]))
            lines.append("")
            lines.append("输出要求：每行一个结果，与要点序号一一对应。")
            lines.append("格式：【序号】段落：Px-Py（单段写Px，不在本段写「无」）")
            lines.append("示例：")
            lines.append("【1】段落：P5")
            lines.append("【2】段落：P12-P15")
            prompt = '\n'.join(lines)

            pf = os.path.join(RESULTS_DIR, f"{safe_name}_块{chunk_idx+1}({pos})_prompt.md")
            with open(pf, 'w', encoding='utf-8') as f:
                f.write(f'# {scene_name} — {pos}块 Prompt\n\n')
                f.write(f'要点序号: {[i+1 for i,_ in items]}\n')
                f.write(f'Prompt字数: {len(prompt)}\n')
                f.write(f'块段落数: {len(chunk)}段\n\n')
                f.write('```\n')
                f.write(prompt)
                f.write('\n```\n')
            print(f'  块{chunk_idx+1}({pos}) Prompt: {len(prompt)}字 -> 已保存')

            raw = await _call_llm(prompt)

            of = os.path.join(RESULTS_DIR, f"{safe_name}_块{chunk_idx+1}({pos})_output.md")
            with open(of, 'w', encoding='utf-8') as f:
                f.write(f'# {scene_name} — {pos}块 LLM 输出\n\n')
                f.write('```\n')
                f.write(raw)
                f.write('\n```\n')

            print(f'  LLM 输出 ({len(raw)}字):')
            print(f'    {raw}')
            print()

            for orig_idx, kp in items:
                tag = f"【{orig_idx+1}】"
                m = re.search(re.escape(tag) + r'\s*段落[：:]\s*(.+)', raw)
                if m:
                    print(f'    要点{orig_idx+1}: {m.group(1).strip()}')
                else:
                    print(f'    要点{orig_idx+1}: 未找到')
        print()

    # 汇总
    sf = os.path.join(RESULTS_DIR, "00_汇总.md")
    with open(sf, 'w', encoding='utf-8') as f:
        f.write('# 批量要点定位测试汇总\n\n')
        f.write(f'文章: t_article_8000.txt ({len(paragraphs)}段, {len(chunks)}块)\n\n')
        f.write('## 要点与块的对应关系\n\n')
        for bi in range(len(chunks)):
            pts = [i+1 for i, m in enumerate(kp_chunk_map) if m == bi]
            pos = "开头" if bi == 0 else "结尾"
            f.write(f'- 块{bi+1}（{pos}, {len(chunks[bi])}段）: 要点 {pts}\n')
        f.write('\n## 场景\n\n')
        for scene_name, point_indices in scenarios:
            f.write(f'### {scene_name}\n')
            f.write(f'请求: {point_indices}\n')
            chunk_groups = defaultdict(list)
            for pi in point_indices:
                ci = kp_chunk_map[pi-1]
                chunk_groups[ci].append(pi)
            parts = [f'块{ci}->{len(pts)}个要点' for ci, pts in chunk_groups.items()]
            f.write(f'分组: {", ".join(parts)}\n')
            f.write(f'LLM调用: {len(chunk_groups)}次\n\n')
    print(f'结果已保存到: {RESULTS_DIR}/')

if __name__ == '__main__':
    asyncio.run(main())
