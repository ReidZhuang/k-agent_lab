#!/usr/bin/env python3
"""从 datafield_detailed_design.md 提取 DataField 并生成 CSV"""
import csv, re, json

MD_PATH = "../design/datafield_detailed_design.md"
CSV_PATH = "../data/fields.csv"

with open(MD_PATH) as f:
    lines = f.readlines()

# 定位表格行
fields = []
current_concept = ""
current_source = ""

for line in lines:
    line_stripped = line.strip()

    # 检测 Concept 标题行
    m = re.match(r"^### CONCEPT_(\w+)", line_stripped)
    if m:
        current_concept = f"CONCEPT_{m.group(1)}"
        continue

    # 检测默认数据源行
    m = re.match(r"> 默认数据源[：:]\s*(.+)$", line_stripped)
    if m:
        current_source = m.group(1).strip()
        continue

    # 检测表格行（有编号列和ID列的表格）
    if line_stripped.startswith("|") and not line_stripped.startswith("|:") and not line_stripped.startswith("|---"):
        cells = [c.strip() for c in line_stripped.split("|")[1:-1]]
        # 标准表格: # | ID | standard_name | alias | description | data_type | unit | 权威 | 时效 | 默认数据源ID
        if len(cells) >= 10:
            # 检查第一列是否为数字序号
            if re.match(r"^\d+$", cells[0]) and cells[1].startswith("FIELD_"):
                field_id = cells[1]
                std_name = cells[2]

                # alias: 从 Python 字面量解析
                alias_raw = cells[3]
                try:
                    alias_list = json.loads(alias_raw.replace("'", '"'))
                except:
                    alias_list = []

                desc = cells[4]
                d_type = cells[5]
                unit = cells[6]
                authority = cells[7]
                refresh = cells[8]
                ds_id = cells[9]

                # 如果最后列是空或短横线，尝试看下一列
                if ds_id in ["—", "—", "-", ""]:
                    if len(cells) > 10:
                        ds_id = cells[10]

                fields.append({
                    "id": field_id,
                    "standard_name": std_name,
                    "alias": json.dumps(alias_list, ensure_ascii=False),
                    "description": desc,
                    "data_type": d_type,
                    "unit": unit,
                    "authority_level": authority,
                    "refresh_time": refresh,
                    "default_datasource_id": ds_id,
                    "belongs_to_concept": current_concept
                })

with open(CSV_PATH, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields[0].keys())
    w.writeheader()
    w.writerows(fields)

print(f"DataField: 提取 {len(fields)} 条 -> {CSV_PATH}")
# 按 Concept 分组统计
from collections import Counter
concept_counts = Counter(f["belongs_to_concept"] for f in fields)
for c, n in concept_counts.most_common(10):
    print(f"  {c}: {n}")
if len(concept_counts) > 10:
    print(f"  ... 共 {len(concept_counts)} 个 Concept")
