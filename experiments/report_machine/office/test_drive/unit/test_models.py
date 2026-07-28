"""
第1层-单元测试：报文模型穷举测试

覆盖所有 Pydantic 模型在各种输入下的序列化/反序列化行为。
包括：正常、字段缺失、类型错误、空值、极端值。
"""
import os
import sys
import json
import time
import copy
from datetime import datetime

BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

from pydantic import ValidationError

from models import (
    ReportRequest, TypeARequest, TypeAResponse, TypeBRequest, TypeBResponse,
    SubWorkerResult, ReportResponse, ReportContext, ReporterResponse,
)

RUN_ID = time.strftime("%Y%m%d_%H%M%S")
TEST_TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ════════════════════════════════════════════════════════════════
# 测试案例定义
# ════════════════════════════════════════════════════════════════

# ---- 1. ReportRequest ----

REPORT_REQUEST_CASES = [
    # (case_name, input_data, expect_success)
    ("正常-4只股票", {"stock_names": ["淮北矿业", "博瑞医药", "凯莱英", "广生堂"]}, True),
    ("正常-1只股票", {"stock_names": ["淮北矿业"]}, True),
    ("正常-带特殊字符", {"stock_names": ["ST华英", "*ST康得", "N中芯"]}, True),
    ("正常-含数字名称", {"stock_names": ["三一重工", "2025概念"]}, True),
    ("边界-空列表", {"stock_names": []}, True),        # 空列表允许，业务层会拒绝
    ("边界-超大列表", {"stock_names": [f"股票{i}" for i in range(1000)]}, True),
    ("边界-重复名称", {"stock_names": ["淮北矿业", "淮北矿业"]}, True),
    ("异常-字段缺失", {}, False),
    ("异常-类型错误-字符串", {"stock_names": "不是数组"}, False),
    ("异常-类型错误-数字", {"stock_names": [123, 456]}, False),
    ("异常-null值", {"stock_names": None}, False),
    ("异常-混合类型", {"stock_names": ["正常股票", None, 123]}, False),
]

# ---- 2. TypeARequest ----

TYPEA_REQ_CASES = [
    ("正常-完整参数", {"writer_id": "w_a1b2c3d4e5f6", "stock_code": "600985"}, True),
    ("正常-短ID", {"writer_id": "w_abc", "stock_code": "300750"}, True),
    ("正常-纯数字代码", {"writer_id": "w_test", "stock_code": "002821"}, True),
    ("边界-超长ID", {"writer_id": "w_" + "x" * 100, "stock_code": "600985"}, True),
    ("边界-超长code", {"writer_id": "w_test", "stock_code": "600985"}, True),
    ("异常-缺失writer_id", {"stock_code": "600985"}, False),
    ("异常-缺失stock_code", {"writer_id": "w_test"}, False),
    ("异常-空字符串writer_id", {"writer_id": "", "stock_code": "600985"}, True),  # 空字符串业务可用
    ("异常-空字符串stock_code", {"writer_id": "w_test", "stock_code": ""}, True),
    ("异常-类型错误-null", {"writer_id": None, "stock_code": "600985"}, False),
    ("异常-类型错误-数字stock_code", {"writer_id": "w_test", "stock_code": 600985}, False),  # int 可转 str
    ("异常-所有字段缺失", {}, False),
]

# ---- 3. TypeAResponse ----

TYPEA_RESP_CASES = [
    ("正常-5引擎全结果", {
        "writer_id": "w_test",
        "results": {
            "sinafin": {"session_id": "s_001", "preview": {"total": 5, "articles": []}, "empty": False, "error": ""},
            "baidufin": {"session_id": "s_002", "preview": None, "empty": True, "error": ""},
            "thsfin": {"session_id": "s_003", "preview": {"total": 3, "articles": []}, "empty": False, "error": ""},
            "juchao": {"session_id": "", "preview": None, "empty": None, "error": "search failed"},
            "qnainfo": {"session_id": "s_005", "preview": {"total": 0, "articles": []}, "empty": True, "error": ""},
        }
    }, True),
    ("正常-空结果", {"writer_id": "w_test", "results": {}}, True),
    ("异常-缺失results", {"writer_id": "w_test"}, False),
    ("异常-缺失writer_id", {"results": {}}, False),
    ("异常-null results", {"writer_id": "w_test", "results": None}, False),
]

# ---- 4. TypeBRequest ----

