#!/usr/bin/env python3
"""
增量导入：新浪财务报表三大报表 → Neo4j

按 data_source_onboarding_playbook.md 标准流程执行：
  Step 4: 写入 DataSource 节点
  Step 6: 创建 DataField 节点
  Step 7: 写入 alias CSV
  Step 8: 生成 Embedding

不会删除或修改现有数据（使用 MERGE 而非 DETACH DELETE）。
"""
import json, csv, sys, os
from neo4j import GraphDatabase
from pathlib import Path

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
ALIAS_FILE = DATA_DIR / "datafield_new_alias_all.txt"

# ===== 定义 3 个新数据源 =====

DATASOURCES = [
    {
        "id": "DS_SINA_INCOME",
        "name": "新浪利润表",
        "protocol": "sina",
        "authority_level": "B",
        "refresh_time": "quarterly",
        "reliability_score": 0.75,
        "table_name": "vFD_ProfitStatement",
        "prompt_dir": "DS_SINA_INCOME",
        "execution_meta": "{}",
    },
    {
        "id": "DS_SINA_BALANCE",
        "name": "新浪资产负债表",
        "protocol": "sina",
        "authority_level": "B",
        "refresh_time": "quarterly",
        "reliability_score": 0.75,
        "table_name": "vFD_BalanceSheet",
        "prompt_dir": "DS_SINA_BALANCE",
        "execution_meta": "{}",
    },
    {
        "id": "DS_SINA_CASHFLOW",
        "name": "新浪现金流量表",
        "protocol": "sina",
        "authority_level": "B",
        "refresh_time": "quarterly",
        "reliability_score": 0.75,
        "table_name": "vFD_CashFlow",
        "prompt_dir": "DS_SINA_CASHFLOW",
        "execution_meta": "{}",
    },
]

# ===== 定义字段 =====
# id, standard_name, api_column, data_type, unit, description, concept_id, simple_alias, qualified_alias, synonyms

