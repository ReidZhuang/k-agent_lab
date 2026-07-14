"""prompt_assembler — 同 exp02 风格，从 agent/ 目录组装 system prompt"""
import os, re

_AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent"))


def _read_md(rel_path: str) -> str:
    full = os.path.join(_AGENT_DIR, rel_path)
    if not os.path.isfile(full):
        return ""
    with open(full, "r", encoding="utf-8") as f:
        return f.read().strip()


def _list_skill_dirs() -> list[str]:
    skills_dir = os.path.join(_AGENT_DIR, "skills")
    if not os.path.isdir(skills_dir):
        return []
    return sorted(d for d in os.listdir(skills_dir)
                  if os.path.isdir(os.path.join(skills_dir, d)))


def _parse_frontmatter(text: str) -> dict:
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
    lines = ["## 可用技能"]
    for name in _list_skill_dirs():
        skill_path = os.path.join("skills", name, "SKILL.md")
        content = _read_md(skill_path)
        fm = _parse_frontmatter(content)
        desc = fm.get("description", "")
        lines.append(f"- **{name}**：{desc}")
    return "\n".join(lines)


def build_prompt(loaded_skills: set[str] | None = None) -> str:
    """组装完整的 system prompt。"""
    parts = [_read_md("SOUL.md")]

    for name in ("AGENTS.md", "PREFERENCES.md"):
        content = _read_md(name)
        if content:
            parts.append(content)

    skill_list = _format_skills_list()
    if skill_list:
        parts.append(skill_list)

    loaded = loaded_skills or set()
    for skill_name in sorted(loaded):
        skill_path = os.path.join("skills", skill_name, "SKILL.md")
        content = _read_md(skill_path)
        if content:
            body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
            if body:
                parts.append(body)

    # 附加当前日期和时间（LLM 自己不知道现在几点）
    import time
    now = time.strftime("%Y%m%d %H:%M:%S")
    today = time.strftime("%Y%m%d")
    parts.append(f"\n## 当前时间\n现在是 {now}（YYYYMMDD={today}），所有相对于今天/上午/中午/下午的查询都以此时间为准。")

    return "\n\n".join(p for p in parts if p)
