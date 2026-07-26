"""
10 只随机股票 × qnainfo 引擎并发测试。

筛选时间: 上一个交易日的前一天至今天（2026-07-23 ~ 2026-07-24）
目标:
  1. 验证 qnainfo 引擎首次调用即返回完整问答内容
  2. 验证空回答条目被自动过滤
  3. 验证分钟级时间精度

用法:
    conda run -n stock_agent python3 test_drive/test_qnainfo.py
"""
import requests, json, time, sys, os
from datetime import datetime

API_BASE = "http://localhost:8300"
START_DATE = "2026-07-23"
END_DATE = "2026-07-24"
MAX_RESULTS = 20

STOCKS = [
    ("贵州茅台", "600519"),
    ("宁德时代", "300750"),
    ("比亚迪", "002594"),
    ("药明康德", "603259"),
    ("中芯国际", "688981"),
    ("招商银行", "600036"),
    ("恒瑞医药", "600276"),
    ("隆基绿能", "601012"),
    ("海康威视", "002415"),
    ("紫金矿业", "601899"),
]

REPORT = []

def log(line=""):
    REPORT.append(line)
    print(line)

def search_one(stock_name, stock_code, idx):
    """调用 /search 接口查询 qnainfo。"""
    t0 = time.time()
    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    sess.mount("http://", adapter)
    try:
        resp = sess.post(f"{API_BASE}/search", json={
            "query": stock_code,
            "engine": "qnainfo",
            "mode": "list",
            "max_results": MAX_RESULTS,
            "start_date": START_DATE,
            "end_date": END_DATE,
        }, timeout=120)
        http_code = resp.status_code
        try:
            j = resp.json()
        except:
            j = {}
        err_detail = j.get("detail", "") if http_code != 200 else ""
    except Exception as e:
        return {"idx": idx, "stock": stock_name, "code": stock_code,
                "http_code": 0, "status": "HTTP_ERR", "session_id": "",
                "total": 0, "articles": [], "elapsed_s": 0,
                "error_detail": str(e)}
    finally:
        sess.close()

    preview = j.get("preview", {})
    arts = preview.get("articles", [])
    return {
        "idx": idx,
        "stock": stock_name,
        "code": stock_code,
        "http_code": http_code,
        "status": j.get("status", "???"),
        "session_id": j.get("session_id", ""),
        "total": preview.get("total", 0),
        "articles": arts,
        "elapsed_s": round(time.time() - t0, 3),
        "error_detail": err_detail,
    }

def verify_articles(articles):
    """验证每篇文章的字段完整性和数据质量。"""
    issues = []
    for a in articles:
        aid = a.get("id", "")
        # 检查必填字段
        if not a.get("_answer"):
            issues.append(f"{aid}: _answer 为空")
        if not a.get("_question"):
            issues.append(f"{aid}: _question 为空")
        if not a.get("_answerer"):
            issues.append(f"{aid}: _answerer 为空")
        if not a.get("_known_date"):
            issues.append(f"{aid}: _known_date 为空")
        # 检查 body_status
        if a.get("body_status") != "ready":
            issues.append(f"{aid}: body_status={a.get('body_status')} 应=ready")
        # 检查 body_avail
        if a.get("body_avail") != "有":
            issues.append(f"{aid}: body_avail={a.get('body_avail')} 应=有")
        # 检查时间精度（应有 HH:MM）
        kd = a.get("_known_date", "")
        if kd and " " in kd and ":" not in kd.split(" ")[1]:
            issues.append(f"{aid}: _known_date 精度不足: {kd}")
    return issues

