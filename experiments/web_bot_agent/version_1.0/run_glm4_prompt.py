"""读取 prompt_input_光刻机.txt → 送入 GLM4 → 输出到 glm4_output_光刻机.md"""
import json, os, time, re, httpx

with open('prompt_input_光刻机.txt', 'r', encoding='utf-8') as f:
    prompt = f.read()

payload = {
    'model': 'glm4:9b-chat-q4_K_M',
    'prompt': prompt,
    'stream': False,
    'options': {'num_predict': 8192, 'temperature': 0}
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

    # 保存到 md
    content = '# GLM4:9b 分组实验\n\n'
    content += f'**输入**: prompt_input_光刻机.txt\n'
    content += f'**模型**: glm4:9b-chat-q4_K_M\n'
    content += f'**参数**: num_predict=8192, temperature=0.1\n'
    content += f'**耗时**: {elapsed:.1f}s\n\n'
    content += '---\n\n## LLM 输出\n\n```\n'
    content += raw
    content += '\n```\n\n'

    # 覆盖分析
    n_paras = 82
    groups = []
    for m in re.finditer(r'【(组\d+)】段落[：:]\s*P(\d+)(?:\s*[-–]\s*P(\d+))?', raw):
        g = m.group(1)
        start_p = int(m.group(2))
        end_p = int(m.group(3)) if m.group(3) else start_p
        groups.append((g, start_p, end_p))

    if groups:
        covered = set()
        for _, s, e in groups:
            for pn in range(s, e + 1):
                covered.add(pn)
        missing = sorted(set(range(1, n_paras + 1)) - covered)

        content += '## 覆盖统计\n\n'
        content += f'- 分组数: {len(groups)}\n'
        content += f'- 覆盖: P{min(covered)}–P{max(covered)}，共 {len(covered)}/{n_paras} 段\n'
        content += f'- 遗漏: {len(missing)} 段\n'
        if missing:
            content += f'- 遗漏段落: P{", P".join(str(x) for x in missing)}\n'
    else:
        content += '## 覆盖统计\n\n- 分组数: 0（未能解析）\n'

    with open('glm4_output_光刻机.md', 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
    if groups:
        print(f'分组: {len(groups)}组 | 覆盖: {len(covered)}/82段 | 遗漏: {len(missing)}段')
    print(f'已保存: glm4_output_光刻机.md')
    print()
    print(raw)

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
