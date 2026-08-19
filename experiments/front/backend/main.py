"""
股神的秘密 — 前端 API 服务

启动:
    conda run -n stock_agent python main.py
"""
import os
import re
import sys
import json
import glob
import zipfile
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Header, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import HOST, PORT, USER_SPACE_BASE
from database import db
from auth import (
    hash_password, verify_password, create_token, validate_token,
    init_default_users,
)
from stock_api import (
    ensure_stock_basic_refreshed, search_stock, get_stocks_by_names,
    fetch_yesterday_daily,
)
from explorer import (
    list_dir, get_file_content, convert_single_to_docx, convert_batch_to_docx,
    delete_item, search_files,
)
from title import build_document_title
from models import (
    LoginRequest, AddStockRequest, FavoriteItem, DownloadRequest,
    ChatCreateRequest, ChatAppendRequest, ChatCompletionsRequest,
    FeedbackRequest, ExplorerWriteRequest,
)
from chat_api import (
    build_session_key, forward_chat_stream, ChatGatewayError,
)

app = FastAPI(title="股神的秘密 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════════
# 依赖：Token 验证
# ════════════════════════════════════════════════════════════════

def _get_user(authorization: str = Header("")) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    # 支持 Bearer token 和直接 token 两种格式
    token = authorization.replace("Bearer ", "").strip()
    user = validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token 已过期")
    return user


# ════════════════════════════════════════════════════════════════
# 认证
# ════════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["id"], user["username"])
    return {"token": token, "user_id": user["id"], "username": user["username"]}


@app.get("/api/auth/me")
def me(user: dict = Depends(_get_user)):
    return {"user_id": user["user_id"], "username": user["username"]}


# ════════════════════════════════════════════════════════════════
# 股票搜索
# ════════════════════════════════════════════════════════════════

@app.get("/api/stock/search")
def stock_search(q: str = Query(""), user: dict = Depends(_get_user)):
    if not q.strip():
        return {"results": []}
    results = search_stock(q.strip())
    return {"results": results}


@app.post("/api/stock/resolve")
def stock_resolve(req: AddStockRequest, user: dict = Depends(_get_user)):
    """输入股票名称列表，返回标准化信息"""
    if not req.stock_names:
        raise HTTPException(status_code=400, detail="股票列表为空")
    # 去除空白
    names = [n.strip() for n in req.stock_names if n.strip()]
    results = get_stocks_by_names(names)
    return {"results": results}


# ════════════════════════════════════════════════════════════════
# 股票池
# ════════════════════════════════════════════════════════════════

@app.get("/api/stock/pool")
def get_pool(user: dict = Depends(_get_user)):
    stocks = db.get_stock_pool(user["user_id"])
    # 获取昨日行情
    ts_codes = [s["ts_code"] for s in stocks]
    daily_map = {}
    if ts_codes:
        daily_map = fetch_yesterday_daily(ts_codes)

    results = []
    for s in stocks:
        item = {
            "ts_code": s["ts_code"],
            "stock_name": s["stock_name"],
            "created_at": s["created_at"],
        }
        if s["ts_code"] in daily_map:
            d = daily_map[s["ts_code"]]
            item["daily"] = d.model_dump() if hasattr(d, "model_dump") else d
        else:
            item["daily"] = None
        results.append(item)

    return {"stocks": results, "total": len(results)}


@app.post("/api/stock/pool")
def add_to_pool(req: AddStockRequest, user: dict = Depends(_get_user)):
    names = [n.strip() for n in req.stock_names if n.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="股票列表为空")

    # 解析名称 → 代码
    stocks_info = get_stocks_by_names(names)
    if not stocks_info:
        raise HTTPException(status_code=400, detail="未找到匹配的股票")

    added = []
    for s in stocks_info:
        db.add_stock_to_pool(user["user_id"], s["ts_code"], s["name"])
        added.append({"ts_code": s["ts_code"], "stock_name": s["name"]})

    return {"added": added, "count": len(added)}


@app.delete("/api/stock/pool/{ts_code}")
def remove_from_pool(ts_code: str, user: dict = Depends(_get_user)):
    db.remove_stock_from_pool(user["user_id"], ts_code)
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════
# 文件浏览
# ════════════════════════════════════════════════════════════════

@app.get("/api/explorer/list")
def explorer_list(path: str = Query(""), user: dict = Depends(_get_user)):
    items = list_dir(path, user["username"], user["user_id"])
    return {"items": items, "path": path}


@app.get("/api/explorer/search")
def explorer_search(q: str = Query(""), user: dict = Depends(_get_user)):
    """按文件名递归搜索用户空间中的文档"""
    results = search_files(q, user["username"])
    return {"results": results}


@app.get("/api/explorer/content")
def explorer_content(path: str = Query(""), user: dict = Depends(_get_user)):
    content = get_file_content(path, user["username"])
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在或格式不支持")
    return {"content": content, "path": path}


@app.get("/api/explorer/download")
def explorer_download(path: str = Query(""), user: dict = Depends(_get_user)):
    """下载单个文件（自动转为 docx）"""
    docx_path = convert_single_to_docx(path, user["username"])
    if not docx_path:
        raise HTTPException(status_code=404, detail="文件不存在或转换失败")

    filename = Path(docx_path).name
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@app.post("/api/explorer/download-batch")
def explorer_download_batch(req: DownloadRequest, user: dict = Depends(_get_user)):
    """批量下载（打包为 zip）"""
    if not req.paths:
        raise HTTPException(status_code=400, detail="请选择至少一个文件")

    zip_path = convert_batch_to_docx(req.paths, user["username"])
    if not zip_path:
        raise HTTPException(status_code=500, detail="转换失败")

    filename = f"documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
    )


