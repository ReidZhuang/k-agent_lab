"""akshare 封装的东方财富财务摘要

底层源: 东方财富网页接口（通过 akshare 库）
数据内容: 80 项财务指标 × 30+ 报告期（可追溯至 2014 年）

覆盖指标类别:
  - 常用指标: 营收、净利润、扣非净利润、ROE、毛利率、净利率、每股收益
  - 每股指标: 每股经营现金流、每股自由现金流、每股净资产、每股营业收入
  - 盈利能力: ROE(摊薄/平均/扣非)、ROA、毛利率、净利率、投入资本回报率
  - 成长能力: 营收增长率、归母净利润增长率、净利润增长率、扣非增长率
  - 收益质量: 经营现金流/销售收入、期间费用率、所得税/利润总额
  - 财务风险: 流动比率、速动比率、资产负债率、权益乘数、产权比率
  - 营运能力: 应收账款周转率、存货周转率、总资产周转率

速度: ~0.3s 每次
"""

import akshare as ak
import pandas as pd


# ── 所有指标的友好名称映射 ──
INDICATOR_LABELS = {
    "归母净利润": "归母净利润",
    "营业总收入": "营业总收入",
    "营业成本": "营业成本",
    "净利润": "净利润",
    "扣非净利润": "扣非净利润",
    "股东权益合计(净资产)": "净资产",
    "基本每股收益": "基本每股收益",
    "每股净资产": "每股净资产",
    "净资产收益率(ROE)": "ROE",
    "总资产报酬率(ROA)": "ROA",
    "毛利率": "毛利率",
    "销售净利率": "净利率",
    "资产负债率": "资产负债率",
    "经营现金流量净额": "经营现金流净额",
    "营业总收入增长率": "营收增长率",
    "归属母公司净利润增长率": "归母净利润增长率",
    "流动比率": "流动比率",
    "速动比率": "速动比率",
    "存货周转率": "存货周转率",
    "总资产周转率": "总资产周转率",
    "期间费用率": "期间费用率",
    "投入资本回报率": "投入资本回报率",
    "每股经营现金流": "每股经营现金流",
    "每股营业收入": "每股营业收入",
    "稀释每股收益": "稀释每股收益",
}


def fetch_abstract(symbol: str) -> pd.DataFrame:
    """获取个股财务摘要数据。

    Args:
        symbol: 股票代码，如 "300750"

    Returns:
        DataFrame: 80 行（指标）× 多列（报告期）
    """
    return ak.stock_financial_abstract(symbol=symbol)


def format_abstract(symbol: str, name: str, indicators: list[str] | None = None) -> str:
    """格式化为可读的财务摘要报告。

    Args:
        symbol: 股票代码
        name: 公司名称
        indicators: 要展示的指标列表（None 表示全部）

    Returns:
        格式化的报告文本
    """
    df = fetch_abstract(symbol)
    if df.empty:
        return f"（{name} 暂无数据）"

    if indicators is None:
        indicators = [
            "营业总收入", "营业成本", "净利润", "归母净利润", "扣非净利润",
            "毛利率", "销售净利率", "净资产收益率(ROE)", "总资产报酬率(ROA)",
            "基本每股收益", "每股净资产", "每股经营现金流",
            "资产负债率", "流动比率", "速动比率",
            "经营现金流量净额", "营业总收入增长率",
            "归属母公司净利润增长率",
        ]

    lines = [f"{name}({symbol}) 财务摘要", "=" * 40]
    periods = [c for c in df.columns if c not in ("选项", "指标")]

    for indicator in indicators:
        row = df[df["指标"] == indicator]
        if row.empty:
            continue
        label = INDICATOR_LABELS.get(indicator, indicator)
        lines.append(f"\n{label}:")

        for p in periods[:6]:
            val = row.iloc[0].get(p)
            if pd.isna(val) or val == "" or val is None:
                continue
            lines.append(f"  {p}: {val}")

    lines.append(f"\n(来源: 东方财富, akshare)")
    return "\n".join(lines)


def format_multi_period_comparison(
    symbol_a: str, name_a: str,
    symbol_b: str, name_b: str,
    indicator: str = "归母净利润",
) -> str:
    """两家公司某项指标的多期对比。"""
    df_a = fetch_abstract(symbol_a)
    df_b = fetch_abstract(symbol_b)
    row_a = df_a[df_a["指标"] == indicator]
    row_b = df_b[df_b["指标"] == indicator]
    if row_a.empty or row_b.empty:
        return f"（{indicator} 数据不足）"

    periods = [c for c in df_a.columns if c not in ("选项", "指标")][:8]
    label = INDICATOR_LABELS.get(indicator, indicator)
    lines = [f"{label} 多期对比", "=" * 40]
    lines.append(f"{'报告期':<16} {name_a:<20} {name_b:<20}")
    lines.append(f"{'─'*16} {'─'*20} {'─'*20}")
    for p in periods:
        va = row_a.iloc[0].get(p)
        vb = row_b.iloc[0].get(p)
        if pd.isna(va) and pd.isna(vb):
            continue
        va_s = f"{va:,.2f}" if not pd.isna(va) else "N/A"
        vb_s = f"{vb:,.2f}" if not pd.isna(vb) else "N/A"
        lines.append(f"{p:<16} {va_s:<20} {vb_s:<20}")
    return "\n".join(lines)
