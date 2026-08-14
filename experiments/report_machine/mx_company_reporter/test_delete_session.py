#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端测试：创建临时会话 -> 删除 -> 验证"""
import json
import os
import urllib.request

from openclaw_rpc import delete_session

BASE = "http://127.0.0.1:18789"
AGENT_STORE = os.path.expanduser("~/.openclaw/agents/mx-agent/sessions/sessions.json")


def read_token():
    with open(os.path.expanduser("~/.openclaw/openclaw.json"), encoding="utf-8") as f:
        return json.load(f)["gateway"]["auth"]["token"]


def chat(key: str, text: str) -> str:
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps({
            "model": "openclaw/mx-agent",
            "messages": [{"role": "user", "content": text}],
        }).encode(),
        headers={
            "Authorization": f"Bearer {read_token()}",
            "Content-Type": "application/json",
            "x-openclaw-session-key": key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def store_keys():
    with open(AGENT_STORE, encoding="utf-8") as f:
        return list(json.load(f).keys())


if __name__ == "__main__":
    key = "report-del-test-2"
    before = store_keys()
    print("1) 调用 API 创建临时会话...")
    reply = chat(key, "只回复两个字：正常")
    print("   回复:", reply[:40])
    after = store_keys()
    print("2) store 中出现的新会话:", [k for k in after if k not in before])

    # 尝试删除：HTTP 端点创建的会话行落在默认 agent(main) 的 store
    for candidate in (f"agent:main:{key}", key):
        try:
            r = delete_session(candidate)
            print(f"3) delete_session({candidate!r}) -> ok, result={r}")
            break
        except Exception as e:
            print(f"   delete_session({candidate!r}) 失败: {e}")

    import glob
    final = store_keys()
    gone = [k for k in after if k not in final]
    print("4) 已从 store 移除:", gone)
    leftover_traj = glob.glob(os.path.expanduser("~/.openclaw/agents/*/sessions/*trajectory*"))
    print("5) 残留轨迹文件:", [os.path.basename(p) for p in leftover_traj if '3ce32f15' in p or 'report' in p] or "无")
    print("6) 残留检查:", "通过 ✅" if not [k for k in final if "report-del-test-2" in k] else "仍有残留 ❌")
