#!/usr/bin/env python3
"""
搜索 → 提取正文 → LLM 摘要 → 输出原始模型回复
"""

import json, os, sys, time, subprocess, asyncio
import httpx

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

PROXY = cfg["proxy"]["http"]
OLLAMA_URL = f"{cfg['ollama']['endpoint']}/api/generate"
MODEL = cfg["ollama"]["models"]["default"]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), cfg["paths"]["results"])
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_PARALLEL = 4

def search(query, max_results=5):
    env = os.environ.copy()
    env["http_proxy"] = PROXY
    env["https_proxy"] = PROXY
    r = subprocess.run(
        ["web-forager", "search", query, "--max-results", str(max_results)],
        capture_output=True, text=True, timeout=20, env=env
    )
    return json.loads(r.stdout)

def fetch_and_extract(url):
    import trafilatura
    try:
        with httpx.Client(proxy=PROXY, timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            html = resp.text
    except Exception as e:
        return f"[抓取失败] {e}", "", 0

    meta_json = trafilatura.extract(html, output_format='json', include_images=False, with_metadata=True)
    date_from_meta = ""
    if meta_json:
        try:
            meta = json.loads(meta_json)
            date_from_meta = meta.get("date", "") or ""
        except:
            pass

    text = trafilatura.extract(html, output_format='markdown', include_images=False)
    if text and len(text.strip()) > 50:
        return text.strip(), date_from_meta, len(html)

    try:
        from readability import Document
        import html2text
        doc = Document(html)
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        h.ignore_images = True
        text2 = h.handle(doc.summary()).strip()
        if text2:
            return text2, date_from_meta, len(html)
    except:
        pass

    return "[提取失败]", date_from_meta, len(html)

def extract_date_from_snippet(snippet):
    if not snippet:
        return ""
    m = __import__('re').search(r'^([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-–—]', snippet)
    return m.group(1) if m else ""

async def infer_one(text, idx):
    prompt = (
        "总结【正文】的内容构成要点，要点必须包括要点标题和要点的简单summary。"
        "从不同角度拆分正文，每个独立信息块作为一个要点。"
        "输出的时候，将要点+匹配其要点的原文的形式输出。"
        "要求：要点部分尽量控制在3-5条左右。对于无内容意义的部分可以归纳为[旁白]或[开头]、[结尾]。"
        "输出的格式应该是：\n\n"
        f"【正文】：\n{text[:3000]}"
    )
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 512, "temperature": 0.1}
    }
    old_http = os.environ.pop("http_proxy", None)
    old_https = os.environ.pop("https_proxy", None)
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            result = resp.json()
            elapsed = time.time() - t0
            return idx, result.get("response", "").strip(), elapsed
    except Exception as e:
        return idx, f"[错误] {e}", time.time() - t0
    finally:
        if old_http: os.environ["http_proxy"] = old_http
        if old_https: os.environ["https_proxy"] = old_https

async def summarize_all(texts):
    sem = asyncio.Semaphore(MAX_PARALLEL)
    async def f(text, i):
        async with sem:
            return await infer_one(text, i)
    tasks = [f(text, i) for i, text in enumerate(texts)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x[0])
    return results

def main():
    SEARCH_QUERY = "site:stcn.com 中国光刻机制造 产业链 技术壁垒"

    print(f"🔍 搜索: {SEARCH_QUERY}", file=sys.stderr)
    results = search(SEARCH_QUERY)
    print(f"📝 共 {len(results)} 条结果\n", file=sys.stderr)

    items = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        print(f"[{i}/{len(results)}] {title}", file=sys.stderr)

        body, meta_date, html_len = fetch_and_extract(url)
        date = extract_date_from_snippet(snippet) or meta_date
        body_len = len(body)
        print(f"   📄 {body_len}c  📅 {date or '-'}", file=sys.stderr)

        items.append({
            "idx": i, "title": title, "url": url,
            "snippet": snippet, "date": date,
            "body": body, "body_len": body_len, "html_len": html_len,
        })
        time.sleep(0.3)

    bodies = [it["body"] for it in items]
    print(f"\n🤖 推理 {len(bodies)} 篇...", file=sys.stderr)
    t0 = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    raw_results = loop.run_until_complete(summarize_all(bodies))
    loop.close()
    total = time.time() - t0

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    report_path = os.path.join(OUTPUT_DIR, "search_summarize_raw.md")

    md = f"# 搜索 → 提取 → LLM 摘要（原始输出）\n\n"
    md += f"> **搜索词:** `{SEARCH_QUERY}`\n"
    md += f"> **LLM 模型:** {MODEL}\n"
    md += f"> **时间:** {timestamp}\n"
    md += f"> **总推理时间:** {total:.1f}s\n\n"
    md += "---\n\n"

    for idx, raw, elapsed in raw_results:
        it = items[idx]
        md += f"## {it['idx']}. {it['title']}\n\n"
        md += f"**URL:** {it['url']}\n\n"
        if it['date']:
            md += f"**日期:** {it['date']}\n\n"
        md += f"**HTML:** {it['html_len']:,}c → **正文:** {it['body_len']:,}c\n\n"
        md += f"**搜索摘要:**\n> {it['snippet']}\n\n"
        md += f"**LLM 原始回复 ({elapsed:.1f}s):**\n\n"
        md += "```\n"
        md += raw
        md += "\n```\n\n"
        md += "**正文全文:**\n\n```markdown\n"
        md += it['body'][:2000]
        if it['body_len'] > 2000:
            md += f"\n... (剩余 {it['body_len']-2000} chars)"
        md += "\n```\n\n---\n\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n✅ 报告已保存: {report_path}", file=sys.stderr)
    print(f"   总推理时间: {total:.1f}s", file=sys.stderr)

if __name__ == "__main__":
    main()
