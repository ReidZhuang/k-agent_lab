"""
综合并发测试 v2: 20 支股票 × 5 引擎 + 正文重试

引擎配置:
  - qnainfo: 最近 5 天
  - juchao:  最近 3 天
  - baidufin / sinafin / thsfin: 上一个交易日至今（filter_days=2）
流程:
  Phase 1 — 并发搜索
  Phase 2 — 随机选文章调 /article，若 processing 则 sleep 重试

用法:
    conda run -n stock_agent python3 test_drive/test_comprehensive_v2.py
"""
import requests, time, os, random, sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"
MAX_RESULTS = 10

# 全局 Session — 连接池放大
_HTTP_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=200)
_HTTP_SESSION.mount("http://", _adapter)

STOCKS = [
    ("贵州茅台", "600519"), ("宁德时代", "300750"), ("格力电器", "000651"),
    ("五粮液", "000858"), ("美的集团", "000333"), ("迈瑞医疗", "300760"),
    ("东方财富", "300059"), ("立讯精密", "002475"), ("阳光电源", "300274"),
    ("牧原股份", "002714"), ("比亚迪", "002594"), ("海康威视", "002415"),
    ("紫金矿业", "601899"), ("恒瑞医药", "600276"), ("隆基绿能", "601012"),
    ("药明康德", "603259"), ("凯莱英", "002821"), ("广生堂", "300436"),
    ("爱尔眼科", "300015"), ("万华化学", "600309"),
]

ENGINES = [
    ("baidufin",  {"filter_days": 2}),
    ("sinafin",   {"filter_days": 2}),
    ("thsfin",    {"filter_days": 2}),
    ("juchao",    {"filter_days": 3}),
    ("qnainfo",   {"start_date": "2026-07-19", "end_date": "2026-07-24"}),
]

REPORT = []
def log(s=""):
    REPORT.append(s)
    print(s)

