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
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

CREDENTIALS_FILE = pathlib.Path.home() / ".config" / "choice_mcp_credentials.json"
STATE_FILE = pathlib.Path.home() / ".config" / "mx_report_server_state.json"
OPENCLAW_JSON = pathlib.Path.home() / ".openclaw" / "openclaw.json"
LOGIN_SCRIPT = pathlib.Path(__file__).parent / "choice_get_api_key.py"
STORAGE_FILE = pathlib.Path.home() / ".config" / "choice_storage.json"  # 浏览器登录态(storage_state), 免滑块

GATEWAY_BASE = "http://127.0.0.1:18789"
LOGIN_TIMEOUT = 240          # 单次登录(playwright 启动+登录+取 key)上限
GATEWAY_RESTART_TIMEOUT = 90  # 重启 gateway 后 /v1/models 恢复等待上限

MAX_CREDENTIALS = 5          # 主 + 备用1~4


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
    """原子写状态文件(tmp + os.replace), 单 worker 无并发写。"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def state_is_today(state: dict, today: str) -> bool:
    return state.get("last_login_date") == today


# ---------- 登录子进程 ----------

def run_login(index: int, timeout: int = LOGIN_TIMEOUT, storage: str | None = None) -> dict:
    """子进程调用 choice_get_api_key.py --index N --json。

    传 storage(playwright storage_state JSON 路径, 通常 STORAGE_FILE)时优先复用
    浏览器登录态免滑块取 Key; 登录态失效由脚本自动回退完整登录流程。

    返回 {"ok": true, "key": "em_...", "index", "elapsed_s"}
    或    {"ok": false, "reason": "...", "index", "elapsed_s"}
    """
    cmd = [sys.executable, str(LOGIN_SCRIPT), "--index", str(index), "--json"]
    if storage and pathlib.Path(storage).exists():
        cmd += ["--storage", storage]
    try:
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
