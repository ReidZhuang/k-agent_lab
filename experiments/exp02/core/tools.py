"""工具定义 — 简短 description，schema 从外部 JSON 文件加载

规则和流程细节放在 agent/skills/cite-and-compress/SKILL.md 中，
在 system prompt 里注入。schema 定义放在 agent/schemas/*.json 中。
"""

import json, os

_SCHEMA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "agent", "schemas")
)


def _load_schema(name: str) -> dict:
    path = os.path.join(_SCHEMA_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取信息。详细规则见系统消息中的 cite-and-compress 技能说明。",
        "parameters": _load_schema("web_search_experiment.json"),
    },
}

# ——— 对照组（旧版）：有引用字段但无行号 ———
WEB_SEARCH_TOOL_CONTROL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取最新信息，用于多轮研究中逐层深入分析。",
        "parameters": _load_schema("web_search_control.json"),
    },
}

# ——— 对照组（纯版）：无任何引用字段，仅 query ———
WEB_SEARCH_TOOL_PLAIN = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取最新信息。",
        "parameters": _load_schema("web_search_plain.json"),
    },
}
