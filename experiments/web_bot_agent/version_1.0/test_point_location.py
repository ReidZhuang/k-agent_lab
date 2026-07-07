"""测试: LLM 能否根据要点反查原文段落编号"""
import os, time, asyncio, httpx

async def main():
    # 读原文并编号
    with open('t_article_test.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])

    point = "半导体产业链通过各环节协同发力，构建自主产业生态。"

    prompt = f"""下文是已编号的文章段落[P1]至[P{len(paragraphs)}]。下面有一句话是从这篇文章某个段落中概括出来的要点。

任务：找出该要点对应的原文段落编号。可能对应一个或多个连续段落。
输出格式：【段落】Px-Py（或 Px 如果只有一段）

要点：{point}

【正文】
{numbered}"""

    print(f'Prompt: {len(prompt)}字')
    print(f'要点: {point}')
    print()

    payload = {
        "model": "glm4:9b-chat-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024, "temperature": 0}
    }

    old_http = os.environ.pop('http_proxy', None)
    old_https = os.environ.pop('https_proxy', None)
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('http://localhost:11434/api/generate', json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        elapsed = time.time() - t0

        print(f'LLM 输出 ({elapsed:.1f}s):')
        print(raw)
    finally:
        if old_http: os.environ['http_proxy'] = old_http
        if old_https: os.environ['https_proxy'] = old_https

if __name__ == '__main__':
    asyncio.run(main())
