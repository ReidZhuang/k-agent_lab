#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""滑块人工验证实验服务(端口 8325)

登录脚本(choice_get_api_key.py --challenge-dir DIR)检测到滑块验证码时,
把拼图(背景+滑块截图)写入 DIR/challenge.json 并等待 DIR/result.json;
本服务把这两个文件暴露为 HTTP 接口, 供前端悬浮窗展示拼图/回传拖动结果。

接口:
    GET  /login-exp/challenge     → 当前拼图(无则 404)
    POST /login-exp/result        → {id, distance, track, duration} 写回结果
    GET  /login-exp/status        → 挑战目录状态(调试用)

正式版将把同样的接口并入 report_server(8323), 文件协议保持不变。

启动: conda run -n stock_agent python login_exp_server.py
"""
import json
import pathlib
import sys
import time

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CHALLENGE_DIR = pathlib.Path.home() / ".config" / "mx_login_challenge"
PORT = 8325


def _read_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: pathlib.Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


app = FastAPI(title="滑块人工验证实验服务")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResultIn(BaseModel):
    id: str
    distance: float = 0
    track: list = []
    duration: float = 0


@app.get("/login-exp/challenge")
def get_challenge():
    c = _read_json(CHALLENGE_DIR / "challenge.json")
    if not c:
        raise HTTPException(404, "no active challenge")
    return c


@app.post("/login-exp/result")
def post_result(r: ResultIn):
    cur = _read_json(CHALLENGE_DIR / "challenge.json")
    if not cur or cur.get("id") != r.id:
        raise HTTPException(409, "challenge 已过期或 id 不匹配")
    _write_json(CHALLENGE_DIR / "result.json", r.model_dump())
    return {"ok": True, "id": r.id}


@app.get("/login-exp/status")
def status():
    return {
        "dir": str(CHALLENGE_DIR),
        "challenge": _read_json(CHALLENGE_DIR / "challenge.json"),
        "result": _read_json(CHALLENGE_DIR / "result.json"),
        "now": int(time.time()),
    }


if __name__ == "__main__":
    CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 挑战目录: {CHALLENGE_DIR}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
