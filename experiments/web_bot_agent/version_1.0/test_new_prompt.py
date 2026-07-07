"""验证：新 prompt + 新 parse_grouping + 新 pipeline"""
import json, os, time, re, httpx
from core import build_grouping_prompt, parse_grouping, run_search_pipeline

# ===== 1. 验证 build_grouping_prompt + parse_grouping =====
print("=" * 60)
print("1. 验证 build_grouping_prompt + parse_grouping")
print("=" * 60)

with open('test_article_光刻机.txt', 'r', encoding='utf-8') as f:
    body = f.read()
paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

prompt = build_grouping_prompt(paragraphs, max_groups=5)
print(f'段落数: {len(paragraphs)}')
print(f'Prompt 长度: {len(prompt)} 字')

# 验证 Pn 是否是动态的
import re
last_p_match = re.search(r'\[P(\d+)\]\]', prompt[::-1])  # 从末尾找最后一个 [Pn]
print(f'Prompt 中最后引用的段落号: [P{len(paragraphs)}]')
assert f'[P{len(paragraphs)}]' in prompt, "Pn 动态替换失败！"
print('✅ Pn 动态替换正确')

# 送入 GLM4
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
    print(f'推理耗时: {elapsed:.1f}s')
    print(f'输出长度: {len(raw)} 字')
    print()

    # 解析
    groups = parse_grouping(raw)
    print(f'解析出 {len(groups)} 组:')
    total_covered = set()
    for g in groups:
        paras = g.get("paragraphs", list(range(g["start_p"], g["end_p"] + 1)))
        total_covered.update(paras)
        print(f'  组{g["group_id"]}: P{min(paras)}-P{max(paras)} ({len(paras)}段) '
              f'| {g["point"][:30]}... | kw: {g.get("keywords", "")[:20]}')

    missing = sorted(set(range(1, len(paragraphs) + 1)) - total_covered)
    print(f'\n总覆盖: {len(total_covered)}/{len(paragraphs)} 段 | 遗漏: {len(missing)} 段')
    if missing:
        print(f'遗漏段落: {missing}')
    else:
        print('✅ 全部覆盖')

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https

print()
print("=" * 60)
print("2. 验证 parse_paragraphs 多种格式")
print("=" * 60)

from core import parse_paragraphs

tests = [
    ("P1-P5", [1, 2, 3, 4, 5]),
    ("P1,P3,P5", [1, 3, 5]),
    ("P1-P3,P7-P9", [1, 2, 3, 7, 8, 9]),
    ("P1", [1]),
    ("P1-P3,P5,P7-P9", [1, 2, 3, 5, 7, 8, 9]),
]
for input_str, expected in tests:
    result = parse_paragraphs(input_str)
    status = "✅" if result == expected else "❌"
    print(f'  {status} parse_paragraphs("{input_str}") → {result}')
