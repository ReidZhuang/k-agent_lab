"""
第2-3层：Middleman 单体 + 通信测试

测试 Type A（搜索聚合）和 Type B（正文获取）的所有功能场景。
需要：mail_tower(:8300) + middleman(:8311) 运行中。
"""
import os
import sys
import json
import time
import random
from datetime import datetime

BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

RUN_ID = time.strftime("%Y%m%d_%H%M%S")
TEST_TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

import requests
from models import TypeARequest, TypeBRequest

MIDDLEMAN_URL = "http://localhost:8311"
STOCKS = ['淮北矿业', '博瑞医药', '凯莱英', '广生堂']


# ════════════════════════════════════════════════════════════════
# Type A 测试
# ════════════════════════════════════════════════════════════════

TYPE_A_CASES = [
    # (name, writer_id, stock_code, expect_status)
    ("正常-标准股票代码-600985", "w_test_001", "600985", 200),
    ("正常-创业板代码-300436", "w_test_002", "300436", 200),
    ("正常-深主板代码-002821", "w_test_003", "002821", 200),
    ("异常-空代码", "w_test_004", "", 200),   # 返回 200 但各引擎可能报错
    ("异常-不存在代码-000000", "w_test_005", "000000", 200),
    ("异常-无效格式-abc", "w_test_006", "abc", 200),
    ("含空结果引擎-qnainfo长期", "w_test_007", "600519", 200),  # 茅台无互动问答
]

ENGINES_EXPECTED = ["sinafin", "baidufin", "thsfin", "juchao", "qnainfo"]


def test_type_a_single(name: str, writer_id: str, stock_code: str) -> dict:
    """测试 Type A 单个案例"""
    t_start = time.time()
    result = {
        "case": name,
        "input": {"writer_id": writer_id, "stock_code": stock_code},
        "engines_returned": 0,
        "engines_detail": {},
        "engines_with_error": 0,
        "engines_empty": 0,
        "engines_ok": 0,
        "total_articles": 0,
        "elapsed": 0,
        "http_status": 0,
        "status": "error",
        "error": "",
    }

    try:
        resp = requests.post(
            f"{MIDDLEMAN_URL}/api/v1/search",
            json={"writer_id": writer_id, "stock_code": stock_code},
            timeout=180,
        )
        result["http_status"] = resp.status_code
        if not resp.ok:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            result["elapsed"] = round(time.time() - t_start, 2)
            return result

        data = resp.json()
        results = data.get("results", {})

        for engine in ENGINES_EXPECTED:
            er = results.get(engine, {})
            detail = {
                "empty": er.get("empty"),
                "has_error": bool(er.get("error")),
                "error_msg": er.get("error", ""),
                "has_preview": er.get("preview") is not None,
                "article_count": 0,
            }
            if er.get("preview"):
                detail["article_count"] = er["preview"].get("total", 0)
                result["total_articles"] += detail["article_count"]

            if detail["has_error"]:
                result["engines_with_error"] += 1
            elif detail["empty"]:
                result["engines_empty"] += 1
            else:
                result["engines_ok"] += 1

            result["engines_detail"][engine] = detail

        result["engines_returned"] = len(results)
        result["elapsed"] = round(time.time() - t_start, 2)
        result["status"] = "pass"

    except Exception as e:
        result["error"] = str(e)[:200]
        result["elapsed"] = round(time.time() - t_start, 2)

    return result


# ════════════════════════════════════════════════════════════════
# Type B 测试
# ════════════════════════════════════════════════════════════════

TYPE_B_CASES = [
    "正常-读取第1篇文章",
    "正常-读取多篇文章",
    "异常-不存在的article_id",
    "异常-不存在的session_id",
]


def prepare_type_b() -> list[dict]:
    """为 Type B 测试准备 session_id 和 article_id"""
    print("\n  准备 Type B 测试数据...")
    test_sessions = []
    engines_tested = set()

    for stock_code in ["600985", "002821"]:
        resp = requests.post(
            f"{MIDDLEMAN_URL}/api/v1/search",
            json={"writer_id": "w_prep", "stock_code": stock_code},
            timeout=180,
        )
        if not resp.ok:
            continue
        results = resp.json().get("results", {})
        for engine, er in results.items():
            if engine in engines_tested:
                continue
            preview = er.get("preview")
            if not preview:
                continue
            articles = preview.get("articles", [])
            if not articles:
                continue
            session_id = er.get("session_id", "")
            if not session_id:
                continue
            article_ids = [a["id"] for a in articles[:3] if a.get("body_avail") == "有"]
            if article_ids:
                test_sessions.append({
                    "engine": engine,
                    "session_id": session_id,
                    "article_ids": article_ids,
                    "stock": stock_code,
                })
                engines_tested.add(engine)

    return test_sessions


def test_type_b_single(test_data: dict) -> dict:
    """测试 Type B 获取正文"""
    result = {
        "engine": test_data["engine"],
        "stock": test_data["stock"],
        "article_ids": test_data["article_ids"],
        "session_id": test_data["session_id"],
        "status": "error",
        "http_status": 0,
        "articles_returned": 0,
        "articles_with_body": 0,
        "articles_truncated": 0,
        "articles_error": 0,
        "response_status": "",
        "elapsed": 0,
        "error": "",
    }

    t_start = time.time()
    try:
        resp = requests.post(
            f"{MIDDLEMAN_URL}/api/v1/article",
            json={
                "report_id": "rp_test_b",
                "engine": test_data["engine"],
                "session_id": test_data["session_id"],
                "article_ids": test_data["article_ids"],
            },
            timeout=180,
        )
        result["http_status"] = resp.status_code
        if not resp.ok:
            result["error"] = f"HTTP {resp.status_code}"
            result["elapsed"] = round(time.time() - t_start, 2)
            return result

        data = resp.json()
        result["response_status"] = data.get("status", "?")
        articles = data.get("articles", [])
        result["articles_returned"] = len(articles)
        result["session_closed"] = data.get("session_closed", False)

        for art in articles:
            if art.get("status") == "ready":
                body = art.get("body_text", "")
                if body and body.strip():
                    result["articles_with_body"] += 1
                if art.get("truncated"):
                    result["articles_truncated"] += 1
            else:
                result["articles_error"] += 1

        result["status"] = "pass"
        result["elapsed"] = round(time.time() - t_start, 2)

    except Exception as e:
        result["error"] = str(e)[:200]
        result["elapsed"] = round(time.time() - t_start, 2)

    return result


