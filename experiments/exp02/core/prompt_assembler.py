"""OpenClaw 风格的动态 prompt 组装器

从 agent/ 目录读取 .md 文件，动态组装 system prompt。

组装逻辑（full mode）：
  1. SOUL.md                     ← 始终
  2. AGENTS.md                   ← 始终
  3. PREFERENCES.md              ← 始终
  4. 可用技能列表                 ← 始终（从 skills/*/SKILL.md frontmatter 生成）
  5. 已激活技能的完整 SKILL.md    ← 仅 skill_loaded 时

文件位置约定（相对于本文件的 ../../../agent/）：
  agent/SOUL.md
  agent/AGENTS.md
  agent/PREFERENCES.md
  agent/skills/<name>/SKILL.md
"""

import os, re

_AGENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "agent")
)


def _read_md(rel_path: str) -> str:
    """读取 agent/ 下的 .md 文件，不存在则返回空字符串。"""
    full = os.path.join(_AGENT_DIR, rel_path)
    if not os.path.isfile(full):
        return ""
    with open(full, "r", encoding="utf-8") as f:
        return f.read().strip()


def _list_skill_dirs() -> list[str]:
    """扫描 agent/skills/ 下的所有子目录名。"""
    skills_dir = os.path.join(_AGENT_DIR, "skills")
    if not os.path.isdir(skills_dir):
        return []
    return sorted([
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    ])


def _parse_frontmatter(text: str) -> dict:
    """简单解析 YAML frontmatter（只取 name 和 description）。"""
    result = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                result["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                result["description"] = line.split(":", 1)[1].strip()
    return result


def _format_skills_list() -> str:
    """生成可用技能列表块（不含已加载技能的完整规则）。"""
    lines = ["## 可用技能"]
    for name in _list_skill_dirs():
        skill_path = os.path.join("skills", name, "SKILL.md")
        content = _read_md(skill_path)
        fm = _parse_frontmatter(content)
        desc = fm.get("description", "")
        lines.append(f"- **{name}**：{desc}")
    return "\n".join(lines)


def build_prompt(mode: str = "full", loaded_skills: set | None = None) -> str:
    """组装 system prompt。

    Args:
        mode: "full" | "control" | "minimal"
            full    → SOUL.md + AGENTS.md + PREFERENCES.md + 技能列表 + (已加载的技能正文)
            control → SOUL.md + AGENTS.md（无 PREFERENCES.md，无技能列表）
            minimal → 仅 SOUL.md
        loaded_skills: 已激活的技能名集合。若有值，对应技能的 SKILL.md
                       正文（不含 frontmatter）会注入到 prompt 末尾。

    Returns:
        组装后的 system prompt 字符串
    """
    parts = [_read_md("SOUL.md")]

    if mode == "full":
        for name in ("AGENTS.md", "PREFERENCES.md"):
            content = _read_md(name)
            if content:
                parts.append(content)

        # 可用技能列表（Round 1 就展示）
        skill_list = _format_skills_list()
        if skill_list:
            parts.append(skill_list)

        # 已激活技能的完整规则
        loaded = loaded_skills or set()
        for skill_name in sorted(loaded):
            skill_path = os.path.join("skills", skill_name, "SKILL.md")
            content = _read_md(skill_path)
            if content:
                # 去掉 frontmatter，仅保留正文
                body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
                if body:
                    parts.append(body)

    elif mode == "control":
        agents_md = _read_md("AGENTS.md")
        if agents_md:
            parts.append(agents_md)

    return "\n\n".join(p for p in parts if p)
