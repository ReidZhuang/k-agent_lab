"""测试新版 summary 模式：带query/keyword的提示词 + 新解析"""
import os, time, asyncio, httpx
from core import build_summary_prompt, parse_summary_output

async def main():
    with open('t_article_test.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    # 模拟 API 传参
    query = "国产芯片 替代 2025"
    keyword = "半导体国产替代"

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
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post('http://localhost:11434/api/generate', json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        elapsed = time.time() - t0

        print(f'=== LLM 原始输出 === ({elapsed:.1f}s, {len(raw)}字)')
        print(raw)
        print()

        parsed = parse_summary_output(raw)
        print(f'=== 解析结果 ===')
        print(f'\n--- 客观概括 ---')
        print(parsed["summary_objective"][:200])
        print(f'\n--- 相关摘要 ---')
        print(parsed["summary_relevant"][:200])
        print(f'\n--- 核心要点 ({len(parsed["key_points"])}个) ---')
        for i, kp in enumerate(parsed["key_points"], 1):
            print(f'  {i}. {kp}')
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https

if __name__ == '__main__':
    asyncio.run(main())
