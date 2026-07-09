"""
核心引擎：搜索 → 提取 → LLM 分组 → 组装
"""

import json, os, sys, time, re, asyncio
from dataclasses import dataclass, field
import httpx

# 配置路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

# search_engine
_SEARCH_PARENT = os.path.join(os.path.dirname(__file__), "..", "..")
if _SEARCH_PARENT not in sys.path:
    sys.path.insert(0, _SEARCH_PARENT)
from search_engine import search as search_web

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
# ChunkUnit — 统一块单元
# ============================================================
@dataclass
class ChunkUnit:
    """文章的一块（或整篇）。提取切块后产出此结构进入块池。"""
    article_id: str
    title: str
    url: str
    date: str
    snippet: str
    source: str
    chunk_index: int
    total_chunks: int
    paragraphs: list
    para_offset: int

    @property
    def is_splitted(self) -> bool:
        return self.total_chunks > 1

    @property
    def position(self) -> str:
        if self.total_chunks <= 1:
            return ""
        if self.chunk_index == 0:
            return "开头"
        if self.chunk_index == self.total_chunks - 1:
            return "结尾"
        return "中间"


# ============================================================
# 1. 搜索（已迁移至 search_engine 模块）
# ============================================================
# search_web() 在模块顶部通过 "from search_engine import search as search_web" 导入


# ============================================================
# 2. 正文提取
# ============================================================
def fetch_and_extract(url: str) -> tuple:
    """返回 (body_text, date_str, html_len, paragraphs)"""
    import trafilatura
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
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
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
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


async def extract_and_chunk_async(item: dict, article_id: str) -> list[ChunkUnit]:
    """提取正文 + 原地切块，返回 ChunkUnit 列表（一块或若干块）。"""
    url = item["url"]
    snippet = item.get("snippet", "")
    body, meta_date, html_len, paragraphs = await fetch_and_extract_async(url)
    date = extract_date_from_snippet(snippet) or meta_date
    source = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
    parts = split_paragraphs(paragraphs)
    units = []
    para_offset = 0
    for pi, part in enumerate(parts):
        units.append(ChunkUnit(
            article_id=article_id,
            title=item["title"],
            url=url,
            date=date or "",
            snippet=snippet,
            source=source,
            chunk_index=pi,
            total_chunks=len(parts),
            paragraphs=part,
            para_offset=para_offset,
        ))
        para_offset += len(part)
    return units


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
    """构建分组 prompt，使用 prompts/grouping.txt 模板"""
    n = len(paragraphs)
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
    return _prompt_grouping_template.replace('{n}', str(n)).replace('{numbered}', numbered)


# ============================================================
# 4b. Summary 模式 prompt
# ============================================================
# 4b. Summary 模式 prompt
# ============================================================
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
PROMPT_SUMMARY_PATH = os.path.join(PROMPTS_DIR, "summary.txt")
PROMPT_MERGE_PATH = os.path.join(PROMPTS_DIR, "summary_merge.txt")
PROMPT_LOCATE_PATH = os.path.join(PROMPTS_DIR, "point_locate.txt")
PROMPT_LOCATE_SIMPLE_PATH = os.path.join(PROMPTS_DIR, "point_locate_simple.txt")
PROMPT_GROUPING_PATH = os.path.join(PROMPTS_DIR, "grouping.txt")

with open(PROMPT_SUMMARY_PATH, encoding='utf-8') as f:
    _prompt_summary_template = f.read()
with open(PROMPT_MERGE_PATH, encoding='utf-8') as f:
    _prompt_merge_template = f.read()
with open(PROMPT_LOCATE_PATH, encoding='utf-8') as f:
    _prompt_locate_template = f.read()
with open(PROMPT_LOCATE_SIMPLE_PATH, encoding='utf-8') as f:
    _prompt_locate_simple_template = f.read()
with open(PROMPT_GROUPING_PATH, encoding='utf-8') as f:
    _prompt_grouping_template = f.read()


def build_summary_prompt(paragraphs: list, query: str = "", keyword: str = "") -> str:
    """构建 summary 模式 prompt：从 prompts/summary.txt 读取模板，注入 query/keyword/body"""
    body = '\n\n'.join(paragraphs)
    return _prompt_summary_template.format(query=query, keyword=keyword, body=body)


