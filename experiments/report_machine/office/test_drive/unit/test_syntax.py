"""
第1层-单元测试：语法检查

覆盖所有 office Python 文件的语法正确性。
"""
import os
import sys
import ast
import json
import time

BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TEST_TIMESTAMP = time.strftime("%Y-%m-%d %H:%M:%S")
RUN_ID = time.strftime("%Y%m%d_%H%M%S")

# 所有需要检查的文件
PYTHON_FILES = [
    "database.py",
    "models.py",
    "fetcher.py",
    "retry_fallback.py",
    "config/config.py",
    "middleman/server.py",
    "writer/server.py",
    "reporter/server.py",
    "reporter/agent.py",
    "output/md_to_docx.py",
]

# 需要测试 import 的模块
IMPORT_TESTS = [
    # (module_name, path_addition, expected_to_pass)
    ("models", None, True),
    ("database", None, True),
    # config.config 与 Python 内置 config 冲突，用完整路径导入
    # fetcher 有 from office.xxx 的引用，不能单独导入
]


def check_syntax(filepath: str, relpath: str) -> dict:
    """检查单个文件的语法"""
    result = {
        "file": relpath,
        "status": "pass",
        "errors": [],
    }
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
    except SyntaxError as e:
        result["status"] = "fail"
        result["errors"].append(f"第 {e.lineno} 行: {e.msg}")
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
    return result


def check_import(module_name: str, path_add: str | None = None) -> dict:
    """检查模块导入"""
    result = {
        "module": module_name,
        "status": "pass",
        "error": "",
    }
    try:
        if path_add:
            sys.path.insert(0, path_add)
        __import__(module_name)
    except ImportError as e:
        result["status"] = "fail"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "warn"
        result["error"] = f"导入成功但初始化异常: {e}"
    return result


def run():
    """执行所有语法检查"""
    results = {
        "test": "语法检查",
        "timestamp": TEST_TIMESTAMP,
        "run_id": RUN_ID,
        "syntax": [],
        "imports": [],
    }

    # ── 语法检查 ──
    for relpath in PYTHON_FILES:
        filepath = os.path.join(BASE_DIR, relpath)
        if not os.path.exists(filepath):
            results["syntax"].append({
                "file": relpath,
                "status": "skip",
                "errors": ["文件不存在"],
            })
            continue
        r = check_syntax(filepath, relpath)
        results["syntax"].append(r)

    # ── import 检查 ──
    sys.path.insert(0, BASE_DIR)
    for module_name, path_add, expect_pass in IMPORT_TESTS:
        if path_add:
            r = check_import(module_name, os.path.join(BASE_DIR, path_add))
        else:
            r = check_import(module_name)
        results["imports"].append(r)

    # ── 汇总 ──
    syntax_pass = sum(1 for r in results["syntax"] if r["status"] == "pass")
    syntax_total = len(results["syntax"])
    import_pass = sum(1 for r in results["imports"] if r["status"] == "pass")
    import_total = len(results["imports"])

    results["summary"] = {
        "syntax": f"{syntax_pass}/{syntax_total} 通过",
        "imports": f"{import_pass}/{import_total} 通过",
        "overall": "通过" if (syntax_pass == syntax_total and import_pass == import_total) else "部分失败",
    }

    # ── 保存 ──
    output_path = os.path.join(RESULTS_DIR, f"syntax_check_{RUN_ID}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {output_path}")

    # ── 输出摘要 ──
    print(f"\n{'='*60}")
    print(f"  语法检查结果")
    print(f"{'='*60}")
    for r in results["syntax"]:
        status = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "💥"}.get(r["status"], "❓")
        print(f"  {status} {r['file']}")
        if r["errors"]:
            for e in r["errors"]:
                print(f"       {e}")
    print()
    for r in results["imports"]:
        status = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(r["status"], "❓")
        print(f"  {status} {r['module']}")
        if r.get("error"):
            print(f"       {r['error']}")
    print(f"\n  汇总: {results['summary']['overall']}")
    print(f"  Syntax: {results['summary']['syntax']}")
    print(f"  Imports: {results['summary']['imports']}")

    return results


if __name__ == "__main__":
    run()
