"""
随机10支股票测试脚本 — 验证 fetch_all 完整链路

步骤:
  1. 从 DB mid_stock_intraday 获取今日午间快照的股票池
  2. 随机选 10 支
  3. 调用 fetch_all 获取完整数据
  4. 输出 result['all'] + 个股详情到 markdown
"""

import sys, json, random
from pathlib import Path

MID_DIR = Path(__file__).resolve().parent.parent
if str(MID_DIR) not in sys.path:
    sys.path.insert(0, str(MID_DIR))

from fetch_midday_data import fetch_all

ETL_DIR = MID_DIR.parent.parent / "etl"
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))
from db_manager import DatabaseManager
from config import DB_PATH

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

db = DatabaseManager(str(DB_PATH))

# ─── 1. 从今日快照获取股票池 ───
if db.table_exists("mid_stock_intraday"):
    times = db.execute(
        "SELECT DISTINCT fetch_time FROM mid_stock_intraday ORDER BY fetch_time DESC LIMIT 1"
    )
    if times:
        snap_time = times[0][0]
        rows = db.execute(
            "SELECT DISTINCT name FROM mid_stock_intraday WHERE fetch_time=? AND name IS NOT NULL",
            (snap_time,)
        )
        pool = [r[0] for r in rows if r[0]]
        print(f"📦 股票池: {len(pool)} 只 (快照时间 {snap_time})")
    else:
        pool = []
        print("⚠️  mid_stock_intraday 无数据")
else:
    pool = []
    print("⚠️  表 mid_stock_intraday 不存在")

if not pool:
    print("❌ 股票池为空，使用预设列表")
    pool = ['贵州茅台', '宁德时代', '中国平安', '招商银行', '长江电力',
            '比亚迪', '美的集团', '五粮液', '药明康德', '伊利股份',
            '迈瑞医疗', '恒瑞医药', '海康威视', '万华化学', '阳光电源',
            '紫金矿业', '中兴通讯', '立讯精密', '格力电器', '东方财富']

# ─── 2. 随机选 10 支 ───
selected = random.sample(pool, min(10, len(pool)))
print(f"🎯 随机选中: {selected}")
print()

# ─── 3. 调用 fetch_all ───
result = fetch_all(selected)

# ─── 4. 输出到文件 ───
output_path = OUTPUT_DIR / f"test_random10_{random.randint(1000,9999)}.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("# 随机10支股票 — 完整测试结果\n\n")
    f.write(f"- 测试时间: 2026-07-24\n")
    f.write(f"- 股票池数量: {len(pool)}\n")
    f.write(f"- 随机选中: {selected}\n\n")
    f.write("---\n\n")

    # result['all']
    f.write("## 📈 全市场情绪\n\n")
    f.write(result.get("all", "❌ 无数据") + "\n\n")
    f.write("---\n\n")

    # 逐个个股
    for stock in selected:
        text = result.get(stock, "")
        f.write(f"## {stock}\n\n")
        f.write(text + "\n\n")
        f.write("---\n\n")

    # JSON 结构预览
    f.write("## JSON 结构预览\n\n")
    summary = {}
    for k, v in result.items():
        if k == "all":
            summary[k] = "str (全市场情绪)"
        else:
            summary[k] = f"str ({len(v)} chars, {len(v.split(chr(10)))} lines)"
    f.write(f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n")

print(f"✅ 已保存到: {output_path}")

# ─── 5. 同时终端输出摘要 ───
print("=" * 60)
print("📈 全市场情绪")
print("=" * 60)
print(result.get("all", ""))
print()

for stock in selected:
    text = result.get(stock, "")
    lines = text.split("\n")

    # 取前几行关键信息
    title = lines[0] if lines else stock
    kw_line = next((l for l in lines if "股票涉及行业关键词" in l), "")
    price_line = next((l for l in lines if "当前价" in l and "涨跌幅" in l), "")

    print(f"── {title} ──")
    if kw_line:
        print(f"  {kw_line}")
    if price_line:
        # 提取关键字段
        parts = price_line.split("|")
        info = [p.strip() for p in parts if any(k in p for k in ["当前价","涨跌幅","换手率","成交额"])]
        print(f"  {' | '.join(info)}")
    print()
