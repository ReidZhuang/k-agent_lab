"""
并发多引擎压力测试 — 生成详细 MD 报告。

流程:
  1. 4 只股票 × 4 引擎 = 16 请求并发 POST /search
  2. 记录每个请求的"发送→响应"精准时间
  3. 从每只股票的每个引擎返回列表中选文取正文
  4. 输出完整的 MD 报告（含时间线+文章列表+正文全文）

用法:
    conda run -n stock_agent python3 test_drive/test_concurrent_engines.py
"""
import requests, json, time, random, sys, os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"

# 4 只股票（名称 + 代码映射）
STOCK_ENTRIES = [
    ("淮北矿业", "600985"),
    ("博瑞医药", "688166"),
    ("凯莱英",  "002821"),
    ("广生堂",  "300436"),
]
ENGINES = ["sinafin", "baidufin", "juchao", "thsfin"]
FILTER_DAYS = 5
MAX_RESULTS = 10

REPORT = []


def log(line=""):
    REPORT.append(line)
    print(line)


def now_ms() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def ts_us() -> float:
    return time.time()


def search_one(stock_name: str, stock_code: str, engine: str, idx: int) -> dict:
    """单个 /search 请求。juchao 用名称，其他引擎用代码。"""
    t_send = ts_us()
    t_send_str = now_ms()
    http_code = 0
    j = {}
    err_detail = ""

    query = stock_name if engine == "juchao" else stock_code

    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    try:
        resp = sess.post(
            f"{API_BASE}/search",
            json={
                "query": query, "engine": engine,
                "mode": "list", "max_results": MAX_RESULTS,
                "filter_days": FILTER_DAYS,
            },
            timeout=120,
        )
        http_code = resp.status_code
        try:
            j = resp.json()
        except Exception as e:
            j = {"raw_text": resp.text[:500]}
        if http_code != 200:
            err_detail = j.get("detail", j.get("raw_text", ""))
    except Exception as e:
        return {
            "idx": idx, "stock": stock_name, "engine": engine,
            "send_at": t_send_str, "recv_at": now_ms(),
            "elapsed_s": round(ts_us() - t_send, 4),
            "http_code": 0, "status": "HTTP_ERR",
            "session_id": "", "total_raw": 0, "total": 0,
            "articles": [], "error": str(e), "error_detail": "",
        }
    finally:
        sess.close()

    preview = j.get("preview", {})
    arts = preview.get("articles", [])
    return {
        "idx": idx, "stock": stock_name, "engine": engine,
        "send_at": t_send_str, "recv_at": now_ms(),
        "elapsed_s": round(ts_us() - t_send, 4),
        "http_code": http_code,
        "status": j.get("status", "???"),
        "session_id": j.get("session_id", ""),
        "total_raw": preview.get("total_raw", 0),
        "total": preview.get("total", 0),
        "articles": arts,
        "filter_stats": preview.get("filter_stats", {}),
        "elapsed_api": j.get("elapsed", 0),
        "error_detail": err_detail,
    }


def fetch_article(session_id: str, aids: list[str]) -> dict:
    t0 = ts_us()
    t_send = now_ms()
    try:
        resp = requests.post(f"{API_BASE}/article", json={
            "session_id": session_id, "article_ids": aids
        }, timeout=30)
        data = resp.json()
    except Exception as e:
        return {"send_at": t_send, "recv_at": now_ms(),
                "elapsed_s": round(ts_us() - t0, 4),
                "articles": [], "error": str(e)}
    return {"send_at": t_send, "recv_at": now_ms(),
            "elapsed_s": round(ts_us() - t0, 4),
            "articles": data.get("articles", [])}


