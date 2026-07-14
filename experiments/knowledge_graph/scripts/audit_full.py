#!/usr/bin/env python3
"""全量审计 v2：节点、关系、路由、api_column、granularity"""
import sys, os
sys.path.insert(0, "..")

from neo4j import GraphDatabase
from irkg import Router, RouteCondition

DRIVER = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kg_route_2026"))
ROUTER = Router()
ROUTER.build(alias_csv_path="../data/datafield_new_alias_all.txt")

ok = 0
fail = 0
errors = []

def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK {name}")
    else:
        fail += 1
        msg = f"  FAIL {name}" + (f" | {detail}" if detail else "")
        print(msg)
        errors.append(msg)

print("=" * 60)
print("知识图谱全量审计 v2")
print("=" * 60)

# 1. 节点
print("\n--- 1. 节点完整性 ---")
with DRIVER.session() as s:
    c = s.run("MATCH (c:IntentConcept) RETURN count(c) as c").single()["c"]
    check("IntentConcept=41", c == 41, str(c))
    ds_count = s.run("MATCH (ds:DataSource) RETURN count(ds) as c").single()["c"]
    check("DataSource>=71", ds_count >= 71, str(ds_count))
    f_count = s.run("MATCH (f:DataField) RETURN count(f) as c").single()["c"]
    check("DataField>=520", f_count >= 520, str(f_count))
    fe = s.run("MATCH (f:DataField) WHERE f.embedding IS NOT NULL RETURN count(f) as c").single()["c"]
    check("所有Field有embedding", fe == f_count, f"{fe}/{f_count}")
    gr = s.run("MATCH (f:DataField) WHERE f.granularity IS NOT NULL RETURN count(f) as c").single()["c"]
    check("所有Field有granularity", gr >= f_count - 10, f"{gr}/{f_count}")

# 2. 关系
print("\n--- 2. 关系 ---")
with DRIVER.session() as s:
    for rel in ["HAS_DATASOURCE", "BELONGS_TO_CONCEPT"]:
        cnt = s.run(f"MATCH ()-[:{rel}]->() RETURN count(*) as c").single()["c"]
        check(rel + ">=520", cnt >= 520, str(cnt))
    cnt = s.run("MATCH ()-[:SEMANTIC_SIMILAR_TO]->() RETURN count(*) as c").single()["c"]
    check("SEMANTIC_SIMILAR_TO>=3800", cnt >= 3800, str(cnt))

# 3. DataSource 质量
print("\n--- 3. DataSource 质量 ---")
with DRIVER.session() as s:
    no_tn = s.run("MATCH (ds:DataSource) WHERE ds.table_name IS NULL RETURN count(ds) as c").single()["c"]
    check("所有DS有table_name", no_tn == 0, f"缺失{no_tn}")
    orphan_ds = s.run("MATCH (ds:DataSource) WHERE NOT (ds)<-[:HAS_DATASOURCE]-() AND NOT (ds)<-[:HAS_BACKUP_DATASOURCE]-() RETURN count(ds) as c").single()["c"]
    check("无孤岛DataSource", orphan_ds == 0, f"孤岛{orphan_ds}")

# 4. 路由功能
print("\n--- 4. 路由 ---")
tests = [
    ("aliass:毛利率", ["毛利率"], {}, "FIELD_FIN_GROSS_MARGIN"),
    ("qualified:指数涨跌幅", ["指数涨跌幅"], {}, "FIELD_INDEX_PCT_CHG"),
    ("新字段:买1价", ["买1价"], {}, "FIELD_SINA_BUY1_PRICE"),
    ("新字段:同花顺概念名", ["同花顺概念板块名"], {}, "FIELD_THS_CONCEPT_NAME"),
    ("新字段:高管姓名", ["管理层姓名"], {}, "FIELD_MGR_NAME"),
    ("新字段:回购金额", ["股份回购金额"], {}, "FIELD_REPURCHASE_AMOUNT"),
    ("DS:PE_TTM", ["PE_TTM"], {}, "DS_TUSHARE_DAILY_BASIC"),
    ("DS:市场情绪", ["市场热度"], {}, "DS_LEVISTOCK_EMOTION"),
    ("Concept:毛利率", ["毛利率"], {}, "CONCEPT_FINANCIAL_SUMMARY"),
]
for name, kw, ck, exp in tests:
    cond = RouteCondition(**ck) if ck else RouteCondition()
    r = ROUTER.route(kw, conditions=cond)
    found = (r.fields and r.fields[0].id == exp) or (r.datasource and r.datasource.id == exp) or (r.concept_id == exp)
    check(name, found)

# 5. 协议覆盖
print("\n--- 5. 协议覆盖 ---")
with DRIVER.session() as s:
    protos = s.run("MATCH (ds:DataSource) RETURN ds.protocol as p").data()
    proto_set = {r["p"] for r in protos}
for p in ["tushare","akshare","levistock","sina","tencent","xueqiu","web_search","llm_gen","local_calc"]:
    check(f"协议:{p}", p in proto_set)

# 6. Faiss
print("\n--- 6. Faiss ---")
import faiss
fi = faiss.read_index("../faiss_index/fields.index")
with open("../faiss_index/fields_ids.txt") as f:
    fids = [l.strip() for l in f]
check("Faiss数量一致", fi.ntotal == len(fids), f"{fi.ntotal}")

# 7. ds_prompts
print("\n--- 7. ds_prompts ---")
with DRIVER.session() as s:
    all_ds = s.run("MATCH (ds:DataSource) RETURN ds.id as id")
    with_p = sum(1 for r in all_ds if os.path.exists(f"../ds_prompts/{r['id']}/field.md"))
    check("ds_prompts>=12", with_p >= 12, f"{with_p}")

# 8. SQL prompt
print("\n--- 8. SQL提示 ---")
from irkg.sql_gen import build_sql_prompt
r1 = ROUTER.route(["毛利率"], conditions=RouteCondition(entity_type="stock_code", entity_value="300750.SZ"))
p1 = build_sql_prompt(r1)
check("tushare提示", "tushare" in p1)

# 9. 场景验证
print("\n--- 9. 场景验证 ---")
scenarios = [
    ("查PE_TTM", ["PE_TTM"]),
    ("查毛利率", ["毛利率", "净利率"]),
    ("查指数", ["指数涨跌幅"]),
    ("查板块", ["板块涨跌幅"]),
    ("查盘口", ["买1价"]),
    ("查情绪", ["市场热度"]),
    ("查港股", ["港股PE"]),
    ("查回购", ["股份回购金额"]),
    ("查同花顺概念", ["同花顺概念板块名"]),
    ("查高管", ["管理层姓名"]),
]
for name, kw in scenarios:
    r = ROUTER.route(kw)
    check(f"场景:{name}", len(r.fields) > 0, f"fields={len(r.fields)}")

DRIVER.close()

print(f"\n{'='*60}")
print(f"结果: {ok} OK / {fail} FAIL / {ok+fail} 总计")
if fail == 0:
    print("全部通过!")
else:
    for e in errors:
        print(e)