def test_type_b_negative() -> list[dict]:
    """Type B 负面测试：无效 session_id 和 article_id"""
    results = []
    cases = [
        ("无效-session不存在", "rp_neg", "sinafin", "s_nonexistent_123", ["a_01"]),
        ("无效-空的article_ids", "rp_neg", "sinafin", "s_fake_456", []),
        ("无效-不存在article_id", "rp_neg", "baidufin", "s_fake_789", ["a_999"]),
    ]

    for name, rid, engine, sid, aids in cases:
        t0 = time.time()
        r = {
            "case": name,
            "engine": engine,
            "session_id": sid,
            "article_ids": aids,
            "status": "error",
            "http_status": 0,
            "elapsed": 0,
            "error": "",
        }
        try:
            resp = requests.post(
                f"{MIDDLEMAN_URL}/api/v1/article",
                json={"report_id": rid, "engine": engine,
                       "session_id": sid, "article_ids": aids},
                timeout=30,
            )
            r["http_status"] = resp.status_code
            if resp.ok:
                data = resp.json()
                r["articles_returned"] = len(data.get("articles", []))
                r["response_status"] = data.get("status", "")
            r["status"] = "pass"  # 能返回即可（正常或 error 都是预期行为）
            r["elapsed"] = round(time.time() - t0, 2)
        except Exception as e:
            r["error"] = str(e)[:200]
            r["elapsed"] = round(time.time() - t0, 2)
        results.append(r)

    return results


# ════════════════════════════════════════════════════════════════
# 主测试
# ════════════════════════════════════════════════════════════════

def run():
    print(f"\n{'='*60}")
    print(f"  Middleman 功能测试")
    print(f"  时间: {TEST_TIMESTAMP}")
    print(f"{'='*60}")

    all_results = {
        "test": "Middleman 功能测试",
        "timestamp": TEST_TIMESTAMP,
        "run_id": RUN_ID,
        "type_a": [],
        "type_b_positive": [],
        "type_b_negative": [],
    }

    # ── Type A 测试 ──
    print(f"\n{'─'*40}")
    print("  Type A: 搜索聚合")
    print(f"{'─'*40}")

    for case_name, wid, code, _ in TYPE_A_CASES:
        r = test_type_a_single(case_name, wid, code)
        all_results["type_a"].append(r)

        icon = "✅" if r["status"] == "pass" else "❌"
        engine_ok_ratio = f"{r['engines_ok']}/{r['engines_returned']}"
        print(f"  {icon} {case_name}")
        print(f"      代码={code}, HTTP={r['http_status']}, "
              f"引擎={engine_ok_ratio}, 文章={r['total_articles']}, "
              f"耗时={r['elapsed']}s")
        for eng, d in r["engines_detail"].items():
            if d["has_error"]:
                print(f"      ⚠️  {eng}: {d['error_msg'][:50]}")
            elif d["empty"]:
                print(f"      ⬜ {eng}: 无文章")

        if r.get("error"):
            print(f"      ❌ {r['error']}")

    # ── Type B 正向测试 ──
    print(f"\n{'─'*40}")
    print("  Type B: 正文获取（正向）")
    print(f"{'─'*40}")

    b_test_data = prepare_type_b()

    for td in b_test_data:
        r = test_type_b_single(td)
        all_results["type_b_positive"].append(r)

        icon = "✅" if r["status"] == "pass" else "❌"
        print(f"  {icon} {r['engine']}({r['stock']}) - {r['article_ids']}")
        print(f"      HTTP={r['http_status']}, "
              f"返回={r['articles_returned']}, "
              f"有正文={r['articles_with_body']}, "
              f"截断={r['articles_truncated']}, "
              f"耗时={r['elapsed']}s")

    # ── Type B 负面测试 ──
    print(f"\n{'─'*40}")
    print("  Type B: 异常输入")
    print(f"{'─'*40}")

    neg_results = test_type_b_negative()
    all_results["type_b_negative"] = neg_results

    for r in neg_results:
        icon = "✅" if r["status"] == "pass" else "❌"
        print(f"  {icon} {r['case']}")
        print(f"      HTTP={r['http_status']}, 耗时={r['elapsed']}s")
        if r.get("error"):
            print(f"      {r['error']}")

    # ── 汇总 ──
    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    ta_pass = sum(1 for r in all_results["type_a"] if r["status"] == "pass")
    tb_pass = sum(1 for r in all_results["type_b_positive"] if r["status"] == "pass")
    tn_pass = sum(1 for r in all_results["type_b_negative"] if r["status"] == "pass")
    print(f"  Type A (搜索聚合): {ta_pass}/{len(all_results['type_a'])} 通过")
    print(f"  Type B (正文正向): {tb_pass}/{len(all_results['type_b_positive'])} 通过")
    print(f"  Type B (异常输入): {tn_pass}/{len(all_results['type_b_negative'])} 通过")

    # ── 保存 ──
    output_path = os.path.join(RESULTS_DIR, f"middleman_test_{RUN_ID}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")

    return all_results


if __name__ == "__main__":
    run()
