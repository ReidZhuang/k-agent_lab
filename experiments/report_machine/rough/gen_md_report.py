"""
从 JSON 生成可读性强的 MD 报告
"""
import json, os, re
from collections import Counter

json_path = "/home/stockagent/project_space/research/experiments/report_machine/rough/sina_sz300750_news_20260717_175627.json"

with open(json_path, encoding="utf-8") as f:
    data = json.load(f)

stock_code = data["stock_code"]
all_news = data["news"]

# ========== 清洗 ==========
# 1. 去掉无关链接（登录、注册等）
noise_keywords = ["找回密码", "登录帮助", "新用户注册", "login"]
cleaned = [n for n in all_news if not any(kw in n["title"] for kw in noise_keywords)]

# 2. 去重（相同标题+URL视为重复）
seen = set()
unique = []
for n in cleaned:
    key = (n["title"], n["url"])
    if key not in seen:
        seen.add(key)
        unique.append(n)

# ========== 分类 ==========
categories = {
    "钠电/储能": [],
    "订单/合作": [],
    "机构评级/研报": [],
    "股价/交易": [],
    "专利/技术": [],
    "产业/行业": [],
    "政策": [],
    "其他": [],
}

def classify(item):
    t = item["title"]
    if any(kw in t for kw in ["钠电", "储能", "钠离子"]):
        return "钠电/储能"
    if any(kw in t for kw in ["订单", "合作", "签", "Alfen"]):
        return "订单/合作"
    if any(kw in t for kw in ["评级", "研报", "伯恩斯坦", "摩根", "目标价", "跑赢"]):
        return "机构评级/研报"
    if any(kw in t for kw in ["大宗交易", "成交额", "涨停", "股价", "融资买入", "净卖出"]):
        return "股价/交易"
    if any(kw in t for kw in ["专利", "实用新型", "授权"]):
        return "专利/技术"
    if any(kw in t for kw in ["产业", "行业", "装机", "增长", "数据", "销量", "产能"]):
        return "产业/行业"
    if any(kw in t for kw in ["政策", "税", "监管", "三部门"]):
        return "政策"
    return "其他"

for n in unique:
    cat = classify(n)
    categories[cat].append(n)

# ========== 生成 MD ==========
md = f"""# 宁德时代 (sz300750) — 个股新闻日报

**抓取日期**: 2026-07-17
**数据来源**: 新浪财经个股新闻列表页
**新闻总数**: {len(unique)} 条（清洗去重后，原始 {len(all_news)} 条）
**日期范围**: 2026-07-17 全天

---

## 目录

"""

for cat, items in categories.items():
    if items:
        md += f"- [{cat}（{len(items)} 条）](#{cat.lower().replace('/', '')})\n"

md += "\n---\n\n"

for cat, items in categories.items():
    if not items:
        continue
    anchor = cat.lower().replace("/", "").replace(" ", "-")
    md += f"## {cat}（{len(items)} 条）\n\n"
    for i, n in enumerate(items, 1):
        md += f"### {i}. {n['title']}\n\n"
        md += f"- **日期**: {n['date']}\n"
        md += f"- **链接**: [{n['url'][:70]}...]({n['url']})\n\n"
    md += "---\n\n"

# 写入
output_path = json_path.replace(".json", ".md")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(md)

print(f"已生成: {output_path}")
print(f"清洗前: {len(all_news)} 条 → 去噪去重后: {len(unique)} 条")
for cat, items in categories.items():
    if items:
        print(f"  {cat}: {len(items)} 条")
