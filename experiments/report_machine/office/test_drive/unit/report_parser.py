"""
第1层-单元测试：结果解析器

读取 test_syntax.py 和 test_models.py 的 JSON 结果，
生成可读性强的 Markdown 报告。
"""
import os
import json
import glob

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
REPORT_DIR = RESULTS_DIR


def parse_syntax_results(filepath: str) -> str:
    """解析语法检查结果"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = [
        f"# 语法检查报告",
        f"",
        f"**测试时间**: {data.get('timestamp', '?')}",
        f"**运行ID**: {data.get('run_id', '?')}",
        f"",
        f"## 语法检查",
        f"",
        f"| 文件 | 状态 | 错误信息 |",
        f"|------|:----:|:---------|",
    ]

    for r in data.get("syntax", []):
        status_icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "💥"}.get(r["status"], "❓")
        errors = "<br>".join(r.get("errors", [])) or "-"
        lines.append(f"| {r['file']} | {status_icon} | {errors} |")

    lines.extend([
        f"",
        f"## Import 检查",
        f"",
        f"| 模块 | 状态 | 错误信息 |",
        f"|------|:----:|:---------|",
    ])

    for r in data.get("imports", []):
        status_icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(r["status"], "❓")
        lines.append(f"| {r['module']} | {status_icon} | {r.get('error', '-')} |")

    lines.extend([
        f"",
        f"## 汇总",
        f"",
        f"- **语法检查**: {data.get('summary', {}).get('syntax', '?')}",
        f"- **Import 检查**: {data.get('summary', {}).get('imports', '?')}",
        f"- **总体**: {data.get('summary', {}).get('overall', '?')}",
    ])

    return "\n".join(lines)


def parse_models_results(filepath: str) -> str:
    """解析模型测试结果"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = [
        f"# 报文模型测试报告",
        f"",
        f"**测试时间**: {data.get('timestamp', '?')}",
        f"**运行ID**: {data.get('run_id', '?')}",
        f"",
        f"## 测试统计",
        f"",
        f"| 指标 | 值 |",
        f"|:-----|:---|",
    ]

    s = data.get("summary", {})
    lines.append(f"| 模型验证总数 | {s.get('model_tests_total', '?')} |")
    lines.append(f"| 通过 | {s.get('model_tests_passed', '?')} |")
    lines.append(f"| 失败 | {s.get('model_tests_failed', '?')} |")
    lines.append(f"| 意外通过 | {s.get('model_tests_unexpected_pass', '?')} |")
    lines.append(f"| 序列化通过 | {s.get('serialization_pass', '?')} |")
    lines.append("")

    # 按模型分组
    models_order = [
        "ReportRequest", "TypeARequest", "TypeAResponse",
        "TypeBRequest", "TypeBResponse", "SubWorkerResult",
        "ReportResponse", "ReportContext", "ReporterResponse",
    ]

    for model_name in models_order:
        model_results = [r for r in data.get("models", []) if r["model"] == model_name]
        if not model_results:
            continue

        failed = [r for r in model_results if r["status"] in ("fail", "unexpected_pass", "error")]
        lines.append(f"### {model_name}")
        lines.append("")
        lines.append(f"| 用例 | 状态 | 错误 |")
        lines.append(f"|:----|:----:|:-----|")

        for r in model_results:
            icon = {"pass": "✅", "fail": "❌", "unexpected_pass": "⚠️", "error": "💥"}.get(r["status"], "❓")
            err = r.get("error", "")[:80] if r["status"] != "pass" else "-"
            lines.append(f"| {r['case']} | {icon} | {err} |")
        lines.append("")

    # 序列化测试
    lines.append("### JSON序列化往返")
    lines.append("")
    lines.append("| 用例 | 状态 | 错误 |")
    lines.append("|:----|:----:|:-----|")
    for r in data.get("serialization", []):
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(r["status"], "❓")
        errs = "<br>".join(r.get("errors", [])) or "-"
        lines.append(f"| {r['case']} | {icon} | {errs} |")

    return "\n".join(lines)


def generate_report():
    """生成完整的单元测试报告"""
    # 查找最新的结果文件
    syntax_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "syntax_check_*.json")))
    models_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "models_test_*.json")))

    if not syntax_files and not models_files:
        print("❌ 未找到测试结果文件")
        return

    report_lines = [
        f"# 第1层：单元测试报告",
        f"",
        f"## 测试环境",
        f"",
        f"- **Python**: 3.10+",
        f"- **conda env**: stock_agent",
        f"- **测试时间**: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    if syntax_files:
        report_lines.append(parse_syntax_results(syntax_files[-1]))
        report_lines.append("")

    if models_files:
        report_lines.append(parse_models_results(models_files[-1]))

    report_path = os.path.join(REPORT_DIR, "unit_test_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"✅ 报告已生成: {report_path}")


if __name__ == "__main__":
    generate_report()
