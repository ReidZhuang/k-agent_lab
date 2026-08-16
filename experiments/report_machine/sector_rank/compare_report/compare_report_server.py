#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板块对比分析报告生成服务(FastAPI + SSE, 端口 8326)

接口:
    POST /api/compare/reports                  创建生成任务(板块名 + 选中股票列表)
    GET  /api/compare/reports/{task_id}/events SSE 实时进度
    GET  /api/compare/reports/{task_id}/status 兜底状态查询(事件缓冲最近 20 条)
    GET  /health                               健康检查

核心流程(登录/换 key 逻辑与公司分析 8323 report_server.py 一致):
    1. 任务开始前检查"今日是否已登录"(状态文件 ~/.config/mx_report_server_state.json,
       与公司分析共用: 同一 gateway 同一 em_api_key):
       未登录 → 用主凭据登录并更新 openclaw.json 的 em_api_key(必要时重启 gateway)
    2. 整份报告一次 agent 调用生成(不是逐股):
       query = f"{sector_name}板块涨幅排名前列的{','.join(stocks)}，合并分析这些上市公司"
       → 触发 mx-agent 的 sector-multi-stock-analysis 技能(形态 B 名单型:
       板块名 + 股票名单逗号隔开 + "合并分析这些上市公司"意图词)
    3. 检测到 MX_QUOTA_EXHAUSTED → 按序切换备用凭据(0主 → 1..4备用):
       新凭据登录拿 key → 更新 openclaw.json → 重启 gateway → 验证 /v1/models → 重试
    4. 全部凭据耗尽 → 任务判失败, 返回"今日用户积分已用尽,报告无法生成,请明日再试"

环境变量:
    MX_COMPARE_FAKE_EXHAUST=1  测试模式: 首次生成伪造配额耗尽,
                              用于演练换 key 全流程而不消耗真实积分(勿在生产开启)

启动: ./compare_report_server.sh start   (nohup + log/compare_report_server.log)
"""
import asyncio
import json
import os
import pathlib
import queue
import re
import shutil
import socket
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

PORT = 8326
GEN_TIMEOUT = 1800      # 整份板块报告生成超时(至多 20 只股票合并分析, agent 逐只取数)
MAX_STOCKS = 20         # 单次任务最多股票数(前端排名表最多 20 行)
QUOTA_ALL_EXHAUSTED_MSG = "今日用户积分已用尽,报告无法生成,请明日再试"

# 本文件位于 sector_rank/compare_report/, report_machine 根 = 上级的上级
_HERE = pathlib.Path(__file__).resolve().parent
_RM_DIR = _HERE.parents[1]
REPORTS_DIR = _HERE / "reports"          # 服务端暂存
USER_BASE = _RM_DIR / "user"             # 用户空间(user/{username}/板块分析/{板块名}/)
USER_SUBDIR = "板块分析"                  # explorer 中独立总文件夹(与"上市公司分析"平行)

# 复用 mx_company_reporter 的登录/凭据/会话管线(与公司分析 8323 同一套):
#   credential_store: 凭据文件/游标状态/run_login/switch_gateway_key
#   company_report_api: SESSION_AGENT_PREFIX / _chat_once / _extract_mcp_error / _delete_session_safe
_MX_DIR = _RM_DIR / "mx_company_reporter"
sys.path.insert(0, str(_MX_DIR))

import credential_store as cs
from company_report_api import (SESSION_AGENT_PREFIX, _chat_once,
                                _delete_session_safe, _extract_mcp_error)

FAKE_EXHAUST = os.environ.get("MX_COMPARE_FAKE_EXHAUST") == "1"


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------- 任务状态与 SSE 事件(照搬 report_server.py 框架) ----------

@dataclass
class TaskState:
    task_id: str
    sector_name: str
    stocks: list[str]
    username: str | None = None      # 前端登录用户名(报告复制目标 user/{username}/)
    status: str = "queued"           # queued | running | done | failed
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    files: list[str] = field(default_factory=list)      # 成功报告绝对路径
    failed: list[dict] = field(default_factory=list)    # [{"sector", "error"}]
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


# ---------- 报告写入与复制 ----------

def _safe_filename(name: str) -> str:
    """过滤文件名非法字符(照搬 company_report_api.py 的规则)。"""
    return re.sub(r'[\\/:*?"<>|\s]+', '_', name).strip("_")


def _save_report(task: TaskState, markdown: str) -> str:
    """整份报告写 reports/, 返回绝对路径。"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{date.today().strftime('%Y%m%d')}_{_safe_filename(task.sector_name)}_对比分析报告.md"
    path = REPORTS_DIR / name
    path.write_text(markdown, encoding="utf-8")
    _log(f"报告已写入: {path}")
    return str(path)


