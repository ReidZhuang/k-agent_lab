"""执行编排层：路由→LLM→执行，失败则降级到备用数据源"""
import sys
import requests
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from irkg import Router, RouteCondition
from irkg.sql_gen import build_sql_prompt, parse_llm_output
from executor import execute_code

OLLAMA = "http://localhost:11434/api/generate"
MODEL = "glm4:9b-chat-q3_K_M"


def _llm(prompt, n=1024):
    r = requests.post(OLLAMA, json={
        "model": MODEL, "prompt": prompt,
        "stream": False, "temperature": 0.1, "num_predict": n,
    }, timeout=180)
    return r.json().get("response", "")


def run(keywords, intent="fact", conditions=None, router=None):
    if router is None:
        router = Router()
        router.build(alias_csv_path=str(ROOT / "data/datafield_new_alias_all.txt"))

    r = router.route(keywords, intent_type=intent, conditions=conditions)
    if not r.fields:
        return {"success": False, "output": "", "error": "路由未命中", "used_backup": False}

    f0 = r.fields[0]
    code = parse_llm_output(_llm(build_sql_prompt(r)))
    ex = execute_code(code)
    if ex["success"]:
        return {"success": True, "output": ex["output"], "error": "", "used_backup": False}

    if not f0.has_backup:
        return {"success": False, "output": "", "error": ex.get("error", "失败且无备用"),
                "used_backup": False}

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kg_route_2026"))
    with driver.session() as s:
        backups = s.run(
            "MATCH (f:DataField {id: $fid})-[r:HAS_BACKUP_DATASOURCE]->(ds:DataSource) "
            "RETURN ds.id as did, ds.name as dn, ds.protocol as proto, ds.prompt_dir as pd, "
            "r.api_column as col, r.priority as pri ORDER BY r.priority",
            fid=f0.id
        ).data()
    driver.close()

    for bk in backups:
        f0.api_column = bk["col"]
        r.datasource = type("DS", (), {
            "id": bk["did"], "name": bk["dn"],
            "protocol": bk["proto"],
            "prompt_dir": bk.get("pd", "") or bk["did"]
        })()
        code2 = parse_llm_output(_llm(build_sql_prompt(r)))
        ex2 = execute_code(code2)
        if ex2["success"]:
            return {"success": True, "output": ex2["output"], "error": "",
                    "used_backup": True, "backup_ds": bk["did"]}
        if "TOKEN" in ex2.get("error", "").upper():
            break

    return {"success": False, "output": "", "error": "主备均失败", "used_backup": True}
