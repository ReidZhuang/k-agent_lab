"""
stage3.py — 可选精炼模块

用法（在 core 外调用）：
    from stage3 import refine_groups
    refined = await refine_groups(paragraphs, groups)

流程：
  将 stage2 合并后的分组 + 带行号的原文 → 送入 LLM 复核精炼
  分组不变，只优化要点/概括/关键字的准确性和简洁性
"""
import json, os, time, re
import httpx

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

OLLAMA_URL = f"{cfg['ollama']['endpoint']}/api/generate"
MODEL = cfg["ollama"]["models"]["default"]
OLLAMA_TIMEOUT = cfg["ollama"]["timeout"]
OLLAMA_NUM_PREDICT = cfg["ollama"]["num_predict"]
OLLAMA_TEMP = cfg["ollama"]["temperature"]

STAGE3_PROMPT = """任务：复核【分组方案】中的每个分组，检查其段落编号范围对应的【正文】内容，与分组的【要点】、【概括】、【关键字】是否一致，并对文字进行精炼。

概念说明：
- 【段落】：指【正文】中已编号的文本单元[P1]、[P2]...[P{n}]。
- 【正文】：指【段落】[P1]至[P{n}]组成的完整文本内容。
- 【分组】：一组相邻段落的集合，包含段落编号范围、要点、概括、关键字。
- 【要点】：该组覆盖正文内容的核心话题（15-50字），多个主题用" + "连接。
- 【概括】：该组覆盖正文内容的关键信息浓缩（50-100字），包含具体数据或结论。
- 【关键字】：该组要点和概括中的核心对象（不超过10字），多个关键字用+连接。

复核要求：
- 对照【正文】中的段落内容，检查【要点】、【概括】、【关键字】是否准确
- 对文字进行精炼，去除冗余
- 分组不变，不得修改段落编号范围
- 只输出复核后的分组方案，不要输出复核过程

输出格式（严格按此格式）：
【分组】段落：【段落信息】
要点： 【要点信息】
概括： 【概括信息】
关键字： 【关键字信息】

【正文】：
{numbered_body}

【分组方案】：
{groups_text}
"""


def _build_groups_text(groups: list) -> str:
    """将 groups 列表格式化为【分组方案】文本"""
    lines = []
    for g in groups:
        ps = g.get("paragraphs", list(range(g["start_p"], g["end_p"] + 1)))
        p_range = f"P{min(ps)}-P{max(ps)}" if min(ps) != max(ps) else f"P{min(ps)}"
        lines.append(f"【分组】段落：{p_range}")
        lines.append(f"要点：{g.get('point', '')}")
        lines.append(f"概括：{g.get('summary', '')}")
        lines.append(f"关键字：{g.get('keywords', '')}")
        lines.append("")
    return '\n'.join(lines).strip()


async def refine_groups(paragraphs: list, groups: list) -> list:
    """
    精炼分组：对照原文复核要点/概括/关键字，分组不变。

    参数：
        paragraphs: 全文段落列表（用于构建带编号的正文）
        groups: stage2 输出分组列表

    返回：
        精炼后的分组列表（结构与输入相同，文字优化）
    """
    n = len(paragraphs)
    numbered_body = '\n\n'.join([f'[P{i+1}] {p}' for i, p in enumerate(paragraphs)])
    groups_text = _build_groups_text(groups)

    prompt = STAGE3_PROMPT.format(
        n=n,
        numbered_body=numbered_body,
        groups_text=groups_text
    )

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
        print(f"[stage3] LLM error: {e}")
        return groups
    finally:
        if old_http: os.environ["http_proxy"] = old_http
        if old_https: os.environ["https_proxy"] = old_https

    # 解析
    from core import parse_grouping, consolidate_ranges
    refined = parse_grouping(raw)
    if not refined:
        print("[stage3] 解析失败，返回原始分组")
        return groups

    # 保留原始 group_id（分组顺序不变）
    for i, g in enumerate(refined, 1):
        g["group_id"] = i

    refined = consolidate_ranges(refined)
    return refined
