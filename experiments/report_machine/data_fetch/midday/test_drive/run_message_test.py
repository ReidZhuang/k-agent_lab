"""
测试脚本：调用 fetch_message.py 的 fetch_all，验证消息补充功能

输出：
  - results/message_dict.txt       → fetch_all 返回的原始 dict（JSON 格式）
  - results/message_report.md      → 可读的 Markdown 报告

运行:
  conda run -n stock_agent python run_message_test.py
"""

import sys
import json
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# 将被测模块加入路径
MIDDAY_DIR = Path(__file__).resolve().parent.parent
ETL_DIR = MIDDAY_DIR.parent / "etl"
for d in [str(MIDDAY_DIR), str(ETL_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

OUTPUT_DIR = Path(__file__).parent / "results"

from fetch_message import fetch_all

TEST_STOCKS = ["光启技术", "贝达药业", "煌上煌", "药康生物", "腾景科技",
                "源杰科技", "飞南资源", "爱施德", "华工科技", "百润股份"]


def save_raw_dict(data: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 原始 dict 已保存: {path}")


def save_readable_report(data: dict, path: Path):
    lines = [
        "# 盘中消息补充测试报告\n",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**测试股票**: {'、'.join(TEST_STOCKS)}\n",
        "---\n",
    ]
    for name, content in data.items():
        lines.append(f"\n{'=' * 80}")
        lines.append(f"\n# {name}\n")
        lines.append(content)
        lines.append(f"\n{'=' * 80}\n")
    lines.append("\n---\n")
    lines.append("*报告结束*\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✓ 可读报告已保存: {path}")


def main():
    print(f"🔍 测试股票: {TEST_STOCKS}")
    print("⏳ 正在获取消息补充（快讯 + 热门板块 + 跌停 + 异动）...\n")

    data = fetch_all(TEST_STOCKS)

    print(f"\n📊 取数完成，共 {len(data)} 只股票\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_raw_dict(data, OUTPUT_DIR / "message_dict.txt")
    save_readable_report(data, OUTPUT_DIR / "message_report.md")

    # 统计各股票的命中情况
    sections_labels = ["今日快讯", "热门板块", "跌停监控", "异动检测"]
    print(f"\n{'股票名称':<10} {'快讯':<5} {'板块':<5} {'跌停':<5} {'异动':<5}")
    print("-" * 35)
    for name, content in data.items():
        hits = [
            "✅" if f"【{s}】" in content else "❌"
            for s in ["今日快讯", "热门板块上涨原因", "跌停监控", "盘中异动监测"]
        ]
        print(f"{name:<10} {hits[0]:<5} {hits[1]:<5} {hits[2]:<5} {hits[3]:<5}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()