def build_merge_prompt(chunk_summaries: list, query: str = "", keyword: str = "") -> str:
    """构建合并 prompt：从 prompts/summary_merge.txt 读取模板"""
    text = ''
    for i, s in enumerate(chunk_summaries, 1):
        text += f'【第{i}部分概括】\n{s}\n\n'
    return _prompt_merge_template.format(query=query, keyword=keyword, chunk_summaries=text.strip())


def build_point_locate_prompt(paragraphs: list, key_point: str,
                               all_key_points: list = None, target_index: int = None) -> str:
    """构建要点定位 prompt。提供 all_key_points 时会在 prompt 中列出全文要点作为上下文。"""
    numbered = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])

    if all_key_points and target_index is not None:
        kp_text = '\n'.join(f"{i+1}. {kp}" for i, kp in enumerate(all_key_points))
        return _prompt_locate_template.format(
            key_point=key_point, numbered_body=numbered,
            all_key_points_text=kp_text, target_index=target_index
        )
    else:
        # 降级：无上下文时用 prompts/point_locate_simple.txt
        return _prompt_locate_simple_template.format(key_point=key_point, numbered_body=numbered)


def parse_summary_output(raw: str) -> dict:
    """
    解析 summary 模式 LLM 输出，返回：
    {
        "summary": str,             # 客观概括 + 相关摘要的合并文本
        "summary_objective": str,   # 【客观概括】内容
        "summary_relevant": str,    # 【相关摘要】内容
        "key_points": [str]         # 【核心要点】列表
    }
    """
    result = {"summary": "", "summary_objective": "", "summary_relevant": "", "key_points": []}

    # 提取【客观概括】
    obj_match = re.search(r'【客观概括】\s*\n(.*?)(?=\n\s*【相关摘要】|\Z)', raw, re.DOTALL)
    if obj_match:
        result["summary_objective"] = obj_match.group(1).strip()

    # 提取【相关摘要】
    rel_match = re.search(r'【相关摘要】\s*\n(.*?)(?=\n\s*【核心要点】|\Z)', raw, re.DOTALL)
    if rel_match:
        result["summary_relevant"] = rel_match.group(1).strip()

    # 合并摘要
    parts = []
    if result["summary_objective"]:
        parts.append(result["summary_objective"])
    if result["summary_relevant"]:
        parts.append(result["summary_relevant"])
    result["summary"] = '\n\n'.join(parts)

    # 提取【核心要点】后的编号列表
    kp_match = re.search(r'【核心要点】\s*\n(.*?)$', raw, re.DOTALL)
    if kp_match:
        kp_text = kp_match.group(1).strip()
        for line in kp_text.split('\n'):
            line = line.strip()
            m = re.match(r'^\d+[.、．]\s*(.*)', line)
            if m:
                point = m.group(1).strip()
                if point:
                    result["key_points"].append(point)

    return result


def parse_merge_output(raw: str) -> str:
    """解析合并 LLM 输出，返回【统一概括】文本"""
    m = re.search(r'【统一概括】\s*\n(.*?)$', raw, re.DOTALL)
    return m.group(1).strip() if m else raw


def parse_point_locate_output(raw: str) -> list[int]:
    """
    解析要点定位 LLM 输出，返回段落编号列表。
    【段落】P5 → [5]
    【段落】P3-P7 → [3,4,5,6,7]
    【段落】无 → []
    """
    m = re.search(r'【段落】\s*(.+)', raw)
    if not m:
        return []
    result_str = m.group(1).strip()
    if result_str == '无':
        return []
    # LLM 有时会漏掉 P 前缀，补上
    if not re.match(r'^[Pp]', result_str):
        result_str = 'P' + result_str
    return parse_paragraphs(result_str)


async def _call_llm(prompt: str) -> str:
    """调用 Ollama /api/generate，返回原始响应文本"""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMP
        }
    }
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        return f"[Ollama 错误] {e}"


