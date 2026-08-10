"""
新浪研报查询服务 — 高并发快返回

API:
    POST /reports  {"code": "002821", "edition": 0}
    GET  /health

设计要点:
  - 同步请求, 不做 session poll: 冷请求 3~8s, 热请求(缓存)~50ms, 30s 超时兜底
  - TTL 缓存(列表600s/正文86400s) + in-flight 合并: 同股票并发请求共享一次抓取
  - 6 篇正文 asyncio.to_thread 并行(httpx.Client 线程安全, 共享连接池)
  - 请求级 Semaphore(32) 限流, 单 worker 部署(纯 IO, 多 worker 破坏缓存共享)

返回结构:
  edition=0: {code, edition, list: [12篇{title,org,date}], bodies: [6篇{title,date,org,body}]}
  edition=1: {code, edition, list: null, bodies: [后6篇{...}]}   (总数<6 → bodies: null)
  异常:      {code, edition, error: {type, message}}  或 200 内嵌 error 字段

用法:
    conda run -n stock_agent python -m uvicorn report_service:app \
        --host 0.0.0.0 --port 8700 --workers 1
"""
import asyncio
import time
from collections import OrderedDict
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fetch_reports import (
    fetch_page, fetch_report_body, parse_reports, resolve_code, _REPORT_URL,
)

app = FastAPI(title="新浪研报查询服务", version="1.0.0")

# ── 常量 ──
LIST_LEN = 12            # 列表返回 12 篇
BODY_LEN = 6             # 正文返回 6 篇
LIST_TTL = 600           # 列表缓存 10 分钟(研报发布频率低)
BODY_TTL = 86400         # 正文缓存 24h(rptid 级, 内容不变)
MAX_LIST_ENTRIES = 200   # LRU 上限
MAX_BODY_ENTRIES = 2000
REQUEST_SEM = asyncio.Semaphore(32)      # 最大并发请求数(超出排队)
BODY_PARALLEL = 6        # 单请求内正文并行数
REQUEST_TIMEOUT = 120    # 整请求超时(秒)
PAGE_TIMEOUT = 15        # 单页抓取超时(秒, httpx 内)
BODY_TIMEOUT = 45        # 单篇正文超时(秒)
BODY_RETRY = 1           # 单篇正文失败重试次数
MAX_BODY_CHARS = 6000    # 正文最多返回字数, 超出截断
TRUNCATE_NOTICE = "\n\n[正文已截断,仅保留前6000字]"


# ── TTL + LRU 缓存 ──
class TTLCache:
    def __init__(self, max_entries: int, ttl: float):
        self._d: OrderedDict = OrderedDict()
        self._max = max_entries
        self._ttl = ttl

    def get(self, key: str):
        item = self._d.get(key)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > self._ttl:
            self._d.pop(key, None)
            return None
        self._d.move_to_end(key)
        return val

    def set(self, key: str, val):
        self._d[key] = (time.time(), val)
        self._d.move_to_end(key)
        while len(self._d) > self._max:
            self._d.popitem(last=False)


_list_cache = TTLCache(MAX_LIST_ENTRIES, LIST_TTL)
_body_cache = TTLCache(MAX_BODY_ENTRIES, BODY_TTL)
_inflight_list: dict[str, asyncio.Future] = {}
_inflight_body: dict[str, asyncio.Future] = {}
_cache_lock = asyncio.Lock()


# ── 抓取(带缓存 + in-flight 合并) ──

async def _get_or_fetch(key: str, cache: TTLCache, inflight: dict,
                        fetch_fn_async, timeout: float):
    """缓存命中 → 直接返回; 未命中 → in-flight 合并(同 key 共享一次抓取)

    fetch_fn_async: 无参异步函数, 内部自带超时/重试
    """
    cached = cache.get(key)
    if cached is not None:
        return cached
    async with _cache_lock:
        cached = cache.get(key)
        if cached is not None:
            return cached
        fut = inflight.get(key)
        if fut is None:
            fut = asyncio.get_running_loop().create_future()
            inflight[key] = fut
            asyncio.create_task(_fetch_and_store(key, cache, inflight, fetch_fn_async))
    try:
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def _fetch_and_store(key, cache, inflight, fetch_fn_async):
    try:
        val = await fetch_fn_async()
        if val is not None:
            cache.set(key, val)
        fut = inflight.get(key)
        if fut is not None:
            fut.set_result(val)
    except Exception as e:
        fut = inflight.get(key)
        if fut is not None:
            fut.set_result(None)
    finally:
        inflight.pop(key, None)


def _fetch_list_sync(symbol: str) -> Optional[list[dict]]:
    """同步抓取列表(串行翻页, 最多3页), 失败返回 None"""
    items = []
    for page in (1, 2, 3):
        url = f"{_REPORT_URL}?symbol={symbol}&t1=all&p={page}"
        try:
            html = fetch_page(url)
        except Exception:
            return None
        page_items = parse_reports(html)
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < 20:
            break
        if len(items) >= LIST_LEN:
            break
    return items[:LIST_LEN]


