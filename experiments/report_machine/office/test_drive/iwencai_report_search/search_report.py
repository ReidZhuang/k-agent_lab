#!/usr/bin/env python3
"""直接调用 iwencai OpenAPI 研报搜索接口（report-search skill 的底层接口）。

契约（与同花顺问财 SkillHub 的 report-search 技能一致）:
- POST https://openapi.iwencai.com/v1/comprehensive/search
- Body: {"query": <query>, "channels": ["report"], "app_id": "AIME_SKILL", "size": N}
- Auth: Authorization: Bearer <IWENCAI_API_KEY>

用法:
    python search_report.py "贵州茅台 研报" --size 10
    python search_report.py "贵州茅台 研报" --size 5 --output raw.json
"""

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKILL_ID = "report-search"
SKILL_VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://openapi.iwencai.com"
DEFAULT_ENDPOINT = "/v1/comprehensive/search"
DEFAULT_TIMEOUT = 30
DEFAULT_SIZE = 10


def load_api_key() -> str:
    """优先取环境变量；未设置时从 ~/.bashrc 提取（bashrc 有非交互 shell 提前 return 保护，
    source 不生效，key 实际写死在文件里）。"""
    key = os.getenv("IWENCAI_API_KEY", "").strip()
    if key:
        return key
    for rc in (Path.home() / ".bashrc", Path.home() / ".profile"):
        if rc.exists():
            m = re.search(r"export\s+IWENCAI_API_KEY='([^']+)'", rc.read_text(encoding="utf-8"))
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def build_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
        "X-Claw-Call-Type": "normal",
        "X-Claw-Skill-Id": SKILL_ID,
        "X-Claw-Skill-Version": SKILL_VERSION,
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


def build_body(query: str, size: int) -> dict:
    return {
        "query": query,
        "channels": ["report"],
        "app_id": "AIME_SKILL",
        "size": size,
    }


def call_api(url: str, query: str, size: int, api_key: str, timeout: int):
    body = json.dumps(build_body(query, size), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers=build_headers(api_key), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="iwencai 研报搜索接口")
    parser.add_argument("query", help="自然语言研报搜索查询，如 '贵州茅台 研报'")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="请求结果条数，默认 10")
    parser.add_argument("--base-url", default=os.getenv("IWENCAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--endpoint", default=os.getenv("IWENCAI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP 超时秒数")
    parser.add_argument("--output", help="将原始响应体原样写入文件（替代 stdout）")
    args = parser.parse_args()

    api_key = load_api_key()
    if not api_key:
        print("IWENCAI_API_KEY 未配置：请在 ~/.bashrc 设置 export IWENCAI_API_KEY='<key>'", file=sys.stderr)
        return 2

    url = args.base_url.rstrip("/") + "/" + args.endpoint.lstrip("/")
    try:
        status_code, raw_body = call_api(url, args.query, args.size, api_key, args.timeout)
    except urllib.error.URLError as exc:
        print("Network error: " + str(exc), file=sys.stderr)
        return 1
    except TimeoutError as exc:
        print("Timeout: " + str(exc), file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_bytes(raw_body)
        print(f"响应已写入 {args.output}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(raw_body)
        if raw_body and not raw_body.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")

    if status_code in (401, 403):
        print("鉴权失败 (401/403)，请检查 API key", file=sys.stderr)
    return 0 if 200 <= status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