def search_engine(name, code, engine, params, idx):
    t0 = time.time()
    body = {"query": code, "engine": engine, "mode": "list", "max_results": MAX_RESULTS}
    body.update(params)
    try:
        r = _HTTP_SESSION.post(f"{API_BASE}/search", json=body, timeout=300)
        http = r.status_code
        j = r.json() if r.ok else {}
    except Exception as e:
        return {"idx": idx, "stock": name, "engine": engine,
                "http": 0, "status": "HTTP_ERR", "session_id": "",
                "total": 0, "articles": [], "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}
    p = j.get("preview", {})
    return {"idx": idx, "stock": name, "engine": engine,
            "http": http, "status": j.get("status", "?"), "session_id": j.get("session_id", ""),
            "total": p.get("total", 0), "articles": p.get("articles", []),
            "elapsed": round(time.time()-t0, 2), "error": ""}

def fetch_article(session_id, article_ids, idx, retry=3):
    """调 /article，若 processing 则 sleep 重试。"""
    last_arts = []
    last_http = 0
    last_elapsed = 0
    last_attempt = 0
    for attempt in range(retry):
        t0 = time.time()
        try:
            r = _HTTP_SESSION.post(f"{API_BASE}/article", json={
                "session_id": session_id, "article_ids": article_ids,
            }, timeout=300)
            last_http = r.status_code
            j = r.json() if r.ok else {}
        except Exception as e:
            return {"idx": idx, "http": 0, "articles": [], "elapsed": round(time.time()-t0, 2),
                    "error": str(e)[:80], "retries": attempt}

        arts = j.get("articles", [])
        last_arts = arts
        last_elapsed = round(time.time()-t0, 2)
        last_attempt = attempt
        statuses = [a.get("status", "?") for a in arts]

        if all(s != "processing" for s in statuses):
            return {"idx": idx, "http": last_http, "articles": last_arts,
                    "elapsed": last_elapsed, "error": "", "retries": attempt}

        if attempt < retry - 1:
            time.sleep(3)

    return {"idx": idx, "http": last_http, "articles": last_arts,
            "elapsed": last_elapsed, "error": "still_processing", "retries": last_attempt}


def run():
    t_start = time.time()

    log(f"# 综合并发测试 v2 — 20 股票 × 5 引擎 + 正文重试")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**测试规模**: {len(STOCKS)} 股票 × {len(ENGINES)} 引擎 = {len(STOCKS)*len(ENGINES)} 搜索请求")
    log(f"**引擎配置**:")
    log(f"  - baidufin / sinafin / thsfin: 上一个交易日至今（filter_days=2）")
    log(f"  - juchao: 最近 3 天（filter_days=3）")
    log(f"  - qnainfo: 最近 5 天（2026-07-19 ~ 2026-07-24）")
    log(f"**正文重试**: /article 若返回 processing，sleep 3s 重试，最多 3 次")
    log()

    # ============================================================
    # Phase 1: 并发搜索
    # ============================================================
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log("| # | 股票 | 引擎 | HTTP | 状态 | 耗时(s) | 条数 | 备注 |")
    log("|---|------|------|:----:|:----:|:-------:|:----:|:-----|")

    tasks = []
    idx = 0
    for name, code in STOCKS:
        for engine, params in ENGINES:
            query = name if engine == "juchao" else code
            tasks.append((name, code, engine, params, query, idx))
            idx += 1

    search_results = [None] * len(tasks)
    t_phase1 = time.time()
    with ThreadPoolExecutor(max_workers=50) as pool:
        fmap = {}
        for name, code, engine, params, query, i in tasks:
            fut = pool.submit(search_engine, name, code, engine, params, i)
            fmap[fut] = i
        for fut in as_completed(fmap):
            r = fut.result()
            search_results[r["idx"]] = r
    phase1_wall = round(time.time() - t_phase1, 2)

    engine_stats = {e: {"ok": 0, "arts": 0, "err": 0} for e, _ in ENGINES}
    for r in search_results:
        if not r: continue
        if r["http"] == 200:
            engine_stats[r["engine"]]["ok"] += 1
            engine_stats[r["engine"]]["arts"] += r["total"]
        else:
            engine_stats[r["engine"]]["err"] += 1

    for r in search_results:
        if not r: continue
        note = r["error"][:40] if r["error"] else ("✔" if r["total"] > 0 else "—")
        log(f"| {r['idx']+1} | {r['stock']} | {r['engine']} | {r['http']} | {r['status']} | {r['elapsed']} | {r['total']} | {note} |")

    total_ok = sum(1 for r in search_results if r and r["http"] == 200)
    total_err = sum(1 for r in search_results if r and r["http"] != 200)
    total_articles = sum((r["total"] for r in search_results if r), 0)

    log()
    log(f"> Phase 1 完成: 请求={len(search_results)}, 成功={total_ok}, 失败={total_err}, "
        f"文章总计={total_articles} 篇, 并发耗时={phase1_wall}s")
    log()
    for eng, st in engine_stats.items():
        log(f">   {eng}: 成功={st['ok']}, 失败={st['err']}, 文章={st['arts']} 篇")
    log()

    # ============================================================
    # Phase 2: 正文提取（含重试）
    # ============================================================
    log("---")
    log("## Phase 2: 正文提取（含 processing 重试）")
    log()

    # 收集可用文章（排除 qnainfo — session 已关闭）
    article_candidates = []
    for r in search_results:
        if not r or r["http"] != 200 or not r["session_id"]:
            continue
        if r["engine"] == "qnainfo":
            continue  # qnainfo session 已自动关闭
        arts = r["articles"]
        if not arts:
            continue
        valid = [a["id"] for a in arts if a.get("body_avail") == "有" and a.get("body_status") != "error"]
        if valid:
            article_candidates.append((r["session_id"], r["engine"], r["stock"], valid))

    if article_candidates:
        log("| # | 股票 | 引擎 | 请求ID | HTTP | 状态 | 重试次数 | 耗时(s) |")
        log("|---|------|------|--------|:----:|:----:|:--------:|:-------:|")

        article_tasks = []
        for sid, eng, stk, aids in article_candidates:
            pick = random.sample(aids, min(2, len(aids)))
            article_tasks.append((sid, pick, eng, stk))

        t_phase2 = time.time()
        article_results = [None] * len(article_tasks)
        with ThreadPoolExecutor(max_workers=30) as pool:
            afmap = {}
            for i, (sid, aids, eng, stk) in enumerate(article_tasks):
                fut = pool.submit(fetch_article, sid, aids, i, 3)
                afmap[fut] = i
            for fut in as_completed(afmap):
                i = afmap[fut]
                article_results[i] = fut.result()

        phase2_wall = round(time.time() - t_phase2, 2)

        ready_cnt = processing_cnt = error_cnt = 0
        for i, (sid, aids, eng, stk) in enumerate(article_tasks):
            ar = article_results[i]
            if not ar: continue
            statuses = [a.get("status", "?") for a in ar.get("articles", [])]
            status_str = ",".join(statuses)
            for s in statuses:
                if s == "ready": ready_cnt += 1
                elif s == "processing": processing_cnt += 1
                elif s == "error": error_cnt += 1

            note = ar.get("error", "")
            log(f"| {i+1} | {stk} | {eng} | {','.join(aids)} | {ar['http']} "
                f"| {status_str} | {ar.get('retries',0)} | {ar['elapsed']} | {note} |")

        log()
        log(f"> Phase 2 完成: 请求={len(article_tasks)}, "
            f"ready={ready_cnt}, processing={processing_cnt}, error={error_cnt}, "
            f"并发耗时={phase2_wall}s")
        log()

        # 正文抽样
        log("### 正文内容抽样")
        log()
        for i, (sid, aids, eng, stk) in enumerate(article_tasks):
            ar = article_results[i]
            if not ar: continue
            for a in ar.get("articles", [])[:1]:
                if a.get("status") == "ready":
                    body = a.get("body_text", "")
                    log(f"**{stk} × {eng} — {a['article_id']}**（正文前 200 字）")
                    log()
                    log(f"> {body[:200]}")
                    if len(body) > 200:
                        log(f"> *...（截断，共 {len(body)} 字）*")
                    log()
                    break
    else:
        phase2_wall = 0
        log("> 无可用文章用于正文提取。")
        log()

    # ============================================================
    # 汇总
    # ============================================================
    total_wall = round(time.time() - t_start, 2)
    log("---")
    log("## 汇总")
    log()
    log("| 阶段 | 并发耗时 |")
    log("|:-----|:--------:|")
    log(f"| Phase 1（搜索） | {phase1_wall}s |")
    log(f"| Phase 2（正文） | {phase2_wall}s |")
    log(f"| **总计** | **{total_wall}s** |")
    log()
    log("### 各引擎表现")
    log()
    log("| 引擎 | 请求 | 成功 | 失败 | 文章数 | 说明 |")
    log("|:-----|:----:|:----:|:----:|:------:|:-----|")
    for eng, st in engine_stats.items():
        desc = {"baidufin": "百度股市通", "sinafin": "新浪财经",
                "thsfin": "同花顺 F10", "juchao": "巨潮公告（3天）",
                "qnainfo": "互动易问答（5天）"}.get(eng, "")
        log(f"| {eng} | {st['ok']+st['err']} | {st['ok']} | {st['err']} | {st['arts']} | {desc} |")
    log()
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"comprehensive_v2_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")
    return path


if __name__ == "__main__":
    run()
