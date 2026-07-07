"""分段总结实验：将长文本分为2篇，分别做逐段总结，再组装"""
import json, os, time, re, httpx

with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
    body = f.read()

# 按段落拆分
paragraphs = [p.strip() for p in re.split(r'\n{2,}', body) if p.strip()]
n = len(paragraphs)
total_chars = sum(len(p) for p in paragraphs)
print(f'原文: {total_chars}字, {n}段')
print()

# 对半切成两篇
mid = n // 2  # 58
part1 = paragraphs[:mid]
part2 = paragraphs[mid:]

PROMPT_TPL = """下文中的[P+数字]是段落编号，比如第一段就是[P1]。请将段落编号后的一段文字写成一句话概括，不要超过20字。输出格式：[P1]:第一段的概括。[P2]:第二段的概括。以此类推。要求：从[P1]至[P{n}]所有的段落都要写概括。如果段落内容是数据，那么就用文字描述数据。

【正文开始】
{numbered}
【正文结束】"""

def call_llm(prompt):
    """调用本地 GLM4:9b"""
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
        with httpx.Client(timeout=300) as client:
            resp = client.post('http://localhost:11434/api/generate', json=payload)
            result = resp.json()
            raw = result.get('response', '').strip()
        elapsed = time.time() - t0
        print(f'  耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
        return raw
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https


def build_prompt(paras):
    """构建带本地编号的 prompt"""
    n_local = len(paras)
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paras)])
    return PROMPT_TPL.replace('{n}', str(n_local)).replace('{numbered}', numbered), n_local


def parse_summaries(raw, offset):
    """解析 [Px]: 摘要 格式，恢复原始段落号"""
    summaries = {}
    for m in re.finditer(r'\[P(\d+)\]\s*[:：]\s*(.+)', raw):
        local_pn = int(m.group(1))
        summary = m.group(2).strip()
        original_pn = local_pn + offset
        summaries[original_pn] = summary
    return summaries


# ======== 第1篇 ========
print(f'=== 第1篇: P1-P{mid} ({len(part1)}段, {sum(len(p) for p in part1)}字) ===')
prompt1, n1 = build_prompt(part1)
print(f'  Prompt: {len(prompt1)}字')
raw1 = call_llm(prompt1)

# ======== 第2篇 ========
print(f'\n=== 第2篇: P{mid+1}-P{n} ({len(part2)}段, {sum(len(p) for p in part2)}字) ===')
prompt2, n2 = build_prompt(part2)
print(f'  Prompt: {len(prompt2)}字')
raw2 = call_llm(prompt2)

# ======== 解析并组装 ========
summaries = {}
summaries.update(parse_summaries(raw1, 0))     # 第1篇: P1-P58 → 不变
summaries.update(parse_summaries(raw2, mid))   # 第2篇: P59-P116 → P(59+58)

# ======== 生成 MD 报告 ========
lines = []
lines.append('# 分段逐段总结结果（两篇分送GLM4再组装）')
lines.append('')
lines.append(f'## 基本信息')
lines.append(f'- **文章**: t_article_8000.txt（信创产业报告）')
lines.append(f'- **总段数**: {n}段')
lines.append(f'- **第1篇**: P1-P{mid}（{len(part1)}段, {sum(len(p) for p in part1)}字, Prompt {len(prompt1)}字）')
lines.append(f'- **第2篇**: P{mid+1}-P{n}（{len(part2)}段, {sum(len(p) for p in part2)}字, Prompt {len(prompt2)}字）')
lines.append(f'- **模型**: GLM4:9b-chat-q4_K_M')
lines.append('')

lines.append('## 逐段总结')
lines.append('')
lines.append('| 段落 | 原文（前50字） | 总结 |')
lines.append('|---|---|---|')

covered = 0
for i, p in enumerate(paragraphs):
    pn = i + 1
    summary = summaries.get(pn, '*未生成*')
    if summary != '*未生成*':
        covered += 1
    preview = p[:50].replace('\n', ' ')
    lines.append(f'| P{pn} | {preview}… | {summary} |')

lines.append('')
lines.append(f'## 统计')
lines.append(f'- **成功总结**: {covered}/{n} 段')
lines.append(f'- **缺失**: {n - covered} 段')
lines.append('')

lines.append('## 原始 LLM 输出')
lines.append('')
lines.append('### 第1篇 LLM 原始输出')
lines.append('')
lines.append('```')
lines.append(raw1)
lines.append('```')
lines.append('')
lines.append('### 第2篇 LLM 原始输出')
lines.append('')
lines.append('```')
lines.append(raw2)
lines.append('```')

md_content = '\n'.join(lines)

output_path = 'split_summary_result.md'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(md_content)

print(f'\n{"="*50}')
print(f'结果已保存到: {output_path}')
print(f'成功总结: {covered}/{n} 段')

# 输出缺失段
missing = [i+1 for i in range(n) if (i+1) not in summaries]
if missing:
    print(f'缺失段落: {missing}')