async def locate_point_text(chunks: list, key_point: str) -> dict:
    """
    根据要点定位原文段落。检查所有分块，选择最佳匹配。
    chunks: [[para1, para2...], [para1, para2...]] 分块段落列表
    key_point: 要点文本
    返回: {"found": bool, "paragraphs": [int], "text": str, "chunk_index": int}
    """
    # 提取要点中的关键词（2字以上连续中文）
    kw_set = set()
    for i in range(len(key_point) - 1):
        token = key_point[i:i+2]
        if any('一' <= c <= '鿿' for c in token):
            kw_set.add(token)

    best = {"found": False, "paragraphs": [], "text": "", "chunk_index": -1, "score": -1}

    for ci, chunk in enumerate(chunks):
        prompt = build_point_locate_prompt(chunk, key_point)
        raw = await _call_llm(prompt)
        paras = parse_point_locate_output(raw)
        if not paras:
            continue
        valid_paras = [p for p in paras if 1 <= p <= len(chunk)]
        if not valid_paras:
            continue
        text_parts = [chunk[p-1] for p in valid_paras]
        matched_text = '\n\n'.join(text_parts)

        # 计算关键词覆盖率作为匹配质量
        score = 0
        if kw_set:
            found_kw = sum(1 for kw in kw_set if kw in matched_text)
            score = found_kw / len(kw_set)

        if score > best["score"]:
            best = {
                "found": True,
                "paragraphs": valid_paras,
                "text": matched_text,
                "chunk_index": ci,
                "score": score
            }

    return {"found": best["found"], "paragraphs": best["paragraphs"],
            "text": best["text"], "chunk_index": best["chunk_index"]}


# ============================================================
# 5. LLM 推理（分组模式）
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


    # (stage2_merge_async 已移除——LLM二次合并导致过度压缩，改用代码合并)
    # (infer_grouping / infer_all 已移除——由 run_search_pipeline 内联 _call_llm 替代)