def _copy_to_user(task: TaskState, md_path: str) -> str | None:
    """复制报告到 user/{username}/板块分析/{板块名}/, 返回目标路径; 失败不阻塞任务。

    username 为空(前端未传)时直接跳过。
    """
    if not task.username:
        return None
    target = USER_BASE / task.username / USER_SUBDIR / _safe_filename(task.sector_name)
    try:
        target.mkdir(parents=True, exist_ok=True)
        dest = target / os.path.basename(md_path)
        shutil.copy2(md_path, dest)
        _log(f"报告已复制到用户目录: {dest}")
        return str(dest)
    except OSError as e:
        _log(f"[WARN] 复制到用户目录失败({task.username}/{task.sector_name}): {e}")
        return None


# ---------- agent 调用(真实 gateway, 整份报告一次生成) ----------

def _build_query(sector_name: str, stocks: list[str]) -> str:
    """组装 agent query, 触发 sector-multi-stock-analysis 技能(形态 B 名单型)。

    格式(与技能文档典型表述逐字同构):
        THS 板块名称 + "板块涨幅排名前列的" + 股票名单(逗号隔开) + "，合并分析这些上市公司"
    前三段来自前端(板块名 + 勾选股票), 最后一句写死。
    """
    return f"{sector_name}板块涨幅排名前列的{','.join(stocks)}，合并分析这些上市公司"


def _call_agent(sector_name: str, stocks: list[str], attempt: int) -> dict:
    """调用 mx-agent 生成整份板块合并分析报告(单次 agent 调用, 非逐股)。

    复用 company_report_api 的会话管线: 唯一 session key(带 agent:mx-agent: 前缀)
    + finally 删会话; 积分耗尽守卫 _extract_mcp_error 命中 → ok:false + 结构化 error。

    FAKE_EXHAUST 测试模式: attempt==1 时伪造 MX_QUOTA_EXHAUSTED,
    用于演练换 key 全流程(不消耗真实积分)。
    """
    if FAKE_EXHAUST and attempt == 1:
        _log(f"[FAKE] 伪造 MX_QUOTA_EXHAUSTED (MX_COMPARE_FAKE_EXHAUST=1, sector={sector_name})")
        return {"ok": False, "error": {"code": "MX_QUOTA_EXHAUSTED", "stage": "fake",
                                       "detail": "测试模式伪造积分耗尽"}}
    session_key = f"{SESSION_AGENT_PREFIX}compare-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    try:
        text = _chat_once(session_key, _build_query(sector_name, stocks), timeout=GEN_TIMEOUT)
        # 积分耗尽守卫: 命中 → 直接进入兜底(换 key 重试), 不落盘
        err = _extract_mcp_error(text)
        if err:
            return {"ok": False, "error": err, "report": text}
        return {"ok": True, "report": text}
    except socket.timeout:
        return {"ok": False, "error": {"code": "CALL_TIMEOUT", "stage": "server",
                                       "detail": f"生成超时({GEN_TIMEOUT}s)"}}
    except Exception as e:
        return {"ok": False, "error": {"code": "CALL_ERROR", "stage": "server", "detail": str(e)}}
    finally:
        # 关键: 无论成功失败, 用完即删临时会话
        _delete_session_safe(session_key)


# ---------- 每日登录 / 换 key(照搬 report_server.py, 与公司分析共用状态文件) ----------

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


