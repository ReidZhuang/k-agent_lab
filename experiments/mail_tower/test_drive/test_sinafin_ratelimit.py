"""
测试 sinafin 文章并发请求的限流阈值。

方法:
  1. 通过 sinafin 后端获取一批文章 URL（20 只股票，各 10 篇）
  2. 按递增并发数（1/5/10/20/30/50）发送 httpx 请求
  3. 在每个并发级别记录：成功数、限流数、错误详情
  4. 找出触发限流的阈值

用法:
    conda run -n stock_agent python3 test_drive/test_sinafin_ratelimit.py
"""
import sys, os, time, requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加 search_engine 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from search_engine.backends.sinafin import SinaFinBackend

STOCKS = [
    "600519", "300750", "000651", "000858", "000333",
    "300760", "300059", "002475", "300274", "002714",
    "002594", "002415", "601899", "600276", "601012",
    "603259", "002821", "300436", "300015", "600309",
]

CONCURRENCY_LEVELS = [1, 5, 10, 20, 30, 50]

REPORT = []
def log(s=""):
    REPORT.append(s)
    print(s)


def try_fetch(session, url, idx):
    """下载单个 sinafin 文章，检测是否被限流。"""
    t0 = time.time()
    try:
        r = session.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=15)
        elapsed = round(time.time() - t0, 3)
        status = r.status_code
        length = len(r.text)

        limited = False
        limit_type = ""
        if status == 429:
            limited = True
            limit_type = "HTTP 429"
        elif status == 403:
            limited = True
            limit_type = "HTTP 403"
        elif status == 200 and length < 200:
            limited = True
            limit_type = f"short_body({length}b)"
        elif status == 200 and ("验证" in r.text[:500] or "captcha" in r.text[:500].lower()):
            limited = True
            limit_type = "captcha"
        elif status != 200:
            limited = True
            limit_type = f"HTTP {status}"

        return {"idx": idx, "status": status, "len": length,
                "limited": limited, "limit_type": limit_type, "elapsed": elapsed,
                "url": url[:60]}
    except Exception as e:
        elapsed = round(time.time() - t0, 3)
        return {"idx": idx, "status": 0, "len": 0,
                "limited": True, "limit_type": str(e)[:40], "elapsed": elapsed,
                "url": url[:60]}


def run():
    log("# sinafin 并发限流阈值测试")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**股票数**: {len(STOCKS)}")
    log(f"**并发级别**: {CONCURRENCY_LEVELS}")
    log(f"**限流判定**: HTTP 429/403/200短内容/captcha")
    log()

    # ── 收集 URL ──
    log("---")
    log("## 收集文章 URL")
    log()

    backend = SinaFinBackend()
    all_urls = []
    for code in STOCKS:
        try:
            results = backend.search(code, max_results=10)
            for r in results:
                url = r.get("url", "")
                if url.startswith("http"):
                    all_urls.append((code, url))
        except Exception as e:
            pass

    log(f"收集到 **{len(all_urls)}** 个 sinafin 文章 URL（来自 {len(STOCKS)} 只股票）")
    if not all_urls:
        log("❌ 无 URL，无法测试")
        return
    log()

    # ── 各并发级别测试 ──
    log("---")
    log("## 并发测试结果")
    log()
    log("| 并发数 | 请求数 | 成功 | 限流 | 成功率 | 最慢(s) | 限流详情 |")
    log("|:------:|:------:|:----:|:----:|:------:|:-------:|:---------|")

    for concurrency in CONCURRENCY_LEVELS:
        pool_urls = all_urls[:concurrency]
        if len(pool_urls) < concurrency:
            log(f"| {concurrency} | {len(pool_urls)} | — | — | — | — | 不足 {concurrency} 个 URL |")
            continue

        results = [None] * len(pool_urls)
        t0 = time.time()

        # 每个并发级别用独立的 Session + 连接池
        sess = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=concurrency, pool_maxsize=concurrency)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            fmap = {}
            for i, (code, url) in enumerate(pool_urls):
                fut = pool.submit(try_fetch, sess, url, i)
                fmap[fut] = i
            for fut in as_completed(fmap):
                i = fmap[fut]
                results[i] = fut.result()

        ok = sum(1 for r in results if r and not r["limited"])
        limited = sum(1 for r in results if r and r["limited"])
        wall = round(time.time() - t0, 2)

        max_t = 0
        for r in results:
            if r and r["elapsed"] > max_t:
                max_t = r["elapsed"]

        # 限流详情
        limit_details = {}
        for r in results:
            if r and r["limited"]:
                lt = r["limit_type"]
                limit_details[lt] = limit_details.get(lt, 0) + 1
        detail_str = "; ".join(f"{k}={v}" for k, v in sorted(limit_details.items()))

        log(f"| {concurrency} | {len(pool_urls)} | {ok} | {limited} | {ok/len(pool_urls)*100:.0f}% | {max_t}s | {detail_str} |")

        # 间隔 3 秒恢复
        time.sleep(3)

    log()
    log("---")
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("_报告自动生成_")

    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"sinafin_ratelimit_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")


if __name__ == "__main__":
    run()
