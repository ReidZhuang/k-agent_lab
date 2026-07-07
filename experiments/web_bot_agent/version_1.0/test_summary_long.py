"""测试 summary 模式 + 长文本（t_article_8000.txt, 8562字, 116段）"""
import os, time, asyncio, httpx, json
from core import build_summary_prompt, parse_summary_output

async def main():
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    query = "信创产业 国产替代 2025"
    keyword = "信创产业生态"

    print(f'原文: {len(paragraphs)}段, {sum(len(p) for p in paragraphs)}字')
    print(f'query: {query}')
    print(f'keyword: {keyword}')
    print()

    # 单块：整篇送入
    print('=== 单块测试（整篇送入）===')
    prompt = build_summary_prompt(paragraphs, query=query, keyword=keyword)
    print(f'Prompt: {len(prompt)}字')
    print()

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
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post('http://localhost:11434/api/generate', json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        elapsed = time.time() - t0

        print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
        print()
        print(raw)
        print()

        parsed = parse_summary_output(raw)
        print(f'=== 解析结果 ===')
        print(f'--- 客观概括 ---')
        print(parsed["summary_objective"])
        print(f'\n--- 相关摘要 ---')
        print(parsed["summary_relevant"])
        print(f'\n--- 核心要点 ({len(parsed["key_points"])}个) ---')
        for i, kp in enumerate(parsed["key_points"], 1):
            print(f'  {i}. {kp}')
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https

if __name__ == '__main__':
    asyncio.run(main())
