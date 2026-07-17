"""Fix gen_report.py - relax query_id validation and extract_json"""
import re

path = "/home/stockagent/project_space/research/experiments/knowledge_graph/query_agent_api/scripts/gen_report.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Fix 1: Relax query_id validation
content = content.replace(
    "re.match(r'^Q_[0-9a-f]{2,}$', qid, re.IGNORECASE)",
    "re.match(r'^Q_[0-9a-zA-Z]{2,}$', qid)"
)

# Fix 2: Improve extract_json to handle more formats
old_extract = """def extract_json(text: str) -> dict | None:
    m = re.search(r'```json\\s*\\n(.*?)```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    m = re.search(r'\\{[\\s\\S]*\\}', text)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return None"""

new_extract = """def extract_json(text: str) -> dict | None:
    # Try ```json ... ``` block
    m = re.search(r'```json\\s*\\n(.*?)```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    # Try ``` ... ``` block
    m = re.search(r'```\\s*\\n(.*?)```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except: pass
    # Try outermost {}
    m = re.search(r'\\{[\\s\\S]*\\}', text)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    return None"""

content = content.replace(old_extract, new_extract)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
