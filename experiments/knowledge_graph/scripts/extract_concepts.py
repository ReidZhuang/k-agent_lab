#!/usr/bin/env python3
"""从 kg_design_deepseek_v4.md 提取 IntentConcept 并生成 CSV"""
import csv, re, json

MD_PATH = "../design/kg_design_deepseek_v4.md"
CSV_PATH = "../data/concepts.csv"

with open(MD_PATH) as f:
    text = f.read()

# 按概念分组: 每个 Concept 是 "#### N." 开始的节
# 格式示例:
# #### 1. 市场整体行情
# ...
# | **属性** | **内容** |
# | :--- | :--- |
# | **id** | CONCEPT_MARKET_INDEX |
# | **name** | 市场整体行情 |
# ...

concepts = []
current_id = ""
current_name = ""
current_desc = ""
current_keywords = ""
current_entity = "[]"
current_fields = ""
current_urls = ""

lines = text.split("\n")
in_concept = False
in_table = False

for i, line in enumerate(lines):
    stripped = line.strip()

    # 检测 Concept 的开始: "#### \d+." 开头
    m = re.match(r"^####\s+(\d+)\.\s+(.+)", stripped)
    if m:
        # 保存上一个
        if current_id:
            concepts.append({
                "id": current_id,
                "name": current_name,
                "description": current_desc,
                "seed_keywords": current_keywords,
                "requires_entity": current_entity,
                "default_seed_fields": current_fields,
                "site_search_urls": current_urls
            })
        # 重置
        current_id = ""
        current_name = m.group(2).strip()
        current_desc = ""
        current_keywords = ""
        current_entity = "[]"
        current_fields = ""
        current_urls = ""
        in_concept = True
        in_table = False
        continue

    if not in_concept:
        continue

    # 检测属性表行
    if stripped.startswith("| **") and "|" in stripped:
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) >= 2:
            key = cells[0].replace("**", "").strip()
            val = cells[1].strip()

            if key == "id":
                current_id = val
            elif key == "name":
                current_name = val
            elif key == "description":
                current_desc = val
            elif key == "seed_keywords":
                current_keywords = val
            elif key == "requires_entity":
                current_entity = val if val != "[]" else "[]"
            elif key == "default_seed_fields":
                current_fields = val
            elif key == "site_search_urls":
                current_urls = val

# 最后一个
if current_id:
    concepts.append({
        "id": current_id,
        "name": current_name,
        "description": current_desc,
        "seed_keywords": current_keywords,
        "requires_entity": current_entity,
        "default_seed_fields": current_fields,
        "site_search_urls": current_urls
    })

with open(CSV_PATH, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=concepts[0].keys())
    w.writeheader()
    w.writerows(concepts)

print(f"IntentConcept: 提取 {len(concepts)} 条 -> {CSV_PATH}")
for c in concepts:
    print(f"  {c['id']}: {c['name']}")
