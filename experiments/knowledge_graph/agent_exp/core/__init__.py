"""prompt_assembler — 从 agent_xxx/ 目录组装 system prompt"""
import os, re

_AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent_router"))
_DEFAULT_AGENT_DIR = _AGENT_DIR


def _read_info(agent_dir: str, rel_path: str) -> str:
    full = os.path.join(agent_dir, rel_path)
    if not os.path.isfile(full):
        return ""
    with open(full, "r", encoding="utf-8") as f:
        return f.read().strip()


def _list_skill_dirs(agent_dir: str) -> list[str]:
    skills_dir = os.path.join(agent_dir, "skills")
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


def _format_skills_list(agent_dir: str) -> str:
    lines = ["## 可用技能"]
    for name in _list_skill_dirs(agent_dir):
        skill_path = os.path.join("skills", name, "SKILL.md")
        content = _read_info(agent_dir, skill_path)
        fm = _parse_frontmatter(content)
        desc = fm.get("description", "")
        lines.append(f"- **{name}**：{desc}")
    return "\n".join(lines)


def build_prompt(loaded_skills: set[str] | None = None,
                 agent_dir: str | None = None) -> str:
    """组装完整的 system prompt。

    Args:
        loaded_skills: 要加载的技能名集合
        agent_dir: agent 目录路径，默认为 agent_router/
    """
    if agent_dir is None:
        agent_dir = _DEFAULT_AGENT_DIR

    parts = [_read_info(agent_dir, "SOUL.md")]

    for name in ("AGENTS.md", "PREFERENCES.md"):
        content = _read_info(agent_dir, name)
        if content:
            parts.append(content)

    loaded = loaded_skills or set()
    for skill_name in sorted(loaded):
        skill_path = os.path.join("skills", skill_name, "SKILL.md")
        content = _read_info(agent_dir, skill_path)
        if content:
            body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
            if body:
                parts.append(body)

    # 注入当前时间 — 用于 LLM 解析"今天/上午/下午"等相对时间
    import time
    now = time.strftime("%Y%m%d %H:%M:%S")
    parts.append(f"\n## 当前时间（用于解析'今天/上午/下午/昨日'等相对时间）\n{now}")

    return "\n\n".join(p for p in parts if p)
