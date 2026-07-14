#!/usr/bin/env python3
"""审计 knowledge/ 中每个接口是否已纳入 KG"""
import re, os
from neo4j import GraphDatabase

BASE = "/home/stockagent/project_space/research/experiments/web_search_base/knowledge"

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kg_route_2026"))


def get_ds_ids():
    with driver.session() as session:
        result = session.run("MATCH (ds:DataSource) RETURN ds.id as id, ds.protocol as p")
        return {r["id"]: r["p"] for r in result}


def extract_apis(text, prefix):
    apis = set()
    for m in re.finditer(rf"{prefix}\.(\w+)\s*\(", text):
        apis.add(m.group(1))
    return sorted(apis)


def extract_sina_types(text):
    """提取新浪财经接口类型"""
    types = set()
    if "hq.sinajs" in text:
        types.add("实时行情")
    if "vip.stock.finance.sina" in text:
        types.add("财务数据")
    if "money.finance.sina" in text:
        types.add("资金流向")
    if "quotes.money.163.com" in text or "quotes.sina" in text:
        types.add("K线")
    return types


def main():
    existing = get_ds_ids()
    driver.close()
    print(f"Neo4j 现有 DataSource: {len(existing)} 个\n")

    # TuShare
    with open(f"{BASE}/tushare/instruction.md") as f:
        text = f.read()
    apis = extract_apis(text, "pro")
    existing_tu = {k for k in existing if k.startswith("DS_TUSHARE_")}
    missing = []
    for api in apis:
        ds_id = f"DS_TUSHARE_{api.upper()}"
        if ds_id not in existing_tu:
            missing.append(api)
    print(f"=== TuShare: {len(apis)} APIs, {len(existing_tu)} 在KG, {len(missing)} 遗漏 ===")
    if missing:
        for a in missing:
            print(f"  pro.{a}()")

    # akshare
    with open(f"{BASE}/akshare/instruction.md") as f:
        text = f.read()
    apis = extract_apis(text, "ak")
    existing_ak = {k for k in existing if k.startswith("DS_AKSHARE_")}
    print(f"\n=== akshare: {len(apis)} APIs, {len(existing_ak)} 在KG ===")

    # levistock
    with open(f"{BASE}/levistock/instruction.md") as f:
        text = f.read()
    apis = extract_apis(text, "lk")
    existing_lk = {k for k in existing if k.startswith("DS_LEVISTOCK_")}
    print(f"\n=== levistock: {len(apis)} APIs, {len(existing_lk)} 在KG ===")
    for a in apis:
        ds_id = f"DS_LEVISTOCK_{a.upper()}"
        status = "OK" if ds_id in existing_lk else "MISS"
        print(f"  lk.{a}() -> {ds_id} [{status}]")

    # pysnowball
    with open(f"{BASE}/pysnowball/instruction.md") as f:
        text = f.read()
    apis = extract_apis(text, "ball")
    existing_xq = {k for k in existing if k.startswith("DS_XUEQIU_")}
    print(f"\n=== pysnowball: {len(apis)} APIs, {len(existing_xq)} 在KG ===")
    for a in apis:
        ds_id = f"DS_XUEQIU_{a.upper()}"
        status = "OK" if ds_id in existing_xq else "MISS"
        print(f"  ball.{a}() -> {ds_id} [{status}]")

    # sina_finance
    with open(f"{BASE}/sina_finance/instruction.md") as f:
        text = f.read()
    types = extract_sina_types(text)
    print(f"\n=== 新浪财经: 完全遗漏! 覆盖能力: {types} ===")

    # tencent
    existing_tc = {k for k in existing if k.startswith("DS_TENCENT_")}
    print(f"\n=== 腾讯财经: {len(existing_tc)} 在KG ===")


if __name__ == "__main__":
    main()
