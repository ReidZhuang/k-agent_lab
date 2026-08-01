"""
Middleman — 作为 Office 成员与 mail_tower 之间的适配层

两个核心端点：
  Type A: POST /api/v1/search  — sub writer → 5 engine /search → 聚合返回
  Type B: POST /api/v1/article — reporter → 单 engine /article → 返回正文

遵循 mail_tower 的 FastAPI + ThreadPoolExecutor 设计模式。
"""
import os
import sys
import json
import time
import random
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── sys.path: 引入 office 公共模块和 ETL/midday 路径 ──
_OFFICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_ETL_DIR = os.path.normpath(os.path.join(_OFFICE_DIR, "..", "etl"))
_MIDDAY_DIR = os.path.normpath(os.path.join(_OFFICE_DIR, "..", "data_fetch", "midday"))
for _p in [_MIDDAY_DIR, _ETL_DIR, _OFFICE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dlog.debug_logger import get_logger
from models import TypeARequest, TypeAResponse, TypeBRequest, TypeBResponse
from cfg import load_config
from database import log_office_error

# ── 共享 HTTP 连接池 ──
_HTTP_SESSION = requests.Session()
_HTTP_ADAPTER = requests.adapters.HTTPAdapter(
    pool_connections=200, pool_maxsize=200, max_retries=0
)
_HTTP_SESSION.mount("http://", _HTTP_ADAPTER)
_HTTP_SESSION.mount("https://", _HTTP_ADAPTER)

# ── 配置加载 ──
_cfg = load_config()
_middleman_cfg = _cfg.get("middleman", {})
_mt_cfg = _cfg.get("mail_tower", {})
_MT_BASE = _mt_cfg.get("base_url", "http://localhost:8300")
_POLL_INTERVAL = _mt_cfg.get("poll_interval", 3)
_MAX_POLL = _mt_cfg.get("max_poll_attempts", 100)

# ── 并发控制（延迟创建，fork-safe） ──
_TYPE_A_POOL = None
_TYPE_B_POOL = None
_POOL_LOCK = threading.Lock()

def _get_type_a_pool():
    global _TYPE_A_POOL
    if _TYPE_A_POOL is None:
        with _POOL_LOCK:
            if _TYPE_A_POOL is None:
                _TYPE_A_POOL = ThreadPoolExecutor(
                    max_workers=_middleman_cfg.get("type_a_max_workers", 24)
                )
    return _TYPE_A_POOL

def _get_type_b_pool():
    global _TYPE_B_POOL
    if _TYPE_B_POOL is None:
        with _POOL_LOCK:
            if _TYPE_B_POOL is None:
                _TYPE_B_POOL = ThreadPoolExecutor(
                    max_workers=_middleman_cfg.get("type_b_max_workers", 64)
                )
    return _TYPE_B_POOL

# ── 引擎配置 ──
_ENGINE_CONFIG = {
    "sinafin":  {"max_results": 15, "mode": "list"},
    "baidufin": {"max_results": 20, "mode": "list"},
    "thsfin":   {"max_results": 20, "mode": "list"},
    "thsnews":  {"max_results": 20, "mode": "list"},
    "juchao":   {"max_results": 10, "mode": "list"},
    "qnainfo":  {"max_results": 20, "mode": "list"},
}

import trade_calendar as _tc

# ── FastAPI 应用 ──
app = FastAPI(title="Office Middleman", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================================
# 工具函数
# ======================================================================

def _get_date_range(engine: str) -> tuple[str, str]:
    """计算 engine 需要的日期范围

    Returns:
        (start_date, end_date) 格式 YYYY-MM-DD
    """
    cal = _tc.get_calendar()
    today = time.strftime("%Y%m%d")
    if engine == "qnainfo":
        # 过去 5 天
        start = _tc.prev_trading_day(today, n=5)
        if start is None:
            start = today
        return (start[:4] + "-" + start[4:6] + "-" + start[6:8],
                today[:4] + "-" + today[4:6] + "-" + today[6:8])
    else:
        # 上一个交易日 ~ 今天
        prev = cal.last_trading_day()
        return (prev[:4] + "-" + prev[4:6] + "-" + prev[6:8],
                today[:4] + "-" + today[4:6] + "-" + today[6:8])


def _call_mail_tower_search(engine: str, stock_code: str) -> dict:
    """调用 mail_tower /search（异步），/poll 轮询直到结果就绪

    重试策略遵循 mail_tower_retry_strategy.md：
      503 → retry 3次 × 3-5s
      504 → retry 2次 × 10-15s
      500(网络) → retry 3次 × 2-3s
      500(参数) → 不重试
      连接失败 → retry 3次 × 递增

    轮询超时策略：
      第 1 轮超时 → 关闭 session → 重新 search（新 session）→ 第 2 轮轮询
      第 2 轮超时 → 关闭 session → 返回 error

    Returns:
        {session_id, preview, empty, error}
    """
    start_date, end_date = _get_date_range(engine)
    ec = _ENGINE_CONFIG.get(engine, {})

    body = {
        "query": stock_code,
        "engine": engine,
        "mode": "list",
        "max_results": ec.get("max_results", 10),
        "start_date": start_date,
        "end_date": end_date,
    }
    ENGINE_TIMEOUT = _mt_cfg.get("search_timeout", 150)
    max_polls = max(1, ENGINE_TIMEOUT // _POLL_INTERVAL)

    for round_num in range(2):  # 最多两轮
        # ── POST /search（带重试） ──
        def _do_search():
            r = _HTTP_SESSION.post(f"{_MT_BASE}/search", json=body, timeout=30)
            return r

        resp = _retry_http(_do_search, engine, "search")

        if resp is None:
            return {"session_id": "", "preview": None, "empty": None,
                    "error": f"{engine} search failed after retries"}

        try:
            data = resp.json()
        except Exception as e:
            return {"session_id": "", "preview": None, "empty": None,
                    "error": f"JSON decode error: {e}"}

        session_id = data.get("session_id", "")
        status = data.get("status", "")

        # 立即就绪
        if status != "processing":
            preview = data.get("preview")
            empty = data.get("empty", preview is None)
            return {"session_id": session_id, "preview": preview,
                    "empty": empty, "error": ""}

        # ── 轮询 ──
        result = _poll_session(engine, session_id, max_poll=max_polls)
        if result.get("error"):
            # 超时 → 关闭 session，下一轮重试
            try:
                _HTTP_SESSION.post(f"{_MT_BASE}/close/{session_id}", timeout=10)
            except Exception:
                pass
            continue

        return result

    # 两轮都超时
    return {"session_id": "", "preview": None, "empty": None,
            "error": f"{engine} search timeout after 2 rounds"}


def _poll_session(engine: str, session_id: str,
                  max_poll: int | None = None) -> dict:
    """轮询 /poll 直到 list_ready / done / error

    Args:
        engine: 引擎名称（仅日志用）
        session_id: mail_tower session id
        max_poll: 最大轮询次数，None 使用默认值
    """
    max_attempts = max_poll or min(_MAX_POLL, 30)  # 默认最长 ~90s (30×3s)
    for attempt in range(max_attempts):
        time.sleep(_POLL_INTERVAL)
        try:
            pr = _HTTP_SESSION.get(f"{_MT_BASE}/poll/{session_id}", timeout=30)
            pj = pr.json() if pr.ok else {}
        except Exception as e:
            if attempt < 3:
                continue
            return {"session_id": session_id, "preview": None,
                    "empty": None, "error": f"poll failed: {e}"}

        poll_status = pj.get("status", "")
        if poll_status in ("list_ready", "done"):
            preview = pj.get("preview")
            empty = pj.get("empty", preview is None)
            return {"session_id": session_id, "preview": preview,
                    "empty": empty, "error": ""}

        if poll_status == "error":
            return {"session_id": session_id, "preview": None,
                    "empty": None, "error": pj.get("error", "unknown error")}

    # 轮询超时
    return {"session_id": session_id, "preview": None,
            "empty": None, "error": f"poll timeout ({_MAX_POLL} attempts)"}


def _call_mail_tower_article(engine: str, session_id: str,
                               article_ids: list[str]) -> dict:
    """调用 mail_tower /article。

    策略：
      - 2xx(ready/error) → 直接返回
      - 2xx(processing) → 5s 轮询最多 600s
      - 5xx → 立即返回 error，不重试（服务端代码错误，重试无意义）
      - 404 → 立即返回 error
      - 其他 4xx/连接失败 → 重试 3 次
      - 第二轮全新 session 做 fallback

    所有返回都携带 http_status 字段反映真实 HTTP 状态码。

    Args:
        engine: 引擎名称（仅用于日志）
        session_id: mail_tower session id
        article_ids: 要获取的文章 ID 列表

    Returns:
        {articles: [...], status: "ready"|"error"|"timeout",
         http_status: int, session_closed: bool}
    """
    MAX_ATTEMPTS = 3
    POLL_SECONDS = 5
    MAX_POLL_PER_ATTEMPT = 120  # 120 × 5s = 600s，匹配 reporter article_timeout=600
    POST_TIMEOUT = _mt_cfg.get("type_b_timeout", 60)

    def _post_article(sid, aids):
        return _HTTP_SESSION.post(
            f"{_MT_BASE}/article",
            json={"session_id": sid, "article_ids": aids},
            timeout=POST_TIMEOUT + 10,
        )

    def _resp(status: str, http_status: int,
              articles: list | None = None,
              session_closed: bool = True) -> dict:
        return {"articles": articles or [], "status": status,
                "http_status": http_status, "session_closed": session_closed}

    # ── POST /article（4xx 最多重试 3 次） ──
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = _post_article(session_id, article_ids)
            # 5xx — 服务端错误，不重试
            if resp.status_code >= 500:
                log_office_error(
                    module="office.middleman",
                    function="_call_mail_tower_article",
                    level="WARNING",
                    error_msg=f"{engine} /article {resp.status_code}",
                    error_code="MIDDLEMAN_ENGINE_ERROR",
                    data_snapshot=json.dumps(
                        {"engine": engine, "status_code": resp.status_code,
                         "resp_body": resp.text[:200]}),
                )
                return {"articles": [], "status": "error",
                        "http_status": resp.status_code, "session_closed": True}
            # 404 — session 不存在
            if resp.status_code == 404:
                return _resp("error", 404)
            # 其他 4xx — 重试
            if not resp.ok:
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(2 + random.random())
                    continue
                return _resp("error", resp.status_code)
            # 2xx
            data = resp.json()
            top_status = data.get("status", "")
            if top_status in ("ready", "error"):
                return {"articles": data.get("articles", []),
                        "status": data.get("status", "error"),
                        "http_status": 200,
                        "session_closed": data.get("session_closed", False)}
            # processing → 轮询（最多 600s，被 reporter 610s 截断）
            for poll_attempt in range(MAX_POLL_PER_ATTEMPT):
                time.sleep(POLL_SECONDS)
                try:
                    pr = _HTTP_SESSION.get(
                        f"{_MT_BASE}/poll/{session_id}", timeout=30
                    )
                    pj = pr.json() if pr.ok else {}
                    p_list_status = pj.get("list_status", "")
                    p_article_status = pj.get("article_status", "")
                    # 列表出错或无结果 → 退出
                    if p_list_status in ("error", "empty"):
                        break
                    # 正文就绪 → 调 /article 取正文
                    if p_article_status == "ready":
                        art_resp = _post_article(session_id, article_ids)
                        if art_resp.ok:
                            ad = art_resp.json()
                            # 如果返回 processing，检查是否有就绪的文章可以立即返回
                            if ad.get("status") == "processing":
                                ready_articles = [a for a in ad.get("articles", []) if a.get("status") == "ready"]
                                if ready_articles:
                                    # 有部分正文就绪 → 直接返回，不再等
                                    return {"articles": ready_articles,
                                            "status": "ready",
                                            "http_status": 200,
                                            "session_closed": ad.get("session_closed", False)}
                                # 没有一篇就绪 → 继续轮询
                                continue
                            return {"articles": ad.get("articles", []),
                                    "status": ad.get("status", "error"),
                                    "http_status": art_resp.status_code,
                                    "session_closed": ad.get("session_closed", False)}
                    # 无正文（qnainfo）或全部失败 → 退出
                    elif p_article_status in ("free", "error"):
                        break
                    # waiting/processing → 继续轮询
                except Exception:
                    continue
            # 轮询超时或 article_status=error/free → 关闭 session 返回 error
            break
        except (requests.Timeout, Exception):
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2 + random.random())
                continue
            break

    # ── 最后一轮：轮询超时后，直接调 /article 取已有正文 ──
    final_articles = []
    try:
        final_resp = _post_article(session_id, article_ids)
        if final_resp.ok:
            final_data = final_resp.json()
            per_articles = final_data.get("articles", [])
            for art in per_articles:
                if art.get("status") == "ready":
                    final_articles.append(art)
                elif art.get("status") == "processing":
                    art["status"] = "error"
                    art["fetch_error"] = "正文获取超时"
                    final_articles.append(art)
                else:
                    final_articles.append(art)
    except Exception:
        pass

    # ── 关闭 session ──
    try:
        _HTTP_SESSION.post(f"{_MT_BASE}/close/{session_id}", timeout=10)
    except Exception:
        pass

    if final_articles:
        return {"articles": final_articles, "status": "ready",
                "http_status": 200, "session_closed": True}

    # 正文获取失败
    log_office_error(
        module="office.middleman",
        function="_call_mail_tower_article",
        level="WARNING",
        error_msg=f"{engine} /article timeout or error after polling",
        error_code="MIDDLEMAN_ENGINE_TIMEOUT",
        data_snapshot=json.dumps({"engine": engine, "session_id": session_id,
                                   "article_ids": article_ids}),
    )
    return _resp("timeout", 0)


def _retry_http(fn, engine: str, label: str) -> requests.Response | None:
    """通用 HTTP 重试（mail_tower 重试策略简化版）

    规则：
      - 连接失败: retry 3次, 5/10/15s 递增
      - 503: retry 3次, 3-5s
      - 504: retry 2次, 10-15s
      - 500(网络类): retry 3次, 2-3s
      - 500(参数类): 不重试，立即返回
    """
    delays_search = [  # (base_delay, max_jitter)
        (5, 2), (10, 5), (15, 5)
    ]
    delays_503 = [(3, 2), (3, 2), (5, 2)]
    delays_504 = [(10, 5), (15, 5)]
    delays_500_net = [(2, 1), (2, 1), (3, 1)]

    for major_attempt in range(3):
        try:
            resp = fn()
            if resp.status_code == 200:
                return resp
            if resp.status_code == 503:
                delay, jitter = delays_503[major_attempt]
                if major_attempt < 2:
                    time.sleep(delay + random.random() * jitter)
                    continue
                else:
                    return None  # 3次后放弃
            elif resp.status_code == 504:
                if major_attempt == 0:
                    time.sleep(10 + random.random() * 5)
                    continue
                elif major_attempt == 1:
                    time.sleep(15 + random.random() * 5)
                    continue
                else:
                    return None
            elif resp.status_code == 500:
                detail = resp.text[:200].lower()
                if any(k in detail for k in ("connectionreset", "connecterror",
                                              "timeouterror")):
                    if major_attempt < 3:
                        d, j = delays_500_net[major_attempt]
                        time.sleep(d + random.random() * j)
                        continue
                elif any(k in detail for k in ("无法解析", "valueerror")):
                    return resp  # 参数错误不重试
                else:
                    if major_attempt < 3:
                        time.sleep(3 + random.random() * 2)
                        continue
            return resp  # 其他状态码直接返回
        except (requests.ConnectionError, requests.Timeout) as e:
            if major_attempt < 3:
                d, j = delays_search[major_attempt]
                time.sleep(d + random.random() * j)
                continue
            log_office_error(
                module="office.middleman",
                function=f"_retry_http.{label}",
                level="WARNING", engine_name=engine,
                error_msg=f"连接失败: {e}",
                error_code="MIDDLEMAN_ENGINE_TIMEOUT",
            )
            return None
        except Exception as e:
            if major_attempt < 2:
                time.sleep(3)
                continue
            log_office_error(
                module="office.middleman",
                function=f"_retry_http.{label}",
                level="ERROR", engine_name=engine,
                error_msg=f"意外异常: {e}",
            )
            return None
    return None


# ======================================================================
# Type A: POST /api/v1/search
# ======================================================================

@app.post("/api/v1/search")
async def search_aggregate(req: TypeARequest):
    """聚合搜索：并发 5 个 engine，聚合后返回（非阻塞版）"""
    log = get_logger("middleman_type_a")
    pool = _get_type_a_pool()
    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(pool, _run_type_a_search, req, log)
    return TypeAResponse(writer_id=req.writer_id, results=result)


def _run_type_a_search(req: TypeARequest, log) -> dict:
    """Type A 同步执行函数（在 _type_a_pool 线程中运行）"""
    t0 = time.time()
    engines = list(_ENGINE_CONFIG.keys())

    def _search_one(engine: str) -> tuple[str, dict]:
        et0 = time.time()
        result = _call_mail_tower_search(engine, req.stock_code)
        log("engine_done", engine=engine, stock_code=req.stock_code,
            has_error=bool(result.get("error")),
            empty=result.get("empty"), _elapsed=time.time()-et0)
        return (engine, result)

    results = {}
    with ThreadPoolExecutor(max_workers=len(engines)) as pool:
        fut_map = {pool.submit(_search_one, eng): eng for eng in engines}
        for fut in as_completed(fut_map):
            engine, result = fut.result()
            results[engine] = result

    engines_ok = sum(1 for r in results.values() if not r.get("error") and not r.get("empty"))
    engines_err = sum(1 for r in results.values() if r.get("error"))
    log("search_aggregate_done", writer_id=req.writer_id, stock_code=req.stock_code,
        engines_ok=engines_ok, engines_err=engines_err, _elapsed=time.time()-t0)

    return results


# ======================================================================
# Type B: POST /api/v1/article
# ======================================================================

@app.post("/api/v1/article")
async def article_body(req: TypeBRequest):
    """获取文章正文（非阻塞版）"""
    log = get_logger("middleman_type_b")
    pool = _get_type_b_pool()
    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(pool, _run_type_b_article, req, log)

    return TypeBResponse(
        report_id=req.report_id,
        engine=req.engine,
        session_id=req.session_id,
        session_closed=result.get("session_closed", True),
        articles=result.get("articles", []),
        status=result.get("status", "timeout"),
        http_status=result.get("http_status", 0),
    )


def _run_type_b_article(req: TypeBRequest, log) -> dict:
    """Type B 同步执行函数（在 _type_b_pool 线程中运行）"""
    t0 = time.time()
    result = _call_mail_tower_article(
        engine=req.engine,
        session_id=req.session_id,
        article_ids=req.article_ids,
    )
    log("article_body_done", report_id=req.report_id, engine=req.engine,
        session_id=req.session_id[:20], requested=len(req.article_ids),
        returned=len(result.get("articles", [])),
        status=result.get("status"),
        http_status=result.get("http_status", 0),
        _elapsed=time.time()-t0)
    return result


# ======================================================================
# 健康检查
# ======================================================================

@app.get("/health")
async def health():
    return {"status": "ok", "service": "office-middleman"}


# ======================================================================
# 启动入口
# ======================================================================

if __name__ == "__main__":
    import uvicorn
    port = _middleman_cfg.get("port", 8311)
    host = _middleman_cfg.get("host", "0.0.0.0")
    workers = _middleman_cfg.get("workers", 4)
    uvicorn.run("server:app", host=host, port=port, workers=workers)
