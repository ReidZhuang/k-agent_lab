"""
综合并发测试 v3: 20 股票 × 5 引擎 + 全量正文轮询

引擎配置:
  - baidufin / sinafin / thsfin:  filter_days=2（上一个交易日至今）
  - juchao:  filter_days=3（最近 3 天）
  - qnainfo: 最近 5 天（start_date/end_date）

测试流程:
  Phase 1 — 并发搜索，记录所有 session_id + 文章 ID
  Phase 2 — 轮询 /article 直至所有选定文章就绪（≤10 分钟整体超时）
            取正文的文章数 ≥ Phase 1 文章总数的一半

用法:
    conda run -n stock_agent python3 test_drive/test_comprehensive_v3.py
"""
import requests, time, os, random, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"
MAX_RESULTS = 10
GLOBAL_TIMEOUT = 300  # 整体超时 5 分钟
POLL_INTERVAL = 3     # 轮询间隔秒

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


# ═══════════════════════════════════════════════
# Phase 1: 并发搜索
# ═══════════════════════════════════════════════

def search_engine(name, code, engine, params, idx):
    t0 = time.time()
    body = {"query": code, "engine": engine, "mode": "list", "max_results": MAX_RESULTS}
    body.update(params)
    try:
        r = _HTTP_SESSION.post(f"{API_BASE}/search", json=body, timeout=300)
        http, j = r.status_code, (r.json() if r.ok else {})
    except Exception as e:
        return {"idx": idx, "stock": name, "engine": engine,
                "http": 0, "status": "HTTP_ERR", "session_id": "",
                "total": 0, "articles": [], "elapsed": round(time.time()-t0, 2), "error": str(e)[:80]}
    p = j.get("preview", {})
    return {"idx": idx, "stock": name, "engine": engine,
            "http": http, "status": j.get("status", "?"), "session_id": j.get("session_id", ""),
            "total": p.get("total", 0), "articles": p.get("articles", []),
            "elapsed": round(time.time()-t0, 2), "error": ""}


