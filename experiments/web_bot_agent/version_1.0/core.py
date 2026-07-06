"""
核心引擎：搜索 → 提取 → LLM 分组 → 组装
"""

import json, os, sys, time, re, subprocess, asyncio
import httpx

# 配置路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

PROXY = cfg["proxy"]["http"]
OLLAMA_URL = f"{cfg['ollama']['endpoint']}/api/generate"
MODEL = cfg["ollama"]["models"]["default"]
MAX_PARALLEL = cfg["ollama"]["max_parallel"]
OLLAMA_TIMEOUT = cfg["ollama"]["timeout"]
OLLAMA_TEMP = cfg["ollama"]["temperature"]
OLLAMA_NUM_PREDICT = cfg["ollama"]["num_predict"]
SPLIT_THRESHOLD = cfg["split"]["threshold_chars"]
SPLIT_PART_TARGET = cfg["split"]["part_target_chars"]


# ============================================================
# 1. 搜索
# ============================================================
def search_web(query: str, max_results: int = 5) -> list:
    """通过 web-forager 搜索，返回 [{title, url, snippet}, ...]"""
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

    # 获取发布日期
    meta_json = trafilatura.extract(html, output_format='json', include_images=False, with_metadata=True)
    date_from_meta = ""
    if meta_json:
        try:
            meta = json.loads(meta_json)
            date_from_meta = meta.get("date", "") or ""
        except:
            pass

    # 提取正文
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


