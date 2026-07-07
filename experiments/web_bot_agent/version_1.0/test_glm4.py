"""
glm4:9b-chat-q4_K_M 快速测试 — 真实场景分组 + MD 输出
用法: python test_glm4.py
"""
import json, os, sys, re, time, asyncio
import httpx

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))

from core import search_web, fetch_and_extract_async, split_paragraphs, build_grouping_prompt, parse_grouping

# 用测试文章（不搜索，直接指定几篇典型长文来测）
TEST_URLS = [
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Large_language_model",
]

OLLAMA_URL = "http://localhost:11434/api/generate"

async def infer_once(paragraphs, max_groups=5, label=""):
    prompt = build_grouping_prompt(paragraphs, max_groups)
    payload = {
        "model": "glm4:9b-chat-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.1}
    }
    old_http = os.environ.pop("http_proxy", None)
    old_https = os.environ.pop("https_proxy", None)
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            result = resp.json()
            elapsed = time.time() - t0
            raw = result.get("response", "").strip()
            return raw, elapsed
    except Exception as e:
        return f"[错误] {e}", 0
    finally:
        if old_http: os.environ["http_proxy"] = old_http
        if old_https: os.environ["https_proxy"] = old_https


async def test():
    for idx, url in enumerate(TEST_URLS):
        print(f"\n{'='*80}")
        print(f"📄 测试文章 #{idx+1}: {url}")
        print(f"{'='*80}")

        # 提取正文
        body, date, html_len, paragraphs = await fetch_and_extract_async(url)
        print(f"  字数: {len(body)} | 段落数: {len(paragraphs)} | 发布日期: {date or 'N/A'}")

        if not paragraphs:
            print("  ❌ 无正文内容")
            continue

        # 分割
        parts = split_paragraphs(paragraphs)
        print(f"  分割块数: {len(parts)}")
        for pi, part in enumerate(parts):
            part_len = sum(len(p) for p in part)
            print(f"    块{pi+1}: {len(part)}段, {part_len}字")

        # LLM 推理
        all_groups = []
        offset = 0
        for pi, part in enumerate(parts):
            max_g = 3 if len(parts) > 1 else 5
            print(f"\n  ⏳ LLM 推理 块{pi+1}/{len(parts)} (max_groups={max_g})...")
            raw, elapsed = await infer_once(part, max_groups=max_g, label=f"art{idx+1}_part{pi+1}")
            groups = parse_grouping(raw)

            # 偏移
            for g in groups:
                g["start_p"] += offset
                g["end_p"] += offset
            all_groups.extend(groups)

            offset += len(part)

            # 输出原始 LLM 响应
            print(f"  ⌛ 耗时: {elapsed:.1f}s")
            print(f"  📝 LLM 原始输出:\n{raw}\n")

        if not all_groups:
            print("  ❌ 未解析到分组")
            continue

        # 合并相邻重叠分组
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
                    groups.append({"group_id": 99, "start_p": start, "end_p": end, "point": "[补充]", "summary": "LLM遗漏的段落"})
                    start = pn
                    end = pn
            groups.append({"group_id": 99, "start_p": start, "end_p": end, "point": "[补充]", "summary": "LLM遗漏的段落"})

        print(f"\n  🔗 合并后分组数: {len(groups)}")

        # ===== Markdown 格式输出 =====
        md = f"""## 文章 {idx+1}) 分组结果

| 组 | 段落范围 | 要点 | 概括 |
|---|---|---|---|
"""
        for g in groups:
            seg_range = f"P{g['start_p']}–P{g['end_p']}" if g['start_p'] != g['end_p'] else f"P{g['start_p']}"
            md += f"| 组{g['group_id']} | {seg_range} | {g['point']} | {g['summary']} |\n"

        print(md)

        # 输出每个分组的原文预览
        print("  **各组原文预览：**\n")
        for g in groups:
            s = max(0, g["start_p"] - 1)
            e = min(len(paragraphs), g["end_p"])
            group_text = '\n\n'.join(paragraphs[s:e])
            seg_range = f"P{g['start_p']}–P{g['end_p']}" if g['start_p'] != g['end_p'] else f"P{g['start_p']}"
            preview = group_text[:200] + "..." if len(group_text) > 200 else group_text
            print(f"  **组{g['group_id']} ({seg_range})** — {g['point']}")
            print(f"  > {preview.replace(chr(10), chr(10)+'  > ')}")
            print()

        print(f"  {'—'*60}")


if __name__ == "__main__":
    asyncio.run(test())
