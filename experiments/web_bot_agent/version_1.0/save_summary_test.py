"""保存 summary 模式测试的 input/output 到 md 文件"""
import os, time, asyncio, httpx
from core import build_summary_prompt, parse_summary_output

async def main():
    # 读文章
    with open('t_article_test.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    # ---- 1. 保存原文 ----
    with open('intro/summary_article_input.md', 'w', encoding='utf-8') as f:
        f.write('# Summary 模式输入原文（t_article_test.txt）\n\n')
        f.write(f'- 段落: {len(paragraphs)}段\n')
        f.write(f'- 总字数: {sum(len(p) for p in paragraphs)}字\n\n')
        for i, p in enumerate(paragraphs, 1):
            f.write(f'[P{i}] ')
            f.write(p)
            f.write('\n\n')
    print('✅ 原文已保存: intro/summary_article_input.md')

    # ---- 2. 保存 Prompt ----
    prompt = build_summary_prompt(paragraphs)
    with open('intro/summary_prompt_input.md', 'w', encoding='utf-8') as f:
        f.write('# Summary 模式 Prompt（t_article_test.txt）\n\n')
        f.write('## 基本信息\n')
        f.write(f'- 文章: t_article_test.txt（半导体国产替代）\n')
        f.write(f'- 段落: {len(paragraphs)}段\n')
        f.write(f'- 正文字数: {sum(len(p) for p in paragraphs)}字\n')
        f.write(f'- Prompt总字数: {len(prompt)}字\n\n')
        f.write('## Prompt 全文\n\n')
        f.write('```\n')
        f.write(prompt)
        f.write('\n```\n')
    print('✅ Prompt 已保存: intro/summary_prompt_input.md')

    # ---- 3. 调用 LLM 并保存输出 ----
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

        parsed = parse_summary_output(raw)

        with open('intro/summary_llm_output.md', 'w', encoding='utf-8') as f:
            f.write('# Summary 模式 LLM 输出（t_article_test.txt）\n\n')
            f.write('## 基本信息\n')
            f.write(f'- 模型: glm4:9b-chat-q4_K_M\n')
            f.write(f'- 耗时: {elapsed:.1f}s\n')
            f.write(f'- 输出字数: {len(raw)}字\n\n')
            f.write('## 解析结果\n\n')
            f.write(f'**摘要**: {parsed["summary"]}\n\n')
            f.write(f'**要点**（{len(parsed["key_points"])}个）:\n\n')
            for i, kp in enumerate(parsed["key_points"], 1):
                f.write(f'{i}. {kp}\n')
            f.write('\n---\n\n')
            f.write('## LLM 原始输出\n\n')
            f.write('```\n')
            f.write(raw)
            f.write('\n```\n')
        print('✅ LLM 输出已保存: intro/summary_llm_output.md')
        print(f'   摘要: {parsed["summary"][:60]}...')
        print(f'   要点: {len(parsed["key_points"])}个')
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https

if __name__ == '__main__':
    asyncio.run(main())
