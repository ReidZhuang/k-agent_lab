"""
第2层-单体测试：Fetcher

测试 fetcher.fetch_all() 在不同输入下的完整功能。
需要：数据库可访问、fetch_midday_data/message 可调用。
"""
import os
import sys
import json
import time
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

STOCKS = ['淮北矿业', '博瑞医药', '凯莱英', '广生堂']

# ════════════════════════════════════════════════════════════════
# 测试案例
# ════════════════════════════════════════════════════════════════

TEST_CASES = [
    {
        "name": "正常-4只标准测试股票",
        "input": STOCKS,
        "expect_success": True,
        "expect_all_stocks_returned": True,
        "expect_data_sections": True,
    },
    {
        "name": "正常-单只股票",
        "input": ["凯莱英"],
        "expect_success": True,
        "expect_all_stocks_returned": True,
        "expect_data_sections": True,
    },
    {
        "name": "边界-空列表",
        "input": [],
        "expect_success": True,
        "expect_all_stocks_returned": True,  # 空列表也应返回空
        "expect_data_sections": False,
    },
    {
        "name": "异常-含未识别股票名",
        "input": ["淮北矿业", "不存在的股票12345", "博瑞医药"],
        "expect_success": True,  # 部分成功也是成功
        "expect_all_stocks_returned": False,
        "expect_data_sections": True,
    },
    {
        "name": "边界-含特殊字符",
        "input": ["ST华英", "N中芯"],
        "expect_success": True,
        "expect_all_stocks_returned": None,  # 不确定能找到
        "expect_data_sections": None,
    },
    {
        "name": "极限-大量股票",
        "input": ["淮北矿业", "博瑞医药", "凯莱英", "广生堂",
                   "宁德时代", "比亚迪", "贵州茅台", "中国平安",
                   "招商银行", "长江电力", "海尔智家", "伊利股份",
                   "恒瑞医药", "药明康德", "紫金矿业"],
        "expect_success": True,
        "expect_all_stocks_returned": None,
        "expect_data_sections": True,
    },
    {
        "name": "异常-重复名称（字典去重，1个entry）",
        "input": ["淮北矿业", "淮北矿业", "淮北矿业"],
        "expect_success": True,
        "expect_all_stocks_returned": None,  # 去重后返回1个，不影响结果
        "expect_data_sections": True,
    },
]


def verify_stock_data(result: dict, stock_name: str) -> dict:
    """验证单只股票的数据结构"""
    v = {
        "stock": stock_name,
        "has_data": False,
        "has_message": False,
        "data_len": 0,
        "message_len": 0,
        "status": "missing",
    }
    stock_data = result.get(stock_name, {})
    if not stock_data:
        v["status"] = "missing"
        return v

    data_text = stock_data.get("data", "")
    message_text = stock_data.get("message", "")

    v["has_data"] = bool(data_text)
    v["has_message"] = bool(message_text)
    v["data_len"] = len(data_text)
    v["message_len"] = len(message_text)

    # 检查 data 是否包含关键部分
    data_sections_found = []
    if data_text:
        for section in ["全市场情绪", "行业关键词", "收盘数据", "收盘行情",
                         "上一个交易日", "融资融券", "资金流向", "资金细分",
                         "板块排名", "技术面", "补充信息"]:
            if section in data_text:
                data_sections_found.append(section)
    v["data_sections"] = data_sections_found
    v["data_section_count"] = len(data_sections_found)

    # 检查 message 是否包含消息部分
    msg_sections_found = []
    if message_text:
        for section in ["今日快讯", "热门板块", "跌停", "异动"]:
            if section in message_text:
                msg_sections_found.append(section)
    v["message_sections"] = msg_sections_found

    # 判定状态
    if data_text:
        v["status"] = "ok" if v["data_section_count"] >= 4 else "partial_data"
    else:
        v["status"] = "no_data"

    return v


