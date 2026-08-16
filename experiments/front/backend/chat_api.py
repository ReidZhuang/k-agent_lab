"""
股小神 — OpenClaw Gateway 转发模块

安全边界（FRONTEND_API.md §5）：gateway token 只存在于后端，
浏览器永远不接触；本模块负责：
  1. 读取 gateway token（每次请求现读，管理员轮换后无需重启）
  2. 用登录用户信息组装 session key（agent:mx-public:<userId>-<convId>）
  3. 流式转发到 gateway 并透传 SSE 字节流给前端
"""
import json
from pathlib import Path

import httpx

GATEWAY_URL = "http://127.0.0.1:18789"
MODEL = "openclaw/mx-public"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


class ChatGatewayError(Exception):
    """gateway 调用失败（含未就绪/配额超限/返回错误）"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _load_gateway_token() -> str:
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        token = cfg["gateway"]["auth"]["token"]
        if token:
            return token
    except (OSError, KeyError, json.JSONDecodeError):
        pass
    raise ChatGatewayError(502, "Gateway 配置不可用（openclaw.json 缺失或格式错误）")


def build_session_key(user_id: int, conv_id: str) -> str:
    """会话隔离 key：前缀必须带 agent:mx-public:，决定路由到 mx-public 的 workspace/skills"""
    return f"agent:mx-public:{user_id}-{conv_id}"


async def forward_chat_stream(messages: list[dict], session_key: str):
    """转发到 gateway 的流式 chat/completions，逐字节透传 SSE。

    非 200 时收集错误体并抛 ChatGatewayError（含配额超限等标准错误块）。
    """
    token = _load_gateway_token()
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{GATEWAY_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "x-openclaw-session-key": session_key,
            },
            json={
                "model": MODEL,
                "stream": True,
                "messages": messages,
            },
        ) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                # 配额超限等标准错误块直接透出 detail，方便前端提示
                try:
                    detail = json.loads(body)["error"]["message"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    detail = body or f"Gateway 返回 HTTP {resp.status_code}"
                raise ChatGatewayError(502, detail)
            async for chunk in resp.aiter_bytes():
                yield chunk