@app.delete("/api/explorer/delete")
def explorer_delete(path: str = Query(""), user: dict = Depends(_get_user)):
    """删除文件或目录（目录递归删除，用户根目录受保护）"""
    ok = delete_item(path, user["username"])
    if not ok:
        raise HTTPException(status_code=400, detail="删除失败：文件不存在，或该目录为根目录不可删除")
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════
# 收藏夹
# ════════════════════════════════════════════════════════════════

@app.get("/api/explorer/favorites")
def get_favorites(user: dict = Depends(_get_user)):
    favs = db.get_favorites(user["user_id"])
    return {"favorites": favs}


@app.post("/api/explorer/favorites")
def add_favorite(req: FavoriteItem, user: dict = Depends(_get_user)):
    db.add_favorite(user["user_id"], req.file_path, req.file_name)
    return {"status": "ok"}


@app.delete("/api/explorer/favorites")
def remove_favorite(path: str = Query(""), user: dict = Depends(_get_user)):
    db.remove_favorite(user["user_id"], path)
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════
# 股小神聊天
# ════════════════════════════════════════════════════════════════

@app.get("/api/chat/sessions")
def chat_sessions(user: dict = Depends(_get_user)):
    """会话列表（按最近更新排序）"""
    return {"sessions": db.list_chat_sessions(user["user_id"])}


@app.post("/api/chat/sessions")
def chat_create_session(req: ChatCreateRequest, user: dict = Depends(_get_user)):
    """创建会话（幂等：conv_id 已存在则返回现有记录）"""
    session = db.create_chat_session(user["user_id"], req.conv_id.strip(), req.title or "新对话")
    return {"session": session}


@app.delete("/api/chat/sessions/{conv_id}")
def chat_delete_session(conv_id: str, user: dict = Depends(_get_user)):
    """删除会话及其全部消息"""
    ok = db.delete_chat_session(user["user_id"], conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "ok"}


