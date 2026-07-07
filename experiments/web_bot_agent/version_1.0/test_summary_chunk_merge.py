"""
长文本 Summary 多块测试：
1. 分块 → 每块 LLM 生成概括/摘要/要点（提示是第几部分）
2. 合并：各块客观概括 → LLM 统一概括
3. 硬合并：各块相关摘要 + 核心要点
"""
import os, time, asyncio, httpx

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "summary_chunk_test")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 读取 prompt 模板
with open(os.path.join(PROMPT_DIR, "summary_chunk.txt"), encoding='utf-8') as f:
    CHUNK_TEMPLATE = f.read()
with open(os.path.join(PROMPT_DIR, "summary_merge.txt"), encoding='utf-8') as f:
    MERGE_TEMPLATE = f.read()


async def call_llm(prompt: str, label: str = "") -> str:
    """调用本地 LLM"""
    payload = {
        "model": "glm4:9b-chat-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 8192, "temperature": 0}
    }
    old_http = os.environ.pop('http_proxy', None)
    old_https = os.environ.pop('https_proxy', None)
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post('http://localhost:11434/api/generate', json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        elapsed = time.time() - t0
        print(f'  [{label}] {elapsed:.1f}s | {len(raw)}字')
        return raw
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https


def parse_chunk_output(raw: str) -> dict:
    """解析分块的 LLM 输出"""
    result = {"summary": "", "relevant": "", "key_points": []}
    import re
    obj = re.search(r'【客观概括】\s*\n(.*?)(?=\n\s*【相关摘要】|\Z)', raw, re.DOTALL)
    if obj: result["summary"] = obj.group(1).strip()
    rel = re.search(r'【相关摘要】\s*\n(.*?)(?=\n\s*【核心要点】|\Z)', raw, re.DOTALL)
    if rel: result["relevant"] = rel.group(1).strip()
    kp = re.search(r'【核心要点】\s*\n(.*?)$', raw, re.DOTALL)
    if kp:
        for line in kp.group(1).strip().split('\n'):
            m = re.match(r'^\d+[.、．]\s*(.*)', line.strip())
            if m:
                pt = m.group(1).strip()
                if pt: result["key_points"].append(pt)
    return result


def parse_merge_output(raw: str) -> str:
    """解析合并输出，返回统一概括"""
    import re
    m = re.search(r'【统一概括】\s*\n(.*?)$', raw, re.DOTALL)
    return m.group(1).strip() if m else raw


async def main():
    # 读长文本
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    query = "信创产业 国产替代 2025"
    keyword = "信创产业生态"

    print(f'原文: {len(paragraphs)}段, {sum(len(p) for p in paragraphs)}字')
    print()

    # ============================================================
    # Step 1: 分块
    # ============================================================
    from core import split_paragraphs
    parts = split_paragraphs(paragraphs)
    total = len(parts)
    print(f'分块: {total}块')
    for pi, part in enumerate(parts, 1):
        pos = "开头" if pi == 1 else ("结尾" if pi == total else "中间")
        print(f'  块{pi}: {len(part)}段, {sum(len(p) for p in part)}字 ({pos})')
    print()

    # 保存拆分后的原文
    with open(os.path.join(RESULTS_DIR, "01_chunks.md"), 'w', encoding='utf-8') as f:
        f.write(f'# 分块结果\n\n')
        f.write(f'原文: {len(paragraphs)}段, {sum(len(p) for p in paragraphs)}字\n\n')
        for pi, part in enumerate(parts, 1):
            pos = "开头" if pi == 1 else ("结尾" if pi == total else "中间")
            f.write(f'## 块{pi} ({pos}, {len(part)}段)\n\n')
            for i, p in enumerate(part, 1):
                f.write(f'[P{i}] {p}\n\n')

    # ============================================================
    # Step 2: 每块送入 LLM
    # ============================================================
    chunk_results = []
    chunk_raws = []

    for pi, part in enumerate(parts, 1):
        pos = "开头" if pi == 1 else ("结尾" if pi == total else "中间")
        body_text = '\n\n'.join(part)
        prompt = CHUNK_TEMPLATE.format(
            part=pi, total=total, position=pos,
            query=query, keyword=keyword, body=body_text
        )

        # 保存每块的 prompt
        with open(os.path.join(RESULTS_DIR, f"02_chunk{pi}_prompt.md"), 'w', encoding='utf-8') as f:
            f.write(f'# 块{pi} Prompt ({pos}, 共{total}块)\n\n')
            f.write(f'**Prompt 字数**: {len(prompt)}\n\n')
            f.write('```\n')
            f.write(prompt)
            f.write('\n```\n')

        print(f'--- 块{pi} ({pos}) ---')
        print(f'Prompt: {len(prompt)}字')
        raw = await call_llm(prompt, label=f"块{pi}")
        chunk_raws.append(raw)

        # 保存每块的 LLM 输出
        with open(os.path.join(RESULTS_DIR, f"03_chunk{pi}_output.md"), 'w', encoding='utf-8') as f:
            f.write(f'# 块{pi} LLM 输出 ({pos})\n\n')
            f.write(f'```\n')
            f.write(raw)
            f.write('\n```\n')

        parsed = parse_chunk_output(raw)
        chunk_results.append(parsed)
        print(f'  客观概括: {parsed["summary"][:60]}...' if len(parsed["summary"]) > 60 else f'  客观概括: {parsed["summary"]}')
        print(f'  相关摘要: {parsed["relevant"][:60]}...' if len(parsed["relevant"]) > 60 else f'  相关摘要: {parsed["relevant"]}')
        print(f'  要点: {len(parsed["key_points"])}个')
        for kp in parsed["key_points"]:
            print(f'    → {kp}')
        print()

    # ============================================================
    # Step 3: 合并客观概括 → LLM 统一概括
    # ============================================================
    print('--- 合并阶段 ---')
    chunk_summaries_text = ''
    for pi, cr in enumerate(chunk_results, 1):
        chunk_summaries_text += f'【第{pi}部分概括】\n{cr["summary"]}\n\n'

    merge_prompt = MERGE_TEMPLATE.format(
        query=query, keyword=keyword, chunk_summaries=chunk_summaries_text
    )

    with open(os.path.join(RESULTS_DIR, "04_merge_prompt.md"), 'w', encoding='utf-8') as f:
        f.write(f'# 合并 Prompt\n\n')
        f.write(f'**Prompt 字数**: {len(merge_prompt)}\n\n')
        f.write('```\n')
        f.write(merge_prompt)
        f.write('\n```\n')

    print(f'合并 Prompt: {len(merge_prompt)}字')
    merge_raw = await call_llm(merge_prompt, label="合并")
    unified_summary = parse_merge_output(merge_raw)

    with open(os.path.join(RESULTS_DIR, "05_merge_output.md"), 'w', encoding='utf-8') as f:
        f.write(f'# 合并 LLM 输出\n\n')
        f.write(f'```\n')
        f.write(merge_raw)
        f.write('\n```\n')

    print(f'统一概括: {unified_summary[:80]}...' if len(unified_summary) > 80 else f'统一概括: {unified_summary}')

    # ============================================================
    # Step 4: 硬合并摘要 + 要点
    # ============================================================
    all_relevant = []
    all_key_points = []
    for cr in chunk_results:
        if cr["relevant"] and cr["relevant"] not in all_relevant:
            all_relevant.append(cr["relevant"])
        for kp in cr["key_points"]:
            if kp not in all_key_points:
                all_key_points.append(kp)

    # ============================================================
    # Step 5: 输出最终结果
    # ============================================================
    print()
    print('=' * 50)
    print('最终输出')
    print('=' * 50)
    print(f'\n【统一概括】\n{unified_summary}')
    print(f'\n【相关摘要】（硬合并, {len(all_relevant)}段）')
    for i, rel in enumerate(all_relevant, 1):
        print(f'\n--- 第{i}段 ---\n{rel}')
    print(f'\n【核心要点】（硬合并, {len(all_key_points)}个）')
    for i, kp in enumerate(all_key_points, 1):
        print(f'  {i}. {kp}')

    # 保存最终结果
    with open(os.path.join(RESULTS_DIR, "06_final_result.md"), 'w', encoding='utf-8') as f:
        f.write('# Summary 分块合并最终结果\n\n')
        f.write(f'query: {query}\n')
        f.write(f'keyword: {keyword}\n\n')
        f.write(f'## 统一概括\n\n{unified_summary}\n\n')
        f.write(f'## 相关摘要（{len(all_relevant)}段）\n\n')
        for i, rel in enumerate(all_relevant, 1):
            f.write(f'### 第{i}段\n\n{rel}\n\n')
        f.write(f'## 核心要点（{len(all_key_points)}个）\n\n')
        for i, kp in enumerate(all_key_points, 1):
            f.write(f'{i}. {kp}\n')

    print(f'\n✅ 所有文件已保存到: {RESULTS_DIR}/')

if __name__ == '__main__':
    asyncio.run(main())
