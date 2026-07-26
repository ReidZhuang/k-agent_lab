"""
测试脚本：验证 fetch_all + 财联社市场情绪集成
股票列表：淮北矿业, 博瑞医药, 凯莱英, 广生堂

输出：
  1. result['all'] — 全市场情绪（独立展示）
  2. 个股输出（完整 md 文本解析）
  3. 输出文件保存到 test_drive/results/
"""

import sys
import json
from pathlib import Path

# 加入 mid 模块路径
MID_DIR = Path(__file__).resolve().parent.parent
if str(MID_DIR) not in sys.path:
    sys.path.insert(0, str(MID_DIR))

from fetch_midday_data import fetch_all

STOCKS = ['淮北矿业', '博瑞医药', '凯莱英', '广生堂']
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print(f"📊 测试 fetch_all + 财联社市场情绪")
print(f"股票列表: {STOCKS}")
print("=" * 60)
print()

# 调用统一入口
result = fetch_all(STOCKS)

# ─── 1. 全市场情绪（result['all']） ───
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("📈 [全市场情绪] result['all']")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(result.get("all", "❌ 无数据"))
print()

# ─── 2. 逐个展示个股输出 ───
for stock in STOCKS:
    text = result.get(stock, "")
    if not text:
        print(f"❌ {stock}: 无数据")
        continue
    print("━" * 60)
    print(f"📄 {stock}")
    print("━" * 60)
    print(text)
    print()

# ─── 3. 保存到文件 ───
output_path = OUTPUT_DIR / "test_cls_emotion_4stocks_20260724.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("# 测试结果：fetch_all + 财联社市场情绪\n\n")
    f.write(f"- 测试时间: 2026-07-24\n")
    f.write(f"- 股票列表: {STOCKS}\n")
    f.write(f"- 测试内容: fetch_market_emotion + fetch_all 集成\n\n")
    f.write("---\n\n")

    # all
    f.write("## 📈 全市场情绪\n\n")
    f.write(result.get("all", "❌ 无数据") + "\n\n")
    f.write("---\n\n")

    # per stock
    for stock in STOCKS:
        text = result.get(stock, "")
        f.write(f"## {stock}\n\n") if not text.startswith(f"## {stock}") else None
        f.write(text + "\n\n")
        f.write("---\n\n")

    # JSON 版本（结构预览）
    f.write("## JSON 结构预览\n\n")
    # Show keys and types
    summary = {}
    for k, v in result.items():
        if k == "all":
            summary[k] = "str (全市场情绪)"
        else:
            summary[k] = f"str ({len(v)} chars)"
    f.write(f"```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n")

print(f"✅ 已保存到: {output_path}")
