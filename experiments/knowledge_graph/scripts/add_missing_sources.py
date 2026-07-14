#!/usr/bin/env python3
"""补齐遗漏的 DataSource + DataField + alias"""

import csv, os, json
from neo4j import GraphDatabase

DS_DIR = "/home/stockagent/project_space/research/experiments/knowledge_graph/ds_prompts"
CSV_PATH = "/home/stockagent/project_space/research/experiments/knowledge_graph/data/datafield_new_alias_520_deepseek.txt"
OUT_PATH = "/home/stockagent/project_space/research/experiments/knowledge_graph/data/datafield_new_alias_all.txt"

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "kg_route_2026"))


def add_datasource(ds_id, name, protocol, **kwargs):
    with driver.session() as session:
        result = session.run("MATCH (ds:DataSource {id: $id}) RETURN ds", id=ds_id).single()
        if result:
            print(f"  DS {ds_id} 已存在，跳过")
            return False
        session.run(
            "CREATE (ds:DataSource {id: $id, name: $name, protocol: $protocol, "
            "authority_level: $al, refresh_time: $rt, reliability_score: $rs, "
            "execution_meta: '{}', prompt_dir: $pd})",
            id=ds_id, name=name, protocol=protocol,
            al=kwargs.get("authority", "B"), rt=kwargs.get("refresh", "realtime"),
            rs=kwargs.get("reliability", 0.7), pd=f"DS_{ds_id}",
        )
        print(f"  + DS {ds_id}: {name} ({protocol})")
        return True


def write_ds_prompt(ds_id, field, table, api):
    d = os.path.join(DS_DIR, ds_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "field.md"), "w") as f:
        f.write(f"# {ds_id} 可用字段\n\n{field.strip()}\n")
    with open(os.path.join(d, "table.md"), "w") as f:
        f.write(f"# {ds_id} 表结构\n\n{table.strip()}\n")
    with open(os.path.join(d, "api.md"), "w") as f:
        f.write(f"# {ds_id} API 调用规则\n\n{api.strip()}\n")


NEW_FIELDS = []

def add_field(fid, std_name, alias, concept, ds_id, dtype="string", unit=""):
    """添加新字段定义（暂存，稍后一并写入）"""
    # 构建4级alias
    aliases = json.loads(alias) if isinstance(alias, str) else alias
    simple = aliases.get("simple", std_name)
    qualified = aliases.get("qualified", std_name)
    business_tag = aliases.get("business_tag", std_name)
    synonyms = aliases.get("synonyms", std_name)

    NEW_FIELDS.append({
        "field_id": fid,
        "standard_name": std_name,
        "concept_id": concept,
        "simple": simple,
        "qualified": qualified,
        "business_tag": business_tag,
        "synonyms": synonyms,
        "data_type": dtype,
        "unit": unit,
        "default_datasource_id": ds_id,
    })


