#!/usr/bin/env python3
"""从 kg_design_deepseek_v4.md 提取 DataSource 并生成 CSV"""
import csv, re

MD_PATH = "../design/kg_design_deepseek_v4.md"
CSV_PATH = "../data/sources.csv"

with open(MD_PATH) as f:
    text = f.read()

# 定位到第五部分 DataSource
sections = text.split("### ")
sources_section = [s for s in sections if s.startswith("5.")]
target = "\n".join(sources_section)

# 提取每个表格行
rows = []
for line in target.split("\n"):
    line = line.strip()
    if line.startswith("|") and not line.startswith("|:") and not line.startswith("|---"):
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 6:
            rows.append(cells)

# 只保留有 ID 的有效行
sources = []
for cells in rows:
    ds_id = cells[0].strip()
    if ds_id.startswith("DS_") and len(ds_id) > 4:
        name = cells[1]
        protocol = cells[2]
        authority = cells[3]
        refresh_time = cells[4]
        reliability = cells[5]
        sources.append({
            "id": ds_id,
            "name": name,
            "protocol": protocol,
            "execution_meta": "{}",
            "authority_level": authority,
            "refresh_time": refresh_time,
            "reliability_score": reliability,
            "latency_ms": "",
            "code_format": "",
            "prompt_dir": ""
        })

with open(CSV_PATH, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=sources[0].keys())
    w.writeheader()
    w.writerows(sources)

print(f"DataSource: 提取 {len(sources)} 条 -> {CSV_PATH}")
for s in sources[:5]:
    print(f"  {s['id']}: {s['name']} ({s['protocol']}, {s['authority_level']})")
print(f"  ...")
