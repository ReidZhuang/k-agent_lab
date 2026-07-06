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
SPLIT_MAX_TOKENS = cfg["split"]["max_tokens"]


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
# 3. Token 估算 & 段落分割（按 token 分块）
# ============================================================
def estimate_tokens(text: str) -> int:
    """估算文本 token 数，中英文混合"""
    chinese = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    ascii_chars = sum(1 for c in text if c.isascii() and c.isprintable())
    other = max(0, len(text) - chinese - ascii_chars)
    # 中文 ~1.8 字/token，英文 ~3.5 字符/token，其他 ~2
    return int(chinese / 1.8 + ascii_chars / 3.5 + other / 2) + 1


def split_paragraphs(paragraphs: list) -> list:
    """
    按 token 数分块，每块 ≤ SPLIT_MAX_TOKENS，不切段落。
    返回 [[para1, para2...], ...] 每个子列表一次 LLM 推理
    """
    total_tokens = estimate_tokens('\n'.join(paragraphs))
    if total_tokens <= SPLIT_MAX_TOKENS:
        return [paragraphs]

    parts = []
    current = []
    current_tokens = 0
    for p in paragraphs:
        p_tokens = estimate_tokens(p)
        if current_tokens + p_tokens > SPLIT_MAX_TOKENS and current:
            parts.append(current)
            current = []
            current_tokens = 0
        current.append(p)
        current_tokens += p_tokens
    if current:
        parts.append(current)
    return parts


# ============================================================
# 4. LLM 分组 prompt
# ============================================================
def build_grouping_prompt(paragraphs: list, max_groups: int = 5) -> str:
    """构建分组 prompt，使用 【正文开始】/【正文结束】 模板，Pn 动态生成"""
    n = len(paragraphs)
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])

    return (
        f"任务：【正文开始】和【正文结束】之间的文字内容是【正文】文本内容，"
        f"其内容的段落已按照[P1]、[P2]...[P{n}]进行编号，"
        f"现在需要对段落进行分组，并对分组覆盖的【正文】内容进行总结。\n"
        "输出要求：只输出分组方案，不要输出原文。\n\n"
        "分组步骤：\n\n"
        f"1. 阅读【正文】所有内容，即[P1]至[P{n}]的所有段落。注意，[P{n}]代表全文最后一个段落的编号。"
        f"将全文概括成3至5个要点（每个要点是文章的一个核心话题，长度为15-50字），"
        f"每一个要点就是一个【分组】。对应每个要点整理出了3至5个【分组】，"
        f"每一个【分组】的【要点信息】就是刚刚归纳的要点。\n"
        "2. 将在上一步中概括的要点逐一整理其覆盖正文中的段落，"
        "并把段落编号记录在这个要点分组下，这些段落编号就是【段落信息】，"
        "每一个【分组】都有一个【段落信息】。\n"
        f"3. 对每一个【分组】覆盖的【段落信息】在【正文】中的内容用几句话（50-100字）进行内容概括。"
        f"这样你就得到了【概括信息】，每一个分组都有一个【概括信息】。\n"
        f"4. 在每一个【分组】覆盖的【段落信息】在【正文】中的内容中寻找内容主题中的关键字，"
        f"这个关键字应该是【分组】的【要点信息】和【概括信息】的主角。"
        f"关键字可以有多个，这些关键字就是【关键字信息】，每一个分组都有一个【关键字信息】。"
        f"【关键字信息】不要超过10个字。\n"
        f"5. 检查【正文】中的[P1]至[P{n}]所有段落是否都包含在了【分组】中，"
        f"注意，[P{n}]代表全文最后一个段落的编号。"
        f"没有归纳入任何【分组】的段落，将其单独分入一组，"
        f"其【要点信息】为\"其他\"。"
        f"【概括信息】根据其覆盖的【正文】段落信息总结，其【段落信息】就是其段落编号。\n\n"
        "分组规则和注意事项：\n"
        "- 分组步骤1中对【正文】所有内容进行要点总结时，需要把总结的要点数量控制在6个以下。\n"
        "- 请尽量将相邻的、主题相近的段落合并为一组。\n"
        "- 每组段落编号尽量连续。\n"
        "- 每组至少包含一个段落，不得引用不存在的段落编号。\n"
        "- 每个段落只能属于一个组，不得重复分配。\n"
        f"- 分组步骤4结束后，每个段落（[P1]、[P2]...[P{n}]）都必须被分配到某个组中，不得遗漏。\n"
        "- 全文只有[P1]一个段落时，只分1组。\n"
        "- 只有【正文开始】和【正文结束】之间的文字内容才属于需要分组处理的【正文】内容，其余文字内容是提示词。\n\n"
        "输出格式（严格按此格式，不要输出其他内容）：\n"
        "【分组】段落：【段落信息】\n"
        "要点： 【要点信息】\n"
        "概括： 【概括信息】\n"
        "关键字： 【关键字信息】\n\n"
        "字段说明：\n"
        "- 【段落信息】：该组包含的段落编号范围，用短横线连接起止编号，用逗号隔开不同段落编号\n"
        "- 【要点信息】：该组覆盖【正文】内容的核心话题（15-50字），多个主题描述用\" + \"连接\n"
        "- 【概括信息】：该组覆盖【正文】内容的关键信息浓缩（50-100字），包含具体数据或结论\n"
        "- 【关键字信息】： 该组覆盖【正文】内容中重点介绍对象。"
        "该组的【要点信息】和【概括信息】中的主角。"
        "可以包含多个关键字。不同的关键字用+号连接。总字数不要超过10个字\n\n"
        "范例：\n"
        "【组1】段落：P1-P3\n"
        "要点：xxx\n"
        "概括：xxx\n"
        "关键字： 国产化需求+国产替代\n\n"
        "【组2】段落：P4-P7\n"
        "要点：xxx\n"
        "概括：xxx\n"
        "关键字： 海外技术限制+产业链整合\n\n"
        "【正文开始】\n"
        f"{numbered}\n"
        "【正文结束】"
    )


