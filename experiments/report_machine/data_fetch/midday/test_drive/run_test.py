"""
测试脚本：调用 fetch_midday_data.py 的 fetch_all，验证补充信息功能

输出：
  - results/raw_dict.txt       → fetch_all 返回的原始 dict（JSON 格式）
  - results/readable_report.md → 可读的 Markdown 报告（每只股票一个文档块）

运行:
  conda run -n stock_agent python run_test.py
"""

import sys
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# 将被测模块加入路径
MIDDAY_DIR = Path(__file__).resolve().parent.parent
ETL_DIR = MIDDAY_DIR.parent / "etl"
for d in [str(MIDDAY_DIR), str(ETL_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

OUTPUT_DIR = Path(__file__).parent / "results"

from fetch_midday_data import fetch_all

TEST_STOCKS = ["光启技术", "贝达药业", "煌上煌", "药康生物", "腾景科技",
              "源杰科技", "飞南资源", "爱施德", "华工科技", "百润股份"]


def save_raw_dict(data: dict, path: Path):
    """保存原始 dict 为格式化的 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 原始 dict 已保存: {path}")


def save_readable_report(data: dict, path: Path):
    """将 dict 解析为可读 Markdown 文档"""
    lines = [
        "# 盘中数据取数测试报告\n",
        f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
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
    print("⏳ 正在取数（包含补充信息：昨日公告 + 昨日波动）...\n")

    # 执行取数
    data = fetch_all(TEST_STOCKS)

    print(f"\n📊 取数完成，共 {len(data)} 只股票\n")

    # 保存结果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_raw_dict(data, OUTPUT_DIR / "raw_dict.txt")
    save_readable_report(data, OUTPUT_DIR / "readable_report.md")

    # 打印统计信息
    for name, content in data.items():
        line_count = content.count("\n") + 1
        # 粗略判断补充信息是否存在
        has_supp = "补充信息" in content
        print(f"  {name}: {line_count} 行{' ✅ 含补充信息' if has_supp else ' ❌ 无补充信息'}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()
