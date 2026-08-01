"""
测试脚本：调用 fetch_message.py — 淮北矿业、博瑞医药、凯莱英、广生堂

输出：
  - results/message_dict_4stocks.txt   → fetch_all 原始 dict（JSON）
  - results/message_report_4stocks.md  → 可读 Markdown 报告

运行:
  conda run -n stock_agent python run_message_test_4stocks.py
"""

import sys
import json
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

MIDDAY_DIR = Path(__file__).resolve().parent.parent
ETL_DIR = MIDDAY_DIR.parent / "etl"
for d in [str(MIDDAY_DIR), str(ETL_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from fetch_message import fetch_all

TEST_STOCKS = ["淮北矿业", "博瑞医药", "凯莱英", "广生堂"]


def save_raw_dict(data: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 原始 dict → {path}")


def save_readable_report(data: dict, path: Path):
    lines = [
        "# 盘中消息补充测试报告\n",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**测试股票**: {'、'.join(TEST_STOCKS)}\n",
        "---\n",
    ]
    for name, content in data.items():
        lines.append(f"\n{'=' * 80}")
        lines.append(f"\n## {name}\n")
        lines.append(content)
        lines.append(f"\n{'=' * 80}\n")
    lines.append("\n---\n")
    lines.append("*报告结束*\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✓ 可读报告 → {path}")


def main():
    print(f"🔍 测试股票: {TEST_STOCKS}")
    print("⏳ 正在获取午间消息补充（快讯 + 热门板块 + 跌停 + 异动）...\n")

    data = fetch_all(TEST_STOCKS)

    print(f"\n📊 取数完成，共 {len(data)} 只股票\n")

    save_raw_dict(data, OUTPUT_DIR / "message_dict_4stocks.txt")
    save_readable_report(data, OUTPUT_DIR / "message_report_4stocks.md")

    # 统计
    labels = ["今日快讯", "热门板块上涨原因", "跌停监控", "盘中异动监测"]
    print(f"\n{'股票名称':<8} {'快讯':<5} {'板块':<5} {'跌停':<5} {'异动':<5}")
    print("-" * 33)
    for name, content in data.items():
        hits = ["✅" if f"【{l}】" in content else "—" for l in labels]
        print(f"{name:<8} {hits[0]:<5} {hits[1]:<5} {hits[2]:<5} {hits[3]:<5}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()
