"""
综合并发测试 v4 — 随机选股 + 错峰正文获取

测试目标:
  1. 20 随机股票 × 5 引擎并发搜索（Phase 1），失败自动重试 3 轮（3-5s 间隔）
  2. Phase 2 逐 session 错峰调 /article（间隔 1-3s），验证:
     - 按需懒加载正常工作
     - 所有引擎/文章最终返回
  3. 最近 2 天（qnainfo 最近 5 天）
  4. 整体超时 20 分钟

用法:
    conda run -n stock_agent python3 test_drive/test_comprehensive_v4.py
"""
import requests, time, os, random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"
MAX_RESULTS = 10
GLOBAL_TIMEOUT = 1200  # 20 分钟
POLL_INTERVAL = 3

_HTTP_SESSION = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=200)
_HTTP_SESSION.mount("http://", _adapter)

# ── 股票池（54 支） ──
STOCK_POOL = [
    ("平安银行", "000001"), ("万科A", "000002"), ("中兴通讯", "000063"),
    ("中联重科", "000157"), ("潍柴动力", "000338"), ("酒鬼酒", "000799"),
    ("双汇发展", "000895"), ("华润三九", "000999"), ("分众传媒", "002027"),
    ("科大讯飞", "002230"), ("上海莱士", "002252"), ("以岭药业", "002603"),
    ("通鼎互联", "002491"), ("汇川技术", "300124"), ("智飞生物", "300122"),
    ("华大基因", "300676"), ("汤臣倍健", "300146"), ("光环新网", "300383"),
    ("中国平安", "601318"), ("中国人寿", "601628"),
    ("贵州茅台", "600519"), ("招商银行", "600036"), ("长江电力", "600900"),
    ("海尔智家", "600690"), ("伊利股份", "600887"),
    ("牧原股份", "002714"), ("宁德时代", "300750"), ("迈瑞医疗", "300760"),
    ("东方财富", "300059"), ("药明康德", "603259"),
    ("比亚迪", "002594"), ("阳光电源", "300274"), ("亿纬锂能", "300014"),
    ("北方华创", "002371"), ("中微公司", "688012"),
    ("金山办公", "688111"), ("中芯国际", "688981"),
    ("恒瑞医药", "600276"), ("复星医药", "600196"), ("长春高新", "000661"),
    ("通威股份", "600438"), ("隆基绿能", "601012"),
    ("紫金矿业", "601899"), ("洛阳钼业", "603993"),
    ("美的集团", "000333"), ("格力电器", "000651"),
    ("中信证券", "600030"), ("东方证券", "600958"),
    ("中国中免", "601888"), ("海康威视", "002415"),
    ("韦尔股份", "603501"), ("三一重工", "600031"),
    ("泸州老窖", "000568"), ("山西汾酒", "600809"),
]

# 抽 20 支
random.seed(int(time.time()))
STOCKS = random.sample(STOCK_POOL, 20)

ENGINES = [
    ("baidufin", {"filter_days": 2}),
    ("sinafin",  {"filter_days": 2}),
    ("thsfin",   {"filter_days": 2}),
    ("juchao",   {"filter_days": 2}),
    ("qnainfo",  {"start_date": "2026-07-19", "end_date": "2026-07-24"}),
]

REPORT = []
def log(s=""):
    REPORT.append(s)
    print(s)


def search_engine(name, code, engine, params, idx):
    """搜索，失败时重试最多 3 轮，每轮间隔 3-5 秒。"""
    body = {"query": code, "engine": engine, "mode": "list", "max_results": MAX_RESULTS}
    body.update(params)
    for attempt in range(3):
        t0 = time.time()
        try:
            r = _HTTP_SESSION.post(f"{API_BASE}/search", json=body, timeout=300)
            if r.ok:
                j = r.json()
                p = j.get("preview", {})
                return {"idx": idx, "stock": name, "engine": engine,
                        "http": r.status_code, "status": j.get("status", "?"),
                        "session_id": j.get("session_id", ""),
                        "total": p.get("total", 0), "articles": p.get("articles", []),
                        "elapsed": round(time.time()-t0, 2), "error": ""}
            # HTTP 错误（非 200）
            err_text = j.get("detail", r.text[:80]) if r.ok else r.text[:80]
        except Exception as e:
            err_text = str(e)[:80]

        if attempt == 2:
            return {"idx": idx, "stock": name, "engine": engine,
                    "http": 0, "status": "HTTP_ERR", "session_id": "",
                    "total": 0, "articles": [], "elapsed": round(time.time()-t0, 2),
                    "error": err_text}

        delay = random.uniform(3.0, 5.0)
        log(f"  ⟳ 第{attempt+1}次失败，{delay:.1f}s 后重试: {name} {engine}（{err_text[:50]}）")
        time.sleep(delay)


