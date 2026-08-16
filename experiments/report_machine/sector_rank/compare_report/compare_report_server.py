#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板块对比分析报告生成服务(FastAPI + SSE, 端口 8326) —— 占位实现

接口:
    POST /api/compare/reports                  创建生成任务(板块名 + 选中股票列表)
    GET  /api/compare/reports/{task_id}/events SSE 实时进度
    GET  /api/compare/reports/{task_id}/status 兜底状态查询(事件缓冲最近 20 条)
    GET  /health                               健康检查

任务流程(单 worker 串行):
    1. 逐股发 generating → _call_agent() 模拟生成(占位, sleep 模拟耗时)
    2. 全部股票处理完 → 合并为一份板块对比分析报告(markdown)
    3. 报告写 reports/ → 复制到 user/{username}/板块分析/{板块名}/ → task_done

⚠️ 占位说明: _call_agent() 目前是占位实现, 不真实调用 openclaw agent。
   agent 生成功能开发完成后, 替换 _call_agent() 函数体为真实 gateway 调用即可
   (参照 mx_company_reporter/company_report_api.py 的 _chat_once 模式)。

启动: ./compare_report_server.sh start   (nohup + log/compare_report_server.log)
"""
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
GEN_SIM_SEC = 1.5        # 占位阶段每只股票的模拟生成耗时(agent 真实生成后将远大于此)
MAX_STOCKS = 20          # 单次任务最多股票数(前端排名表最多 20 行)

# 本文件位于 sector_rank/compare_report/, report_machine 根 = 上级的上级
_HERE = pathlib.Path(__file__).resolve().parent
_RM_DIR = _HERE.parents[1]
REPORTS_DIR = _HERE / "reports"          # 服务端暂存
USER_BASE = _RM_DIR / "user"             # 用户空间(user/{username}/板块分析/{板块名}/)
USER_SUBDIR = "板块分析"                  # explorer 中独立总文件夹(与"上市公司分析"平行)


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


# ---------- 占位 agent 调用(★ 后续替换点) ----------

def _safe_filename(name: str) -> str:
    """过滤文件名非法字符(照搬 company_report_api.py 的规则)。"""
    return re.sub(r'[\\/:*?"<>|\s]+', '_', name).strip("_")


def _call_agent(sector_name: str, stock: str) -> dict:
    """调用 openclaw agent 生成"个股简要分析"段落 —— 占位实现, 不真实调用。

    TODO(替换点): agent 生成功能开发完成后, 替换本函数体为真实 gateway 调用:
      POST http://127.0.0.1:18789/v1/chat/completions   (model: openclaw/mx-agent)
      headers: Authorization: Bearer <token>  +  x-openclaw-session-key: <唯一>
      query(整份报告一次生成, 含全部股票简要分析+对比分析):
        f"生成{','.join(stocks)}的公司简要分析报告和对比分析报告"
      参照 mx_company_reporter/company_report_api.py:
        _load_token() / _chat_once() / _extract_mcp_error() / _delete_session_safe()
      成功返回 {"ok": True, "markdown": "<整份报告>"},
      失败返回 {"ok": False, "error": "<原因>"}
    替换后任务流程相应改为: 整份报告一次生成(不需要逐股段落拼接)。
    """
    time.sleep(GEN_SIM_SEC)  # 模拟 agent 耗时, 让前端进度有真实感
    return {"ok": True, "markdown": (
        f"### {stock}\n\n"
        f"- **简要分析**：占位内容 —— agent 生成功能开发中，本段落将在接入 "
        f"OpenClaw mx-agent 后自动生成。\n"
    )}


# ---------- 报告写入与复制 ----------

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


def _build_report(task: TaskState, parts: list[str]) -> str:
    """汇总占位报告(板块信息 + 逐股简要分析段落 + 对比分析待生成章节)。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"# {task.sector_name} 板块对比分析报告\n\n"
        f"- 生成日期：{now}\n"
        f"- 板块：{task.sector_name}\n"
        f"- 涉及股票（{len(task.stocks)} 只）：{'、'.join(task.stocks)}\n"
        f"- 生成方式：OpenClaw mx-agent（**占位实现**，待 agent 生成功能开发完成后启用）\n\n"
        f"> ⚠️ 本报告为**占位文件**：agent 生成功能尚未开发完成，"
        f"以下内容将在开发完成后自动替换为真实分析。\n\n"
        f"## 一、个股简要分析\n\n"
        + "\n".join(parts)
        + "\n## 二、对比分析\n\n"
        + "（待生成：涨幅、主力资金、估值、成长性等维度的横向对比。）\n"
    )


# ---------- 任务主循环(无积分/登录逻辑的精简版) ----------

def _run_task(task_id: str):
    task = TASKS[task_id]
    task.status = "running"
    task.started_at = time.time()
    _log(f"任务 {task_id} 开始: {task.sector_name} / {task.stocks}")
    try:
        # 逐股模拟生成, 收集段落
        total = len(task.stocks)
        parts: list[str] = []
        for i, stock in enumerate(task.stocks):
            _emit(task, "generating", stock=stock, index=i, total=total)
            _log(f"{stock}: 开始生成 ({i + 1}/{total})")
            outcome = _call_agent(task.sector_name, stock)
            if outcome.get("ok"):
                parts.append(outcome["markdown"])
                _emit(task, "stock_done", stock=stock, index=i, total=total)
                _log(f"{stock}: 段落生成完成 ({i + 1}/{total})")
            else:
                err = outcome.get("error", "未知错误")
                task.failed.append({"stock": stock, "error": err})
                _emit(task, "stock_failed", stock=stock, index=i, total=total, error=err)
                _log(f"{stock}: 失败 - {err}")

        # 合并为整份报告 → 写盘 → 复制到用户目录
        if parts:
            md = _build_report(task, parts)
            path = _save_report(task, md)
            task.files.append(path)
            user_path = _copy_to_user(task, path)
            if user_path:
                _log(f"已复制到用户目录: {user_path}")

        # 终态
        task.finished_at = time.time()
        task.status = "done"
        _emit(task, "task_done", task_id=task_id, files=list(task.files),
              failed=list(task.failed),
              duration_s=round(task.finished_at - task.started_at, 1))
        _log(f"任务 {task_id} 完成: {len(task.files)} 份报告 / {len(task.failed)} 只失败")
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


@app.post("/api/compare/reports", status_code=202)
def create_report(req: CompareReportRequest):
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
                task.cond.wait_for(
                    lambda: len(task.events) > sent or task.status in ("done", "failed"),
                    timeout=15)
                new_events = list(task.events[sent:])
                sent = len(task.events)
                terminal = task.status in ("done", "failed")
            if not new_events:
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
    return {"status": "ok", "port": PORT, "user_base": str(USER_BASE)}


if __name__ == "__main__":
    _log(f"compare_report_server 启动, 端口 {PORT} (占位模式: agent 调用未接入)")
    threading.Thread(target=_worker_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
