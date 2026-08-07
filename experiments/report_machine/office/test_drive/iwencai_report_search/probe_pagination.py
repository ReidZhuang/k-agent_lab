#!/usr/bin/env python3
"""探查接口分页能力：尝试在 body 里追加 offset/page/start 等参数，看能否翻页取全量结果。"""

import json
import os
import re
import secrets
import urllib.error
import urllib.request


def load_api_key() -> str:
    key = os.getenv("IWENCAI_API_KEY", "").strip()
    if key:
        return key
    for rc in ("~/.bashrc", "~/.profile"):
        p = os.path.expanduser(rc)
        if os.path.exists(p):
            m = re.search(r"export\s+IWENCAI_API_KEY='([^']+)'", open(p, encoding="utf-8").read())
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def call(body: dict):
    req = urllib.request.Request(
        "https://openapi.iwencai.com/v1/comprehensive/search",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + load_api_key(),
            "X-Claw-Skill-Id": "report-search",
            "X-Claw-Skill-Version": "1.0.0",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    candidates = [
        {},
        {"offset": 3},
        {"page": 2},
        {"start": 3},
        {"from": 3, "to": 6},
        {"page_num": 2, "page_size": 3},
    ]
    for extra in candidates:
        body = {"query": "广生堂 研报", "channels": ["report"], "app_id": "AIME_SKILL", "size": 50}
        body.update(extra)
        status, resp = call(body)
        d = resp.get("data", [])
        uid_date = (d[0].get("uid"), d[0].get("publish_date")) if d else ("-", "-")
        print(f"extra={extra} -> status={status} total={resp.get('total')} 返回{len(d)}条 首条={uid_date}")


if __name__ == "__main__":
    main()
