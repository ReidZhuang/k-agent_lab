#!/usr/bin/env python3
"""生成首批 ds_prompts 文件"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DS_DIR = os.path.join(BASE, "..", "ds_prompts")


def write_ds(ds_id, field, table, api):
    d = os.path.join(DS_DIR, ds_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "field.md"), "w") as f:
        f.write(f"# {ds_id} 可用字段\n\n{field.strip()}\n")
    with open(os.path.join(d, "table.md"), "w") as f:
        f.write(f"# {ds_id} 表结构\n\n{table.strip()}\n")
    with open(os.path.join(d, "api.md"), "w") as f:
        f.write(f"# {ds_id} API 调用规则\n\n{api.strip()}\n")
    print(f"  {ds_id}")


# === DS_TUSHARE_DAILY ===
write_ds("DS_TUSHARE_DAILY",
    "|字段|类型|说明|\n|:---|:---:|:---|\n|ts_code|str|股票代码|\n|trade_date|str|交易日期|\n|open|float|开盘价|\n|high|float|最高价|\n|low|float|最低价|\n|close|float|收盘价|\n|pre_close|float|前收盘|\n|change|float|涨跌额|\n|pct_chg|float|涨跌幅%|\n|vol|float|成交量(手)|\n|amount|float|成交额(千元)|",
    "函数: pro.daily(ts_code, start_date, end_date)\n单次最多 5000 行",
    "```python\npro.daily(ts_code='000001.SZ', start_date='20260101', end_date='20260630')\n```")

# === DS_TUSHARE_DAILY_BASIC ===
write_ds("DS_TUSHARE_DAILY_BASIC",
    "|字段|类型|说明|\n|:---|:---:|:---|\n|ts_code|str|股票代码|\n|trade_date|str|日期|\n|close|float|收盘价|\n|turnover_rate|float|换手率%|\n|pe|float|动态PE|\n|pe_ttm|float|滚动PE|\n|pb|float|市净率|\n|ps_ttm|float|滚动PS|\n|total_mv|float|总市值(万元)|\n|float_mv|float|流通市值(万元)|\n|dv_ttm|float|股息率%|\n|limit_status|int|涨跌停状态|\n|total_share|float|总股本|\n|float_share|float|流通股本|",
    "函数: pro.daily_basic(ts_code, start_date, end_date, fields='')",
    "```python\npro.daily_basic(ts_code='000001.SZ', start_date='20260101')\n```")

# === DS_TUSHARE_FINA_IND ===
write_ds("DS_TUSHARE_FINA_IND",
    "常用财务指标:\n|字段|说明|\n|:---|:---|\n|roe|ROE(加权)%|\n|roe_dt|ROE(扣非)%|\n|gross_profit_margin|毛利率%|\n|net_profit_margin|净利率%|\n|eps|基本每股收益|\n|dt_eps|稀释每股收益|\n|bps|每股净资产|\n|or_yoy|营收同比%|\n|profit_yoy|净利同比%|\n|debt_to_assets|资产负债率%|\n|roic|投入资本回报率%|\n|ebit|息税前利润|\n|fcff|企业自由现金流|",
    "函数: pro.fina_indicator(ts_code, start_date, end_date)\n返回 200+ 指标列",
    "```python\npro.fina_indicator(ts_code='300750.SZ', start_date='20200101', end_date='20240630')\n```")

# === DS_TUSHARE_INCOME ===
write_ds("DS_TUSHARE_INCOME",
    "|字段|说明|\n|:---|:---|\n|revenue|营业收入|\n|oper_cost|营业成本|\n|sell_exp|销售费用|\n|admin_exp|管理费用|\n|rd_exp|研发费用|\n|fin_exp|财务费用|\n|operate_profit|营业利润|\n|total_profit|利润总额|\n|n_income|净利润|\n|n_income_attr_p|归母净利润|\n|basic_eps|基本每股收益|",
    "函数: pro.income(ts_code, start_date, end_date)",
    "```python\npro.income(ts_code='300750.SZ', start_date='20200101')\n```")

# === DS_TUSHARE_BALANCE ===
write_ds("DS_TUSHARE_BALANCE",
    "|字段|说明|\n|:---|:---|\n|total_assets|总资产|\n|total_liab|总负债|\n|total_hldr_eqy|股东权益|\n|money_cap|货币资金|\n|accts_receiv|应收账款|\n|inventories|存货|\n|fix_assets|固定资产|\n|intan_assets|无形资产|\n|goodwill|商誉|\n|st_borr|短期借款|\n|lt_borr|长期借款|",
    "函数: pro.balancesheet(ts_code, start_date, end_date)",
    "```python\npro.balancesheet(ts_code='300750.SZ', start_date='20200101')\n```")

# === DS_TUSHARE_CASHFLOW ===
write_ds("DS_TUSHARE_CASHFLOW",
    "|字段|说明|\n|:---|:---|\n|cashflow_op|经营现金流净额|\n|cashflow_inv|投资现金流净额|\n|cashflow_fin|筹资现金流净额|\n|end_bal_cash|期末现金余额|\n|free_cashflow|自由现金流|",
    "函数: pro.cashflow(ts_code, start_date, end_date)",
    "```python\npro.cashflow(ts_code='300750.SZ', start_date='20200101')\n```")

# === DS_TUSHARE_MONEYFLOW ===
write_ds("DS_TUSHARE_MONEYFLOW",
    "|字段|说明|\n|:---|:---|\n|buy_sm_vol|小单买入量(手)|\n|sell_sm_vol|小单卖出量|\n|buy_md_vol|中单买入量|\n|sell_md_vol|中单卖出量|\n|buy_lg_vol|大单买入量|\n|sell_lg_vol|大单卖出量|\n|buy_elg_vol|特大单买入量|\n|sell_elg_vol|特大单卖出量|\n|net_mf_vol|净流入量(手)|\n|net_mf_amount|净流入额(万元)|",
    "函数: pro.moneyflow(ts_code, start_date, end_date)",
    "```python\npro.moneyflow(ts_code='000001.SZ', start_date='20260101')\n```")

# === DS_TUSHARE_CN_MACRO ===
write_ds("DS_TUSHARE_CN_MACRO",
    "多张表:\n-cn_gdp: GDP(quarter, gdp, gdp_yoy)\n-cn_cpi: CPI(month, cpi_yoy)\n-cn_ppi: PPI(month, ppi_yoy)\n-cn_pmi: PMI(month, pmi)\n-cn_m: M0/M1/M2(month, m2_yoy)\n-shibor: 利率(date, on, 1w, 1m, 3m)\n-shibor_lpr: LPR(lpr_1y, lpr_5y)\n-sf_month: 社融(inc_month)\n-us_tycr: 美债(y1,y2,y5,y10,y30)\n-libor: Libor(on,3m,6m)",
    "不同指标不同函数",
    "```python\npro.cn_gdp()\npro.cn_cpi()\npro.cn_pmi()\npro.shibor()\n```")

# === DS_TENCENT_QUOTE ===
write_ds("DS_TENCENT_QUOTE",
    "|字段|类型|说明|\n|:---|:---:|:---|\n|name|str|股票名称|\n|code|str|代码|\n|price|float|当前价|\n|pct_chg|float|涨跌幅%|\n|volume|float|成交量(手)|\n|amount|float|成交额(万元)|\n|high|float|最高价|\n|low|float|最低价|\n|open|float|开盘价|\n|pre_close|float|昨收|\n|total_mv|float|总市值(亿元)|\n|pe_dynamic|float|动态PE|\n|pb|float|市净率|\n|turnover_rate|float|换手率%|",
    "API: http://web.sqt.gtimg.cn/q=sh600519\n免Token",
    "```python\nimport requests\nurl = f'http://web.sqt.gtimg.cn/q=sh600519'\n```\n免Token")

# === DS_AKSHARE_SECTOR_SPOT ===
write_ds("DS_AKSHARE_SECTOR_SPOT",
    "东方财富板块实时行情:\n|列|说明|\n|:---|:---|\n|板块名称|str|\n|板块代码|str|\n|涨跌幅|float%|\n|成交额|float(亿元)|\n|换手率|float%|\n|领涨股|str|\n|主力净流入|float|",
    "函数: ak.stock_board_industry_spot_em()\n或 ak.stock_board_concept_spot_em()",
    "```python\nimport akshare as ak\ndf = ak.stock_board_industry_spot_em()\n```")

# === DS_LEVISTOCK_EMOTION ===
write_ds("DS_LEVISTOCK_EMOTION",
    "返回 dict:\n|字段|说明|\n|:---|:---|\n|market_degree|市场热度0-100|\n|up_ratio|上涨占比%|\n|profit_ratio|赚钱效应%|\n|shsz_balance|两市成交额|\n|limit_up_board|涨停梯队dict|",
    "函数: lk.market_emotion_cls()",
    "```python\nimport levistock as lk\nemotion = lk.market_emotion_cls()\n```")

# === DS_LEVISTOCK_NEWS ===
write_ds("DS_LEVISTOCK_NEWS",
    "list[dict]:\n|字段|说明|\n|:---|:---|\n|time|时间|\n|title|标题|\n|content|正文|",
    "函数: lk.news_telegraph_cls(category='important')",
    "```python\nlk.news_telegraph_cls(category='important')\n```")

print(f"\n完成! 12 个 DataSource prompt 文件已生成到 {DS_DIR}")