TYPEB_REQ_CASES = [
    ("正常-单文章", {"report_id": "rp_001", "engine": "sinafin", "session_id": "s_001", "article_ids": ["a_01"]}, True),
    ("正常-多文章", {"report_id": "rp_001", "engine": "baidufin", "session_id": "s_002", "article_ids": ["a_01", "a_02", "a_03"]}, True),
    ("正常-空文章列表", {"report_id": "rp_001", "engine": "thsfin", "session_id": "s_003", "article_ids": []}, True),
    ("正常-所有引擎", {"report_id": "rp_001", "engine": "qnainfo", "session_id": "s_004", "article_ids": ["a_01"]}, True),
    ("边界-超长article_ids", {"report_id": "rp_001", "engine": "juchao", "session_id": "s_005", "article_ids": [f"a_{i:02d}" for i in range(100)]}, True),
    ("异常-缺失engine", {"report_id": "rp_001", "session_id": "s_001", "article_ids": ["a_01"]}, False),
    ("异常-缺失session_id", {"report_id": "rp_001", "engine": "sinafin", "article_ids": ["a_01"]}, False),
    ("异常-缺失article_ids", {"report_id": "rp_001", "engine": "sinafin", "session_id": "s_001"}, False),
    ("异常-缺失report_id", {"engine": "sinafin", "session_id": "s_001", "article_ids": ["a_01"]}, False),
    ("异常-空字符串engine", {"report_id": "rp_001", "engine": "", "session_id": "s_001", "article_ids": ["a_01"]}, True),
    ("异常-类型错误-engine是数字", {"report_id": "rp_001", "engine": 123, "session_id": "s_001", "article_ids": ["a_01"]}, False),
    ("异常-null report_id", {"report_id": None, "engine": "sinafin", "session_id": "s_001", "article_ids": ["a_01"]}, False),
]

# ---- 5. TypeBResponse ----

TYPEB_RESP_CASES = [
    ("正常-ready有正文", {"report_id": "rp_001", "engine": "sinafin", "session_id": "s_001",
     "session_closed": False, "articles": [{"article_id": "a_01", "body_text": "正文内容...", "truncated": False}], "status": "ready"}, True),
    ("正常-全部error", {"report_id": "rp_001", "engine": "baidufin", "session_id": "s_002",
     "session_closed": True, "articles": [], "status": "error"}, True),
    ("正常-timeout", {"report_id": "rp_001", "engine": "thsfin", "session_id": "s_003",
     "session_closed": True, "articles": [], "status": "timeout"}, True),
    ("正常-多篇混合", {"report_id": "rp_001", "engine": "juchao", "session_id": "s_004",
     "session_closed": False, "articles": [
         {"article_id": "a_01", "body_text": "正文1", "truncated": False},
         {"article_id": "a_02", "body_text": "正文2很长..." * 1000, "truncated": True},
         {"article_id": "a_03", "body_text": "", "truncated": False},
     ], "status": "ready"}, True),
    ("边界-超大正文", {"report_id": "rp_001", "engine": "qnainfo", "session_id": "s_005",
     "session_closed": False, "articles": [
         {"article_id": "a_01", "body_text": "大" * 50000, "truncated": True}
     ], "status": "ready"}, True),
    ("边界-空status", {"report_id": "rp_001", "engine": "sinafin", "session_id": "s_001",
     "session_closed": False, "articles": [], "status": ""}, True),
]

# ---- 6. SubWorkerResult ----

SUBWORKER_CASES = [
    ("正常-成功", {"stock_name": "淮北矿业", "success": True, "error": ""}, True),
    ("正常-失败", {"stock_name": "博瑞医药", "success": False, "error": "reporter 无响应"}, True),
    ("正常-空error", {"stock_name": "凯莱英", "success": True, "error": ""}, True),
    ("边界-超长名称", {"stock_name": "A" * 100, "success": True, "error": ""}, True),
    ("边界-超长error", {"stock_name": "测试", "success": False, "error": "E" * 2000}, True),
]

# ---- 7. ReportResponse ----

REPORT_RESP_CASES = [
    ("正常-全部成功", {"report_id": "r_001", "total": 4, "success": 4, "failed": [], "results": [
        {"stock_name": "淮北矿业", "success": True, "error": ""},
        {"stock_name": "博瑞医药", "success": True, "error": ""},
    ]}, True),
    ("正常-全部失败", {"report_id": "r_002", "total": 2, "success": 0, "failed": ["淮北矿业", "博瑞医药"], "results": [
        {"stock_name": "淮北矿业", "success": False, "error": "timeout"},
        {"stock_name": "博瑞医药", "success": False, "error": "timeout"},
    ]}, True),
    ("正常-部分成功", {"report_id": "r_003", "total": 4, "success": 3, "failed": ["广生堂"], "results": [
        {"stock_name": "淮北矿业", "success": True, "error": ""},
        {"stock_name": "广生堂", "success": False, "error": "error"},
    ]}, True),
    ("边界-total=0", {"report_id": "r_004", "total": 0, "success": 0, "failed": [], "results": []}, True),
    ("边界-total != results长度", {"report_id": "r_005", "total": 5, "success": 2, "failed": [], "results": []}, True),  # 业务不一致但模型允许
]

