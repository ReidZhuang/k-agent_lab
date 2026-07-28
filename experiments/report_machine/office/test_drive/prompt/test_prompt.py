"""
第5层：Agent Prompt 测试

验证 DeepSeek v4 Flash 是否能正确理解 prompt 并调用 get_article_body。
使用模板 context（含多 engine 有正文/无正文文章）。

测试要点：
  1. LLM 是否会调用 get_article_body（有正文可调用时）
  2. LLM 是否跳过 body_avail=无 的文章
  3. LLM 生成报告的完整性和质量
  4. 工具返回的正文是否正确注入上下文
"""
import os
import sys
import json
import time
import glob

BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

import requests
from models import ReportContext

REPORTER_URL = "http://localhost:8312"
RUN_ID = time.strftime("%Y%m%d_%H%M%S")


def test_with_template():
    """使用模板 context 测试 agent loop"""
    print(f"🔵 [{time.strftime('%H:%M')}] Prompt 测试：模板 context")
    print()

    with open(os.path.join(os.path.dirname(__file__), "template_context.json"), "r") as f:
        ctx_data = json.load(f)

    ctx = ReportContext(**ctx_data)
    t_start = time.time()

    resp = requests.post(
        f"{REPORTER_URL}/api/v1/generate",
        json=ctx.model_dump(),
        timeout=300,
    )

    elapsed = time.time() - t_start
    result = resp.json()

    print(f"  耗时: {elapsed:.1f}s")
    print(f"  状态: {result.get('status')}")
    print(f"  轮次: {result.get('rounds')}")
    print(f"  输出: {result.get('output_path', '无')}")
    print()

    # 检查生成的报告
    output_path = result.get("output_path", "")
    if output_path and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"  报告大小: {len(content)} 字")
        print(f"  报告行数: {content.count(chr(10)) + 1}")
        print()

        # 检查报告质量指标
        checks = {
            "包含正文标题": "【今日11:30收盘数据】" in content,
            "包含消息": "【今日快讯】" in content,
            "包含板块": "板块" in content,
            "包含技术面": "技术" in content or "MA" in content,
            "包含风险提示": "风险" in content,
            "包含综合研判": "综合研判" in content or "总体判断" in content or "主力观点" in content,
            "标题为凯莱英": "凯莱英" in content[:50],
            "不含占位符": "待补充" not in content and "TODO" not in content,
        }
        print("=== 质量检查 ===")
        all_pass = True
        for check, passed in checks.items():
            icon = "✅" if passed else "❌"
            if not passed:
                all_pass = False
            print(f"  {icon} {check}")

        # 检查是否调用了 tool（通过轮次判断，2轮+表示大概率有用tool）
        if result.get("rounds", 0) >= 2:
            print(f"  ✅ 可能调用了 tool（共 {result.get('rounds')} 轮）")
        else:
            print(f"  ⚠️  仅 {result.get('rounds')} 轮，可能未调用 tool")

        # 保存结果摘要
        summary = {
            "test": "prompt_test",
            "status": result.get("status"),
            "rounds": result.get("rounds"),
            "elapsed": elapsed,
            "output_path": output_path,
            "output_size": len(content),
            "checks": checks,
            "all_pass": all_pass,
        }
        summary_path = os.path.join(RESULTS_DIR, f"prompt_test_{RUN_ID}.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n  结果已保存: {summary_path}")
        return summary
    else:
        print(f"  ❌ 报告未生成")
        return {"test": "prompt_test", "status": "error", "error": "no output"}


if __name__ == "__main__":
    test_with_template()