# ============================================================
# 5. LLM 推理
# ============================================================
def parse_paragraphs(para_str: str) -> list[int]:
    """
    解析段落编号字符串，支持：
    - P1-P5    → [1,2,3,4,5]
    - P1,P3,P5 → [1,3,5]
    - P1-P3,P7-P9 → [1,2,3,7,8,9]
    - P1       → [1]
    """
    paragraphs = []
    parts = [p.strip() for p in para_str.split(',')]
    for part in parts:
        range_match = re.match(r'P(\d+)\s*[-–]\s*P(\d+)', part, re.IGNORECASE)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            paragraphs.extend(range(start, end + 1))
        else:
            single_match = re.match(r'P(\d+)', part, re.IGNORECASE)
            if single_match:
                paragraphs.append(int(single_match.group(1)))
    return sorted(set(paragraphs))


def parse_grouping(raw: str) -> list:
    """
    解析新格式的 LLM 分组输出，返回：
    [{group_id, paragraphs, start_p, end_p, point, summary, keywords}, ...]
    """
    groups = []
    blocks = re.split(r'【分组】', raw)
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # 解析段落信息
        para_match = re.search(r'段落[：:]\s*(.*?)(?=\n\s*要点[：:])', block, re.DOTALL)
        if not para_match:
            continue
        para_str = para_match.group(1).strip()
        para_numbers = parse_paragraphs(para_str)
        if not para_numbers:
            continue

        group = {
            "paragraphs": para_numbers,
            "start_p": min(para_numbers),
            "end_p": max(para_numbers),
        }

        # 解析要点
        point_match = re.search(r'要点[：:]\s*(.*?)(?=\n\s*概括[：:])', block, re.DOTALL)
        group["point"] = point_match.group(1).strip() if point_match else ""

        # 解析概括
        summary_match = re.search(r'概括[：:]\s*(.*?)(?=\n\s*关键字[：:])', block, re.DOTALL)
        group["summary"] = summary_match.group(1).strip() if summary_match else ""

        # 解析关键字
        kw_match = re.search(r'关键字[：:]\s*(.*?)(?=\n|$)', block, re.DOTALL)
        group["keywords"] = kw_match.group(1).strip() if kw_match else ""

        groups.append(group)

    # 按输出顺序分配 group_id
    for i, g in enumerate(groups, 1):
        g["group_id"] = i

    return groups


def consolidate_ranges(groups: list) -> list:
    """代码合并段落号，将 P1-P2,P3-P7 合并为 P1-P7"""
    for g in groups:
        ps = g.get("paragraphs", [])
        if not ps:
            ps = list(range(g["start_p"], g["end_p"] + 1))
            g["paragraphs"] = ps
        g["start_p"] = min(ps)
        g["end_p"] = max(ps)
    return groups


STAGE2_MERGE_PROMPT = """任务：将下方【初步分组方案】中的分组进行合并，形成更精简的【最终分组方案】。

概念说明：
- 【分组】：一组相邻段落的集合，包含段落编号范围、要点、概括、关键字。
- 合并：将要点相似的相邻分组合并为一个新分组。

合并步骤：

第1步：找出相邻分组中要点相似或主题重叠的对。
第2步：将要点相似的相邻分组合并，段落号范围合并为最简连续区间。
第3步：对合并后的新分组，整合原有各组的要点形成新的要点，整合原有各组的概括形成新的概括。
第4步：重复第1-3步，直到总组数不超过5组。

输出格式（严格按此格式）：
【分组】段落：【段落信息】
要点： 【要点信息】
概括： 【概括信息】
关键字： 【关键字信息】

【段落信息】格式要求：
- 每个分组只能有一个连续的段落区间
- 用短横线连接起止编号
- 正确示例：P1-P7；错误示例：P1-P2, P3-P7

【初步分组方案】：
{groups_text}"""