def _generate_with_retry(task: TaskState) -> dict:
    """整份报告生成 + 配额耗尽换 key 重试。

    返回 {"ok": True, "report"} | {"ok": False, "error", "all_exhausted"?}。
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

        result = _call_agent(task.sector_name, task.stocks, attempt)
        if result.get("ok"):
            report = (result.get("report") or "").strip()
            if not report:
                return {"ok": False, "error": "报告内容为空"}
            return {"ok": True, "report": report}
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
        _emit(task, "retrying", stock=f"{task.sector_name}（{len(task.stocks)} 只）",
              credential=nxt, attempt=attempt)
        _log(f"{task.sector_name}: 已换到凭据{nxt}, 重试(attempt={attempt})")


# ---------- 任务主循环 ----------

def _run_task(task_id: str):
    task = TASKS[task_id]
    task.status = "running"
    task.started_at = time.time()
    _log(f"任务 {task_id} 开始: {task.sector_name} / {task.stocks}")
    try:
        # 1. 每日登录检查
        ok, err = _daily_login(task)
        if not ok:
            task.finished_at = time.time()
            task.status = "failed"
            _emit(task, "task_failed", task_id=task_id, error=err)
            _log(f"任务 {task_id} 失败: {err}")
            return

        # 2. 整份报告一次生成(单 worker 串行, 含配额耗尽换 key 重试)
        count = len(task.stocks)
        _emit(task, "generating", sector_name=task.sector_name, count=count,
              index=0, total=1)
        _log(f"{task.sector_name}: 开始生成 {count} 只股票的合并分析报告")
        outcome = _generate_with_retry(task)
        if outcome.get("ok"):
            path = _save_report(task, outcome["report"])
            task.files.append(path)
            user_path = _copy_to_user(task, path)
            if user_path:
                _log(f"已复制到用户目录: {user_path}")
        else:
            err = outcome["error"]
            task.failed.append({"sector": task.sector_name, "error": err})
            _log(f"{task.sector_name}: 生成失败 - {err}")
            if outcome.get("all_exhausted"):
                _emit(task, "all_quota_exhausted",
                      used_credentials=cs.load_state().get("exhausted", []))
                _log("当日全部凭据已耗尽")

        # 3. 终态
        task.finished_at = time.time()
        task.status = "done"
        _emit(task, "task_done", task_id=task_id, files=list(task.files),
              failed=list(task.failed),
              duration_s=round(task.finished_at - task.started_at, 1))
        _log(f"任务 {task_id} 完成: {len(task.files)} 份报告 / {len(task.failed)} 失败")
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

app = FastAPI(title="板块对比分析报告生成服务")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompareReportRequest(BaseModel):
    sector_name: str
    stocks: list[str]
    username: str | None = None   # 前端登录用户名, 报告复制到 user/{username}/板块分析/


@app.get("/api/compare/reports/history")
def compare_report_history(username: str, limit: int = 5):
    """列出 user/{username}/板块分析/ 下最近生成的报告(按 mtime 倒序)。

    与 8323 的 /api/reports/history 同构, 供前端"历史生成记录"使用:
    报告复制到用户目录时 copy2 保留生成时刻的 mtime, 按 mtime 倒序即按生成时间倒序。
    """
    if not username:
        return {"items": []}
    user_root = USER_BASE / username
    base = user_root / USER_SUBDIR
    items = []
    if base.is_dir():
        for fp in base.rglob("*.md"):
            try:
                st = fp.stat()
            except OSError:
                continue
            items.append({
                "name": fp.stem,                              # 20260817_白酒概念_对比分析报告
                "dir": fp.parent.name,                        # 板块名文件夹
                "rel_path": str(fp.relative_to(user_root)),   # 相对用户目录路径
                "mtime": int(st.st_mtime),
            })
    items.sort(key=lambda it: it["mtime"], reverse=True)
    return {"items": items[: max(1, min(limit, 50))]}


@app.post("/api/compare/reports", status_code=202)
def create_report(req: CompareReportRequest):
    if not cs.credentials_available():
        raise HTTPException(503, cs.credentials_error())
    state = cs.load_state()
    today = date.today().isoformat()
    if cs.state_is_today(state, today) and state.get("cursor") == -1:
        raise HTTPException(409, "今日用户积分已用尽,请明日再试")
    sector = (req.sector_name or "").strip()
    if not sector:
        raise HTTPException(400, "板块名称为空")
    names = [s.strip() for s in (req.stocks or []) if s.strip()]
    if not names:
        raise HTTPException(400, "股票列表为空")
    if len(names) > MAX_STOCKS:
        raise HTTPException(400, f"单次最多 {MAX_STOCKS} 只")
    username = (req.username or "").strip() or None
    task = TaskState(task_id=uuid.uuid4().hex[:12], sector_name=sector,
                     stocks=names, username=username, created_at=time.time())
    TASKS[task.task_id] = task
    _emit(task, "task_queued", task_id=task.task_id, sector_name=sector,
          stocks=names, position=_QUEUE.qsize() + 1)
    _QUEUE.put(task.task_id)
    _log(f"新任务 {task.task_id}: {sector} / {names} (队列位置 {_QUEUE.qsize()})")
    return {"task_id": task.task_id, "status": "queued"}


@app.get("/api/compare/reports/{task_id}/events")
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
                # 非阻塞等待（不能用 threading.Condition.wait_for：会阻塞事件循环）
                await asyncio.sleep(2)
                yield ": ping\n\n"
                if terminal:
                    break
                continue
            for e in new_events:
                yield f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
            if terminal:
                break

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/compare/reports/{task_id}/status")
def report_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在或服务已重启")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "sector_name": task.sector_name,
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
        "port": PORT,
        "credentials_available": cs.credentials_available(),
        "today": date.today().isoformat(),
        "state": cs.load_state(),
    }


if __name__ == "__main__":
    if FAKE_EXHAUST:
        _log("[WARN] MX_COMPARE_FAKE_EXHAUST=1 测试模式: 首次生成将伪造配额耗尽, 演练换 key 流程")
    _log("compare_report_server 启动 (真实 agent 调用: sector-multi-stock-analysis 技能)")
    threading.Thread(target=_worker_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
