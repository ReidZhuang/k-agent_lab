#!/usr/bin/env python3
"""
搜索 → 提取正文 → LLM 段落分组 → 合并输出 JSON
"""

import json, os, sys, time, re, subprocess, asyncio
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


# ============================================================
# 1. 搜索
# ============================================================
def search(query: str, max_results: int = 5) -> list:
    print(f"🔍 搜索: {query}", file=sys.stderr)
    env = os.environ.copy()
    env["http_proxy"] = PROXY
    env["https_proxy"] = PROXY
    r = subprocess.run(
        ["web-forager", "search", query, "--max-results", str(max_results)],
        capture_output=True, text=True, timeout=20, env=env
    )
    return json.loads(r.stdout)


# ============================================================
# 2. 正文提取
# ============================================================
def fetch_and_extract(url: str) -> tuple:
    """返回 (body_text, date_str, html_len, paragraphs)"""
    import trafilatura
    try:
        with httpx.Client(proxy=PROXY, timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            html = resp.text
            html_len = len(html)
    except Exception as e:
        return f"[抓取失败] {e}", "", 0, []

    meta_json = trafilatura.extract(html, output_format='json', include_images=False, with_metadata=True)
    date_from_meta = ""
    if meta_json:
        try:
            meta = json.loads(meta_json)
            date_from_meta = meta.get("date", "") or ""
        except:
            pass

    body = trafilatura.extract(html, output_format='markdown', include_images=False)
    if not body or len(body.strip()) < 10:
        try:
            from readability import Document
            import html2text
            doc = Document(html)
            h = html2text.HTML2Text()
            h.body_width = 0
            h.ignore_links = False
            h.ignore_images = True
            body = h.handle(doc.summary()).strip()
        except:
            pass

    # 分段
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    return body or "[提取失败]", date_from_meta, html_len, paragraphs


def extract_date_from_snippet(snippet: str) -> str:
    if not snippet:
        return ""
    m = re.search(r'^([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-–—]', snippet)
    return m.group(1) if m else ""


# ============================================================
# 3. LLM 段落分组
# ============================================================
def build_grouping_prompt(paragraphs: list, max_groups: int = 5) -> str:
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
    return (
        "任务：将下方【正文】中已编号的段落（[P1]、[P2]...[Pn]）进行分组。\n\n"
        "输出要求：只输出分组方案，不要输出原文。\n\n"
        "分组规则：\n"
        "- 将相邻的、主题相近的段落合并为一组\n"
        f"- 全文分成≤{max_groups}组，如果全文只有一段，那么全文只分1组即可\n"
        "- 每组内的段落编号必须是连续的（例如 P2,P3,P4 可以，P2,P5 不可以）\n"
        "- 每组至少包含一个段落，不得引用不存在的段落编号\n"
        "- 每个段落只能属于一个组，不得重复分配\n"
        "- 分组结束后，每个段落（[P1]、[P2]...[Pn]）都必须被分配到某个组中，不得遗漏\n\n"
        "输出格式（严格按此格式，不要输出其他内容）：\n\n"
        "【组1】段落：P1-P3\n"
        "要点：xxx\n"
        "概括：xxx\n\n"
        "【组2】段落：P4-P7\n"
        "要点：xxx\n"
        "概括：xxx\n\n"
        "字段说明：\n"
        "- 「段落」：该组包含的段落编号范围，用短横线连接起止编号\n"
        "- 「要点」：该组核心话题（15-50字），多个主题描述用\" + \"连接\n"
        "- 「概括」：该组关键信息浓缩（50-100字），包含具体数据或结论\n\n"
        "要求：\n"
        "- 每组段落编号必须连续\n"
        f"- 总组数≤{max_groups}组\n"
        "- 全文只有[P1]一段时，只分1组\n"
        "- 所有段落（[P1]、[P2]...[Pn]）都必须被分配到某个组\n\n"
        f"【正文】：\n{numbered[:4000]}"
    )


def split_paragraphs(paragraphs: list) -> list:
    """如果总字数>3000字，按每段约2000字分割。返回多个段落列表。"""
    total = sum(len(p) for p in paragraphs)
    if total <= 3000:
        return [paragraphs]

    parts = []
    while True:
        remaining = sum(len(p) for p in paragraphs)
        if remaining <= 2000:
            parts.append(paragraphs)
            break

        cum = 0
        split_idx = 0
        for i, p in enumerate(paragraphs):
            cum += len(p)
            if cum >= 2000:
                split_idx = i + 1
                break

        if split_idx < 3 or split_idx > len(paragraphs) - 3:
            split_idx = len(paragraphs) // 2

        first = paragraphs[:split_idx]
        parts.append(first)
        paragraphs = paragraphs[split_idx:]

        if len(parts) > 10:
            break

    return parts


def parse_grouping(raw: str) -> list:
    """解析 LLM 分组输出，返回 [{group_id, start_p, end_p, point, summary}, ...]"""
    groups = []
    # 匹配 【组N】段落：Px-Py 或 【组N】段落：Px
    for m in re.finditer(
        r'【组(\d+)】段落[：:]\s*P(\d+)(?:\s*[-–]\s*P(\d+))?.*?要点[：:]\s*(.*?)\s*概括[：:]\s*(.*?)(?=\n\n【组|\n*$)',
        raw, re.DOTALL
    ):
        start_p = int(m.group(2))
        end_p = int(m.group(3)) if m.group(3) else start_p
        groups.append({
            "group_id": int(m.group(1)),
            "start_p": start_p,
            "end_p": end_p,
            "point": m.group(4).strip(),
            "summary": m.group(5).strip(),
        })
    return groups


async def infer_grouping(paragraphs: list, idx: int, max_groups: int = 5) -> tuple:
    prompt = build_grouping_prompt(paragraphs, max_groups)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.1}
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
        return idx, f"[Ollama 错误] {e}", time.time() - t0
    finally:
        if old_http: os.environ["http_proxy"] = old_http
        if old_https: os.environ["https_proxy"] = old_https


