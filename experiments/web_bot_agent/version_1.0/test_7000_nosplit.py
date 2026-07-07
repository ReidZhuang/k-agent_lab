"""测试用户提供的 7000+ 字文章，不分块"""
import json, os, time, re, httpx
from core import build_grouping_prompt, parse_grouping

with open('7000c.txt', 'r', encoding='utf-8') as f:
    body = f.read()

paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
total = sum(len(p) for p in paragraphs)
print(f'正文: {total}字, {len(paragraphs)}段')

prompt = build_grouping_prompt(paragraphs, max_groups=5)
print(f'Prompt: {len(prompt)}字, 最后段落号: [P{len(paragraphs)}]')
print()

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
    print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
    print()
    print(raw)
    print()

    # 解析
    groups = parse_grouping(raw)
    if groups:
        covered = set()
        for g in groups:
            for pn in range(g['start_p'], g['end_p'] + 1):
                covered.add(pn)
        missing = sorted(set(range(1, len(paragraphs) + 1)) - covered)
        print(f'--- 统计 ---')
        print(f'分组: {len(groups)}组')
        print(f'覆盖: {len(covered)}/{len(paragraphs)}段')
        print(f'遗漏: {len(missing)}段')
        if missing:
            print(f'遗漏段落: {missing[:30]}{"..." if len(missing) > 30 else ""}')
    else:
        print('❌ 未解析到分组')

    # 保存 md
    md = "# 不分块测试：7000字级文章\n\n"
    md += "## 基本信息\n\n"
    md += f"- **字数**: {total}字\n"
    md += f"- **段落**: {len(paragraphs)}段\n"
    md += f"- **Prompt**: {len(prompt)}字\n"
    md += f"- **模型**: glm4:9b-chat-q4_K_M\n"
    md += f"- **耗时**: {elapsed:.1f}s\n\n"
    md += "---\n\n## 文章原文\n\n"
    md += body
    md += "\n\n---\n\n## LLM 输出\n\n```\n"
    md += raw
    md += "\n```\n\n"
    md += "## 统计\n\n"
    md += f"- 分组数: {len(groups)}\n"
    md += f"- 覆盖: {len(covered)}/{len(paragraphs)} 段\n"
    md += f"- 遗漏: {len(missing)} 段\n"
    if missing:
        md += f"- 遗漏段落: {missing}\n"
    if groups:
        md += "\n## 分组明细\n\n| 组 | 段落范围 | 段数 | 要点 | 关键字 |\n|---|---|---|---|---|\n"
        for g in groups:
            paras = g.get('paragraphs', list(range(g['start_p'], g['end_p'] + 1)))
            seg_range = f"P{g['start_p']}-P{g['end_p']}" if g['start_p'] != g['end_p'] else f"P{g['start_p']}"
            md += f"| {g['group_id']} | {seg_range} | {len(paras)}段 | {g['point'][:45]} | {g.get('keywords', '')[:20]} |\n"

    with open('test_7000_nosplit_result.md', 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'\n已保存: test_7000_nosplit_result.md')

finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
