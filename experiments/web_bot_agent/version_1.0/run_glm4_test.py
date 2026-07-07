"""读取 prompt_input_光刻机.txt → 送入 GLM4 → 输出 glm4_output_光刻机.md"""
import json, os, time, re, httpx

with open('prompt_input_光刻机.txt', 'r', encoding='utf-8') as f:
    prompt = f.read()

print(f'输入长度: {len(prompt)} 字')
print('送入 GLM4...')

payload = {
    'model': 'glm4:9b-chat-q4_K_M',
    'prompt': prompt,
    'stream': False,
    'options': {'num_predict': 8192, 'temperature': 0.1}
}

old_http = os.environ.pop('http_proxy', None)
old_https = os.environ.pop('https_proxy', None)
try:
    t0 = time.time()
    with httpx.Client(timeout=180) as client:
        resp = client.post('http://localhost:11434/api/generate', json=payload)
        result = resp.json()
        raw = result.get('response', '').strip()
    elapsed = time.time() - t0
    print(f'耗时: {elapsed:.1f}s')
    print(f'输出长度: {len(raw)} 字')
    print()

    # 解析分组
    groups = []
    for m in re.finditer(
        r'【(组\d+)】段落[：:]\s*P(\d+)(?:\s*[-–]\s*P(\d+))?.*?要点[：:]\s*(.*?)\s*概括[：:]\s*(.*?)(?=\n\n【组|\n*$)',
        raw, re.DOTALL
    ):
        g = m.group(1)
        start_p = int(m.group(2))
        end_p = int(m.group(3)) if m.group(3) else start_p
        groups.append((g, start_p, end_p, m.group(4).strip(), m.group(5).strip()))

    covered = set()
    for _, s, e, _, _ in groups:
        for pn in range(s, e + 1):
            covered.add(pn)

    n_paras = 82
    print(f'分组数: {len(groups)}')
    if groups:
        print(f'覆盖范围: P{min(covered)}-P{max(covered)} ({len(covered)}段)')
    missing = sorted(set(range(1, n_paras + 1)) - covered)
    print(f'遗漏: {len(missing)}段')
    if missing:
        print(f'遗漏段落: {", ".join(str(x) for x in missing[:20])}{"..." if len(missing) > 20 else ""}')
    print()

    # 写入 md
    md_lines = []
    md_lines.append('# GLM4:9b 分组结果')
    md_lines.append('')
    md_lines.append(f'**输入**: prompt_input_光刻机.txt（{n_paras}段，{len(prompt)}字）')
    md_lines.append('**模型**: glm4:9b-chat-q4_K_M')
    md_lines.append('**参数**: num_predict=8192, temperature=0.1')
    md_lines.append(f'**耗时**: {elapsed:.1f}s')
    md_lines.append('')
    md_lines.append('---')
    md_lines.append('')
    md_lines.append('## 分组方案')
    md_lines.append('')
    md_lines.append('| 组 | 段落范围 | 要点 | 概括 |')
    md_lines.append('|---|---|---|---|')

    for g, s, e, pt, sm in groups:
        seg_range = f'P{s}–P{e}' if s != e else f'P{s}'
        md_lines.append(f'| {g} | {seg_range} | {pt} | {sm} |')

    md_lines.append('')
    md_lines.append('## 覆盖统计')
    md_lines.append('')
    md_lines.append(f'- 分组数: {len(groups)}')
    if groups:
        md_lines.append(f'- 覆盖: P{min(covered)}–P{max(covered)}，共 {len(covered)} 段')
    md_lines.append(f'- 遗漏: {len(missing)} 段')
    if missing:
        md_lines.append(f'- 遗漏段落号: {", ".join(str(x) for x in missing)}')

    md_lines.append('')
    md_lines.append('## LLM 原始输出')
    md_lines.append('')
    md_lines.append('```')
    md_lines.append(raw)
    md_lines.append('```')
    md_lines.append('')

    md = '\n'.join(md_lines)

    with open('glm4_output_光刻机.md', 'w', encoding='utf-8') as f:
        f.write(md)

    print(raw)
finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