def verify_warnings(result: dict, stock_name: str) -> dict:
    """验证某股票是否在 warning 中"""
    # warnings 在 fetch_all 返回的第二个元素中
    return {}


def test_fetcher_case(case: dict) -> dict:
    """测试一个 fetcher 案例"""
    from fetcher import fetch_all

    t_start = time.time()
    error = ""
    data_by_stock = {}
    warnings_by_tscode = {}
    stock_verifications = []

    try:
        data_by_stock, warnings_by_tscode = fetch_all(case["input"])
    except Exception as e:
        error = f"异常: {e}"

    elapsed = round(time.time() - t_start, 2)

    # 如果没有异常，验证每只股票
    if not error:
        for stock_name in case["input"]:
            v = verify_stock_data(data_by_stock, stock_name)
            stock_verifications.append(v)

    # 汇总
    stocks_requested = len(case["input"])
    stocks_returned = len(data_by_stock)
    stocks_with_data = sum(1 for v in stock_verifications if v["status"] == "ok")
    stocks_partial = sum(1 for v in stock_verifications if v["status"] == "partial_data")
    stocks_missing = sum(1 for v in stock_verifications if v["status"] == "missing")

    # 判定是否成功
    if error:
        test_pass = False
    elif case["expect_all_stocks_returned"] is True:
        test_pass = stocks_with_data >= stocks_requested  # 去重后可能少于请求数
    elif case["expect_all_stocks_returned"] is False:
        # 部分成功：应有股票返回，且不是全部成功（含未识别股票）
        test_pass = stocks_returned > 0 and (stocks_missing > 0 or
                    any(v["status"] == "no_data" for v in stock_verifications))
    else:
        test_pass = stocks_returned > 0

    return {
        "case": case["name"],
        "input_count": stocks_requested,
        "output_count": stocks_returned,
        "with_data": stocks_with_data,
        "partial": stocks_partial,
        "missing": stocks_missing,
        "elapsed": elapsed,
        "passed": test_pass,
        "error": error,
        "stock_verifications": stock_verifications,
    }


def run():
    print(f"\n{'='*60}")
    print(f"  Fetcher 单体功能测试")
    print(f"  时间: {TEST_TIMESTAMP}")
    print(f"{'='*60}")

    all_results = {
        "test": "Fetcher 单体功能测试",
        "timestamp": TEST_TIMESTAMP,
        "run_id": RUN_ID,
        "cases": [],
    }

    for case in TEST_CASES:
        print(f"\n── {case['name']} ──")
        result = test_fetcher_case(case)
        all_results["cases"].append(result)

        icon = "✅" if result["passed"] else "❌"
        print(f"  {icon} 输入={result['input_count']}, 返回={result['output_count']}, "
              f"有数据={result['with_data']}, 部分={result['partial']}, "
              f"缺失={result['missing']}, 耗时={result['elapsed']}s")
        if result["error"]:
            print(f"     错误: {result['error']}")

        # 打印每只股票的详情
        for v in result.get("stock_verifications", []):
            print(f"    {v['stock']}: {v['status']} "
                  f"(data={v['data_len']}char, msg={v['message_len']}char, "
                  f"段数={v.get('data_section_count', 0)})")

    # 汇总
    total = len(all_results["cases"])
    passed = sum(1 for r in all_results["cases"] if r["passed"])
    total_stocks = sum(r["input_count"] for r in all_results["cases"])
    total_returned = sum(r["output_count"] for r in all_results["cases"])

    summary = {
        "total_cases": total,
        "passed": passed,
        "failed": total - passed,
        "total_stocks_requested": total_stocks,
        "total_stocks_returned": total_returned,
    }
    all_results["summary"] = summary

    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")
    print(f"  案例: {passed}/{total} 通过")
    print(f"  总请求股票数: {total_stocks}, 总返回: {total_returned}")

    # 保存
    output_path = os.path.join(RESULTS_DIR, f"fetcher_test_{RUN_ID}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")

    return all_results


if __name__ == "__main__":
    run()