# ---- 8. ReportContext ----

REPORT_CONTEXT_CASES = [
    ("正常-完整", {
        "stock_name": "凯莱英", "ts_code": "002821.SZ",
        "fetch_data": "## 凯莱英 (002821.SZ)\n\n【今日11:30收盘数据】...",
        "fetch_message": "## 凯莱英 (002821.SZ)\n\n【今日快讯】...",
        "fetch_warnings": {"002821.SZ": {"critical": [], "non_critical": []}},
        "articles": {
            "sinafin": {"session_id": "s_001", "preview": {"total": 3, "articles": []}},
        },
        "middleman_warnings": [],
    }, True),
    ("正常-无消息", {
        "stock_name": "广生堂", "ts_code": "300436.SZ",
        "fetch_data": "## 广生堂...", "fetch_message": "",
        "fetch_warnings": {}, "articles": {}, "middleman_warnings": [],
    }, True),
    ("正常-有warning", {
        "stock_name": "淮北矿业", "ts_code": "600985.SH",
        "fetch_data": "...", "fetch_message": "...",
        "fetch_warnings": {"600985.SH": {"critical": ["全市场情绪"], "non_critical": ["融资融券"]}},
        "articles": {}, "middleman_warnings": ["sinafin: search failed"],
    }, True),
    ("边界-超长fetch_data", {
        "stock_name": "测试", "ts_code": "000001.SZ",
        "fetch_data": "D" * 100000,  # 100K 字符
        "fetch_message": "M" * 100000,
        "fetch_warnings": {}, "articles": {}, "middleman_warnings": [],
    }, True),
    ("异常-缺失stock_name", {"ts_code": "600985.SH", "fetch_data": "...", "fetch_message": "...",
     "fetch_warnings": {}, "articles": {}, "middleman_warnings": []}, False),
    ("异常-缺失ts_code", {"stock_name": "测试", "fetch_data": "...", "fetch_message": "...",
     "fetch_warnings": {}, "articles": {}, "middleman_warnings": []}, False),
]

# ---- 9. ReporterResponse ----

REPORTER_RESP_CASES = [
    ("正常-成功", {"report_id": "r_001", "status": "ok", "output_path": "/path/to/report.md", "rounds": 5, "error": ""}, True),
    ("正常-部分", {"report_id": "r_002", "status": "partial", "output_path": "", "rounds": 8, "error": "未生成完整报告"}, True),
    ("正常-错误", {"report_id": "r_003", "status": "error", "output_path": "", "rounds": 0, "error": "LLM API 异常"}, True),
    ("边界-空路径", {"report_id": "r_004", "status": "ok", "output_path": "", "rounds": 3, "error": ""}, True),
    ("异常-缺失status", {"report_id": "r_005", "output_path": "", "rounds": 0, "error": ""}, False),
]

# ════════════════════════════════════════════════════════════════
# 序列化/反序列化测试（JSON 往返）
# ════════════════════════════════════════════════════════════════

SERIALIZATION_CASES = [
    ("ReportContext-JSON往返", ReportContext, REPORT_CONTEXT_CASES[0][1]),
    ("TypeAResponse-JSON往返", TypeAResponse, TYPEA_RESP_CASES[0][1]),
    ("TypeBResponse-JSON往返", TypeBResponse, TYPEB_RESP_CASES[0][1]),
    ("ReportResponse-JSON往返", ReportResponse, REPORT_RESP_CASES[0][1]),
    ("ReporterResponse-JSON往返", ReporterResponse, REPORTER_RESP_CASES[0][1]),
]


# ════════════════════════════════════════════════════════════════
# 测试执行
# ════════════════════════════════════════════════════════════════

def test_model(model_class, cases, model_name: str) -> list:
    """测试单个模型的所有案例"""
    results = []
    for case_name, input_data, expect_success in cases:
        r = {
            "case": case_name,
            "model": model_name,
            "status": "pass",
            "error": "",
        }
        try:
            instance = model_class(**input_data)
            if not expect_success:
                r["status"] = "unexpected_pass"
                r["error"] = "预期失败但通过了"
            else:
                # 验证输出
                dumped = instance.model_dump()
                if isinstance(input_data, dict):
                    for k, v in input_data.items():
                        if k in dumped and v is not None and dumped[k] is not None:
                            r[f"field_{k}"] = "ok"
        except ValidationError as e:
            if expect_success:
                r["status"] = "fail"
                r["error"] = str(e)[:300]
            else:
                r["status"] = "pass"  # 预期中的失败
        except Exception as e:
            r["status"] = "error"
            r["error"] = str(e)[:300]
        results.append(r)
    return results


