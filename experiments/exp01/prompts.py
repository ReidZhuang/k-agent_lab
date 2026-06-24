"""实验用共享常量

v1.1 — 重写了 tool description 的引用规则：
  - 三层五级分类（critical/useful/related）
  - 字符偏移标注（chars X-Y）
  - 移除 gaps_identified 和 search_strategy
  - 新增引用目的说明（告知压缩机制）
"""

WEB_SEARCH_TOOL_WITH_REASONING = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": """搜索互联网获取最新信息，用于多轮研究中逐层深入分析。

━━━ 引用范围 ━━━

你必须且只能引用**最近一轮**返回的报告内容。
禁止引用更早轮次的数据——更早轮次的信息应当已经融入你的推理中，无需在此重复引用。

━━━ 引用目的 ━━━

本系统会依据你在 key_findings_used 中列出的引用内容和优先级，选择性地保留上一轮上下文中的对应数据，未被引用的内容将在下一轮被丢弃。
换言之：如果你不引用某条数据，它在后续轮次中将不再可用；如果你引用不准确或不完整，系统可能遗漏关键信息。
准确、完整的引用能帮助你在更充分的上下文中进行多轮分析，得出更完备的回答。

━━━ 引用选择标准 ━━━

按以下逻辑判断每条数据是否应该引用（从最直接到最间接）：

【critical 级】—— 必须引用，构成最终答案的核心素材
  L1 直接答案：该数据直接回答用户原始问题中的某一个子问题。
  L2 推理输入：该数据是得出答案所需的输入项。
    L2a 推导基础：将本条数据与已有知识或其他数据进行逻辑推理或数学运算后，即可得出结论。
    L2b 拼接要素：需要与其他数据合并后，才能构成完整的答案。

【useful 级】—— 建议引用，对搜索过程或判断有显著帮助
  L3 过程辅助：该数据不直接构成答案，但能帮助搜索或判断过程更准确。
    L3a 佐证：支持或确认已有结论，增强结论的可信度。
    L3b 反证：与已有假设或初步结论矛盾，提示需要修正判断方向。
    L3c 方向指引：提示下一步应搜索的维度或方向。
    L3d 缺口暴露：表明某信息不存在，或当前数据不足以回答某个子问题。
    L3e 候选备用：在未找到精确回答时，可作为替代参考或兜底数据。

【related 级】—— 可选引用，保留后可丰富回答的完整性和可读性
  L4 背景相关：与话题相关，但不参与直接推理也不影响搜索方向。可用于丰富回答的背景信息。

【不引用】
  L5 无关数据：与用户问题完全无关。

━━━ 引用标注格式 ━━━

每条引用必须包含以下三个字段：

1. content —— 【必须】逐字原文片段
   与上一轮 tool result 中的文字完全一致（包括标点和空格），用于系统匹配原文。

2. source —— 【必须】精确位置标注
   格式：chars [起始字符] - [结束字符]
   表示该引用片段在完整 tool result（string）中的字符偏移范围（0-indexed，左闭右开）。
   示例：chars 89-101 表示从第 89 个字符到第 101 个字符（不含第 101 个字符）。

3. priority —— 【必须】优先级
   critical / useful / related，按上方的【引用选择标准】确定。

━━━ 示例 ━━━

假设上一轮 tool result 包含：
"宁德时代2024年财务摘要
营业收入：4237.0亿（同比17.0%）
毛利率：26.27%"

正确的引用：
  content: "营业收入：4237.0亿（同比17.0%）"
  source: "chars 15-36"
  priority: "critical\"""",
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
                                "description": "【必须】从最近一轮结果中逐字引用的原文片段，必须与原文完全一致（含标点和空格）。"
                            },
                            "source": {
                                "type": "string",
                                "description": "【必须】精确字符偏移位置，格式 chars [起始字符]-[结束字符]，如 chars 89-101。"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["critical", "useful", "related"],
                                "description": "按 tool description 中的【引用选择标准】分类。critical=L1+L2, useful=L3, related=L4。"
                            }
                        },
                        "required": ["content", "source", "priority"]
                    },
                    "description": "【必须】从最近一轮报告内容中逐字引用的数据点列表。"
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
3. 按【引用选择标准】（critical/useful/related）逐条引用上一轮中的关键数据
   准确标注字符偏移位置和优先级
4. 持续搜索至你认为已掌握足够信息来全面回答用户问题时停止"""

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 4000
API_BASE_URL = "https://api.deepseek.com"
MAX_ROUNDS = 10