def write_all():
    # 1. 写 DataSource 到 Neo4j
    print("\n=== 添加 DataSource ===")

    # === SINA ===
    add_datasource("DS_SINA_QUOTE", "新浪实时行情", "sina",
                   authority="B", refresh="realtime", reliability=0.75)
    add_datasource("DS_SINA_KLINE", "新浪K线数据", "sina",
                   authority="B", refresh="realtime", reliability=0.70)
    add_datasource("DS_SINA_FINANCE", "新浪财务报表", "sina",
                   authority="B", refresh="quarterly", reliability=0.75)

    # === LEVISTOCK 补齐 ===
    add_datasource("DS_LEVISTOCK_MARKET_INDEX", "levistock指数行情", "levistock",
                   authority="B", refresh="intraday", reliability=0.80)
    add_datasource("DS_LEVISTOCK_STOCK_CHANGES", "levistock异动监测", "levistock",
                   authority="B", refresh="intraday", reliability=0.75)

    # === PYSNOWBALL ===
    add_datasource("DS_XUEQIU_QUOTE", "雪球个股行情", "xueqiu",
                   authority="B", refresh="realtime", reliability=0.80)
    add_datasource("DS_XUEQIU_KLINE", "雪球K线数据", "xueqiu",
                   authority="B", refresh="daily_17:00", reliability=0.80)

    # 2. 写 ds_prompts
    print("\n=== 添加 ds_prompts ===")
    write_ds_prompt("DS_SINA_QUOTE",
        "|字段|说明|\n|:---|:---|\n|name|股票名称|\n|code|代码|\n|price|当前价|\n|pct_chg|涨跌幅%|\n|open|开盘价|\n|high|最高|\n|low|最低|\n|prev_close|昨收|\n|volume|成交量|\n|amount|成交额|\n|buy1~buy5|买一~买五价格|\n|sell1~sell5|卖一~卖五价格|\n|b1_v~b5_v|买一~买五量|\n|s1_v~s5_v|卖一~卖五量|",
        "API: http://hq.sinajs.cn/list=sh600519\n返回 GBK 编码文本",
        "```python\nimport requests\nr = requests.get('http://hq.sinajs.cn/list=sh600519')\nr.encoding = 'gbk'\n```")
    write_ds_prompt("DS_SINA_KLINE",
        "|字段|说明|\n|:---|:---|\n|date|时间|\n|open|开盘|\n|high|最高|\n|low|最低|\n|close|收盘|\n|volume|成交量|",
        "API: https://quotes.sina.com.cn/.../index.html?datalen=120",
        "```python\n# 分时K线\nscale=240 # 日线\n```")
    write_ds_prompt("DS_SINA_FINANCE",
        "三大报表HTML页面解析，含利润表/资产负债表/现金流量表详细科目",
        "HTML解析，从新浪财经页面提取表格",
        "```python\n# 从页面对应URL提取财务数据\n# 利润表、资产负债表、现金流量表各有独立URL\n```")

    # 3. 定义新字段
    print("\n=== 定义新字段 ===")
    # --- 新浪五档盘口（独有） ---
    for i in range(1, 6):
        # 买盘
        add_field(f"FIELD_SINA_BUY{i}_PRICE", f"买{i}价",
            {"simple": f"买{i}价", "qualified": f"新浪买{i}价|买盘{i}价格",
             "business_tag": f"盘口数据|买卖盘口|五档行情",
             "synonyms": f"买{i}|买盘{i}价格|申买{i}价|买方{i}报价"},
            "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "元")
        add_field(f"FIELD_SINA_BUY{i}_VOL", f"买{i}量",
            {"simple": f"买{i}量", "qualified": f"新浪买{i}量|买盘{i}数量",
             "business_tag": f"盘口数据|买卖盘口|五档行情",
             "synonyms": f"买{i}手|买盘{i}量|申买{i}量|买方{i}委托"},
            "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "手")
        # 卖盘
        add_field(f"FIELD_SINA_SELL{i}_PRICE", f"卖{i}价",
            {"simple": f"卖{i}价", "qualified": f"新浪卖{i}价|卖盘{i}价格",
             "business_tag": f"盘口数据|买卖盘口|五档行情",
             "synonyms": f"卖{i}|卖盘{i}价格|申卖{i}价|卖方{i}报价"},
            "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "元")
        add_field(f"FIELD_SINA_SELL{i}_VOL", f"卖{i}量",
            {"simple": f"卖{i}量", "qualified": f"新浪卖{i}量|卖盘{i}数量",
             "business_tag": f"盘口数据|买卖盘口|五档行情",
             "synonyms": f"卖{i}手|卖盘{i}量|申卖{i}量|卖方{i}委托"},
            "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "手")

    # --- 新浪港股行情（独有：港股PE/市值） ---
    add_field("FIELD_SINA_HK_PRICE", "港股最新价",
        {"simple": "港股最新价", "qualified": "新浪港股当前价|港股实时价",
         "business_tag": "港股行情|香港市场|港股价",
         "synonyms": "港股现价|港股实时|港股报价|港股价格"},
        "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "港元")
    add_field("FIELD_SINA_HK_PE", "港股PE",
        {"simple": "港股PE", "qualified": "新浪港股市盈率|港股PE_TTM",
         "business_tag": "港股行情|香港市场|港股估值",
         "synonyms": "港股市盈率|港股PE|香港PE|港股估值"},
        "CONCEPT_REALTIME_QUOTE", "DS_SINA_QUOTE", "float", "倍")

    # --- 雪球补齐 ---
    add_field("FIELD_XUEQIU_QUOTE_PRICE", "雪球实时价",
        {"simple": "雪球实时价", "qualified": "雪球个股当前价|雪球实时行情",
         "business_tag": "雪球行情|雪球报价|雪球数据",
         "synonyms": "雪球价|雪球实时|雪球报价|雪球现价"},
        "CONCEPT_REALTIME_QUOTE", "DS_XUEQIU_QUOTE", "float", "元")

    print(f"  共定义 {len(NEW_FIELDS)} 个新字段")

    # 4. 写入 Neo4j
    print("\n=== 写入 Neo4j DataField 节点 ===")
    with driver.session() as session:
        for f in NEW_FIELDS:
            # 检查是否已存在
            r = session.run("MATCH (f:DataField {id: $id}) RETURN f", id=f["field_id"]).single()
            if r:
                print(f"  字段 {f['field_id']} 已存在，跳过")
                continue
            session.run(
                "CREATE (f:DataField {id: $id, standard_name: $sn, "
                "data_type: $dt, unit: $u, default_datasource_id: $ds, "
                "alias: '[]', description: $desc})",
                id=f["field_id"], sn=f["standard_name"],
                dt=f["data_type"], u=f["unit"], ds=f["default_datasource_id"],
                desc=f["standard_name"],
            )
            # BELONGS_TO_CONCEPT
            session.run(
                "MATCH (f:DataField {id: $fid}) MATCH (c:IntentConcept {id: $cid}) "
                "MERGE (f)-[:BELONGS_TO_CONCEPT {relevance_score: 0.7, is_approved: true, is_auto_suggested: false}]->(c)",
                fid=f["field_id"], cid=f["concept_id"],
            )
        print(f"  写入完成")

    # 5. 追加到 alias CSV
    print("\n=== 追加 alias CSV ===")
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        existing = list(reader)
        fieldnames = reader.fieldnames

    # 检查重复 alias
    existing_aliases = set()
    for r in existing:
        existing_aliases.add(r["simple"])
        for q in r["qualified"].split("|"):
            existing_aliases.add(q.strip())

    new_rows = []
    for f in NEW_FIELDS:
        # 只取 alias CSV 需要的字段
        row = {k: f[k] for k in fieldnames if k in f}
        new_rows.append(row)

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing)
        writer.writerows(new_rows)

    print(f"\n  原文件: {len(existing)} 行")
    print(f"  新追加: {len(new_rows)} 行")
    print(f"  总计: {len(existing) + len(new_rows)} 行")
    print(f"  输出: {OUT_PATH}")

    driver.close()
    print("\n完成!")


if __name__ == "__main__":
    write_all()
