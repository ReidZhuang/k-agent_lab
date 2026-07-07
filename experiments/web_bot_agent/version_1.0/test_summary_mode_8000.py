"""测试 summary 模式 + 长文本（8000字，~116段）"""
import os, time, asyncio, httpx
from core import build_summary_prompt, parse_summary_output, estimate_tokens, split_paragraphs

async def main():
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()

    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    total_chars = sum(len(p) for p in paragraphs)

    print(f'原文: {len(paragraphs)}段, {total_chars}字')
    print()

    # 分块
    parts = split_paragraphs(paragraphs)
    print(f'分块: {len(parts)}块')
    for pi, part in enumerate(parts, 1):
        chunk_tk = estimate_tokens('\n'.join(part))
        print(f'  块{pi}: {len(part)}段, {sum(len(p) for p in part)}字, ~{chunk_tk}tk')
    print()

    # 逐块处理
    all_summaries = []
    all_key_points = []

    for pi, part in enumerate(parts, 1):
        prompt = build_summary_prompt(part)
        prompt_tk = estimate_tokens(prompt)
        print(f'  块{pi} Prompt: {len(prompt)}字, ~{prompt_tk}tk')

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
            print(f'    耗时: {elapsed:.1f}s | 输出: {len(raw)}字')

            parsed = parse_summary_output(raw)
            if parsed["summary"]:
                all_summaries.append(parsed["summary"])
            for p in parsed["key_points"]:
                if p and p not in all_key_points:
                    all_key_points.append(p)

            print(f'    摘要: {parsed["summary"][:80]}...' if len(parsed["summary"]) > 80 else f'    摘要: {parsed["summary"]}')
            print(f'    要点数: {len(parsed["key_points"])}')
            if parsed["key_points"]:
                for kp in parsed["key_points"]:
                    print(f'      → {kp}')
            print()
        finally:
            if old_http: os.environ['http_proxy'] = old_http
            if old_https: os.environ['https_proxy'] = old_https

    # 合并结果
    print(f'=== 合并结果 ===')
    final_summary = all_summaries[0] if len(all_summaries) == 1 else ' | '.join(all_summaries)
    print(f'最终摘要: {final_summary}')
    print(f'总要点: {len(all_key_points)}个')
    for i, kp in enumerate(all_key_points, 1):
        print(f'  {i}. {kp}')

if __name__ == '__main__':
    asyncio.run(main())
