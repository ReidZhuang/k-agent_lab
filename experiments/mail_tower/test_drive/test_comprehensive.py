"""
综合并发测试：20 支股票 × 5 引擎（baidufin, sinafin, thsfin, juchao, qnainfo）
  - qnainfo: 最近 5 天
  - 其他引擎: 上一个交易日至今
  - 列表返回后随机选取文章请求正文
  - 全部并发，记录完整时间

用法:
    conda run -n stock_agent python3 test_drive/test_comprehensive.py
"""
import requests, time, os, random, sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as fut_wait

API_BASE = "http://localhost:8300"
MAX_RESULTS = 10

# 全局 Session — 连接池放大到 200，避免客户端连接瓶颈
_HTTP_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=200)
_HTTP_SESSION.mount("http://", _adapter)

# 20 支股票
STOCKS = [
    ("贵州茅台", "600519"),
    ("宁德时代", "300750"),
    ("格力电器", "000651"),
    ("五粮液", "000858"),
    ("美的集团", "000333"),
    ("迈瑞医疗", "300760"),
    ("东方财富", "300059"),
    ("立讯精密", "002475"),
    ("阳光电源", "300274"),
    ("牧原股份", "002714"),
    ("比亚迪", "002594"),
    ("海康威视", "002415"),
    ("紫金矿业", "601899"),
    ("恒瑞医药", "600276"),
    ("隆基绿能", "601012"),
    ("药明康德", "603259"),
    ("凯莱英", "002821"),
    ("广生堂", "300436"),
    ("爱尔眼科", "300015"),
    ("万华化学", "600309"),
]

ENGINES = [
    ("baidufin",  {"filter_days": 2}),   # 上一个交易日至今
    ("sinafin",   {"filter_days": 2}),
    ("thsfin",    {"filter_days": 2}),
    ("juchao",    {"filter_days": 2}),
    ("qnainfo",   {"start_date": "2026-07-19", "end_date": "2026-07-24"}),  # 最近5天
]

REPORT = []
LOG_BUF = []

def log(s="", buf=True):
    REPORT.append(s)
    if buf:
        LOG_BUF.append(s)
    print(s)

def flush_log():
    LOG_BUF.clear()