async def infer_all(tasks_list: list) -> list:
    """tasks_list: [(paragraphs, max_groups), ...]"""
    sem = asyncio.Semaphore(MAX_PARALLEL)
    async def f(paras, mg, i):
        async with sem:
            return await infer_grouping(paras, i, mg)
    tasks = [f(paras, mg, i) for i, (paras, mg) in enumerate(tasks_list)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x[0])
    return results


# ============================================================
# 4. 主流程
# ============================================================
def main():
    SEARCH_QUERY = "site:stcn.com 中国光刻机制造 产业链 技术壁垒"
    session_id = f"s_{time.strftime('%Y%m%d_%H%M%S')}"

    # 搜索
    try:
        results = search(SEARCH_QUERY)
    except Exception as e:
        print(f"❌ 搜索失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("❌ 未搜索到结果", file=sys.stderr)
        sys.exit(1)

    print(f"📝 共 {len(results)} 条结果", file=sys.stderr)

    # 提取正文➕分段
    items = []
    for i, item in enumerate(results):
        title = item.get("title", "")
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        print(f"\n[{i+1}/{len(results)}] {title}", file=sys.stderr)

        body, meta_date, html_len, paragraphs = fetch_and_extract(url)
        date = extract_date_from_snippet(snippet) or meta_date
        print(f"   📄 HTML:{html_len:,}c → 正文:{len(body)}c → {len(paragraphs)}段  📅 {date or '-'}", file=sys.stderr)

        items.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "date": date,
            "body": body,
            "body_len": len(body),
            "paragraphs": paragraphs,
        })
        time.sleep(0.3)

    # 分割 + 推理
    # 构建推理任务列表: (文章idx, 分割部分idx, 段落列表)
    inference_tasks = []
    for idx, it in enumerate(items):
        parts = split_paragraphs(it["paragraphs"])
        it["split_parts"] = parts  # 保存分割结果
        for pi, part in enumerate(parts):
            inference_tasks.append((idx, pi, part))

    total_calls = len(inference_tasks)
    print(f"\n🤖 LLM 段落分组 {len(items)} 篇 → {total_calls} 次调用 (并行 {MAX_PARALLEL})...", file=sys.stderr)

    # 判断每个调用是完整文章还是分割部分，决定 max_groups
    tasks_for_llm = []
    for art_idx, part_idx, part_paras in inference_tasks:
        full_paras = items[art_idx]["paragraphs"]
        total_full = sum(len(p) for p in full_paras)
        max_g = 3 if total_full > 3000 else 5  # 被分割的用3组，完整的用5组
        tasks_for_llm.append((part_paras, max_g))

    t0 = time.time()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    raw_results = loop.run_until_complete(infer_all(tasks_for_llm))
    loop.close()
    total_llm = time.time() - t0

    # 将推理结果按文章合并
    article_results = {}  # idx -> [(part_idx, raw, elapsed, groups)]
    for (art_idx, part_idx, _), (llm_idx, raw, elapsed) in zip(inference_tasks, raw_results):
        if art_idx not in article_results:
            article_results[art_idx] = []
        groups = parse_grouping(raw)
        groups.sort(key=lambda g: g["start_p"])
        article_results[art_idx].append((part_idx, raw, elapsed, groups))

    # 组装 JSON
    articles = {}
    all_segments = {}
    article_id_base = f"a_{time.strftime('%Y%m%d')}"

    for idx in range(len(items)):
        it = items[idx]
        paragraphs = it["paragraphs"]
        parts = it["split_parts"]
        results = article_results.get(idx, [])
        results.sort(key=lambda x: x[0])  # 按部分排序

        # 计算段落偏移并合并分组
        offset = 0
        all_groups = []
        for part_idx, raw, elapsed, groups in results:
            # 对当前部分的段落编号加上偏移
            for g in groups:
                g["start_p"] += offset
                g["end_p"] += offset
            all_groups.extend(groups)
            # 更新偏移：当前部分的段落数
            if part_idx < len(parts):
                offset += len(parts[part_idx])

        # 合并完成后重新编号
        merged_groups = []
        for g in all_groups:
            if merged_groups and g["start_p"] <= merged_groups[-1]["end_p"]:
                prev = merged_groups[-1]
                prev["end_p"] = max(prev["end_p"], g["end_p"])
                prev["point"] += " + " + g["point"]
                prev["summary"] += "；" + g["summary"]
            else:
                merged_groups.append(g)

        groups = merged_groups
        # 按段落起始编号排序，保证输出顺序与原文一致
        groups.sort(key=lambda g: g["start_p"])

        # 去重：如果相邻组有重叠的段落范围，合并
        deduped = []
        for g in groups:
            if deduped and g["start_p"] <= deduped[-1]["end_p"]:
                # 重叠了，合并到前一组
                prev = deduped[-1]
                prev["end_p"] = max(prev["end_p"], g["end_p"])
                prev["point"] += " + " + g["point"]
                prev["summary"] += "；" + g["summary"]
            else:
                deduped.append(g)
        groups = deduped

        if not groups:
            print(f"   [{idx+1}] ⚠️ 分组解析失败", file=sys.stderr)
            continue

        # 检查是否有段落未被覆盖，补充缺失组
        covered = set()
        for g in groups:
            for pn in range(g["start_p"], g["end_p"] + 1):
                covered.add(pn)
        all_paras = set(range(1, len(paragraphs) + 1))
        missing = sorted(all_paras - covered)
        if missing:
            # 将缺失的连续段落合并为补充组
            start = missing[0]
            end = missing[0]
            for pn in missing[1:]:
                if pn == end + 1:
                    end = pn
                else:
                    groups.append({"group_id": 99, "start_p": start, "end_p": end,
                                   "point": "[补充]", "summary": "LLM遗漏的段落"})
                    start = pn
                    end = pn
            groups.append({"group_id": 99, "start_p": start, "end_p": end,
                           "point": "[补充]", "summary": "LLM遗漏的段落"})

        aid = f"{article_id_base}_{idx+1:02d}"
        segment_texts = {}
        segments_out = []
        total_charnum = 0

        for gi, g in enumerate(groups, 1):
            s = max(0, g["start_p"] - 1)
            e = min(len(paragraphs), g["end_p"])
            group_text = '\n\n'.join(paragraphs[s:e])
            charnum = len(group_text)
            total_charnum += charnum
            seg_id = f"s{gi}"

            segments_out.append({"id": seg_id, "charnum": charnum})
            segment_texts[seg_id] = group_text

            sid = f"{aid}_{seg_id}"
            all_segments[sid] = {
                "article_id": aid,
                "point": g["point"],
                "summary": g["summary"],
                "charnum": charnum
            }

        # 构建 article 条目
        source = re.sub(r'https?://(www\.)?', '', it["url"]).split('/')[0]
        articles[aid] = {
            "title": it["title"],
            "url": it["url"],
            "date": it["date"] or "",
            "snippet": it["snippet"],
            "source": source,
            "charnum": total_charnum,
            "segments": segments_out,
            "_segment_texts": segment_texts
        }

        print(f"   [{idx+1}] {len(groups)}组 ({total_charnum}c) | {elapsed:.1f}s", file=sys.stderr)

    # 输出 JSON
    output = {
        "search_meta": {
            "session_id": session_id,
            "query": SEARCH_QUERY,
            "keyword": "",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "llm_model": MODEL,
            "llm_time_s": round(total_llm, 1)
        },
        "articles": articles,
        "segments": all_segments
    }

    output_path = os.path.join(OUTPUT_DIR, f"search_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}", file=sys.stderr)
    print(f"✅ JSON: {output_path}", file=sys.stderr)
    print(f"   文章数: {len(articles)} | 总段数: {len(all_segments)} | LLM: {total_llm:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
