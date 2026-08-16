#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公司分析报告生成服务(FastAPI + SSE, 端口 8323)

接口:
    POST /api/reports                  创建生成任务(股票列表, 串行生成)
    GET  /api/reports/{task_id}/events SSE 实时进度
    GET  /api/reports/{task_id}/status 兜底状态查询(事件缓冲最近 20 条)
    GET  /health                       健康检查

核心流程:
    1. 任务开始前检查"今日是否已登录"(状态文件 ~/.config/mx_report_server_state.json):
       未登录 → 用主凭据登录并更新 openclaw.json 的 em_api_key(必要时重启 gateway)
    2. 逐股串行调用 company_report_api.generate_company_report(复用现管线:
       PROMPT_TEMPLATE + mx-agent + 积分耗尽守卫 + 会话清理)
    3. 检测到 MX_QUOTA_EXHAUSTED → 按序切换备用凭据(0主 → 1..4备用):
       新凭据登录拿 key → 更新 openclaw.json → 重启 gateway → 验证 /v1/models → 重试该股
    4. 全部凭据耗尽 → 剩余股票直接判失败, 返回"今日用户积分已用尽,报告无法生成,请明日再试"

环境变量:
    MX_REPORT_FAKE_EXHAUST=1  测试模式: 每只股票首次生成伪造配额耗尽,
                              用于演练换 key 全流程而不消耗真实积分(勿在生产开启)

