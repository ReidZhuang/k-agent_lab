#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""凭据 / 游标状态 / gateway 切换管理(报告生成服务专用)

职责:
    1. 凭据文件(~/.config/choice_mcp_credentials.json)读取与校验
    2. 当日游标状态(~/.config/mx_report_server_state.json)原子读写
    3. run_login(index): 子进程调用 choice_get_api_key.py --index N --json
       (playwright 在子进程内, 崩溃/泄漏不影响服务进程; 密码不经过命令行参数)
    4. switch_gateway_key(key): 仅 key 变化时更新 openclaw.json 并重启
       openclaw-gateway, 轮询 /v1/models 验证恢复

凭据索引约定(全服务统一): 0 = primary, 1..4 = backups[0..3]。

并发安全: 8323(公司分析)与 8326(板块对比)是两个独立进程, 共用同一
gateway / openclaw.json / 状态文件。登录与换 key 是互斥临界区, 必须用
mutex() 文件锁包住整个流程, 否则两服务同时写 openclaw.json / 重启
gateway 会互相打断(实测曾因此损坏配置)。
"""
import fcntl
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager

CREDENTIALS_FILE = pathlib.Path.home() / ".config" / "choice_mcp_credentials.json"
STATE_FILE = pathlib.Path.home() / ".config" / "mx_report_server_state.json"
OPENCLAW_JSON = pathlib.Path.home() / ".openclaw" / "openclaw.json"
LOGIN_SCRIPT = pathlib.Path(__file__).parent / "choice_get_api_key.py"
STORAGE_FILE = pathlib.Path.home() / ".config" / "choice_storage.json"  # 浏览器登录态(storage_state), 免滑块
MUTEX_FILE = pathlib.Path.home() / ".config" / "mx_report_server.lock"  # 跨进程互斥锁(登录/换key共用)

GATEWAY_BASE = "http://127.0.0.1:18789"
LOGIN_TIMEOUT = 240          # 单次登录(playwright 启动+登录+取 key)上限
GATEWAY_RESTART_TIMEOUT = 90  # 重启 gateway 后 /v1/models 恢复等待上限

MAX_CREDENTIALS = 5          # 主 + 备用1~4


# ---------- 跨进程互斥 ----------

_local = threading.local()


@contextmanager
def mutex(desc: str = "登录/换key"):
    """跨进程互斥锁(flock, 8323/8326 共用 gateway 与配置文件)。

    登录(最长 LOGIN_TIMEOUT)与换 key(重启 gateway)期间互斥持有, 防止
    两服务同时写 openclaw.json / 重启 gateway 互相打断。阻塞等待无超时
    (对方最长持锁约 LOGIN_TIMEOUT + GATEWAY_RESTART_TIMEOUT, 换 key 方
    本就要等配额耗尽后的重试, 可接受)。进程退出自动释放。

    同进程内可重入(flock 对同文件不同 fd 互斥, 嵌套会自我死锁):
    外层流程(如 _switch_credential 整段)持锁后, 内部 run_login /
    switch_gateway_key / save_state 的 mutex 直接放行——它们本就属于
    同一临界区。跨进程的互斥不受影响。
    """
    if getattr(_local, "held", False):
        yield
        return
    MUTEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MUTEX_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        _local.held = True
        try:
            yield
        finally:
            _local.held = False
            fcntl.flock(fh, fcntl.LOCK_UN)


def locked(desc: str):
    """装饰器: 整个函数体在跨进程互斥锁内执行(8323/8326 并发安全)。

    用于 _daily_login / _switch_credential 等「读状态→登录/换key→写状态」
    的完整流程; 内部 run_login/switch_gateway_key/save_state 的 mutex
    可重入。长耗时的 agent 调用本身不加锁(会阻塞对方), 由调用方把
    agent 调用放在锁外。
    """
    def deco(fn):
        def wrapper(*args, **kwargs):
            with mutex(desc):
                return fn(*args, **kwargs)
        return wrapper
    return deco


# ---------- 凭据文件 ----------

def credentials_available() -> bool:
    """凭据文件是否存在且可解析为合法结构(primary + backups 数组)。"""
    if not CREDENTIALS_FILE.exists():
        return False
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    primary = data.get("primary")
    backups = data.get("backups")
    if not isinstance(primary, dict) or not primary.get("username") or not primary.get("password"):
        return False
    if not isinstance(backups, list):
        return False
    return True


def credentials_error() -> str:
    """凭据文件问题的中文描述(供 503 响应/日志), 无问题时返回空串。"""
    if not CREDENTIALS_FILE.exists():
        return f"凭据配置缺失: {CREDENTIALS_FILE}"
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return f"凭据配置不是合法 JSON: {e}"
    primary = data.get("primary")
    if not isinstance(primary, dict) or not primary.get("username") or not primary.get("password"):
        return "凭据配置缺少 primary(username/password)"
    if not isinstance(data.get("backups"), list):
        return "凭据配置的 backups 必须是数组(可为空)"
    return ""


def total_credentials() -> int:
    """可用凭据总数(1 + len(backups), 上限 MAX_CREDENTIALS)。"""
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        return min(1 + len(data.get("backups") or []), MAX_CREDENTIALS)
    except Exception:
        return 0


# ---------- 游标状态文件 ----------

def load_state() -> dict:
    """读取当日游标状态。文件缺失/损坏时返回空状态(由调用方判定是否需要每日登录)。"""
    default = {"last_login_date": "", "cursor": 0, "exhausted": [], "current_key_prefix": ""}
    if not STATE_FILE.exists():
        return default
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
    for k, v in default.items():
        data.setdefault(k, v)
    return data


def save_state(state: dict) -> None:
    """原子写状态文件(tmp + os.replace)。8323/8326 双服务并发写时互斥,
    防同一 tmp 文件互相覆盖(调用方流程已持锁时可重入)。"""
    with mutex("写状态"):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_FILE)


def state_is_today(state: dict, today: str) -> bool:
    return state.get("last_login_date") == today


# ---------- 登录子进程 ----------

def run_login(index: int, timeout: int = LOGIN_TIMEOUT, storage: str | None = None) -> dict:
    """子进程调用 choice_get_api_key.py --index N --json。

    默认走 CDP 模式(--cdp): 连接/自动启动真实 Chrome(指纹=真实用户, 滑块
    验证自动放行), 登录态用账号标记复用(免账号密码, 且不串号), 无需手动
    开浏览器。显式传 storage(playwright storage_state JSON 路径)时改用
    storage 复用(旧方案, 仅兼容)。

    返回 {"ok": true, "key": "em_...", "index", "elapsed_s"}
    或    {"ok": false, "reason": "...", "index", "elapsed_s"}
    """
    cmd = [sys.executable, str(LOGIN_SCRIPT), "--index", str(index), "--json"]
    if storage and pathlib.Path(storage).exists():
        cmd += ["--storage", storage]
    else:
        cmd += ["--cdp"]
    try:
        # 登录全程持锁: 防止与另一服务(8323/8326)的登录/换key并发
        with mutex(f"登录(index={index})"):
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                cwd=str(LOGIN_SCRIPT.parent),
            )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"登录超时(>{timeout}s)", "index": index, "elapsed_s": timeout}
    # stdout 最后一行 JSON 是结构化结果(成功/失败都有; 人类日志在 stderr)
    tail = [line for line in r.stdout.strip().splitlines() if line.startswith("{")]
    if tail:
        try:
            return json.loads(tail[-1])
        except json.JSONDecodeError:
            pass
    reason = "登录脚本异常退出"
    err_lines = [line for line in r.stderr.strip().splitlines() if line.strip()]
    if err_lines:
        reason = err_lines[-1][:200]
    return {"ok": False, "reason": reason, "index": index, "elapsed_s": 0}


# ---------- gateway 切换 ----------

def _load_gateway_token() -> str:
    env = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    if env:
        return env
    with open(OPENCLAW_JSON, encoding="utf-8") as f:
        return json.load(f)["gateway"]["auth"]["token"]


def get_current_em_api_key() -> str:
    """读 openclaw.json 当前的 em_api_key, 读取失败返回空串。"""
    try:
        with open(OPENCLAW_JSON, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg["mcp"]["servers"]["mx-ds-mcp"]["headers"].get("em_api_key", "")
    except Exception:
        return ""


def wait_gateway_ready(timeout: int = GATEWAY_RESTART_TIMEOUT) -> bool:
    """轮询 GET /v1/models 直到 gateway 恢复(带 token 认证)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            token = _load_gateway_token()
            req = urllib.request.Request(
                f"{GATEWAY_BASE}/v1/models",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def switch_gateway_key(new_key: str) -> tuple[bool, str]:
    """把新 key 写入 openclaw.json; 仅当 key 发生变化时重启 gateway 并等待恢复。

    返回 (ok, reason)。ok=False 时 reason 为失败原因。
    """
    from choice_get_api_key import update_openclaw  # 同目录, 复用备份+写入逻辑

    # 写 openclaw.json + 重启 gateway 全程互斥: 防止与另一服务的登录/换key并发
    with mutex("换key"):
        old = get_current_em_api_key()
        if not update_openclaw(new_key):
            return False, "更新 openclaw.json 失败(路径缺失或配置错误)"
        if old == new_key:
            return True, "key 未变化, 无需重启 gateway"
        try:
            r = subprocess.run(
                ["systemctl", "--user", "restart", "openclaw-gateway"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                return False, f"重启 openclaw-gateway 失败: {r.stderr.strip()[:200]}"
        except Exception as e:
            return False, f"重启 openclaw-gateway 异常: {e}"
        if not wait_gateway_ready():
            return False, f"gateway 重启后 {GATEWAY_RESTART_TIMEOUT}s 内未恢复"
        return True, "gateway 已重启并恢复"


if __name__ == "__main__":
    # 简单自检: python credential_store.py
    print("凭据可用:", credentials_available())
    if not credentials_available():
        print(credentials_error())
    print("可用凭据数:", total_credentials())
    print("当前状态:", json.dumps(load_state(), ensure_ascii=False))
    print("当前 em_api_key:", get_current_em_api_key()[:12] + "...")
