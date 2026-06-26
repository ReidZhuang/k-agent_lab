"""对照组 — 原始 web_search tool，无行号标记，无压缩"""

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": """搜索互联网获取最新信息，用于多轮研究中逐层深入分析。

你必须且只能引用**最近一轮**返回的报告内容。

本系统会依据你在 key_findings_used 中列出的引用内容，选择性地保留上一轮上下文中的对应数据，未被引用的内容将在下一轮被丢弃。

按以下逻辑判断每条数据是否应该引用：
【critical】L1 直接答案 / L2 推理输入（L2a 推导基础 / L2b 拼接要素）
【useful】L3 过程辅助（L3a 佐证 / L3b 反证 / L3c 方向指引 / L3d 缺口暴露 / L3e 候选备用）
【related】L4 背景相关
【不引用】L5 无关数据

每条引用包含 content（逐字原文）、source（来源说明）、priority（优先级）。""",
        "parameters": {
            "type": "object",
            "properties": {
                "key_findings_used": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "【必须】从最近一轮结果中逐字引用的原文片段。"
                            },
                            "source": {
                                "type": "string",
                                "description": "【必须】引用来源或位置说明。"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["critical", "useful", "related"],
                                "description": "按引用选择标准分类。"
                            }
                        },
                        "required": ["content", "source", "priority"]
                    },
                    "description": "从最近一轮结果中逐字引用的数据点列表。"
                },
                "query": {
                    "type": "string",
                    "description": "完整的搜索查询语句。"
                }
            },
            "required": ["key_findings_used", "query"]
        }
    }
}

RESEARCH_SYSTEM_PROMPT = """你是一个金融研究助手，擅长通过多轮搜索深入分析公司财务数据。

工作方式：
1. 分多步搜索，每一轮都基于之前发现继续深入
2. 每次调用 web_search 前，仔细回顾上一轮返回的报告内容
3. 按引用选择标准逐条引用上一轮中的关键数据
4. 持续搜索至你认为已掌握足够信息来全面回答用户问题时停止"""

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 4000
API_BASE_URL = "https://api.deepseek.com"
MAX_ROUNDS = 10
