"""第二阶段：只输入分组结果，不输入原文"""
import json, os, time, re, httpx
from core import parse_grouping

with open('rnd2_7000c.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取第一阶段分组结果（9组）
stage1_match = re.search(r'(【分组】段落：P1-P2.*?)(?=合并步骤)', content, re.DOTALL)
stage1_output = stage1_match.group(1).strip() if stage1_match else ""

# 统计分组数
n_groups = stage1_output.count('【分组】')
print(f'第一阶段: {n_groups}组')
print(f'分组结果长度: {len(stage1_output)}字')

prompt = f"""任务：请将下方【初步分组方案】中的分组进行合并，形成更精简的【最终分组方案】。

概念说明：
- 【分组】：一组相邻段落的集合，包含段落编号范围、要点、概括、关键字四个信息。
- 合并：将两个或多个相邻的分组合并为一个新分组。合并后段落号范围扩大，要点和概括重新整合。

合并步骤：

第1步：找出相邻分组中要点相似或主题重叠的对。
第2步：将要点相似的相邻分组合并。合并时先将段落号范围合并（如"P1-P2"和"P3-P7"合并为"P1-P7"），关键字直接用+拼接。
第3步：对合并后的新分组，根据其段落号范围，整合原有各组的要点形成新的要点，整合原有各组的概括形成新的概括。
第4步：重复第1-3步，直到总组数不超过5组。
第5步：检查【初步分组方案】中所有段落范围是否都被覆盖。如有遗漏的段落编号区间，单独分入一组，要点为"其他"。

要求：
- 只合并相邻的分组，不能跨段合并
- 合并后的段落编号必须连续
- 每个段落只能属于一个组
- 最终总组数不得超过5组
- 不得遗漏任何段落

输出格式（严格按此格式，只输出最终分组方案，不要输出思考过程）：
【分组】段落：【段落信息】
要点： 【要点信息】
概括： 【概括信息】
关键字： 【关键字信息】

【初步分组方案】：
{stage1_output}"""

print(f'第二阶段 Prompt: {len(prompt)}字')
print()

payload = {'model': 'glm4:9b-chat-q4_K_M', 'prompt': prompt, 'stream': False,
           'options': {'num_predict': 8192, 'temperature': 0}}
old_http = os.environ.pop('http_proxy', None)
old_https = os.environ.pop('https_proxy', None)
try:
    t0 = time.time()
    with httpx.Client(timeout=180) as client:
        resp = client.post('http://localhost:11434/api/generate', json=payload)
        raw = resp.json().get('response', '').strip()
    elapsed = time.time() - t0

    groups = parse_grouping(raw)
    # 解析段落范围覆盖
    all_paras = set()
    for g in groups:
        for pn in range(g['start_p'], g['end_p'] + 1):
            all_paras.add(pn)
    # 从第一阶段分组结果提取总段落范围
    first_paras = set()
    all_p = [int(x) for x in re.findall(r'P(\d+)', stage1_output)]
    for start, end in re.findall(r'P(\d+)\s*[-–]\s*P(\d+)', stage1_output):
        for pn in range(int(start), int(end) + 1):
            first_paras.add(pn)
    if not first_paras and all_p:
        first_paras = set(range(min(all_p), max(all_p) + 1))

    missing = sorted(first_paras - all_paras) if first_paras else []

    print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
    print(f'分组: {len(groups)}组 | 遗漏: {len(missing)}段')
    print()
    print(raw)
    if missing:
        print(f'\n遗漏段落: {missing}')
finally:
    if old_http: os.environ['http_proxy'] = old_http
    if old_https: os.environ['https_proxy'] = old_https
