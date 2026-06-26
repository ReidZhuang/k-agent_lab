"""行号标记系统

行号标记是"系统层"的工作——在注入 tool result 之前自动完成。
LLM 只需看到带行号的文本，不需要理解标记机制的工作原理。

职责：
  inject_line_tags()           → 给文本加 N~ 行号，返回 (tagged, line_map)
  parse_line_ref()             → 解析 "4-6,8,11-13" → [4,5,6,8,11,12,13]
  reconstruct_content()        → 根据行号和 line_map 还原原文
  format_compressed_citation() → 将引用结果压缩为 markdown
"""

import re


def inject_line_tags(raw_text: str):
    """给原始文本添加 N~ 行号标记。

    规则：
    - 原文天然断行的 → 逐行打标
    - 单行超过 100 个字符 → 在第 100 字符处强制截断，续行接续编号

    Args:
        raw_text: 原始文本

    Returns:
        (tagged_text, line_map)
        tagged_text: 带行号标记的文本
        line_map: dict[int, str] 行号→原始行内容（不含标记）
    """
    if not raw_text:
        return "", {}

    raw_lines = raw_text.split("\n")
    tagged_lines = []
    line_map: dict[int, str] = {}
    line_no = 0

    for raw_line in raw_lines:
        remaining = raw_line
        while len(remaining) > 100:
            part = remaining[:100]
            tagged_lines.append(f"{line_no}~ {part}")
            line_map[line_no] = part
            remaining = remaining[100:]
            line_no += 1

        tagged_lines.append(f"{line_no}~ {remaining}")
        line_map[line_no] = remaining
        line_no += 1

    tagged_body = "\n".join(tagged_lines)
    return (
        f"<<<CITATION_BLOCK>>>\n{tagged_body}\n<<<END_CITATION_BLOCK>>>",
        line_map,
    )


def parse_line_ref(lines_str: str) -> list[int]:
    """解析行号引用字符串，返回排序去重后的行号列表。

    "4-6,8,11-13" → [4, 5, 6, 8, 11, 12, 13]
    """
    if not lines_str:
        return []
    result = []
    for part in lines_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                result.extend(range(int(a.strip()), int(b.strip()) + 1))
            except (ValueError, TypeError):
                continue
        else:
            try:
                result.append(int(part))
            except (ValueError, TypeError):
                continue
    return sorted(set(result))


def reconstruct_content(lines_str: str, line_map: dict[int, str]) -> str:
    """根据行号引用和 line_map 还原原文内容。"""
    nums = parse_line_ref(lines_str)
    segs = []
    for n in nums:
        if n in line_map:
            segs.append(line_map[n])
    return "\n".join(segs)


def _line_data_in_context(line: str, context: str) -> bool:
    """检查本行的数值数据是否已被 context 覆盖。

    提取行中所有数值（含百分比），逐项检查 context 中是否包含。
    如果所有数值都在 context 中出现 → 行可省略。
    如果行中没有数值（如标题行）→ 保留。
    """
    if not line or not context:
        return False

    values = re.findall(r"\d+\.?\d*%?", line)
    if not values:
        return False

    for v in values:
        if v in context:
            continue
        v_stripped = v.rstrip("%")
        if v_stripped != v and v_stripped in context:
            continue
        if f"+{v}" in context or f"-{v}" in context:
            continue
        if v.endswith(".0") and v[:-2] in context:
            continue
        return False

    return True


def _is_null_citation(f: dict) -> bool:
    """判断一条引用是否为 null 占位（表示无引用）。"""
    content = f.get("content")
    return content is None


def format_compressed_citation(findings: list[dict], line_map: dict[int, str]) -> str:
    """将引用结果压缩为 markdown 格式。

    每条引用输出：
    ### 重要性: <priority>
    ### summary: <context>
    ### content:
    （未包含在 summary 中的原文行）

    优化：如果某行数据已出现在 context 中，则省略该行。
    特殊规则：content 为 null 的引用被视为"无引用占位"，跳过不处理。
    """
    parts = []
    for f in findings:
        # 跳过 null 占位引用
        if _is_null_citation(f):
            continue

        line_ref = f.get("content", "")
        priority = f.get("priority", "")
        context = f.get("context", "")
        cited_text = reconstruct_content(line_ref, line_map)

        kept_lines = []
        for cl in cited_text.split("\n"):
            if not _line_data_in_context(cl, context):
                kept_lines.append(cl)

        kept_text = "\n".join(kept_lines).strip()
        if kept_text:
            block = (
                f"### 重要性: {priority}\n"
                f"### summary: {context}\n"
                f"### content:\n{kept_text}"
            )
        else:
            block = f"### 重要性: {priority}\n### summary: {context}"
        parts.append(block)
    return "\n\n".join(parts)
