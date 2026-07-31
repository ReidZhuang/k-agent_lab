"""
sinafin 限流阈值测试 v2 — 通过 API 并发调用来复现 httpx 空响应。

方法：
  1. 通过 API 调用 sinafin 搜索（获取文章 URL），
     然后调 /article 获取正文——完整模拟真实场景
  2. 逐步增加并发请求数，记录每个级别的空响应率
  3. 目标是复现 15s 超时并找到触发阈值

用法:
    conda run -n stock_agent python3 test_drive/test_sinafin_ratelimit_v2.py
"""
import requests, time, sys, os, random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"

# 20 只不同股票
STOCKS = [
    "000001", "000002", "000063", "000157", "000338",
    "000799", "000895", "000999", "002027", "002230",
    "002252", "002603", "002491", "300124", "300122",
    "300676", "300146", "300383", "601318", "601628",
]

# 并发级别（控制同时发起的 /search 请求数）
CONCURRENCY = [1, 5, 10, 15, 20, 25, 30]

REPORT = []

def log(s=""):
    REPORT.append(s)
    print(s)

def do_search(stock_code, engine, idx):
    """调 /search，返回文章列表"""
    t0 = time.time()
    try:
        r = requests.post(f"{API_BASE}/search", json={
            "query": stock_code, "engine": engine, "mode": "list",
            "max_results": 10, "filter_days": 90,
        }, timeout=120)
        j = r.json() if r.ok else {}
        elapsed = round(time.time() - t0, 2)
        arts = j.get("preview", {}).get("articles", [])
        sid = j.get("session_id", "")
        return {"idx": idx, "code": stock_code, "engine": engine,
                "http": r.status_code, "total": j.get("preview", {}).get("total", 0),
                "articles": arts, "session_id": sid,
                "elapsed": elapsed, "error": ""}
    except Exception as e:
        return {"idx": idx, "code": stock_code, "engine": engine,
                "http": 0, "total": 0, "articles": [], "session_id": "",
                "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}


def do_article(session_id, article_ids, idx):
    """调 /article，取正文"""
    t0 = time.time()
    try:
        r = requests.post(f"{API_BASE}/article", json={
            "session_id": session_id, "article_ids": article_ids,
        }, timeout=120)
        j = r.json() if r.ok else {}
        elapsed = round(time.time() - t0, 2)
        return {"idx": idx, "http": r.status_code, "articles": j.get("articles", []),
                "elapsed": elapsed, "error": ""}
    except Exception as e:
        return {"idx": idx, "http": 0, "articles": [],
                "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}


def run():
    log("# sinafin 限流阈值测试 v2 — API 并发真实场景")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**方法**: 递增并发 /search 请求数，每个请求获取文章后调 /article 取正文")
    log(f"**观察指标**: 空响应（empty response / httpx 超时）的出现频率")
    log()

    _HTTP_SESSION = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    _HTTP_SESSION.mount("http://", adapter)

    for concurrency in CONCURRENCY:
        # 随机选 concurrency 只股票
        selected = random.sample(STOCKS, min(concurrency, len(STOCKS)))

        log(f"---")
        log(f"## 并发 = {concurrency}")
        log()

        t0 = time.time()
        search_tasks = [(code, "sinafin", i) for i, code in enumerate(selected)]
        search_results = [None] * len(search_tasks)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            fmap = {}
            for code, eng, i in search_tasks:
                fut = pool.submit(do_search, code, eng, i)
                fmap[fut] = i
            for fut in as_completed(fmap):
                r = fut.result()
                search_results[r["idx"]] = r

        search_elapsed = round(time.time() - t0, 2)

        # Phase 2: 取正文
        article_results = []
        for r in search_results:
            if not r or r["http"] != 200 or not r["session_id"]:
                continue
            arts = r["articles"]
            avail = [a["id"] for a in arts if a.get("body_avail") == "有"]
            if avail:
                ar = do_article(r["session_id"], avail, r["idx"])
                article_results.append(ar)

        total_elapsed = round(time.time() - t0, 2)

        # 统计
        total_searches = len(search_results)
        ok_searches = sum(1 for r in search_results if r and r["http"] == 200)
        total_articles = sum((r["total"] for r in search_results if r), 0)

        # 正文提取结果
        ready = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "ready")
        error = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "error")
        processing = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "processing")
        empty_errors = [a.get("fetch_error", "") for ar in article_results for a in ar.get("articles", []) if a.get("status") == "error"]

        log(f"| 搜索成功 | 文章总数 | 正文 ready | 正文 error | processing | 空响应率 | 总耗时 |")
        log(f"|:--------:|:--------:|:----------:|:----------:|:----------:|:--------:|:------:|")
        error_rate = f"{error/(error+ready)*100:.1f}%" if (error+ready) > 0 else "0%"
        log(f"| {ok_searches}/{total_searches} | {total_articles} | {ready} | {error} | {processing} | {error_rate} | {total_elapsed}s |")

        if empty_errors:
            log()
            log("**空响应详情:**")
            for err in set(empty_errors):
                count = empty_errors.count(err)
                log(f"  - `{err}` × {count}")

        log()

        time.sleep(5)  # 间隔 5 秒让系统恢复

    log("---")
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"sinafin_ratelimit_v2_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")


if __name__ == "__main__":
    run()