@app.get("/api/chat/sessions/{conv_id}/messages")
def chat_session_messages(conv_id: str, user: dict = Depends(_get_user)):
    """会话消息历史（按时间正序，用于恢复现场）"""
    return {"messages": db.list_chat_messages(user["user_id"], conv_id)}


@app.post("/api/chat/sessions/{conv_id}/messages")
def chat_append_message(conv_id: str, req: ChatAppendRequest, user: dict = Depends(_get_user)):
    """追加一条消息（流结束后前端回存 assistant 回复；abort 时回存已生成部分）"""
    if req.role not in ("user", "assistant"):
        raise HTTPException(status_code=400, detail="role 仅支持 user / assistant")
    message = db.append_chat_message(user["user_id"], conv_id, req.role, req.content)
    if not message:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": message}


@app.post("/api/chat/completions")
async def chat_completions(req: ChatCompletionsRequest, user: dict = Depends(_get_user)):
    """转发到 OpenClaw Gateway 流式对话（token 只留在后端）。

    前端把完整历史放在 messages 里 → 后端落库最后一条 user 消息 →
    以 agent:mx-public:<userId>-<convId> 作为 session key 流式透传 SSE。
    """
    conv_id = req.conv_id.strip()
    if not conv_id or not req.messages:
        raise HTTPException(status_code=400, detail="conv_id 与 messages 不能为空")
    # 会话不存在则自动创建（前端首页输入框直接发第一条时无需先建会话）
    db.create_chat_session(user["user_id"], conv_id)
    # 落库最后一条 user 消息（首条自动生成标题；重复 append 由前端保证时序）。
    # 「重新生成」重放历史时 persist_last_user=false，末条 user query 已在库中不再重复落库。
    last = req.messages[-1]
    if last.role == "user" and req.persist_last_user:
        db.append_chat_message(user["user_id"], conv_id, "user", last.content)

    session_key = build_session_key(user["user_id"], conv_id)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def _proxy():
        try:
            async for chunk in forward_chat_stream(messages, session_key):
                yield chunk
        except ChatGatewayError as e:
            # SSE 帧里带错误，前端解析 data: 时看到 error 字段会提示
            err = json.dumps({"error": {"message": e.detail}}, ensure_ascii=False)
            yield f"data: {err}\n\n".encode("utf-8")

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/api/chat/sessions/{conv_id}/assistant")
def chat_delete_last_assistant(conv_id: str, user: dict = Depends(_get_user)):
    """「重新生成」：删除会话最后一条 assistant 回复（保留触发它的 user 问句）。"""
    ok = db.delete_last_assistant_message(user["user_id"], conv_id)
    if not ok:
        raise HTTPException(status_code=400, detail="无可删除的 assistant 回复")
    return {"status": "ok"}


# ── 反馈 skill 快照：按 sessionKey 定位 transcript，从 trajectory 提取 skill 清单 ──
_MX_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "mx-public" / "sessions"
_SKILL_PATTERN = re.compile(
    r"(mx-ds-mcp__[A-Za-z0-9_]+|hithink-[A-Za-z0-9-]+|"
    r"tushare[_-][A-Za-z0-9_-]+|company-analysis|news-aggregator-skill|"
    r"sector-multi-stock-analysis|data-source-priority|rd-leaders-[a-z-]+)"
)