async def stage2_merge_async(groups: list) -> list:
    """当分组 > 8 时触发 stage2 合并"""
    if len(groups) <= 8:
        return groups

    # 构建 stage2 输入文本
    lines = []
    for g in groups:
        ps = g.get("paragraphs", list(range(g["start_p"], g["end_p"] + 1)))
        p_range = f"P{min(ps)}-P{max(ps)}" if min(ps) != max(ps) else f"P{min(ps)}"
        lines.append(f"【分组】段落：{p_range}")
        lines.append(f"要点：{g.get('point', '')}")
        lines.append(f"概括：{g.get('summary', '')}")
        lines.append(f"关键字：{g.get('keywords', '')}")
        lines.append("")
    groups_text = '\n'.join(lines).strip()

    prompt = STAGE2_MERGE_PROMPT.format(groups_text=groups_text)

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
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            result = resp.json()
            raw = result.get("response", "").strip()
    except Exception as e:
        return groups  # 失败时返回原始分组
    finally:
        if old_http: os.environ["http_proxy"] = old_http
        if old_https: os.environ["https_proxy"] = old_https

    merged = parse_grouping(raw)
    if not merged:
        return groups  # 解析失败时返回原始分组

    # 代码合并段落号
    merged = consolidate_ranges(merged)
    return merged


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
    执行完整 pipeline：搜索 → 提取 → token分块 → stage1分组 → 偏移合并 → stage2合并 → 组装
    返回: {
        "articles": { article_id: {title, url, date, snippet, source, charnum, segments} },
        "segments": { segment_id: {article_id, point, summary, charnum, keywords?} },
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

    # ============================================================
    # 每篇文章独立处理
    # ============================================================
    articles = {}
    all_segments = {}
    all_texts = {}

    for idx in range(len(items)):
        it = items[idx]
        paragraphs = it["paragraphs"]

        # ---- 1. 分块（token 阈值） ----
        parts = split_paragraphs(paragraphs)
        it["split_parts"] = parts

        # ---- 2. stage1：逐块推理（每块独立编号 P1-Pn） ----
        chunk_results = []
        para_offset = 0  # 全局段落偏移
        for pi, part in enumerate(parts):
            # 构建 prompt（local P1-Pn）
            prompt = build_grouping_prompt(part)
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
                async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                    resp = await client.post(OLLAMA_URL, json=payload)
                    resp.raise_for_status()
                    result = resp.json()
                    raw = result.get("response", "").strip()
            except Exception as e:
                raw = f"[Ollama 错误] {e}"
            finally:
                if old_http: os.environ["http_proxy"] = old_http
                if old_https: os.environ["https_proxy"] = old_https

            groups = parse_grouping(raw)
            # 偏移还原到全局段落号
            for g in groups:
                g["start_p"] += para_offset
                g["end_p"] += para_offset
                if "paragraphs" in g:
                    g["paragraphs"] = [p + para_offset for p in g["paragraphs"]]
            chunk_results.append(groups)
            para_offset += len(part)

        # ---- 3. 合并所有 chunk 的分组 ----
        all_groups = []
        for groups in chunk_results:
            all_groups.extend(groups)

        if not all_groups:
            continue

        # 合并相邻重叠
        merged = []
        for g in all_groups:
            if merged and g["start_p"] <= merged[-1]["end_p"]:
                prev = merged[-1]
                prev["end_p"] = max(prev["end_p"], g["end_p"])
                prev["point"] += " + " + g["point"]
                prev["summary"] += "；" + g["summary"]
                prev_kw = prev.get("keywords", "").strip()
                g_kw = g.get("keywords", "").strip()
                if prev_kw and g_kw and prev_kw != g_kw:
                    prev["keywords"] = prev_kw + "+" + g_kw
                if "paragraphs" in prev and "paragraphs" in g:
                    prev["paragraphs"] = sorted(set(prev["paragraphs"] + g["paragraphs"]))
            else:
                if "paragraphs" not in g:
                    g["paragraphs"] = list(range(g["start_p"], g["end_p"] + 1))
                merged.append(g)

        groups = consolidate_ranges(merged)

        # ---- 5. 补充遗漏段落 ----
        covered = set()
        for g in groups:
            for pn in range(g["start_p"], g["end_p"] + 1):
                covered.add(pn)
        all_paras_set = set(range(1, len(paragraphs) + 1))
        missing = sorted(all_paras_set - covered)
        if missing:
            start = missing[0]
            end = missing[0]
            for pn in missing[1:]:
                if pn == end + 1:
                    end = pn
                else:
                    groups.append({"group_id": 99, "start_p": start, "end_p": end,
                                   "paragraphs": list(range(start, end + 1)),
                                   "point": "[补充]", "summary": "LLM遗漏的段落", "keywords": ""})
                    start = pn
                    end = pn
            groups.append({"group_id": 99, "start_p": start, "end_p": end,
                           "paragraphs": list(range(start, end + 1)),
                           "point": "[补充]", "summary": "LLM遗漏的段落", "keywords": ""})

        # ---- 6. 构建文章数据 ----
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
            seg_item = {
                "article_id": article_id,
                "point": g["point"],
                "summary": g["summary"],
                "charnum": charnum
            }
            if g.get("keywords"):
                seg_item["keywords"] = g["keywords"]
            all_segments[sid] = seg_item

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