def run():
    log(f"# 并发多引擎压力测试报告")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**API**: {API_BASE}")
    log(f"**并发配置**: 12 workers, Semaphore(16)")
    log(f"**测试参数**: {len(STOCK_ENTRIES)} 只股票 × {len(ENGINES)} 引擎 = {len(STOCK_ENTRIES)*len(ENGINES)} 请求并发")
    log(f"**filter_days**: {FILTER_DAYS}, **max_results**: {MAX_RESULTS}")
    log()

    # ── Phase 1: 并发搜索 ──
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log("### 请求时间线")
    log()
    log("| # | 股票 | 引擎 | query | 发送时刻 | 返回时刻 | 耗时(s) | HTTP | 状态 | 条数 |")
    log("|---|------|------|-------|----------|----------|---------|------|------|------|")

    tasks = []
    idx = 0
    for name, code in STOCK_ENTRIES:
        for eng in ENGINES:
            tasks.append((name, code, eng, idx))
            idx += 1

    all_results = []
    t_all_start = ts_us()
    with ThreadPoolExecutor(max_workers=16) as pool:
        fmap = {pool.submit(search_one, n, c, e, i): i for n, c, e, i in tasks}
        for fut in as_completed(fmap):
            all_results.append(fut.result())

    total_elapsed = round(ts_us() - t_all_start, 3)
    all_results.sort(key=lambda r: r["idx"])

    code_map = {n: c for n, c in STOCK_ENTRIES}
    for r in all_results:
        q = r["stock"] if r["engine"] == "juchao" else code_map.get(r["stock"], "?")
        extra = r.get("error_detail", "")[:60]
        log(
            f"| {r['idx']+1} | {r['stock']} | {r['engine']} "
            f"| {q} | {r['send_at']} | {r['recv_at']} "
            f"| {r['elapsed_s']} | {r['http_code']} "
            f"| {r['status']} | {r['total']}/{r['total_raw']} "
            f"{'⚠ ' + extra if extra else ''} |"
        )

    log()
    log(f"> 16 请求全部返回总耗时: **{total_elapsed}s**")
    log()

    # ── 文章列表 ──
    log("### 各引擎返回文章列表")
    log()
    for r in all_results:
        sid = r["session_id"]
        arts = r["articles"]
        log(f"<details>")
        log(f"<summary><b>{r['stock']} × {r['engine']}</b> — "
            f"HTTP {r['http_code']} / {r['status']} / "
            f"{len(arts)} 篇 / {r['elapsed_s']}s / session: <code>{sid}</code></summary>")
        log()
        if not arts:
            log("  _(无文章或请求失败)_")
        else:
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

    # ── Phase 2: 取正文 ──
    log("---")
    log("## Phase 2: 取正文")
    log()
    log("从每只股票的每个引擎返回结果中，随机选 1~2 篇文章取正文。")
    log()

    # ── 展示被选文章 ID ──
    log("### 被选文章 ID")
    log()
    log("| 股票 | 引擎 | 被选文章ID | 标题 |")
    log("|------|------|-----------|------|")

    body_queue = []
    for r in all_results:
        sid = r["session_id"]
        arts = r["articles"]
        if sid and arts and r["http_code"] == 200:
            sample = random.sample(arts, min(len(arts), 2))
            body_queue.append({
                "stock": r["stock"], "engine": r["engine"],
                "session_id": sid,
                "aids": [a["id"] for a in sample],
                "titles": [a["title"] for a in sample],
            })
            aids_str = ", ".join(a["id"] for a in sample)
            titles_str = " ; ".join(a["title"][:30] for a in sample)
            log(f"| {r['stock']} | {r['engine']} | {aids_str} | {titles_str} |")

    if not body_queue:
        log("_(无可用文章)_")
    else:
        log(f"共 {len(body_queue)} 个 session, {sum(len(q['aids']) for q in body_queue)} 篇正文待取。")
        log()

        pending = [q for q in body_queue if q["engine"] != "ddg"]
        if pending:
            log("**等待后台 PDF/正文提取...**")
            for q in pending:
                for _ in range(15):
                    time.sleep(2)
                    try:
                        st = requests.get(f"{API_BASE}/poll/{q['session_id']}", timeout=5
                        ).json().get("status", "")
                        if st == "done":
                            break
                    except Exception:
                        pass
            log("  后台提取完成。")
            log()

        # 正文记录
        log("### 正文提取记录")
        log()
        log("| 股票 | 引擎 | 请求时刻 | 返回时刻 | 耗时(s) | 文章ID | 状态 | 字数 |")
        log("|------|------|----------|----------|---------|--------|------|------|")
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [(q, pool.submit(fetch_article, q["session_id"], q["aids"])) for q in body_queue]
            for q, fut in futs:
                br = fut.result()
                for a in br.get("articles", []):
                    body = a.get("body_text", "")
                    log(f"| {q['stock']} | {q['engine']} | {br['send_at']} | {br['recv_at']} "
                        f"| {br['elapsed_s']} | {a['article_id']} | {a['status']} | {len(body)} |")
        log()

        # 正文全文
        log("### 正文全文")
        log()
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [(q, pool.submit(fetch_article, q["session_id"], q["aids"])) for q in body_queue]
            for q, fut in futs:
                br = fut.result()
                for i, a in enumerate(br.get("articles", [])):
                    body = a.get("body_text", "")
                    title_short = q["titles"][i][:60] if i < len(q["titles"]) else a["article_id"]
                    log(f"<details>")
                    log(f"<summary><b>{q['stock']} × {q['engine']}</b> — "
                        f"<code>{a['article_id']}</code> {title_short} ({len(body)}字)</summary>")
                    log()
                    log("```text")
                    log(body if body else "(正文为空)")
                    log("```")
                    log()
                    log("</details>")
                    log()

    # ── 尾部 ──
    log("---")
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log()
    log("_报告自动生成 by test_concurrent_engines.py_")

    # 导出
    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = f"{out_dir}/concurrent_test_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n报告已导出: {md_path}")

    json_path = f"{out_dir}/concurrent_test_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "stocks": [s for s, _ in STOCK_ENTRIES],
            "engines": ENGINES,
            "search_results": [{
                "stock": r["stock"], "engine": r["engine"],
                "http_code": r["http_code"],
                "send_at": r["send_at"], "recv_at": r["recv_at"],
                "elapsed_s": r["elapsed_s"],
                "status": r["status"], "session_id": r["session_id"],
                "total_raw": r["total_raw"], "total": r["total"],
                "filter_stats": r["filter_stats"],
                "articles": [{"id": a["id"], "title": a["title"],
                              "date": a.get("date", ""),
                              }
                             for a in r.get("articles", [])],
            } for r in all_results],
        }, f, ensure_ascii=False, indent=2)
    print(f"原始数据: {json_path}")


if __name__ == "__main__":
    run()