def _extract_dislike_skills(user_id: int, conv_id: str) -> list[str]:
    """dislike 时在场抓取该会话用过的 skill/tool 清单。

    通过 sessionKey `agent:mx-public:<user_id>-<conv_id>` 反查 transcript →
    同名 trajectory → 用正则提取 skill/tool 名。transcript 仅保留约 7 天，
    所以「当场抓取」保证可关联。抓不到时返回空列表（不阻断反馈落库）。
    """
    sess_dir = _MX_SESSIONS_DIR
    if not sess_dir.exists():
        return []
    session_key = f"agent:mx-public:{user_id}-{conv_id}"
    transcript = None
    for f in glob.glob(str(sess_dir / "*.jsonl")):
        if ".trajectory" in f:
            continue
        try:
            if session_key in open(f, encoding="utf-8", errors="replace").read():
                transcript = f
                break
        except OSError:
            continue
    if not transcript:
        return []
    traj = transcript.replace(".jsonl", "") + ".trajectory.jsonl"
    if not os.path.exists(traj):
        return []
    skills = set()
    try:
        with open(traj, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for m in _SKILL_PATTERN.findall(line):
                    if m == "mx-ds-mcp__mx_":
                        continue  # 截断的裸前缀, 非真实工具名
                    skills.add(m)
    except OSError:
        return []
    return sorted(skills)


@app.post("/api/chat/feedback")
def chat_feedback(req: "FeedbackRequest", user: dict = Depends(_get_user)):
    """记录一条 喜欢/不喜欢 反馈。dislike 时抓取该会话 skill 快照落库。"""
    if req.feedback not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="feedback 仅支持 like / dislike")
    skills = None
    if req.feedback == "dislike":
        sk = _extract_dislike_skills(user["user_id"], req.conv_id)
        if sk:
            skills = json.dumps(sk, ensure_ascii=False)
    db.add_feedback(user["user_id"], req.conv_id, req.message_id, req.feedback, skills)
    return {"status": "ok"}


@app.post("/api/explorer/write")
def explorer_write(req: "ExplorerWriteRequest", user: dict = Depends(_get_user)):
    """保存 markdown 到用户空间（「保存成文档」）。文件路径在用户根目录内，防穿越。"""
    base = USER_SPACE_BASE / user["username"]
    rel = (req.dir_path or "").replace("\\", "/").strip().strip("/")
    target_dir = (base / rel).resolve()
    if not str(target_dir).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="目录不在用户空间内")
    target_dir.mkdir(parents=True, exist_ok=True)

    # 文件名：未显式给 filename 时，用 query 经 TextRank 生成「日期_主题」名
    filename = req.filename.strip()
    if not filename and req.query.strip():
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{build_document_title(req.query)}.md"
    # 文件名清洗：去掉路径分隔符与非法字符，避免被当作路径
    safe_name = re.sub(r"[\\/:*?\"<>|\n\r\t]+", "", filename).strip()
    if not safe_name or Path(safe_name).suffix not in (".md",):
        raise HTTPException(status_code=400, detail="文件名不合法，仅支持 .md")
    target = (target_dir / safe_name).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="保存路径越界")

    # 重名自动追加序号，避免覆盖已有文档
    i = 1
    stem = target.stem
    while target.exists():
        target = target_dir / f"{stem}_{i}{target.suffix}"
        i += 1
    target.write_text(req.content or "", encoding="utf-8")
    rel_path = str(target.relative_to(base)).replace(os.sep, "/")
    return {"status": "ok", "path": rel_path, "filename": target.name}


# ════════════════════════════════════════════════════════════════
# 静态文件托管（前端构建后启用）
# ════════════════════════════════════════════════════════════════

_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


# ════════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("🚀 股神的秘密后端启动中...")
    init_default_users()

    # 确保用户空间基础目录存在
    USER_SPACE_BASE.mkdir(parents=True, exist_ok=True)

    # 后台预热：确保 stock_basic 已拉取（后台线程，不阻塞启动）
    import threading
    def _warmup():
        try:
            ensure_stock_basic_refreshed()
            print("  ✅ 股票基础信息预热完成")
        except Exception as e:
            print(f"  ⚠️  股票基础信息预热失败: {e}")
    threading.Thread(target=_warmup, daemon=True).start()

    print(f"\n  📡 API 服务: http://{HOST}:{PORT}")
    print(f"  📁 用户空间: {USER_SPACE_BASE}/＜用户名＞/")
    print(f"  🗄️  数据库: /home/stockagent/project_space/database/report_market.db")
    print()
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