# ============================================================
# 6. 主流程（单次搜索 -> 结构化 JSON）
# ============================================================
async def run_search_pipeline(query: str, keyword: str, max_results: int = 5, mode: str = "segments",
                               site: str | None = None, timelimit: str | None = None) -> dict:
    """
    执行完整 pipeline。

    mode="segments"（默认）：搜索 → 提取 → token分块 → LLM分组 → 偏移合并 → 补充遗漏 → 组装
    mode="summary"：  搜索 → 提取 → LLM摘要+要点 → 组装

    返回: {
        "articles": { article_id: {title, url, date, snippet, source, charnum, segments} },
        "segments": { segment_id: {article_id, point, summary, charnum, keywords?} },
        "_texts": { article_id: { segment_id: text } }
    }
    """
    # 搜索
    raw_results = search_web(query, max_results=max_results, site=site, timelimit=timelimit)
    if not raw_results:
        return {"articles": {}, "segments": {}, "_texts": {}}

    sem_fetch = asyncio.Semaphore(MAX_PARALLEL)
    sem_llm = asyncio.Semaphore(MAX_PARALLEL)

    async def _bounded_fetch(item, aid):
        async with sem_fetch:
            return await extract_and_chunk_async(item, aid)

    # ============================================================
    # Phase 1: 并行提取 + 切块 → ChunkUnit 池
    # ============================================================
    fetch_tasks = [_bounded_fetch(item, f"a_{i+1:02d}") for i, item in enumerate(raw_results)]
    chunk_lists = await asyncio.gather(*fetch_tasks)
    chunk_pool = [cu for cl in chunk_lists for cu in cl]

    # ============================================================
    # Phase 2: 并行 LLM 推理（全量块一并送入）
    # ============================================================
    async def _infer_chunk(cu: ChunkUnit) -> dict:
        if mode == "summary":
            prompt = build_summary_prompt(cu.paragraphs, query=query, keyword=keyword)
            raw = await _call_llm(prompt)
            parsed = parse_summary_output(raw)
            return {"article_id": cu.article_id, "cu": cu, "parsed": parsed}
        else:
            prompt = build_grouping_prompt(cu.paragraphs)
            raw = await _call_llm(prompt)
            groups = parse_grouping(raw)
            for g in groups:
                g["start_p"] += cu.para_offset
                g["end_p"] += cu.para_offset
                if "paragraphs" in g:
                    g["paragraphs"] = [p + cu.para_offset for p in g["paragraphs"]]
            return {"article_id": cu.article_id, "cu": cu, "groups": groups}

    async def _bounded_infer(cu):
        async with sem_llm:
            return await _infer_chunk(cu)

    chunk_results = await asyncio.gather(*[_bounded_infer(cu) for cu in chunk_pool])

    # ============================================================
    # Phase 3: 按 article_id 分组 → 并行合并
    # ============================================================
    from collections import defaultdict
    by_article = defaultdict(list)
    for cr in chunk_results:
        by_article[cr["article_id"]].append(cr)

    articles = {}
    all_segments = {}
    all_texts = {}

    async def _merge_article(aid: str, cr_list: list):
        cu0 = cr_list[0]["cu"]
        total_charnum = sum(len(p) for c in cr_list for p in c["cu"].paragraphs)
        all_paras = sum([c["cu"].paragraphs for c in cr_list], [])

        if mode == "summary":
            parsed_list = [c["parsed"] for c in cr_list]
            summaries = [p["summary_objective"] for p in parsed_list if p["summary_objective"]]
            if len(summaries) > 1:
                merge_raw = await _call_llm(build_merge_prompt(summaries, query=query, keyword=keyword))
                unified_summary = parse_merge_output(merge_raw)
            else:
                unified_summary = summaries[0] if summaries else ""

            all_relevant = []
            for p in parsed_list:
                r = p["summary_relevant"]
                if r and r not in all_relevant:
                    all_relevant.append(r)

            all_key_points = []
            kp_chunk_map = []
            for ci, p in enumerate(parsed_list):
                for kp in p["key_points"]:
                    if kp not in all_key_points:
                        all_key_points.append(kp)
                        kp_chunk_map.append(ci)

            texts_data = {
                "_chunks": [c["cu"].paragraphs for c in cr_list],
                "_kp_chunk_map": kp_chunk_map,
            }

            return {
                "title": cu0.title, "url": cu0.url, "date": cu0.date,
                "snippet": cu0.snippet, "source": cu0.source,
                "charnum": total_charnum, "mode": "summary",
                "summary": unified_summary,
                "summary_relevant": all_relevant,
                "key_points": all_key_points,
                "segments": [],
            }, {}, texts_data

        else:
            all_groups = []
            for c in cr_list:
                all_groups.extend(c["groups"])
            if not all_groups:
                return None, {}, None

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
            covered = set()
            for g in groups:
                for pn in range(g["start_p"], g["end_p"] + 1):
                    covered.add(pn)
            n_total = sum(len(c["cu"].paragraphs) for c in cr_list)
            missing = sorted(set(range(1, n_total + 1)) - covered)
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

            segment_texts = {}
            segments_out = []
            article_segments = {}
            for gi, g in enumerate(groups, 1):
                s = max(0, g["start_p"] - 1)
                e = min(n_total, g["end_p"])
                group_text = '\n\n'.join(all_paras[s:e])
                charnum = len(group_text)
                seg_id = f"s{gi}"
                segments_out.append({"id": seg_id, "charnum": charnum})
                segment_texts[seg_id] = group_text
                sid = f"{aid}_{seg_id}"
                seg_item = {"article_id": aid, "point": g["point"],
                            "summary": g["summary"], "charnum": charnum}
                if g.get("keywords"):
                    seg_item["keywords"] = g["keywords"]
                article_segments[sid] = seg_item

            return {
                "title": cu0.title, "url": cu0.url, "date": cu0.date,
                "snippet": cu0.snippet, "source": cu0.source,
                "charnum": total_charnum, "segments": segments_out,
            }, {**article_segments, "_texts": segment_texts}, None

    merge_results = await asyncio.gather(*[_merge_article(aid, crs) for aid, crs in by_article.items()])

    for aid, (art_entry, extra, texts_data) in zip(by_article.keys(), merge_results):
        if art_entry is None:
            continue
        articles[aid] = art_entry
        if extra:
            segs = {k: v for k, v in extra.items() if k != "_texts"}
            all_segments.update(segs)
            if "_texts" in extra:
                all_texts[aid] = extra["_texts"]
        if texts_data:
            all_texts[aid] = texts_data

    return {"articles": articles, "segments": all_segments, "_texts": all_texts}

    # (旧版 for 循环已移除，改为上面的三阶段并行架构)
