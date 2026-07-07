"""
测试：GLM4 一次处理全文82段，大 num_predict
"""
import json, os, time, re, httpx

with open('test_article_光刻机.txt', 'r', encoding='utf-8') as f:
    body = f.read()

paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])

prompt = (
    '任务：将下方【正文】中已编号的段落（[P1]、[P2]...[Pn]）进行分组。\n\n'
    '输出要求：只输出分组方案，不要输出原文。\n\n'
    '分组规则：\n'
    '- 将相邻的、主题相近的段落合并为一组\n'
    '- 全文分成≤5组\n'
    '- 每组内的段落编号必须是连续的\n'
    '- 每组至少包含一个段落\n'
    '- 每个段落只能属于一个组\n'
    '- 所有段落都必须被分配到某个组中，不得遗漏\n\n'
    '输出格式：\n\n'
    '【组1】段落：P1-P3\n要点：xxx\n概括：xxx\n\n'
    '【组2】段落：P4-P7\n要点：xxx\n概括：xxx\n\n'
    '要求：\n'
    '- 所有段落（[P1]到[P82]）都必须被分配到某个组\n\n'
    f'【正文】：\n{numbered}'
)

print(f'段落数: {len(paragraphs)}')
print(f'总字数: {sum(len(p) for p in paragraphs)}')
print(f'Prompt长度: {len(prompt)}字')
print('---')

payload = {
    'model': 'glm4:9b-chat-q4_K_M',
    'prompt': prompt,
    'stream': False,
    'options': {'num_predict': 4096, 'temperature': 0.1}
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
    print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
    print()
    print(raw)
    print()
    print('--- 覆盖检查 ---')
    groups = []
    for m in re.finditer(r'【(组\d+)】段落[：:]\s*P(\d+)(?:\s*[-–]\s*P(\d+))?', raw):
        g = m.group(1)
        start_p = int(m.group(2))
        end_p = int(m.group(3)) if m.group(3) else start_p
        groups.append((g, start_p, end_p))

    covered = set()
    for g, s, e in groups:
        for pn in range(s, e+1):
            covered.add(pn)

    print(f'分组数: {len(groups)}')
    print(f'覆盖范围: P{min(covered)}-P{max(covered)} ({len(covered)}段)')
    missing = sorted(set(range(1, 83)) - covered)
    print(f'遗漏: {len(missing)}段')
    if missing:
        print(f'遗漏段落号: {missing[:30]}{"..." if len(missing) > 30 else ""}')
finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
