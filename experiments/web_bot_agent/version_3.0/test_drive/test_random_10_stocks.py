"""
10 只随机股票 × 4 引擎 × filter_days=2 测试脚本。

用法:
    conda run -n stock_agent python3 test_drive/test_random_10_stocks.py
"""
import requests, json, time, sys, os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"
FILTER_DAYS = 2
MAX_RESULTS = 10

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

ENGINES = ["baidufin", "sinafin", "juchao", "thsfin"]

REPORT = []

def log(line=""):
    REPORT.append(line)
    print(line)

def search_one(stock_name, stock_code, engine, idx):
    t0 = time.time()
    query = stock_name if engine == "juchao" else stock_code
    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    sess.mount("http://", adapter)
    try:
        resp = sess.post(f"{API_BASE}/search", json={
            "query": query, "engine": engine, "mode": "list",
            "max_results": MAX_RESULTS, "filter_days": FILTER_DAYS,
        }, timeout=120)
        http_code = resp.status_code
        try:
            j = resp.json()
        except:
            j = {}
        err_detail = j.get("detail", "") if http_code != 200 else ""
    except Exception as e:
        return {"idx": idx, "stock": stock_name, "engine": engine,
                "http_code": 0, "status": "HTTP_ERR", "session_id": "",
                "total_raw": 0, "total": 0, "articles": [], "elapsed_s": 0,
                "error_detail": str(e)}
    finally:
        sess.close()

    preview = j.get("preview", {})
    arts = preview.get("articles", [])
    return {
        "idx": idx, "stock": stock_name, "engine": engine,
        "http_code": http_code,
        "status": j.get("status", "???"),
        "session_id": j.get("session_id", ""),
        "total_raw": preview.get("total_raw", 0),
        "total": preview.get("total", 0),
        "articles": arts,
        "elapsed_s": round(time.time() - t0, 3),
        "error_detail": err_detail,
    }

def run():
    log(f"# 10 只随机股票 × 4 引擎并发测试报告")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**filter_days**: {FILTER_DAYS}（近2天）")
    log(f"**测试参数**: {len(STOCKS)} 只股票 × {len(ENGINES)} 引擎 = {len(STOCKS)*len(ENGINES)} 请求")
    log()

    # Phase 1: 并发搜索
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log("| # | 股票 | 代码 | 引擎 | query | 耗时(s) | HTTP | 状态 | 条数 |")
    log("|---|------|------|------|-------|---------|------|------|------|")

    tasks = []
    idx = 0
    for name, code in STOCKS:
        for eng in ENGINES:
            tasks.append((name, code, eng, idx))
            idx += 1

    all_results = []
    t_all = time.time()
    with ThreadPoolExecutor(max_workers=20) as pool:
        fmap = {pool.submit(search_one, n, c, e, i): i for n, c, e, i in tasks}
        for fut in as_completed(fmap):
            all_results.append(fut.result())

    all_results.sort(key=lambda r: r["idx"])
    total_elapsed = round(time.time() - t_all, 3)

    for r in all_results:
        code = dict(STOCKS)[r["stock"]]
        q = r["stock"] if r["engine"] == "juchao" else code
        err = r.get("error_detail", "")[:40]
        log(f"| {r['idx']+1} | {r['stock']} | {code} | {r['engine']} | {q} "
            f"| {r['elapsed_s']} | {r['http_code']} | {r['status']} "
            f"| {r['total']}/{r['total_raw']} {'⚠' + err if err else ''} |")

    log()
    log(f"> 全部 {len(all_results)} 请求返回总耗时: **{total_elapsed}s**")
    log()

    # 各引擎返回文章列表
    log("### 各引擎返回详情")
    log()

    for r in all_results:
        sid = r["session_id"]
        arts = r["articles"]
        if not arts:
            continue
        log(f"<details>")
        log(f"<summary><b>{r['stock']} × {r['engine']}</b> — "
            f"{len(arts)} 篇 / {r['elapsed_s']}s / session: <code>{sid}</code></summary>")
        log()
        log("  | ID | 日期 | 有无正文 | 分类 | 标题 |")
        log("  |----|------|---------|------|------|")
        for a in arts:
            title = a.get("title", "").replace("|", "\\|")
            date = a.get("date", "")
            cat = a.get("_category", "")
            ba = a.get("body_avail", "有")
            log(f"  | {a['id']} | {date} | {ba} | {cat} | {title[:60]} |")
        log()
        log("</details>")
        log()

    # 尾部
    log("---")
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"_报告自动生成_")

    # 写入文件
    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = f"{out_dir}/random_10_stocks_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n报告已导出: {md_path}")

if __name__ == "__main__":
    run()