async def get_list(symbol: str) -> Optional[list[dict]]:
    async def _sync():
        return await asyncio.to_thread(_fetch_list_sync, symbol)
    return await _get_or_fetch(f"L:{symbol}", _list_cache, _inflight_list,
                               _sync, PAGE_TIMEOUT * 3)


async def _fetch_body_retry(url: str) -> Optional[dict]:
    """单篇正文: 45s 超时 + 重试 BODY_RETRY 次(用户定: 高并发下 30~50s/篇)"""
    for attempt in range(BODY_RETRY + 1):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(fetch_report_body, url), timeout=BODY_TIMEOUT)
        except asyncio.TimeoutError:
            print(f"[report_service] 正文超时({BODY_TIMEOUT}s) 第{attempt+1}次: {url[:80]}", flush=True)
        except Exception as e:
            print(f"[report_service] 正文抓取异常 第{attempt+1}次: {type(e).__name__} {url[:80]}", flush=True)
    return None


async def get_body(url: str) -> Optional[dict]:
    return await _get_or_fetch(f"B:{url}", _body_cache, _inflight_body,
                               lambda: _fetch_body_retry(url),
                               BODY_TIMEOUT * (BODY_RETRY + 1) + 5)


# ── 组装响应 ──

def _pick_body_fields(info: dict) -> dict:
    body = info["body"]
    truncated = len(body) > MAX_BODY_CHARS
    if truncated:
        body = body[:MAX_BODY_CHARS] + TRUNCATE_NOTICE
    return {"title": info["title"], "date": info["date"],
            "org": info["org"], "body": body, "truncated": truncated}


async def _fetch_bodies_parallel(urls: list[str]) -> list:
    """并行抓取多篇正文, 每篇独立超时; 失败篇返回 {"error": ...}"""
    results = [None] * len(urls)
    sem = asyncio.Semaphore(BODY_PARALLEL)

    async def one(i, url):
        async with sem:
            try:
                info = await asyncio.wait_for(get_body(url), timeout=BODY_TIMEOUT)
                results[i] = _pick_body_fields(info) if info else {"error": "body_fetch_failed"}
            except asyncio.TimeoutError:
                results[i] = {"error": "body_timeout"}
            except Exception:
                results[i] = {"error": "body_error"}

    await asyncio.gather(*[one(i, u) for i, u in enumerate(urls)])
    return results


async def handle_request(code: str, edition: int) -> dict:
    """核心处理: 返回响应字典(错误走 400/503 由端点处理)"""
    if edition not in (0, 1):
        return {"code": code, "edition": edition,
                "error": {"type": "invalid_edition", "message": "edition 只支持 0/1"}}
    try:
        symbol = resolve_code(code)
    except ValueError as e:
        return {"code": code, "edition": edition,
                "error": {"type": "invalid_code", "message": str(e)}}

    items = await get_list(symbol)
    if items is None:
        return {"code": code, "edition": edition,
                "error": {"type": "list_fetch_failed",
                          "message": "新浪研报列表抓取失败(网络/超时)"}}
    if not items:
        return {"code": code, "edition": edition,
                "list": [], "bodies": None}

    if edition == 0:
        bodies = await _fetch_bodies_parallel([it["url"] for it in items[:BODY_LEN]])
        resp = {"code": code, "edition": 0,
                "list": [{"title": it["title"], "org": it["org"],
                          "date": it["date"]} for it in items[:LIST_LEN]],
                "bodies": bodies}
    else:
        tail = items[BODY_LEN:LIST_LEN]          # 第 7~12 篇
        if len(items) <= BODY_LEN:
            resp = {"code": code, "edition": 1, "list": None, "bodies": None}
        else:
            bodies = await _fetch_bodies_parallel([it["url"] for it in tail])
            resp = {"code": code, "edition": 1, "list": None, "bodies": bodies}
    return resp


# ── API ──

class ReportRequest(BaseModel):
    code: str
    edition: int = 0


@app.post("/reports")
async def reports(req: ReportRequest):
    async with REQUEST_SEM:
        try:
            resp = await asyncio.wait_for(handle_request(req.code, req.edition),
                                          timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            return {"code": req.code, "edition": req.edition,
                    "error": {"type": "timeout", "message": f"处理超过{REQUEST_TIMEOUT}s"}}

    if "error" in resp and resp["error"]["type"] in ("invalid_code", "invalid_edition"):
        return JSONResponse(content=resp, status_code=400)
    if "error" in resp and resp["error"]["type"] in ("list_fetch_failed",):
        return JSONResponse(content=resp, status_code=503)
    return resp


@app.get("/health")
async def health():
    return {"status": "ok",
            "list_cache": len(_list_cache._d), "body_cache": len(_body_cache._d)}