FIELDS = [
    # ── 利润表 (DS_SINA_INCOME) ──
    ("FIELD_INC_REVENUE", "营业收入", "revenue", "float", "万元", "主营业务收入(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "营业收入", "利润表营业收入|新浪营业收入", "营收|主营业务收入|销售收入|营业总额"),
    ("FIELD_INC_COST", "营业成本", "cost", "float", "万元", "主营业务成本(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "营业成本", "利润表营业成本|新浪营业成本", "成本|主营业务成本|销售成本|营业支出"),
    ("FIELD_INC_SALES_EXP", "销售费用", "sales_exp", "float", "万元", "销售费用(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "销售费用", "利润表销售费用|新浪销售费用", "销售支出|推广费用|市场费用|营销费用"),
    ("FIELD_INC_ADMIN_EXP", "管理费用", "admin_exp", "float", "万元", "管理费用(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "管理费用", "利润表管理费用|新浪管理费用", "管理支出|行政费用|办公费用"),
    ("FIELD_INC_FIN_EXP", "财务费用", "fin_exp", "float", "万元", "财务费用(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "财务费用", "利润表财务费用|新浪财务费用", "利息支出|融资成本|资金成本"),
    ("FIELD_INC_RD_EXP", "研发费用", "rd_exp", "float", "万元", "研发费用(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "研发费用", "利润表研发费用|新浪研发费用", "研发支出|研究费用|开发支出|技术投入"),
    ("FIELD_INC_INV_INCOME", "投资收益", "inv_income", "float", "万元", "投资收益(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "投资收益", "利润表投资收益|新浪投资收益", "投资回报|权益法收益|投资收入"),
    ("FIELD_INC_OPER_PROFIT", "营业利润", "operating_profit", "float", "万元", "营业利润(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "营业利润", "利润表营业利润|新浪营业利润", "经营利润|息税前利润|EBIT"),
    ("FIELD_INC_TOTAL_PROFIT", "利润总额", "total_profit", "float", "万元", "利润总额(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "利润总额", "利润表利润总额|新浪利润总额", "税前利润|会计利润|税前收益|EBT"),
    ("FIELD_INC_TAX_EXP", "所得税费用", "tax_exp", "float", "万元", "所得税费用(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "所得税费用", "利润表所得税|新浪所得税", "所得税|企业所得税|当期所得税"),
    ("FIELD_INC_NET_PROFIT", "净利润", "net_profit", "float", "万元", "净利润(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "净利润", "利润表净利润|新浪净利润", "净收入|税后利润|盈利|净收益"),
    ("FIELD_INC_NET_PROFIT_PARENT", "归母净利润", "net_profit_parent", "float", "万元", "归属于母公司所有者的净利润(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "归母净利润", "利润表归母净利润|新浪归母净利润", "归属母公司净利润|母公司净利润|合并净利润"),
    ("FIELD_INC_EPS_BASIC", "基本每股收益", "eps_basic", "float", "元/股", "基本每股收益(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "基本每股收益", "利润表基本每股收益|新浪基本每股收益", "每股盈利|基本EPS|每股收益"),
    ("FIELD_INC_EPS_DILUTED", "稀释每股收益", "eps_diluted", "float", "元/股", "稀释每股收益(利润表)", "CONCEPT_FINANCIAL_STATEMENTS", "稀释每股收益", "利润表稀释每股收益|新浪稀释每股收益", "稀释EPS|摊薄每股收益|全面摊薄"),

    # ── 资产负债表 (DS_SINA_BALANCE) ──
    ("FIELD_BS_CASH", "货币资金", "cash", "float", "万元", "货币资金(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "货币资金", "资产负债表货币资金|新浪货币资金", "现金|银行存款|现金及等价物|资金余额"),
    ("FIELD_BS_TRADING_ASSETS", "交易性金融资产", "trading_assets", "float", "万元", "交易性金融资产(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "交易性金融资产", "资产负债表交易性金融资产|新浪交易性金融资产", "短期投资|金融资产|交易性资产"),
    ("FIELD_BS_ACCOUNTS_RCV", "应收账款", "accounts_receivable", "float", "万元", "应收账款(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "应收账款", "资产负债表应收账款|新浪应收账款", "应收款|应收帐款|客户欠款"),
    ("FIELD_BS_NOTES_RCV", "应收票据", "notes_receivable", "float", "万元", "应收票据(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "应收票据", "资产负债表应收票据|新浪应收票据", "应收票据|商业承兑汇票|银行承兑汇票"),
    ("FIELD_BS_PREPAYMENTS", "预付款项", "prepayments", "float", "万元", "预付款项(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "预付款项", "资产负债表预付款项|新浪预付款项", "预付账款|预付费用|预缴款项"),
    ("FIELD_BS_INVENTORY", "存货", "inventory", "float", "万元", "存货(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "存货", "资产负债表存货|新浪存货", "库存|产成品|在产品|原材料"),
    ("FIELD_BS_CURRENT_ASSETS", "流动资产合计", "current_assets", "float", "万元", "流动资产合计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "流动资产合计", "资产负债表流动资产|新浪流动资产", "流动资产|流动资本|运营资金"),
    ("FIELD_BS_LT_EQUITY_INV", "长期股权投资", "long_term_equity_inv", "float", "万元", "长期股权投资(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "长期股权投资", "资产负债表长期股权投资|新浪长期股权投资", "长期投资|权益法投资|联营投资"),
    ("FIELD_BS_FIXED_ASSETS", "固定资产", "fixed_assets", "float", "万元", "固定资产净额(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "固定资产", "资产负债表固定资产|新浪固定资产", "固定资产净值|厂房设备|PP&E|固定资产原值"),
    ("FIELD_BS_INTANGIBLE_ASSETS", "无形资产", "intangible_assets", "float", "万元", "无形资产(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "无形资产", "资产负债表无形资产|新浪无形资产", "知识产权|专利权|商标权|软件"),
    ("FIELD_BS_GOODWILL", "商誉", "goodwill", "float", "万元", "商誉(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "商誉", "资产负债表商誉|新浪商誉", "并购商誉| goodwill|合并溢价"),
    ("FIELD_BS_TOTAL_ASSETS", "资产总计", "total_assets", "float", "万元", "资产总计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "资产总计", "资产负债表资产总计|新浪资产总计", "总资产|资产总额|全部资产"),
    ("FIELD_BS_SHORT_TERM_LOANS", "短期借款", "short_term_loans", "float", "万元", "短期借款(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "短期借款", "资产负债表短期借款|新浪短期借款", "短期贷款|一年内到期借款|银行短期借款"),
    ("FIELD_BS_ACCOUNTS_PAY", "应付账款", "accounts_payable", "float", "万元", "应付账款(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "应付账款", "资产负债表应付账款|新浪应付账款", "应付款|应付帐款|供应商欠款"),
    ("FIELD_BS_NOTES_PAY", "应付票据", "notes_payable", "float", "万元", "应付票据(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "应付票据", "资产负债表应付票据|新浪应付票据", "应付票据|应付商业票据"),
    ("FIELD_BS_TAXES_PAY", "应交税费", "taxes_payable", "float", "万元", "应交税费(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "应交税费", "资产负债表应交税费|新浪应交税费", "应交税金|应缴税款|欠缴税费"),
    ("FIELD_BS_CURRENT_LIAB", "流动负债合计", "current_liabilities", "float", "万元", "流动负债合计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "流动负债合计", "资产负债表流动负债|新浪流动负债", "流动负债|短期负债|一年内到期负债"),
    ("FIELD_BS_LONG_TERM_LOANS", "长期借款", "long_term_loans", "float", "万元", "长期借款(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "长期借款", "资产负债表长期借款|新浪长期借款", "长期贷款|长期债务|长期融资"),
    ("FIELD_BS_TOTAL_LIAB", "负债合计", "total_liabilities", "float", "万元", "负债合计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "负债合计", "资产负债表负债合计|新浪负债合计", "总负债|负债总额|全部负债"),
    ("FIELD_BS_SHARE_CAPITAL", "股本", "share_capital", "float", "万元", "实收资本(股本)(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "股本", "资产负债表股本|新浪股本", "实收资本|注册资本|总股本"),
    ("FIELD_BS_RETAINED_EARNINGS", "未分配利润", "retained_earnings", "float", "万元", "未分配利润(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "未分配利润", "资产负债表未分配利润|新浪未分配利润", "留存收益|累计利润|保留盈余"),
    ("FIELD_BS_EQUITY_PARENT", "归母股东权益", "equity_parent", "float", "万元", "归属于母公司股东权益合计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "归母股东权益", "资产负债表归母权益|新浪归母权益", "母公司权益|归属母公司权益|净资产"),
    ("FIELD_BS_TOTAL_EQUITY", "股东权益合计", "total_equity", "float", "万元", "所有者权益合计(资产负债表)", "CONCEPT_FINANCIAL_STATEMENTS", "股东权益合计", "资产负债表股东权益|新浪股东权益", "所有者权益|净资产|权益总额"),

    # ── 现金流量表 (DS_SINA_CASHFLOW) ──
    ("FIELD_CF_SALES_CASH", "销售收现", "cash_from_sales", "float", "万元", "销售商品、提供劳务收到的现金(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "销售收现", "现金流量表销售收现|新浪销售收现", "销售收到的现金|收现收入|现金收入"),
    ("FIELD_CF_OPER_INFLOW", "经营活动现金流入", "op_cash_inflow", "float", "万元", "经营活动现金流入小计(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "经营活动现金流入", "现金流量表经营活动现金流入|新浪经营活动现金流入", "经营流入|经营收入现金|营业现金流入"),
    ("FIELD_CF_OPER_OUTFLOW", "经营活动现金流出", "op_cash_outflow", "float", "万元", "经营活动现金流出小计(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "经营活动现金流出", "现金流量表经营活动现金流出|新浪经营活动现金流出", "经营流出|经营付现|营业现金流出"),
    ("FIELD_CF_OPER_FLOW", "经营活动现金流净额", "op_cash_flow", "float", "万元", "经营活动产生的现金流量净额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "经营活动现金流净额", "现金流量表经营现金流|新浪经营现金流", "经营现金流|OCF|经营现金净额|运营现金流"),
    ("FIELD_CF_CAPEX", "资本支出", "capex", "float", "万元", "购建固定资产、无形资产和其他长期资产所支付的现金(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "资本支出", "现金流量表资本支出|新浪资本支出", "CAPEX|资本开支|投资性支出|购建资产"),
    ("FIELD_CF_INV_FLOW", "投资活动现金流净额", "inv_cash_flow", "float", "万元", "投资活动产生的现金流量净额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "投资活动现金流净额", "现金流量表投资现金流|新浪投资现金流", "投资现金流|ICF|投资现金净额"),
    ("FIELD_CF_FIN_FLOW", "筹资活动现金流净额", "fin_cash_flow", "float", "万元", "筹资活动产生的现金流量净额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "筹资活动现金流净额", "现金流量表筹资现金流|新浪筹资现金流", "筹资现金流|FCF|融资现金流"),
    ("FIELD_CF_CASH_DIVIDEND", "分配股利付现", "cash_for_dividend", "float", "万元", "分配股利、利润或偿付利息所支付的现金(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "分配股利付现", "现金流量表分配股利付现|新浪分配股利付现", "股利支付|分红支出|利息支付"),
    ("FIELD_CF_NET_INCREASE", "现金净增加额", "cash_net_increase", "float", "万元", "现金及现金等价物净增加额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "现金净增加额", "现金流量表现金净增|新浪现金净增", "现金变动|现金增减|现金变化"),
    ("FIELD_CF_CASH_BEGIN", "期初现金", "cash_begin", "float", "万元", "期初现金及现金等价物余额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "期初现金", "现金流量表期初现金|新浪期初现金", "年初现金|期初余额|年初余额"),
    ("FIELD_CF_CASH_END", "期末现金", "cash_end", "float", "万元", "期末现金及现金等价物余额(现金流量表)", "CONCEPT_FINANCIAL_STATEMENTS", "期末现金", "现金流量表期末现金|新浪期末现金", "年末现金|期末余额|年末余额"),
]


def escape_cypher_str(s: str) -> str:
    """转义 Cypher 字符串中的特殊字符"""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()
    print("✅ Neo4j 连接成功\n")

    # ── Step 4: 写入 DataSource 节点 ──
    print("=== Step 4: 创建 DataSource 节点 ===")
    with driver.session() as session:
        for ds in DATASOURCES:
            session.run("""
                MERGE (ds:DataSource {id: $id})
                ON CREATE SET
                    ds.name = $name,
                    ds.protocol = $protocol,
                    ds.authority_level = $al,
                    ds.refresh_time = $rt,
                    ds.reliability_score = $rs,
                    ds.table_name = $tn,
                    ds.prompt_dir = $pd,
                    ds.execution_meta = $em
                ON MATCH SET
                    ds.name = $name,
                    ds.protocol = $protocol
            """, id=ds["id"], name=ds["name"], protocol=ds["protocol"],
                 al=ds["authority_level"], rt=ds["refresh_time"], rs=ds["reliability_score"],
                 tn=ds["table_name"], pd=ds["prompt_dir"], em=ds["execution_meta"])
            print(f"  + {ds['id']}: {ds['name']}")

    # ── Step 6: 创建 DataField 节点 ──
    print("\n=== Step 6: 创建 DataField 节点 ===")
    # 先查出 datasource id 对应的昵称映射
    ds_name_map = {ds["id"]: ds["name"] for ds in DATASOURCES}
    inc_fields = [f for f in FIELDS if f[0].startswith("FIELD_INC")]
    bs_fields = [f for f in FIELDS if f[0].startswith("FIELD_BS")]
    cf_fields = [f for f in FIELDS if f[0].startswith("FIELD_CF")]

    with driver.session() as session:
        for fid, sname, col, dtype, unit, desc, concept, simple, qualified, syns in FIELDS:
            # 确定属于哪个数据源
            if fid.startswith("FIELD_INC"):
                ds_id = "DS_SINA_INCOME"
            elif fid.startswith("FIELD_BS"):
                ds_id = "DS_SINA_BALANCE"
            elif fid.startswith("FIELD_CF"):
                ds_id = "DS_SINA_CASHFLOW"
            else:
                continue

            result = session.run("""
                MERGE (f:DataField {id: $id})
                ON CREATE SET
                    f.standard_name = $sn,
                    f.api_column = $col,
                    f.data_type = $dt,
                    f.unit = $unit,
                    f.description = $desc,
                    f.granularity = 'quarterly,个股级别'
                ON MATCH SET
                    f.standard_name = $sn,
                    f.api_column = $col
                RETURN f.id
            """, id=fid, sn=sname, col=col, dt=dtype, unit=unit, desc=desc)
            _ = result.single()

            # 创建 HAS_DATASOURCE 关系
            session.run("""
                MATCH (f:DataField {id: $fid})
                MATCH (ds:DataSource {id: $dsid})
                MERGE (f)-[:HAS_DATASOURCE]->(ds)
            """, fid=fid, dsid=ds_id)

            # 创建 BELONGS_TO_CONCEPT 关系
            session.run("""
                MATCH (f:DataField {id: $fid})
                MATCH (c:IntentConcept {id: $cid})
                MERGE (f)-[:BELONGS_TO_CONCEPT]->(c)
            """, fid=fid, cid=concept)

            print(f"  + {fid}: {sname} → {ds_id} [{concept}]")

    # ── Step 7: 写入 alias CSV ──
    print("\n=== Step 7: 写入 alias CSV ===")
    new_rows = []
    for fid, sname, col, dtype, unit, desc, concept, simple, qualified, syns in FIELDS:
        new_rows.append({
            "field_id": fid,
            "standard_name": sname,
            "concept_id": concept,
            "simple": simple,
            "qualified": qualified,
            "business_tag": "财务报表|新浪财务|科目数据",
            "synonyms": syns,
        })

    # 追加到 alias 文件
    with open(ALIAS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["field_id","standard_name","concept_id","simple","qualified","business_tag","synonyms"])
        for row in new_rows:
            writer.writerow(row)
    print(f"  追加 {len(new_rows)} 条到 {ALIAS_FILE}")

    # ── Step 8: 生成 Embedding ──
    print("\n=== Step 8: 生成 Embedding ===")
    print("  跳过：本地 embedding 模型未加载，后续可单独执行")
    print("  (不影响路由功能，仅影响 Faiss 模糊搜索)")

    # ── 统计 ──
    print(f"\n{'='*50}")
    print(f"新增 DataSource: {len(DATASOURCES)}")
    print(f"新增 DataField: {len(FIELDS)}（利润表 {len(inc_fields)} + 资产负债表 {len(bs_fields)} + 现金流量表 {len(cf_fields)}）")
    print(f"\n下一步: 运行 python3 scripts/audit_full.py")

    driver.close()


if __name__ == "__main__":
    main()