def search_engine(name, code, engine, params, idx):
    """单次 /search 请求。"""
    t0 = time.time()
    body = {"query": code, "engine": engine, "mode": "list", "max_results": MAX_RESULTS}
    body.update(params)
    try:
        r = _HTTP_SESSION.post(f"{API_BASE}/search", json=body, timeout=300)
        http = r.status_code
        j = r.json() if r.ok else {}
        err = ""
    except Exception as e:
        return {"idx": idx, "stock": name, "code": code, "engine": engine,
                "http": 0, "status": "HTTP_ERR", "session_id": "",
                "total": 0, "articles": [], "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}
    p = j.get("preview", {})
    return {"idx": idx, "stock": name, "code": code, "engine": engine,
            "http": http, "status": j.get("status", "?"), "session_id": j.get("session_id", ""),
            "total": p.get("total", 0), "articles": p.get("articles", []),
            "elapsed": round(time.time()-t0, 2), "error": ""}

def fetch_article(session_id, article_ids, idx):
    """单次 /article 请求。"""
    t0 = time.time()
    try:
        r = _HTTP_SESSION.post(f"{API_BASE}/article", json={
            "session_id": session_id, "article_ids": article_ids,
        }, timeout=300)
        j = r.json() if r.ok else {}
    except Exception as e:
        return {"idx": idx, "http": 0, "articles": [], "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}
    return {"idx": idx, "http": r.status_code,
            "articles": j.get("articles", []),
            "elapsed": round(time.time()-t0, 2), "error": ""}


def run():
    global REPORT, LOG_BUF
    t_start = time.time()

    log(f"# 综合并发测试：20 支股票 × 5 引擎")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**测试规模**: {len(STOCKS)} 股票 × {len(ENGINES)} 引擎 = {len(STOCKS)*len(ENGINES)} 搜索请求")
    log(f"**引擎配置**:")
    log(f"  - baidufin / sinafin / thsfin / juchao: **上一个交易日至今**（filter_days=2）")
    log(f"  - qnainfo: **最近 5 天**（2026-07-19 ~ 2026-07-24）")
    log()

    # ============================================================
    # Phase 1: 并发搜索
    # ============================================================
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log(f"| # | 股票 | 引擎 | query | HTTP | 状态 | 耗时(s) | 条数 | 备注 |")
    log(f"|---|------|------|-------|:----:|:----:|:-------:|:----:|:-----|")

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

    # 统计
    total_ok = sum(1 for r in search_results if r and r["http"] == 200)
    total_err = sum(1 for r in search_results if r and r["http"] != 200)
    total_articles = sum((r["total"] for r in search_results if r), 0)
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
        q = r["stock"] if r["engine"] == "juchao" else r["code"]
        note = r["error"][:40] if r["error"] else ("✔" if r["total"] > 0 else "—")
        log(f"| {r['idx']+1} | {r['stock']} | {r['engine']} | {q} "
            f"| {r['http']} | {r['status']} | {r['elapsed']} | {r['total']} | {note} |")

    log()
    log(f"> Phase 1 完成: 请求={len(search_results)}, 成功={total_ok}, 失败={total_err}, "
        f"文章总计={total_articles} 篇, 并发耗时={phase1_wall}s")
    log()
    for eng, st in engine_stats.items():
        log(f">   {eng}: 成功={st['ok']}, 失败={st['err']}, 文章={st['arts']} 篇")
    log()

    # ============================================================
    # Phase 2: 正文提取 — 每只股票随机选 2 篇调 /article
    # ============================================================
    log("---")
    log("## Phase 2: 正文提取（随机选文章调 /article）")
    log()

    # 按引擎+股票收集 session_id 和可用的 article_ids
    article_candidates = []  # [(session_id, engine, stock, [article_ids])]

    for r in search_results:
        if not r or r["http"] != 200 or not r["session_id"]:
            continue
        arts = r["articles"]
        if not arts:
            continue
        # 只取 body_status=ready 或 body_avail=有的文章
        valid = [a["id"] for a in arts if a.get("body_avail") == "有" and a.get("body_status") != "error"]
        if valid:
            article_candidates.append((r["session_id"], r["engine"], r["stock"], valid))

    if article_candidates:
        log("| # | 股票 | 引擎 | 请求文章ID | HTTP | 文章状态 | 耗时(s) |")
        log("|---|------|------|-----------|:----:|:--------:|:-------:|")

        # 每只股票×引擎 最多请求 2 篇
        article_tasks = []
        for sid, eng, stk, aids in article_candidates:
            pick = random.sample(aids, min(2, len(aids)))
            article_tasks.append((sid, pick, eng, stk))

        t_phase2 = time.time()
        article_results = [None] * len(article_tasks)
        with ThreadPoolExecutor(max_workers=30) as pool:
            afmap = {}
            for i, (sid, aids, eng, stk) in enumerate(article_tasks):
                fut = pool.submit(fetch_article, sid, aids, i)
                afmap[fut] = i
            for fut in as_completed(afmap):
                i = afmap[fut]
                article_results[i] = fut.result()

        phase2_wall = round(time.time() - t_phase2, 2)

        ready_count = 0
        processing_count = 0
        error_count = 0
        notfound_count = 0

        for i, (sid, aids, eng, stk) in enumerate(article_tasks):
            ar = article_results[i]
            if not ar:
                continue
            statuses = [a.get("status", "?") for a in ar.get("articles", [])]
            status_str = ",".join(statuses)
            for s in statuses:
                if s == "ready": ready_count += 1
                elif s == "processing": processing_count += 1
                elif s == "error": error_count += 1
                else: notfound_count += 1

            note = ar["error"][:30] if ar["error"] else ""
            log(f"| {i+1} | {stk} | {eng} | {','.join(aids)} "
                f"| {ar['http']} | {status_str} | {ar['elapsed']} | {note} |")

        log()
        log(f"> Phase 2 完成: 请求={len(article_tasks)}, "
            f"ready={ready_count}, processing={processing_count}, "
            f"error={error_count}, not_found={notfound_count}, "
            f"并发耗时={phase2_wall}s")
        log()

        # 正文样例
        log("### 正文内容抽样")
        log()
        for i, (sid, aids, eng, stk) in enumerate(article_tasks):
            ar = article_results[i]
            if not ar: continue
            for a in ar.get("articles", [])[:1]:  # 每篇只取第一个文章
                if a.get("status") == "ready":
                    body = a.get("body_text", "")
                    log(f"**{stk} × {eng} — {a['article_id']}**（正文前 200 字）")
                    log()
                    log(f"> {body[:200]}")
                    log(f"> *...（截断，共 {len(body)} 字）*" if len(body) > 200 else "")
                    log()
                    break

    else:
        log("> 无可用文章用于正文提取。")
        log()
        phase2_wall = 0

    # ============================================================
    # 汇总
    # ============================================================
    total_wall = round(time.time() - t_start, 2)
    log("---")
    log("## 汇总")
    log()
    log(f"| 阶段 | 并发耗时 |")
    log(f"|:-----|:--------:|")
    log(f"| Phase 1（搜索） | {phase1_wall}s |")
    log(f"| Phase 2（正文） | {phase2_wall}s |")
    log(f"| **总计** | **{total_wall}s** |")
    log()
    log("### 各引擎表现")
    log()
    log("| 引擎 | 请求 | 成功 | 失败 | 文章数 | 说明 |")
    log("|:-----|:----:|:----:|:----:|:------:|:-----|")
    for eng, st in engine_stats.items():
        desc = {
            "baidufin": "百度股市通",
            "sinafin": "新浪财经",
            "thsfin": "同花顺 F10",
            "juchao": "巨潮公告",
            "qnainfo": "互动易问答（session 自动关闭）",
        }.get(eng, "")
        log(f"| {eng} | {st['ok']+st['err']} | {st['ok']} | {st['err']} | {st['arts']} | {desc} |")

    log()
    log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("_报告自动生成_")

    # 写入文件
    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"comprehensive_test_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")
    return path


if __name__ == "__main__":
    run()
