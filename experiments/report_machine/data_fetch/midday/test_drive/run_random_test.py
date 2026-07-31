"""
随机测试 10 支股票 — 验证 MG 关键词匹配算法
"""
import sys
import json
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

MIDDAY_DIR = Path(__file__).resolve().parent.parent
ETL_DIR = MIDDAY_DIR.parent.parent / "etl"
KG_DIR = MIDDAY_DIR.parent.parent / "knowledge_graph"
for d in [str(MIDDAY_DIR), str(ETL_DIR), str(KG_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from db_manager import DatabaseManager
from config import DB_PATH
from fetch_midday_message import fetch_all

# 随机取 10 只股票
db = DatabaseManager(str(DB_PATH))
rows = db.execute("SELECT DISTINCT name FROM mid_stock_intraday ORDER BY RANDOM() LIMIT 10")
TEST_STOCKS = [r[0] for r in rows]

print(f"🔍 随机测试股票: {TEST_STOCKS}")
print("⏳ 正在获取午间消息补充...\n")

data = fetch_all(TEST_STOCKS)

print(f"\n📊 取数完成，共 {len(data)} 只股票\n")

# 保存原始 dict
dict_path = OUTPUT_DIR / "message_random_dict.txt"
with open(dict_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"  ✓ 原始 dict → {dict_path}")

# 生成可读报告
lines = [
    "# 盘中消息补充随机测试报告\n",
    f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
    f"**测试股票**: {'、'.join(TEST_STOCKS)}\n",
    "---\n",
]
for name, content in data.items():
    lines.append(f"\n{'=' * 80}")
    lines.append(f"\n## {name}\n")
    lines.append(content)
    lines.append(f"\n{'=' * 80}\n")
lines.append("\n---\n*报告结束*\n")

report_path = OUTPUT_DIR / "message_random_report.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"  ✓ 可读报告 → {report_path}")

# 统计
labels = ["今日快讯", "热门板块上涨原因", "跌停监控", "盘中异动监测"]
print(f"\n{'股票名称':<10} {'快讯':<6} {'板块':<6} {'跌停':<6} {'异动':<6}  匹配关键词")
print("-" * 70)
for name, content in data.items():
    hits = ["✅" if f"【{l}】" in content else "—" for l in labels]
    # 提取关键词信息
    kw_info = ""
    for line in content.split("\n"):
        if "相关关键词" in line:
            kws = line.split(":")[-1].strip()
            kw_info = kws[:40]
            break
        elif "相关方式" in line and "名称匹配" in line:
            kw_info = "名称匹配"
            break
        elif "相关方式" in line and "代码匹配" in line:
            kw_info = "代码匹配"
            break
    print(f"{name:<10} {hits[0]:<6} {hits[1]:<6} {hits[2]:<6} {hits[3]:<6}  {kw_info}")

print("\n✅ 随机测试完成")
