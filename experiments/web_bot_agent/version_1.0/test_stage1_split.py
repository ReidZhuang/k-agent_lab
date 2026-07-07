"""Stage 1 实验：只分组，不提取要点/概括/关键字"""
import json, os, time, re, httpx

with open('prompt_stage1_draft.txt', 'r', encoding='utf-8') as f:
    template = f.read()

with open('t_article_test.txt', 'r', encoding='utf-8') as f:
    body = f.read()

paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
total = sum(len(p) for p in paragraphs)
n = len(paragraphs)

print(f'原文: {total}字, {n}段')
print(f'分组范围: 3001-6000字 → 建议5组, 最大8组')
print()

# 构建 numbered 正文
numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
prompt = template.replace('{n}', str(n))
prompt += f'\n\n【正文开始】\n{numbered}\n【正文结束】'

print(f'Prompt: {len(prompt)}字')
print()

# 送入 LLM
payload = {
    'model': 'glm4:9b-chat-q4_K_M',
    'prompt': prompt,
    'stream': False,
    'options': {'num_predict': 2048, 'temperature': 0}
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

    # 解析分组
    groups = []
    for m in re.finditer(r'【分组】段落[：:]\s*P(\d+)\s*[-–]\s*P(\d+)', raw):
        groups.append((int(m.group(1)), int(m.group(2))))
    for m in re.finditer(r'【分组】段落[：:]\s*P(\d+)(?!\s*[-–])', raw):
        pn = int(m.group(1))
        if not any(pn >= s and pn <= e for s, e in groups):
            groups.append((pn, pn))

    if groups:
        covered = set()
        for s, e in groups:
            for pn in range(s, e + 1):
                covered.add(pn)
        missing = sorted(set(range(1, n + 1)) - covered)
        print(f'分组数: {len(groups)}组')
        print(f'覆盖: {len(covered)}/{n}段 | 遗漏: {len(missing)}段')
        print()
        for gid, (s, e) in enumerate(groups, 1):
            sr = f'P{s}-P{e}' if s != e else f'P{s}'
            print(f'  组{gid}: {sr} ({e-s+1}段)')

    print()
    print('=== LLM 原始输出 ===')
    print(raw)

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
