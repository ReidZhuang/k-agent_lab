"""分割成~4000字/块，每块用新 prompt 模板，保留全局 P 编号"""
import json, os, time, re, httpx
from core import parse_grouping

# ===== 读取文章 =====
with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
    body = f.read()
paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
total_chars = sum(len(p) for p in paragraphs)
print(f'全文: {len(paragraphs)}段, {total_chars}字')

# ===== 以 4000 字为参考分块 =====
def split_at_4000(paras, target=4000):
    """按字数分割，每块接近 target 字，不切段落"""
    parts = []
    current = []
    current_len = 0
    para_idx = 0
    for p in paras:
        current.append(p)
        current_len += len(p)
        para_idx += 1
        # 达到目标字数 + 至少3段 + 剩余至少3段
        if current_len >= target and len(current) >= 3 and (len(paras) - para_idx) >= 3:
            parts.append(current)
            current = []
            current_len = 0
    if current:
        parts.append(current)
    return parts

parts = split_at_4000(paragraphs, 4000)
print(f'分割: {len(parts)} 块')
for i, part in enumerate(parts):
    plen = sum(len(p) for p in part)
    # 全局起始段落号
    start_idx = sum(len(p) for p in paragraphs[:sum(len(p) for p in paragraphs[:sum(len(q) for q in parts[:i])])])
    print(f'  块{i+1}: {len(part)}段, {plen}字')

# ===== prompt 模板 =====
PROMPT_TEMPLATE = """任务：【正文开始】和【正文结束】之间的文字内容是【正文】文本内容，其内容的段落已按照[P1]、[P2]...[P{total_n}]进行编号，现在需要对段落进行分组，并对分组覆盖的【正文】内容进行总结。
输出要求：只输出分组方案，不要输出原文。

分组步骤：

1. 阅读【正文】所有内容，即[P1]至[P{total_n}]的所有段落。注意，[P{total_n}]代表全文最后一个段落的编号。将全文概括成3至5个要点（每个要点是文章的一个核心话题，长度为15-50字），每一个要点就是一个【分组】。对应每个要点整理出了3至5个【分组】，每一个【分组】的【要点信息】就是刚刚归纳的要点。
2. 将在上一步中概括的要点逐一整理其覆盖正文中的段落，并把段落编号记录在这个要点分组下，这些段落编号就是【段落信息】，每一个【分组】都有一个【段落信息】。
3. 对每一个【分组】覆盖的【段落信息】在【正文】中的内容用几句话（50-100字）进行内容概括。这样你就得到了【概括信息】，每一个分组都有一个【概括信息】。
4. 在每一个【分组】覆盖的【段落信息】在【正文】中的内容中寻找内容主题中的关键字，这个关键字应该是【分组】的【要点信息】和【概括信息】的主角。关键字可以有多个，这些关键字就是【关键字信息】，每一个分组都有一个【关键字信息】。【关键字信息】不要超过10个字。
5. 检查【正文】中的[P1]至[P{total_n}]所有段落是否都包含在了【分组】中，注意，[P{total_n}]代表全文最后一个段落的编号。没有归纳入任何【分组】的段落，将其单独分入一组，其【要点信息】为"其他"。【概括信息】根据其覆盖的【正文】段落信息总结，其【段落信息】就是其段落编号。

分组规则和注意事项：
- 分组步骤1中对【正文】所有内容进行要点总结时，需要把总结的要点数量控制在6个以下。
- 请尽量将相邻的、主题相近的段落合并为一组。
- 每组段落编号尽量连续。
- 每组至少包含一个段落，不得引用不存在的段落编号。
- 每个段落只能属于一个组，不得重复分配。
- 分组步骤4结束后，每个段落（[P1]、[P2]...[P{total_n}]）都必须被分配到某个组中，不得遗漏。
- 全文只有[P1]一个段落时，只分1组。
- 只有【正文开始】和【正文结束】之间的文字内容才属于需要分组处理的【正文】内容，其余文字内容是提示词。

输出格式（严格按此格式，不要输出其他内容）：
【分组】段落：【段落信息】
要点： 【要点信息】
概括： 【概括信息】
关键字： 【关键字信息】

字段说明：
- 【段落信息】：该组包含的段落编号范围，用短横线连接起止编号，用逗号隔开不同段落编号
- 【要点信息】：该组覆盖【正文】内容的核心话题（15-50字），多个主题描述用" + "连接
- 【概括信息】：该组覆盖【正文】内容的关键信息浓缩（50-100字），包含具体数据或结论
- 【关键字信息】： 该组覆盖【正文】内容中重点介绍对象。该组的【要点信息】和【概括信息】中的主角。可以包含多个关键字。不同的关键字用+号连接。总字数不要超过10个字

范例：
【组1】段落：P1-P3
要点：xxx
概括：xxx
关键字： 国产化需求+国产替代

【组2】段落：P4-P7
要点：xxx
概括：xxx
关键字： 海外技术限制+产业链整合

【正文开始】
{numbered}
【正文结束】"""

def build_prompt_for_part(part_paras, global_start, total_n):
    """为分块构建 prompt，保留全局编号"""
    numbered = '\n\n'.join([f'[P{global_start + i}] {p}' for i, p in enumerate(part_paras)])
    return PROMPT_TEMPLATE.format(total_n=total_n, numbered=numbered)

total_n = len(paragraphs)

# ===== 逐块送入 LLM =====
old_http = os.environ.pop('http_proxy', None)
old_https = os.environ.pop('https_proxy', None)

all_results = []
para_offset = 0

for pi, part in enumerate(parts):
    global_start = para_offset + 1  # 全局起始段落号
    prompt = build_prompt_for_part(part, global_start, total_n)

    print(f'\n{"="*60}')
    print(f'块{pi+1}/{len(parts)}: 全局P{global_start}-P{global_start+len(part)-1} ({len(part)}段)')
    print(f'Prompt: {len(prompt)}字')

    payload = {
        'model': 'glm4:9b-chat-q4_K_M',
        'prompt': prompt,
        'stream': False,
        'options': {'num_predict': 8192, 'temperature': 0}
    }

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
        all_results.append((pi, raw, global_start, len(part)))
    except Exception as e:
        print(f'错误: {e}')
        all_results.append((pi, f'[错误] {e}', global_start, len(part)))

    para_offset += len(part)

# ===== 汇总覆盖情况 =====
print(f'\n{"="*60}')
print('汇总覆盖情况')
print('='*60)

all_covered = set()
for pi, raw, gs, plen in all_results:
    groups = parse_grouping(raw)
    for g in groups:
        for pn in range(g['start_p'], g['end_p'] + 1):
            all_covered.add(pn)

total = len(paragraphs)
missing = sorted(set(range(1, total + 1)) - all_covered)
print(f'总覆盖: {len(all_covered)}/{total} 段')
print(f'遗漏: {len(missing)} 段')
if missing:
    print(f'遗漏段落: P{", P".join(str(x) for x in missing[:30])}{"..." if len(missing) > 30 else ""}')

if old_http: os.environ['http_proxy'] = old_http
if old_https: os.environ['https_proxy'] = old_https
