"""走 split 流程逐块送入 GLM4 → 输出 md"""
import json, os, time, re, httpx
from core import split_paragraphs, build_grouping_prompt, parse_grouping, SPLIT_THRESHOLD

with open('test_article_光刻机.txt', 'r', encoding='utf-8') as f:
    body = f.read()
paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

total = sum(len(p) for p in paragraphs)
print(f'总字数: {total} | 阈值: {SPLIT_THRESHOLD}')

parts = split_paragraphs(paragraphs)
print(f'分割成 {len(parts)} 块:')
for i, part in enumerate(parts):
    plen = sum(len(p) for p in part)
    print(f'  块{i+1}: {len(part)}段, {plen}字')
print()

md_lines = []
md_lines.append('# GLM4:9b 分组结果（走 split 流程）')
md_lines.append('')
md_lines.append(f'**输入**: test_article_光刻机.txt（{len(paragraphs)}段，{total}字）')
md_lines.append(f'**分割**: {len(parts)} 块')
md_lines.append('**模型**: glm4:9b-chat-q4_K_M')
md_lines.append('**参数**: num_predict=8192, temperature=0.1')
md_lines.append('')
md_lines.append('---')
md_lines.append('')

old_http = os.environ.pop('http_proxy', None)
old_https = os.environ.pop('https_proxy', None)

try:
    for pi, part in enumerate(parts):
        max_g = 3 if len(parts) > 1 else 5
        prompt = build_grouping_prompt(part, max_groups=max_g)
        payload = {
            'model': 'glm4:9b-chat-q4_K_M',
            'prompt': prompt,
            'stream': False,
            'options': {'num_predict': 8192, 'temperature': 0.1}
        }
        print(f'块{pi+1}/{len(parts)} (max_groups={max_g}, prompt={len(prompt)}字)...')
        t0 = time.time()
        with httpx.Client(timeout=180) as client:
            resp = client.post('http://localhost:11434/api/generate', json=payload)
            result = resp.json()
            raw = result.get('response', '').strip()
        elapsed = time.time() - t0
        print(f'  耗时: {elapsed:.1f}s | 输出: {len(raw)}字')

        groups = parse_grouping(raw)
        md_lines.append(f'## 块 {pi+1}/{len(parts)}（max_groups={max_g}）')
        md_lines.append('')

        if groups:
            covered = set()
            for g in groups:
                for pn in range(g['start_p'], g['end_p'] + 1):
                    covered.add(pn)
            total_paras = len(part)
            missing = total_paras - len(covered)

            md_lines.append(f'覆盖: P{min(covered)}–P{max(covered)}，共 {len(covered)}/{total_paras} 段，遗漏 {missing} 段')
            md_lines.append('')
            md_lines.append('| 组 | 段落范围 | 要点 | 概括 |')
            md_lines.append('|---|---|---|---|')
            for g in groups:
                seg_range = f'P{g["start_p"]}–P{g["end_p"]}' if g['start_p'] != g['end_p'] else f'P{g["start_p"]}'
                md_lines.append(f'| 组{g["group_id"]} | {seg_range} | {g["point"]} | {g["summary"]} |')
        else:
            md_lines.append('（LLM 输出无法解析）')

        md_lines.append('')
        md_lines.append('**LLM 原始输出:**')
        md_lines.append('')
        md_lines.append('```')
        md_lines.append(raw)
        md_lines.append('```')
        md_lines.append('')

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https

with open('glm4_output_split_光刻机.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

print(f'\n输出已保存: glm4_output_split_光刻机.md')