def fetch_articles(session_id, article_ids, idx, label):
    """调 /article，一直重试到全部 ready/error。"""
    for attempt in range(200):
        t0 = time.time()
        try:
            r = _HTTP_SESSION.post(f"{API_BASE}/article", json={
                "session_id": session_id, "article_ids": article_ids,
            }, timeout=120)
            j = r.json() if r.ok else {}
        except Exception as e:
            return {"idx": idx, "http": 0, "articles": [],
                    "elapsed": round(time.time()-t0, 2), "error": str(e)[:80], "retries": attempt}

        arts = j.get("articles", [])
        statuses = [a.get("status", "?") for a in arts]

        if all(s in ("ready", "error") for s in statuses):
            return {"idx": idx, "http": r.status_code, "articles": arts,
                    "elapsed": round(time.time()-t0, 2), "error": "", "retries": attempt}

        time.sleep(POLL_INTERVAL)

    return {"idx": idx, "http": 0, "articles": [],
            "elapsed": 0, "error": "max_retries", "retries": 200}


def run():
    t_start = time.time()

    log(f"# 综合并发测试 v4 — 随机选股 + 错峰正文获取")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**整体超时**: {GLOBAL_TIMEOUT}s（8 分钟）")
    log(f"**规模**: {len(STOCKS)} 股票 × {len(ENGINES)} 引擎 = {len(STOCKS)*len(ENGINES)} 请求")
    log(f"**Phase 2 间隔**: 1-3 秒随机，逐 session 串行")
    log(f"**随机股票**: {', '.join(f'{n}({c})' for n, c in STOCKS)}")
    log()

    # ════════════════════════════════════════
    # Phase 1: 并发搜索
    # ════════════════════════════════════════
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log("| # | 股票 | 引擎 | HTTP | 状态 | 耗时(s) | 条数 | 备注 |")
    log("|---|------|------|:----:|:----:|:-------:|:----:|:----:|")

    tasks = []
    for idx, (name, code) in enumerate(STOCKS):
        for eng, p in ENGINES:
            tasks.append((name, code, eng, p, len(tasks)))
    search_results = [None] * len(tasks)
    t_phase1 = time.time()

    with ThreadPoolExecutor(max_workers=50) as pool:
        fmap = {}
        for t in tasks:
            fut = pool.submit(search_engine, *t)
            fmap[fut] = t[-1]
        for f in as_completed(fmap):
            r = f.result()
            search_results[r["idx"]] = r

    phase1_wall = round(time.time() - t_phase1, 2)

    engine_stats = {e: {"ok": 0, "arts": 0, "err": 0} for e, _ in ENGINES}
    for r in search_results:
        if not r: continue
        k = engine_stats[r["engine"]]
        if r["http"] == 200: k["ok"] += 1; k["arts"] += r["total"]
        else: k["err"] += 1

    for r in search_results:
        if not r: continue
        note = r["error"][:50] if r["error"] else ""
        log(f"| {r['idx']+1} | {r['stock']} | {r['engine']} | {r['http']} | {r['status']} | {r['elapsed']} | {r['total']} | {note} |")

    total_arts = sum((r["total"] for r in search_results if r), 0)
    ok = sum(1 for r in search_results if r and r["http"] == 200)
    fail = sum(1 for r in search_results if r and r["http"] != 200)

    log()
    log(f"> Phase 1: 请求={len(search_results)}, 成功={ok}, 失败={fail}, 文章={total_arts} 篇, 耗时={phase1_wall}s")
    for eng, st in engine_stats.items():
        log(f">   {eng}: 成功={st['ok']}, 失败={st['err']}, 文章={st['arts']} 篇")
    log()

    # ════════════════════════════════════════
    # Phase 2: 错峰正文获取（间隔 1-3s）
    # ════════════════════════════════════════
    # 排除 qnainfo（正文已随 search 返回）
    sessions = []
    for r in search_results:
        if not r or r["http"] != 200 or not r["session_id"]: continue
        if r["engine"] == "qnainfo": continue
        arts = [a for a in r["articles"] if a.get("body_avail") == "有"]
        if not arts: continue
        sessions.append({
            "session_id": r["session_id"],
            "article_ids": [a["id"] for a in arts],
            "stock": r["stock"],
            "engine": r["engine"],
            "count": len(arts),
        })

    total_sessions = len(sessions)
    total_articles = sum(s["count"] for s in sessions)

    log("---")
    log("## Phase 2: 错峰正文获取（间隔 1-3s）")
    log()
    log(f"**待取 session 数**: {total_sessions}")
    log(f"**待取文章数**: {total_articles}")
    log()

    if total_sessions == 0:
        log("> 无可用 session，跳过 Phase 2。")
        phase2_wall = 0
    else:
        t_phase2 = time.time()

        log("| # | 股票 | 引擎 | 文章数 | 间隔(s) | 状态 | 重试 | 耗时 |")
        log("|---|------|------|:------:|:-------:|:----:|:----:|:----:|")

        article_results = []

        for i, sess in enumerate(sessions):
            # 错峰：每次 session 调用间隔 1-3 秒
            if i > 0:
                delay = random.uniform(1.0, 3.0)
                time.sleep(delay)
            else:
                delay = 0.0

            label = f"{sess['stock']}×{sess['engine']}"
            ar = fetch_articles(sess["session_id"], sess["article_ids"], i, label)
            ar["stock"] = sess["stock"]
            ar["engine"] = sess["engine"]
            ar["count"] = sess["count"]
            ar["delay"] = round(delay, 2)
            article_results.append(ar)

            statuses = [a.get("status", "?") for a in ar.get("articles", [])]
            ready = statuses.count("ready")
            error = statuses.count("error")
            result_str = f"✅{ready}/❌{error}" if ready+error > 0 else "⏳?"

            note = ar.get("error", "")
            log(f"| {i+1} | {sess['stock']} | {sess['engine']} | {sess['count']} | {ar['delay']} | {result_str} | {ar.get('retries',0)} | {ar['elapsed']}s | {note} |")

        phase2_wall = round(time.time() - t_phase2, 2)

        ready_cnt = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "ready")
        error_cnt = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "error")
        still_pending = sum(1 for ar in article_results for a in ar.get("articles", []) if a.get("status") == "processing")
        total_target = sum(len(ar.get("articles", [])) for ar in article_results)

        log()
        log(f"> Phase 2: 目标={total_target}, ready={ready_cnt}, error={error_cnt}, "
            f"still_processing={still_pending}, 耗时={phase2_wall}s")
        log()

        # 正文抽样
        log("### 正文抽样（前 10 篇）")
        log()
        sampled = 0
        for ar in article_results:
            if not ar: continue
            for a in ar.get("articles", []):
                if sampled >= 10:
                    break
                body = a.get("body_text", "")
                err = a.get("fetch_error", "")
                sid = a.get("article_id", "?")
                eng = ar.get("engine", "?")
                stk = ar.get("stock", "?")
                if a.get("status") == "error":
                    log(f"⚠ **{stk}×{eng} — {sid}**: {err}")
                    log()
                elif a.get("status") == "ready" and body:
                    log(f"✅ **{stk}×{eng} — {sid}**（{len(body)} 字）")
                    log(f"> {body[:200]}")
                    log()
                    sampled += 1

    # ════════════════════════════════════════
    # 汇总
    # ════════════════════════════════════════
    total_wall = round(time.time() - t_start, 2)
    log("---")
    log("## 汇总")
    log()
    log("| 阶段 | 耗时 |")
    log("|:-----|:----:|")
    log(f"| Phase 1（搜索） | {phase1_wall}s |")
    log(f"| Phase 2（正文） | {phase2_wall}s |")
    log(f"| **总耗时** | **{total_wall}s** |")
    log()
    log("### 各引擎")
    log()
    log("| 引擎 | 请求 | 成功 | 失败 | 文章数 |")
    log("|:-----|:----:|:----:|:----:|:------:|")
    for eng, st in engine_stats.items():
        log(f"| {eng} | {st['ok']+st['err']} | {st['ok']} | {st['err']} | {st['arts']} |")
    log()
    log(f"**调试日志**: `logs/debug_{datetime.now().strftime('%Y%m%d')}.log`")
    log(f"**结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 保存
    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"comprehensive_v4_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")


if __name__ == "__main__":
    run()
