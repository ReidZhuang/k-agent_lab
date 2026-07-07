"""测试 summary 模式：验证 prompt 构建 + LLM 调用 + 解析"""
import json, os, time, asyncio, httpx
from core import build_summary_prompt, parse_summary_output, estimate_tokens

async def main():
    # 读测试文章
    with open('t_article_test.txt', 'r', encoding='utf-8') as f:
        body = f.read()

    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    print(f'文章: {len(paragraphs)}段, {sum(len(p) for p in paragraphs)}字')
    print()

    # 构建 summary prompt
    prompt = build_summary_prompt(paragraphs)
    print(f'=== Prompt 长度 ===')
    print(f'总字符: {len(prompt)}')
    print(f'估算token: {estimate_tokens(prompt)}')
    print()

    # 调用 LLM
    payload = {
        "model": "glm4:9b-chat-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 8192,
            "temperature": 0
        }
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
        print(f'=== LLM 输出 ===')
        print(f'耗时: {elapsed:.1f}s | 输出: {len(raw)}字')
        print()
        print(raw)
        print()

        # 解析
        parsed = parse_summary_output(raw)
        print(f'=== 解析结果 ===')
        print(f'摘要: {parsed["summary"][:100]}...' if len(parsed["summary"]) > 100 else f'摘要: {parsed["summary"]}')
        print(f'要点数: {len(parsed["key_points"])}')
        for i, p in enumerate(parsed["key_points"], 1):
            print(f'  要点{i}: {p}')
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https

if __name__ == '__main__':
    asyncio.run(main())