async def fetch_and_extract_async(url: str) -> tuple:
    """异步版本，与 fetch_and_extract 功能相同"""
    import trafilatura
    try:
        async with httpx.AsyncClient(proxy=PROXY, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
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

    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    return body or "[提取失败]", date_from_meta, html_len, paragraphs


def extract_date_from_snippet(snippet: str) -> str:
    if not snippet:
        return ""
    m = re.search(r'^([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-–—]', snippet)
    return m.group(1) if m else ""


# ============================================================
# 3. 段落分割
# ============================================================
def split_paragraphs(paragraphs: list) -> list:
    """
    如果总字数 > threshold，按每段约 target 字数分割。
    返回: [[para1, para2...], ...] 每个子列表一次 LLM 推理
    """
    total = sum(len(p) for p in paragraphs)
    if total <= SPLIT_THRESHOLD:
        return [paragraphs]

    parts = []
    remaining = paragraphs[:]
    while True:
        rem_total = sum(len(p) for p in remaining)
        if rem_total <= SPLIT_PART_TARGET:
            parts.append(remaining)
            break

        cum = 0
        split_idx = 0
        for i, p in enumerate(remaining):
            cum += len(p)
            if cum >= SPLIT_PART_TARGET:
                split_idx = i + 1
                break

        if split_idx < 3 or split_idx > len(remaining) - 3:
            split_idx = len(remaining) // 2

        parts.append(remaining[:split_idx])
        remaining = remaining[split_idx:]

        if len(parts) > 10:
            break

    return parts


# ============================================================
# 4. LLM 分组 prompt
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
        "【组1】段落：P1-P3\n要点：xxx\n概括：xxx\n\n"
        "【组2】段落：P4-P7\n要点：xxx\n概括：xxx\n\n"
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


# ============================================================
# 5. LLM 推理
# ============================================================
def parse_grouping(raw: str) -> list:
    """解析 LLM 分组输出，返回 [{group_id, start_p, end_p, point, summary}, ...]"""
    groups = []
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
        "options": {
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMP
        }
    }
    old_http = os.environ.pop("http_proxy", None)
    old_https = os.environ.pop("https_proxy", None)
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
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
# 6. 主流程（单次搜索 -> 结构化 JSON）
# ============================================================
async def run_search_pipeline(query: str, keyword: str, max_results: int = 5) -> dict:
    """
    执行完整 pipeline：搜索 → 提取 → 分割 → LLM 分组 → 合并
    返回: {
        "articles": { article_id: {title, url, date, snippet, source, charnum, segments} },
        "segments": { segment_id: {article_id, point, summary, charnum} },
        "_texts": { article_id: { segment_id: text } }
    }
    """
    # 搜索
    raw_results = search_web(query, max_results)
    if not raw_results:
        return {"articles": {}, "segments": {}, "_texts": {}}

    # 并行提取正文
    async def _fetch_one(item: dict) -> dict:
        url = item["url"]
        snippet = item.get("snippet", "")
        body, meta_date, html_len, paragraphs = await fetch_and_extract_async(url)
        date = extract_date_from_snippet(snippet) or meta_date
        return {
            "title": item["title"],
            "url": url,
            "snippet": snippet,
            "date": date,
            "paragraphs": paragraphs,
        }

    sem_fetch = asyncio.Semaphore(MAX_PARALLEL)
    async def _bounded_fetch(item):
        async with sem_fetch:
            return await _fetch_one(item)

    items = await asyncio.gather(*[_bounded_fetch(item) for item in raw_results])

    # 分割 + 构建推理任务
    inference_tasks = []
    for idx, it in enumerate(items):
        parts = split_paragraphs(it["paragraphs"])
        it["split_parts"] = parts
        for pi, part in enumerate(parts):
            inference_tasks.append((idx, pi, part))

    # 判断每个调用的 max_groups
    tasks_for_llm = []
    for art_idx, part_idx, part_paras in inference_tasks:
        full_paras = items[art_idx]["paragraphs"]
        total_full = sum(len(p) for p in full_paras)
        max_g = 3 if total_full > SPLIT_THRESHOLD else 5
        tasks_for_llm.append((part_paras, max_g))

    # 并行推理
    raw_llm_results = await infer_all(tasks_for_llm)

    # 按文章合并结果
    article_results = {}
    for (art_idx, part_idx, _), (_, raw, elapsed) in zip(inference_tasks, raw_llm_results):
        if art_idx not in article_results:
            article_results[art_idx] = []
        groups = parse_grouping(raw)
        groups.sort(key=lambda g: g["start_p"])
        article_results[art_idx].append((part_idx, raw, elapsed, groups))

    # 组装 JSON
    articles = {}
    all_segments = {}
    all_texts = {}

    for idx in range(len(items)):
        it = items[idx]
        paragraphs = it["paragraphs"]
        parts = it["split_parts"]
        results = article_results.get(idx, [])
        results.sort(key=lambda x: x[0])

        # 偏移合并
        offset = 0
        all_groups = []
        for part_idx, raw, elapsed, groups in results:
            for g in groups:
                g["start_p"] += offset
                g["end_p"] += offset
            all_groups.extend(groups)
            if part_idx < len(parts):
                offset += len(parts[part_idx])

        # 去重合并
        merged = []
        for g in all_groups:
            if merged and g["start_p"] <= merged[-1]["end_p"]:
                prev = merged[-1]
                prev["end_p"] = max(prev["end_p"], g["end_p"])
                prev["point"] += " + " + g["point"]
                prev["summary"] += "；" + g["summary"]
            else:
                merged.append(g)

        groups = merged
        if not groups:
            continue

        # 补充遗漏段落
        covered = set()
        for g in groups:
            for pn in range(g["start_p"], g["end_p"] + 1):
                covered.add(pn)
        all_paras = set(range(1, len(paragraphs) + 1))
        missing = sorted(all_paras - covered)
        if missing:
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

        # 构建文章数据
        article_id = f"a_{idx+1:02d}"
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

            sid = f"{article_id}_{seg_id}"
            all_segments[sid] = {
                "article_id": article_id,
                "point": g["point"],
                "summary": g["summary"],
                "charnum": charnum
            }

        source = re.sub(r'https?://(www\.)?', '', it["url"]).split('/')[0]
        articles[article_id] = {
            "title": it["title"],
            "url": it["url"],
            "date": it["date"] or "",
            "snippet": it["snippet"],
            "source": source,
            "charnum": total_charnum,
            "segments": segments_out
        }
        all_texts[article_id] = segment_texts

    return {
        "articles": articles,
        "segments": all_segments,
        "_texts": all_texts
    }
