"""prompt_assembler — 从 agent_xxx/ 目录组装 system prompt"""
import os, re

_AGENTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def build_prompt(agent_name: str, loaded_skills: set[str] | None = None) -> str:
    """组装 agent 的完整 system prompt。

    Args:
        agent_name: agent 目录名，如 'agent_guide', 'agent_router', 'agent_coder'
        loaded_skills: 要加载的技能名集合
    """
    agent_dir = os.path.join(_AGENTS_DIR, agent_name)
    if not os.path.isdir(agent_dir):
        return f"错误：agent 目录 {agent_dir} 不存在"

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

    # 注入当前时间
    import time
    now = time.strftime("%Y%m%d %H:%M:%S")
    parts.append(f"\n## 当前时间（用于解析'今天/上午/下午/昨日'等相对时间）\n{now}")

    return "\n\n".join(p for p in parts if p)