def run():
    log(f"# qnainfo 引擎并发测试报告")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**引擎**: qnainfo（互动易问答）")
    log(f"**时间范围**: {START_DATE} ~ {END_DATE}")
    log(f"**测试规模**: {len(STOCKS)} 只股票 × 1 引擎 = {len(STOCKS)} 请求")
    log(f"**最大返回**: {MAX_RESULTS} 条/请求")
    log()

    # ============================================================
    # 阶段 1: 并发搜索
    # ============================================================
    log("---")
    log("## 阶段 1: 并发搜索")
    log()
    log("| # | 股票 | 代码 | HTTP | 状态 | 耗时(s) | 返回条数 | 备注 |")
    log("|---|------|------|:----:|:----:|:-------:|:--------:|:-----|")

    tasks = [(name, code, i) for i, (name, code) in enumerate(STOCKS)]
    all_results = []
    t_all = time.time()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        fmap = {pool.submit(search_one, n, c, i): i for n, c, i in tasks}
        for fut in concurrent.futures.as_completed(fmap):
            all_results.append(fut.result())

    all_results.sort(key=lambda r: r["idx"])
    total_elapsed = round(time.time() - t_all, 3)

    total_articles = 0
    stocks_with_data = 0
    stocks_empty = 0
    stocks_error = 0

    for r in all_results:
        total_articles += r["total"]
        if r["http_code"] != 200:
            stocks_error += 1
            note = f"⚠ HTTP {r['http_code']}"
        elif r["total"] > 0:
            stocks_with_data += 1
            note = ""
        else:
            stocks_empty += 1
            note = "无数据"

        err = r.get("error_detail", "")[:50]
        if err:
            note += f" {err}"

        log(f"| {r['idx']+1} | {r['stock']} | {r['code']} "
            f"| {r['http_code']} | {r['status']} "
            f"| {r['elapsed_s']} | {r['total']} | {note} |")

    log()
    log(f"> 聚合统计:")
    log(f"> - 总请求: {len(all_results)} 个，并发完成耗时: **{total_elapsed}s**")
    log(f"> - 有数据的股票: {stocks_with_data} 只")
    log(f"> - 无数据的股票: {stocks_empty} 只")
    log(f"> - 报错的股票: {stocks_error} 只")
    log(f"> - 返回文章总计: {total_articles} 篇")
    log()

    # ============================================================
    # 阶段 2: 数据质量验证
    # ============================================================
    log("---")
    log("## 阶段 2: 数据质量验证")
    log()

    all_issues = []
    for r in all_results:
        if not r["articles"]:
            continue
        issues = verify_articles(r["articles"])
        if issues:
            all_issues.append((r["stock"], r["code"], issues))
            for iss in issues:
                log(f"- ⚠ {r['stock']}({r['code']}): {iss}")
        else:
            log(f"- ✅ {r['stock']}({r['code']}): {r['total']} 篇全部字段完整、body_status=ready")

    if not all_issues:
        log()
        log("> **无任何数据质量问题。**")
    log()

    # ============================================================
    # 阶段 3: 各股票详情
    # ============================================================
    log("---")
    log("## 阶段 3: 各股票详情")
    log()

    for r in all_results:
        sid = r["session_id"]
        arts = r["articles"]
        log(f"<details>")
        if arts:
            log(f"<summary><b>{r['stock']}({r['code']})</b> — "
                f"{r['total']} 篇 / {r['elapsed_s']}s / session: <code>{sid}</code></summary>")
            log()
            log(f"  | ID | 更新时间 | 提问时间 | 回答者 | 回答非空 | 问题摘要 |")
            log(f"  |----|----------|----------|--------|----------|----------|")
            for a in arts:
                kd = a.get("_known_date", "")
                ask_time = a.get("_ask_time", "")
                answerer = a.get("_answerer", "")
                question = a.get("_question", a.get("title", ""))
                answer = a.get("_answer", "")
                has_answer = "✅" if answer else "❌"
                log(f"  | {a['id']} | {kd} | {ask_time} | {answerer} | {has_answer} | {question[:50]} |")
            log()
        else:
            log(f"<summary><b>{r['stock']}({r['code']})</b> — "
                f"无数据 ({r['elapsed_s']}s) <code>{sid}</code></summary>")
            log()
            log("  _无问答记录或该时间段内无已回答条目_")
            log()
        log("</details>")
        log()

    # ============================================================
    # 阶段 4: 时间精度抽样验证
    # ============================================================
    log("---")
    log("## 阶段 4: 时间精度抽样")
    log()

    log("| 股票 | 文章ID | _known_date | 精度 |")
    log("|------|--------|-------------|------|")
    samples_shown = 0
    for r in all_results:
        for a in r["articles"][:2]:  # 每只取前2篇
            kd = a.get("_known_date", "")
            precision = "分钟级 ✅" if ":" in kd.split(" ")[1] else "仅日期 ⚠" if " " in kd else "无时间 ⚠"
            log(f"| {r['stock']} | {a['id']} | `{kd}` | {precision} |")
            samples_shown += 1

    if samples_shown == 0:
        log("| _(无数据，无法抽样)_ |")

    log()

    # ============================================================
    # 尾部
    # ============================================================
    log("---")
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"_报告自动生成_")

    # 写入文件
    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(out_dir, f"qnainfo_test_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    log(f"\n报告已导出: {md_path}")
    return md_path

if __name__ == "__main__":
    path = run()
    print(f"\n✅ 测试完成 → {path}")