def run():
    t_start = time.time()
    deadline = t_start + GLOBAL_TIMEOUT

    log(f"# 综合并发测试 v3 — 全量轮询正文")
    log()
    log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"**配置**: {len(STOCKS)} 股票 × {len(ENGINES)} 引擎 = {len(STOCKS)*len(ENGINES)} 搜索请求")
    log(f"**整体超时**: {GLOBAL_TIMEOUT}s（{GLOBAL_TIMEOUT//60} 分钟）")
    for eng, p in ENGINES:
        desc = f"filter_days={p['filter_days']}" if 'filter_days' in p else f"{p['start_date']}~{p['end_date']}"
        log(f"  - {eng}: {desc}")
    log()

    # ── Phase 1: 并发搜索 ──
    log("---")
    log("## Phase 1: 并发搜索")
    log()
    log("| # | 股票 | 引擎 | HTTP | 状态 | 耗时(s) | 条数 | 备注 |")
    log("|---|------|------|:----:|:----:|:-------:|:----:|:-----|")

    tasks = []
    for i, (name, code) in enumerate(STOCKS):
        for eng, p in ENGINES:
            tasks.append((name, code, eng, p, len(tasks)))  # 全局唯一 idx

    search_results = [None] * len(tasks)
    t_phase1 = time.time()

    with ThreadPoolExecutor(max_workers=50) as pool:
        fmap = {}
        for t in tasks:
            fut = pool.submit(search_engine, *t)
            fmap[fut] = t[-1]  # 唯一 idx
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
        note = r["error"][:50] if r["error"] else ("✔" if r["total"] > 0 else "—")
        log(f"| {r['idx']+1} | {r['stock']} | {r['engine']} | {r['http']} | {r['status']} | {r['elapsed']} | {r['total']} | {note} |")

    total_arts = sum((r["total"] for r in search_results if r), 0)
    ok = sum(1 for r in search_results if r and r["http"] == 200)
    fail = sum(1 for r in search_results if r and r["http"] != 200)

    log()
    log(f"> Phase 1: 请求={len(search_results)}, 成功={ok}, 失败={fail}, 文章={total_arts} 篇, 耗时={phase1_wall}s")
    for eng, st in engine_stats.items():
        log(f">   {eng}: 成功={st['ok']}, 失败={st['err']}, 文章={st['arts']} 篇")
    log()

    # ── Phase 2: 全量正文轮询 ──
    # 收集可用的 session → articles（排除 qnainfo）
    session_articles = {}  # session_id → [(article_id, stock, engine)]
    for r in search_results:
        if not r or r["http"] != 200 or not r["session_id"]: continue
        if r["engine"] == "qnainfo": continue  # session 已关闭
        sid = r["session_id"]
        for a in r["articles"]:
            if a.get("body_avail") == "无": continue
            if a.get("body_status") == "error": continue
            session_articles.setdefault(sid, []).append(
                (a["id"], r["stock"], r["engine"]))

    selected_articles = []  # (session_id, article_id, stock, engine)
    for sid, arts in session_articles.items():
        selected_articles.extend((sid, aid, stk, eng) for aid, stk, eng in arts)

    total_available = len(selected_articles)
    min_required = max(1, math.ceil(total_arts / 2))
    actual_to_fetch = min(total_available, min_required)

    if actual_to_fetch == 0:
        log("## Phase 2: 正文轮询")
        log()
        log("> 无可用文章，跳过。")
        log()
        phase2_wall = 0
    else:
        # 随机选取 min_required 篇
        random.shuffle(selected_articles)
        to_fetch = selected_articles[:actual_to_fetch]

        # 按 session 分组
        fetch_by_session = {}
        for sid, aid, stk, eng in to_fetch:
            fetch_by_session.setdefault(sid, []).append((aid, stk, eng))

        log("---")
        log("## Phase 2: 正文轮询")
        log()
        log(f"**Phase 1 文章总数**: {total_arts}")
        log(f"**可用文章（排除 qnainfo + 无正文）**: {total_available}")
        log(f"**需获取正文（≥50%）**: {actual_to_fetch} 篇（来自 {len(fetch_by_session)} 个 session）")
        log(f"**轮询间隔**: {POLL_INTERVAL}s，**整体超时**: 剩余 {max(0, int(deadline-time.time()))}s")
        log()
        log("| Session | 股票 | 引擎 | 文章数 | 轮询次数 | 最终状态 | 耗时 |")
        log("|---------|------|------|:------:|:--------:|:--------:|:----:|")

        t_phase2 = time.time()

        # 准备轮询状态
        poll_state = {}
        for sid, items in fetch_by_session.items():
            poll_state[sid] = {
                "articles": {aid: {"stock": stk, "engine": eng, "status": "pending"}
                             for aid, stk, eng in items},
                "polls": 0,
                "done": False,
            }

        # 轮询循环
        total_polls = 0
        while time.time() < deadline:
            still_pending = 0
            for sid, state in poll_state.items():
                if state["done"]: continue

                pending = [aid for aid, s in state["articles"].items() if s["status"] in ("pending", "processing")]
                if not pending:
                    # 全部已确定
                    errs = [aid for aid, s in state["articles"].items() if s["status"] == "error"]
                    state["done"] = True

                    stk = state["articles"][list(state["articles"].keys())[0]]["stock"]
                    eng = state["articles"][list(state["articles"].keys())[0]]["engine"]
                    ready_cnt = sum(1 for s in state["articles"].values() if s["status"] == "ready")
                    log(f"| {sid[-24:]} | {stk} | {eng} | {len(state['articles'])} | {state['polls']} | ready={ready_cnt} err={len(errs)} | {round(time.time()-t_phase2,1)}s |")
                    continue

                # 还有 pending 的，调 /article
                try:
                    r = _HTTP_SESSION.post(f"{API_BASE}/article", json={
                        "session_id": sid, "article_ids": pending,
                    }, timeout=60)
                    state["polls"] += 1
                    total_polls += 1

                    if r.status_code == 404:
                        # session 已关闭 → 这些标记为 error
                        for aid in pending:
                            state["articles"][aid]["status"] = "error"
                        continue

                    j = r.json() if r.ok else {}
                    for art in j.get("articles", []):
                        aid = art["article_id"]
                        s = art.get("status", "processing")
                        if aid in state["articles"]:
                            state["articles"][aid]["status"] = s

                except Exception as e:
                    state["polls"] += 1
                    # 网络错误，下次重试

            if still_pending == 0:
                # 检查是否全部 done
                if all(s["done"] for s in poll_state.values()):
                    log()
                    log("> ✅ 全部文章正文就绪。")
                    break

            elapsed = time.time() - t_phase2
            if all(s["done"] for s in poll_state.values()):
                break

            # 还有 pending，等待后继续
            remaining = [sid for sid, s in poll_state.items() if not s["done"]]
            log(f"[轮询中] 还有 {sum(1 for sid in remaining for a in poll_state[sid]['articles'].values() if a['status'] in ('pending','processing'))} 篇未就绪 "
                f"（{len(remaining)} 个 session），已过 {elapsed:.0f}s...")
            time.sleep(POLL_INTERVAL)
        else:
            log()
            log("> ⏰ **整体超时**，未完成的文章标记为 timeout。")
            for sid, state in poll_state.items():
                if not state["done"]:
                    for aid, s in state["articles"].items():
                        if s["status"] in ("pending", "processing"):
                            s["status"] = "timeout"
                    state["done"] = True

        phase2_wall = round(time.time() - t_phase2, 2)

        # 统计
        ready = sum(1 for s in poll_state.values() for a in s["articles"].values() if a["status"] == "ready")
        err = sum(1 for s in poll_state.values() for a in s["articles"].values() if a["status"] == "error")
        timeout = sum(1 for s in poll_state.values() for a in s["articles"].values() if a["status"] == "timeout")

        log()
        log(f"> Phase 2: 目标={actual_to_fetch}, ready={ready}, error={err}, timeout={timeout}, "
            f"总轮询={total_polls} 次, 耗时={phase2_wall}s")
        log()

        # 正文抽样
        log("### 正文内容抽样")
        log()
        sampled = 0
        for sid, state in poll_state.items():
            for aid, info in state["articles"].items():
                if info["status"] == "ready" and sampled < 10:
                    r = _HTTP_SESSION.post(f"{API_BASE}/article", json={
                        "session_id": sid, "article_ids": [aid],
                    }, timeout=30)
                    if r.ok:
                        j = r.json()
                        for art in j.get("articles", []):
                            body = art.get("body_text", "")
                            if body:
                                log(f"**{info['stock']} × {info['engine']} — {aid}**（正文前 200 字）")
                                log()
                                log(f"> {body[:200]}")
                                if len(body) > 200:
                                    log(f"> *...（截断，共 {len(body)} 字）*")
                                log()
                                sampled += 1
                                break

    # ── 总计 ──
    total_wall = round(time.time() - t_start, 2)
    log("---")
    log("## 总计")
    log()
    log("| 阶段 | 耗时 |")
    log("|:-----|:----:|")
    log(f"| Phase 1（搜索） | {phase1_wall}s |")
    log(f"| Phase 2（正文轮询） | {phase2_wall}s |")
    log(f"| **总耗时** | **{total_wall}s** |")
    log()
    log("### 各引擎")
    log()
    log("| 引擎 | 请求 | 成功 | 失败 | 文章数 |")
    log("|:-----|:----:|:----:|:----:|:------:|")
    for eng, st in engine_stats.items():
        log(f"| {eng} | {st['ok']+st['err']} | {st['ok']} | {st['err']} | {st['arts']} |")
    log()
    log(f"**结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    out_dir = "test_drive/results"
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"comprehensive_v3_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n✅ 报告: {path}")


if __name__ == "__main__":
    run()
