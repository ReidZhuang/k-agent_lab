"""验证全流程：新 prompt + 全量输入 + 新 parser"""
import json, time, re, httpx, os
from core import build_grouping_prompt, parse_grouping, parse_paragraphs, split_paragraphs

with open('test_article_光刻机.txt', 'r', encoding='utf-8') as f:
    body = f.read()
paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

# split_paragraphs 返回全文
parts = split_paragraphs(paragraphs)
assert len(parts) == 1
assert len(parts[0]) == len(paragraphs)
print(f'✅ split_paragraphs: 1 块, {len(parts[0])} 段')

# build prompt
prompt = build_grouping_prompt(paragraphs)
print(f'✅ build_grouping_prompt: {len(prompt)} 字, Pn=[P{len(paragraphs)}]')

# 送入 LLM
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
    print(f'✅ LLM 推理: {elapsed:.1f}s, 输出 {len(raw)} 字')

    # 解析
    groups = parse_grouping(raw)
    covered = set()
    for g in groups:
        for pn in range(g['start_p'], g['end_p'] + 1):
            covered.add(pn)

    missing = sorted(set(range(1, len(paragraphs) + 1)) - covered)

    print(f'  分组数: {len(groups)}')
    print(f'  覆盖: {len(covered)}/{len(paragraphs)} 段')
    print(f'  遗漏: {len(missing)} 段')
    if missing:
        print(f'  遗漏段落: {missing}')
    print()

    # 输出 JSON 示例
    print('=== 输出 JSON 示例（前2组）===')
    for g in groups[:2]:
        item = {
            'id': f's{g["group_id"]}',
            'point': g['point'],
            'summary': g['summary'],
            'keywords': g.get('keywords', ''),
            'charnum': sum(len(paragraphs[p-1]) for p in g.get('paragraphs', range(g['start_p'], g['end_p']+1)))
        }
        print(json.dumps(item, ensure_ascii=False, indent=2))
        print()

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