def test_serialization(model_class, input_data, case_name: str) -> dict:
    """测试 JSON 序列化→反序列化往返"""
    r = {
        "case": case_name,
        "status": "pass",
        "errors": [],
    }
    try:
        instance = model_class(**input_data)
        json_str = instance.model_dump_json()
        restored = model_class.model_validate_json(json_str)
        # 验证关键字段
        for k in input_data:
            if k in ("results", "articles", "fetch_warnings", "middleman_warnings",
                     "fetch_data", "fetch_message"):
                continue  # 复杂类型跳过简单相等比较
            if k in input_data and hasattr(restored, k):
                original = input_data[k]
                restored_val = getattr(restored, k)
                if type(original) != type(restored_val) and original is not None and restored_val is not None:
                    r["errors"].append(f"字段 {k} 类型变化: {type(original)} → {type(restored_val)}")
        if r["errors"]:
            r["status"] = "warn"
    except Exception as e:
        r["status"] = "fail"
        r["errors"].append(str(e)[:300])
    return r


def run():
    """运行所有模型测试"""
    print(f"\n{'='*60}")
    print(f"  报文模型穷举测试")
    print(f"  时间: {TEST_TIMESTAMP}")
    print(f"{'='*60}")

    all_results = {
        "test": "报文模型测试",
        "timestamp": TEST_TIMESTAMP,
        "run_id": RUN_ID,
        "models": [],
        "serialization": [],
    }

    # ── 模型验证测试 ──
    model_tests = [
        (ReportRequest, REPORT_REQUEST_CASES, "ReportRequest"),
        (TypeARequest, TYPEA_REQ_CASES, "TypeARequest"),
        (TypeAResponse, TYPEA_RESP_CASES, "TypeAResponse"),
        (TypeBRequest, TYPEB_REQ_CASES, "TypeBRequest"),
        (TypeBResponse, TYPEB_RESP_CASES, "TypeBResponse"),
        (SubWorkerResult, SUBWORKER_CASES, "SubWorkerResult"),
        (ReportResponse, REPORT_RESP_CASES, "ReportResponse"),
        (ReportContext, REPORT_CONTEXT_CASES, "ReportContext"),
        (ReporterResponse, REPORTER_RESP_CASES, "ReporterResponse"),
    ]

    for model_class, cases, model_name in model_tests:
        print(f"\n── {model_name} ──")
        results = test_model(model_class, cases, model_name)
        all_results["models"].extend(results)

        for r in results:
            icon = {"pass": "✅", "fail": "❌", "unexpected_pass": "⚠️", "error": "💥"}.get(r["status"], "❓")
            print(f"  {icon} {r['case']}")
            if r["status"] in ("fail", "unexpected_pass", "error"):
                print(f"      {r['error'][:100]}")

    # ── 序列化测试 ──
    print(f"\n── JSON序列化往返 ──")
    for case_name, model_class, input_data in SERIALIZATION_CASES:
        r = test_serialization(model_class, input_data, case_name)
        all_results["serialization"].append(r)
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(r["status"], "❓")
        print(f"  {icon} {case_name}")
        if r.get("errors"):
            for e in r["errors"]:
                print(f"      {e}")

    # ── 汇总 ──
    total = len(all_results["models"])
    passed = sum(1 for r in all_results["models"] if r["status"] == "pass")
    failed = sum(1 for r in all_results["models"] if r["status"] == "fail")
    unexpected = sum(1 for r in all_results["models"] if r["status"] == "unexpected_pass")
    serial_pass = sum(1 for r in all_results["serialization"] if r["status"] == "pass")

    summary = {
        "model_tests_total": total,
        "model_tests_passed": passed,
        "model_tests_failed": failed,
        "model_tests_unexpected_pass": unexpected,
        "serialization_pass": f"{serial_pass}/{len(all_results['serialization'])}",
    }
    all_results["summary"] = summary

    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  模型验证: {passed}/{total} 通过, {failed} 失败, {unexpected} 意外通过")
    print(f"  序列化: {summary['serialization_pass']} 通过")

    # ── 保存 ──
    output_path = os.path.join(RESULTS_DIR, f"models_test_{RUN_ID}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")

    return all_results


if __name__ == "__main__":
    run()