启动: ./report_server.sh start   (nohup + log/report_server.log)
"""
import json
import os
import pathlib
import queue
import shutil
import socket
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import credential_store as cs
from company_report_api import generate_company_report

PORT = 8323
GEN_TIMEOUT = 600       # 单股生成超时(agent 调用上限)
MAX_STOCKS = 5          # 单次任务最多股票数(串行, 每只约数分钟)
QUOTA_ALL_EXHAUSTED_MSG = "今日用户积分已用尽,报告无法生成,请明日再试"

# 报告复制到用户目录(user/{username}/{股票名}/)的根路径
USER_BASE = pathlib.Path(__file__).resolve().parents[1] / "user"

FAKE_EXHAUST = os.environ.get("MX_REPORT_FAKE_EXHAUST") == "1"


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------- 任务状态与 SSE 事件 ----------

@dataclass
class TaskState:
    task_id: str
    stocks: list[str]
    username: str | None = None      # 前端登录用户名(报告复制目标 user/{username}/)
    status: str = "queued"           # queued | running | done | failed
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    files: list[str] = field(default_factory=list)      # 成功报告绝对路径
    failed: list[dict] = field(default_factory=list)    # [{"stock", "error"}]
    events: list[dict] = field(default_factory=list)    # SSE 事件缓冲(上限 1000)
    seq: int = 0
    cond: threading.Condition = field(default_factory=threading.Condition)


TASKS: dict[str, TaskState] = {}
_QUEUE: queue.Queue = queue.Queue()


def _emit(task: TaskState, etype: str, **extra):
    """记录 SSE 事件(带 seq, 环形缓冲上限 1000)并唤醒等待连接的线程。"""
    ev = {"type": etype, "ts": int(time.time()), "seq": task.seq, **extra}
    with task.cond:
        task.events.append(ev)
        task.seq += 1
        if len(task.events) > 1000:
            del task.events[: len(task.events) - 1000]
        task.cond.notify_all()


# ---------- 报告复制到用户目录 ----------

def _copy_to_user(stock: str, md_path: str, username: str | None) -> str | None:
    """复制报告到 user/{username}/上市公司分析/{股票名}/, 返回目标路径; 失败不阻塞任务。

    username 为空(前端未传)时直接跳过。
    """
    if not username:
        return None
    target = USER_BASE / username / "上市公司分析" / stock
    try:
        target.mkdir(parents=True, exist_ok=True)
        dest = target / os.path.basename(md_path)
        shutil.copy2(md_path, dest)
        _log(f"报告已复制到用户目录: {dest}")
        return str(dest)
    except OSError as e:
        _log(f"[WARN] 复制到用户目录失败({username}/{stock}): {e}")
        return None


# ---------- 生成调用(唯一调用点) ----------

def _call_report(stock: str, attempt: int) -> dict:
    """调用 company_report_api 单次生成; 底层异常归类为失败结果, 不穿透。

    FAKE_EXHAUST 测试模式: attempt==1 时伪造 MX_QUOTA_EXHAUSTED,
    用于演练换 key 全流程(不消耗真实积分)。
    """
    if FAKE_EXHAUST and attempt == 1:
        _log(f"[FAKE] 伪造 MX_QUOTA_EXHAUSTED (MX_REPORT_FAKE_EXHAUST=1, stock={stock})")
        return {"ok": False, "stock": stock,
                "error": {"code": "MX_QUOTA_EXHAUSTED", "stage": "fake",
                          "detail": "测试模式伪造积分耗尽"}}
    try:
        return generate_company_report(stock, timeout=GEN_TIMEOUT)
    except socket.timeout:
        return {"ok": False, "stock": stock,
                "error": {"code": "CALL_TIMEOUT", "stage": "server",
                          "detail": f"生成超时({GEN_TIMEOUT}s)"}}
    except Exception as e:
        return {"ok": False, "stock": stock,
                "error": {"code": "CALL_ERROR", "stage": "server", "detail": str(e)}}


# ---------- 每日登录 ----------

@cs.locked("每日登录")
def _daily_login(task: TaskState) -> tuple[bool, str]:
    """每日第一个任务开始前: 登录主凭据并更新 gateway key。

    返回 (ok, err_msg)。成功时游标状态已重置(今日首次)。
    """
    state = cs.load_state()
    today = date.today().isoformat()
    if cs.state_is_today(state, today):
        return True, ""
    _emit(task, "login_started", credential=0, reason="daily_first")
    res = cs.run_login(0)  # 默认 CDP 模式(自动启动真实 Chrome)
    if not res.get("ok"):
        reason = res.get("reason", "未知原因")
        _emit(task, "login_failed", credential=0, reason=reason)
        return False, f"主凭据登录失败: {reason}"
    key = res["key"]
    _emit(task, "login_ok", credential=0, key_prefix=key[:8])
    ok, reason = cs.switch_gateway_key(key)
    if not ok:
        _emit(task, "login_failed", credential=0, reason=f"gateway 切换失败: {reason}")
        return False, f"gateway 切换失败: {reason}"
    cs.save_state({"last_login_date": today, "cursor": 0, "exhausted": [],
                   "current_key_prefix": key[:8]})
    _log(f"每日登录完成(主凭据), key 前缀 {key[:8]}")
    return True, ""


# ---------- 换 key(备用凭据轮换) ----------

@cs.locked("换key")
def _switch_credential(task: TaskState, from_idx: int) -> tuple[int | None, str]:
    """从 from_idx+1 起按序尝试可用备用凭据(跳过当日已 exhausted 的)。

    成功: 返回 (新凭据 index, "")。
    失败: 返回 (None, 原因)。原因为空表示"没有更多可用凭据"(配额耗尽语义);
          非空表示最后一个失败的登录/切换原因。
    """
    state = cs.load_state()
    total = cs.total_credentials()
    nxt = from_idx + 1
    last_err = ""
    while nxt < total:
        if nxt in state.get("exhausted", []):
            nxt += 1
            continue
        _emit(task, "login_started", credential=nxt, reason="quota_switch")
        res = cs.run_login(nxt)  # 默认 CDP 模式
        if not res.get("ok"):
            reason = res.get("reason", "未知原因")
            last_err = f"备用{nxt}登录失败: {reason}"
            _emit(task, "login_failed", credential=nxt, reason=reason)
            state["exhausted"].append(nxt)
            cs.save_state(state)
            nxt += 1
            continue
        key = res["key"]
        _emit(task, "login_ok", credential=nxt, key_prefix=key[:8])
        ok, reason = cs.switch_gateway_key(key)
        if not ok:
            last_err = f"备用{nxt}切换失败: {reason}"
            _emit(task, "login_failed", credential=nxt, reason=f"gateway 切换失败: {reason}")
            state["exhausted"].append(nxt)
            cs.save_state(state)
            nxt += 1
            continue
        _log(f"已切换到备用{nxt}, key 前缀 {key[:8]}")
        return nxt, ""
    if last_err:
        return None, last_err
    return None, QUOTA_ALL_EXHAUSTED_MSG


def _generate_with_retry(task: TaskState, stock: str) -> dict:
    """单股生成 + 配额耗尽换 key 重试。

    返回 {"ok": bool, "path"? | "error", "all_exhausted"?}。
    """
    attempt = 0
    while True:
        attempt += 1
        state = cs.load_state()
        cur = state.get("cursor", 0)
        if cur in state.get("exhausted", []):
            # 当前凭据已确认耗尽 → 直接换(不浪费一次生成调用)
            _emit(task, "quota_switching", from_credential=cur, to_credential=cur + 1)
            nxt, err_msg = _switch_credential(task, cur)
            if nxt is None:
                return {"ok": False, "error": err_msg, "all_exhausted": True}
            state = cs.load_state()
            state["cursor"] = nxt
            cs.save_state(state)
            continue

        result = _call_report(stock, attempt)
        if result.get("ok"):
            report = (result.get("report") or "").strip()
            if not report:
                return {"ok": False, "error": "报告内容为空"}
            return {"ok": True, "path": result["md_path"]}
        err = result.get("error") or {}
        code = err.get("code", "")
        if code != "MX_QUOTA_EXHAUSTED":
            detail = err.get("detail") or str(err)
            return {"ok": False, "error": f"[{code}] {detail}" if code else detail}

        # 配额耗尽 → 标记当前凭据, 换下一套
        state = cs.load_state()
        exhausted = state.setdefault("exhausted", [])
        if cur not in exhausted:
            exhausted.append(cur)
        cs.save_state(state)
        _emit(task, "quota_switching", from_credential=cur, to_credential=cur + 1)
        nxt, err_msg = _switch_credential(task, cur)
        if nxt is None:
            state = cs.load_state()
            state["cursor"] = -1
            cs.save_state(state)
            return {"ok": False, "error": err_msg, "all_exhausted": True}
        state = cs.load_state()
        state["cursor"] = nxt
        cs.save_state(state)
        _emit(task, "retrying", stock=stock, credential=nxt, attempt=attempt)
        _log(f"{stock}: 已换到凭据{nxt}, 重试(attempt={attempt})")


# ---------- 任务主循环 ----------

def _run_task(task_id: str):
    task = TASKS[task_id]
    task.status = "running"
    task.started_at = time.time()
    _log(f"任务 {task_id} 开始: {task.stocks}")
    try:
        # 1. 每日登录检查
        ok, err = _daily_login(task)
        if not ok:
            task.finished_at = time.time()
            task.status = "failed"
            _emit(task, "task_failed", task_id=task_id, error=err)
            _log(f"任务 {task_id} 失败: {err}")
            return

        # 2. 逐股串行生成
        total = len(task.stocks)
        for i, stock in enumerate(task.stocks):
            _emit(task, "generating", stock=stock, index=i, total=total)
            _log(f"{stock}: 开始生成 ({i + 1}/{total})")
            outcome = _generate_with_retry(task, stock)
            if outcome.get("ok"):
                path = outcome["path"]
                task.files.append(path)
                user_path = _copy_to_user(stock, path, task.username)
                _emit(task, "stock_done", stock=stock, index=i, total=total,
                      file=os.path.basename(path), path=path,
                      user_path=user_path)
                _log(f"{stock}: 完成 -> {path}" + (f" (user: {user_path})" if user_path else ""))
            else:
                err = outcome["error"]
                task.failed.append({"stock": stock, "error": err})
                _emit(task, "stock_failed", stock=stock, index=i, total=total, error=err)
                _log(f"{stock}: 失败 - {err}")
                if outcome.get("all_exhausted"):
                    # 积分已尽: 剩余股票直接判失败, 不再白跑
                    for j in range(i + 1, total):
                        rest = task.stocks[j]
                        task.failed.append({"stock": rest, "error": QUOTA_ALL_EXHAUSTED_MSG})
                        _emit(task, "stock_failed", stock=rest, index=j, total=total,
                              error=QUOTA_ALL_EXHAUSTED_MSG)
                    _emit(task, "all_quota_exhausted",
                          used_credentials=cs.load_state().get("exhausted", []))
                    _log("当日全部凭据已耗尽")
                    break

        # 3. 终态
        task.finished_at = time.time()
        task.status = "done"
        _emit(task, "task_done", task_id=task_id, files=list(task.files),
              failed=list(task.failed),
              duration_s=round(task.finished_at - task.started_at, 1))
        _log(f"任务 {task_id} 完成: {len(task.files)} 成功 / {len(task.failed)} 失败")
    except Exception as e:
        task.finished_at = time.time()
        task.status = "failed"
        _emit(task, "task_failed", task_id=task_id, error=f"服务内部错误: {e}")
        _log(f"任务 {task_id} 内部错误: {e}")
    finally:
        with task.cond:
            task.cond.notify_all()


def _worker_loop():
    while True:
        task_id = _QUEUE.get()
        try:
            _run_task(task_id)
        except Exception as e:
            task = TASKS.get(task_id)
            if task:
                task.status = "failed"
                task.finished_at = time.time()
                _emit(task, "task_failed", task_id=task_id, error=f"worker 异常: {e}")
                with task.cond:
                    task.cond.notify_all()
            _log(f"worker 异常({task_id}): {e}")
        finally:
            _QUEUE.task_done()


# ---------- FastAPI ----------

app = FastAPI(title="公司分析报告生成服务")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportRequest(BaseModel):
    stocks: list[str]
    username: str | None = None   # 前端登录用户名, 报告复制到 user/{username}/{股票名}/


@app.post("/api/reports", status_code=202)
def create_report(req: ReportRequest):
    if not cs.credentials_available():
        raise HTTPException(503, cs.credentials_error())
    state = cs.load_state()
    today = date.today().isoformat()
    if cs.state_is_today(state, today) and state.get("cursor") == -1:
        raise HTTPException(409, "今日用户积分已用尽,请明日再试")
    names = [s.strip() for s in (req.stocks or []) if s.strip()]
    if not names:
        raise HTTPException(400, "股票列表为空")
    if len(names) > MAX_STOCKS:
        raise HTTPException(400, f"单次最多 {MAX_STOCKS} 只(串行生成)")
    username = (req.username or "").strip() or None
    task = TaskState(task_id=uuid.uuid4().hex[:12], stocks=names,
                     username=username, created_at=time.time())
    TASKS[task.task_id] = task
    _emit(task, "task_queued", task_id=task.task_id, stocks=names,
          position=_QUEUE.qsize() + 1)
    _QUEUE.put(task.task_id)
    _log(f"新任务 {task.task_id}: {names} (队列位置 {_QUEUE.qsize()})")
    return {"task_id": task.task_id, "status": "queued"}


@app.get("/api/reports/{task_id}/events")
async def report_events(task_id: str, request: Request):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在或服务已重启")

    async def gen():
        sent = 0
        while True:
            if await request.is_disconnected():
                break
            with task.cond:
                new_events = list(task.events[sent:])
                sent = len(task.events)
                terminal = task.status in ("done", "failed")
            if not new_events:
                yield ": ping\n\n"
                if terminal:
                    break
                # 非阻塞等待（不能用 threading.Condition.wait_for：会阻塞事件循环）
                await asyncio.sleep(2)
                continue
            for e in new_events:
                yield f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
            if terminal:
                break

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/reports/{task_id}/status")
def report_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在或服务已重启")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "stocks": task.stocks,
        "files": task.files,
        "failed": task.failed,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "last_events": task.events[-20:],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "credentials_available": cs.credentials_available(),
        "today": date.today().isoformat(),
        "state": cs.load_state(),
    }


if __name__ == "__main__":
    if FAKE_EXHAUST:
        _log("[WARN] MX_REPORT_FAKE_EXHAUST=1 测试模式: 首次生成将伪造配额耗尽, 演练换 key 流程")
    threading.Thread(target=_worker_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
