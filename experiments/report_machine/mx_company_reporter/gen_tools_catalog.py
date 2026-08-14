#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 mx-ds-mcp 的 tools/list 生成完整工具说明书 Markdown"""
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MX_MCP_TOOLS_CATALOG.md")

with open(os.path.expanduser("~/.openclaw/openclaw.json"), encoding="utf-8") as f:
    KEY = json.load(f)["mcp"]["servers"]["mx-ds-mcp"]["headers"]["em_api_key"]

body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
req = urllib.request.Request(
    "https://mxapi.eastmoney.com/mxds/mcp", data=body,
    headers={"em_api_key": KEY, "Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"})
with urllib.request.urlopen(req, timeout=30) as resp:
    tools = json.load(resp)["result"]["tools"]

lines = [
    "# 妙想 MCP 工具说明书（mx-ds-mcp）",
    "",
    f"> 自动生成于 tools/list（{len(tools)} 个工具），生成时间见文件时间戳。",
    "> 数据源：东方财富数据库。所有工具均为**自然语言查询**（参数仅 `query`），",
    "> 单次请求最多支持 500 只标的，可多次请求。",
    "",
    "## 工具列表",
    "",
]
for i, t in enumerate(tools, 1):
    desc = (t.get("description") or "").strip()
    schema = t.get("inputSchema", {})
    props = list(schema.get("properties", {}).keys())
    required = schema.get("required", [])
    lines += [
        f"### {i}. `{t.get('name')}`",
        "",
        f"**参数**: `{', '.join(props)}`（必填: {', '.join(required) or '无'}）",
        "",
        "**描述**:",
        "",
    ]
    for para in desc.split("\n"):
        para = para.strip()
        if para:
            lines.append(f"> {para}")
    lines.append("")
    lines.append("---")
    lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("已生成:", OUT)
