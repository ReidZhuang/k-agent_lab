#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw Gateway 极简 WebSocket RPC 客户端（纯标准库，零依赖）

用途：调用 Gateway 的 WS RPC 方法（如 sessions.delete），
用于在每次 API 报告调用后立即删除临时会话。

前提：Gateway 运行在 127.0.0.1:18789（loopback），auth.mode=token。
"""
import base64
import json
import os
import socket
import struct
import uuid

GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18789


# ---------- 极简 WebSocket 帧协议 ----------

def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def _send_frame(sock, opcode, payload: bytes):
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    header = bytearray([0x80 | opcode])  # FIN + opcode(text=1)
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    header += mask_key
    sock.sendall(bytes(header) + masked)


def _recv_frame(sock):
    b0, b1 = _recv_exact(sock, 2)
    opcode = b0 & 0x0F
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if (b1 & 0x80) else None
    payload = _recv_exact(sock, n) if n else b""
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def _open_ws():
    """HTTP Upgrade 握手，返回已建立 WS 连接的 socket。"""
    sock = socket.create_connection((GATEWAY_HOST, GATEWAY_PORT), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {GATEWAY_HOST}:{GATEWAY_PORT}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
    if b" 101 " not in resp.split(b"\r\n", 1)[0]:
        raise RuntimeError(f"WebSocket 握手失败: {resp[:200]!r}")
    return sock


def _read_json_message(sock, timeout=15):
    """读取一条 JSON 消息；自动应答 ping，遇 close 抛错。"""
    sock.settimeout(timeout)
    while True:
        opcode, payload = _recv_frame(sock)
        if opcode == 0x9:                      # ping -> pong
            _send_frame(sock, 0xA, payload)
            continue
        if opcode == 0x8:                      # close
            raise RuntimeError("连接被 Gateway 关闭")
        if opcode == 0x1:                      # text
            return json.loads(payload.decode("utf-8"))
        # 0x0/0x2 等其它帧忽略


# ---------- Gateway RPC ----------

def _load_token():
    """从 openclaw.json 读取 gateway token（也可改用环境变量）。"""
    env = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    if env:
        return env
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)["gateway"]["auth"]["token"]


def rpc(method: str, params: dict, token: str | None = None, timeout: int = 30) -> dict:
    """
    调用一个 Gateway WS RPC 方法，返回响应 payload。
    例如: rpc("sessions.delete", {"key": "agent:mx-agent:report-xxx"})
    """
    token = token or _load_token()
    sock = _open_ws()
    try:
        req_id = "req-" + uuid.uuid4().hex[:8]
        connect = {
            "type": "req", "id": req_id, "method": "connect",
            "params": {
                "minProtocol": 4, "maxProtocol": 4,
                "client": {"id": "gateway-client", "version": "1.0.0",
                           "platform": "linux", "mode": "backend"},
                "role": "operator",
                "scopes": ["operator.admin", "operator.approvals", "operator.pairing",
                            "operator.read", "operator.talk.secrets", "operator.write"],
                "caps": [], "commands": [], "permissions": {},
                "auth": {"token": token},
                "locale": "zh-CN",
                "userAgent": "python-report-api",
            },
        }
        _send_frame(sock, 0x1, json.dumps(connect).encode())

        # 等待 connect 响应（hello-ok）
        while True:
            msg = _read_json_message(sock, timeout=timeout)
            if msg.get("type") == "res" and msg.get("id") == req_id:
                if not msg.get("ok"):
                    raise RuntimeError(f"connect 失败: {msg.get('error')}")
                break

        # 发送目标 RPC
        rid = "req-" + uuid.uuid4().hex[:8]
        _send_frame(sock, 0x1, json.dumps({
            "type": "req", "id": rid, "method": method, "params": params,
        }).encode())

        while True:
            msg = _read_json_message(sock, timeout=timeout)
            if msg.get("type") == "res" and msg.get("id") == rid:
                if not msg.get("ok"):
                    raise RuntimeError(f"{method} 失败: {msg.get('error')}")
                return msg.get("payload", {})
    finally:
        sock.close()


def delete_session(session_key: str, token: str | None = None) -> dict:
    """删除一个会话（幂等：不存在的 key 也安全）。"""
    return rpc("sessions.delete", {"key": session_key}, token=token)


if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else None
    if not key:
        print("用法: python3 openclaw_rpc.py <session-key>")
        sys.exit(1)
    try:
        result = delete_session(key)
        print("已删除:", key, "->", result)
    except Exception as e:
        print("删除失败:", e)
        sys.exit(1)
