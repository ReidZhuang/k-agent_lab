"""统一搜索路由 — 根据查询内容自动选择合适的数据源

搜索策略:
  1. 查询中包含"宁德时代"/"比亚迪"等公司名 → 调东方财富财报数据
  2. 查询中包含"对比"/"比较" → 调两家公司的对比数据
  3. 查询中包含"股价"/"行情"/"市值"/"市盈率" → 调腾讯/新浪行情
  4. 查询中包含"趋势"/"历史"/"增长率" → 调 akshare 多期财务摘要
  5. 其他 → 返回公司基本信息
"""

from .sources.eastmoney import (
    format_financial_report,
    format_comparison,
    get_stock_list_from_query,
)
from .sources.akshare_em import format_abstract, format_multi_period_comparison
from .sources.tencent import format_quote as tencent_format_quote


def search(query: str) -> str:
    """主搜索入口。根据查询自动路由到合适的数据源。

    Args:
        query: 自然语言查询

    Returns:
        格式化的搜索结果文本
    """
    stocks = get_stock_list_from_query(query)

    is_comparison = any(kw in query for kw in ["对比", "比较", "vs", "VS", " versus"])
    is_quote = any(kw in query for kw in ["股价", "行情", "市值", "市盈率", "市净率", "换手率"])
    is_trend = any(kw in query for kw in ["趋势", "历史", "增长率", "变化", "连续", "逐年"])
    is_deep = any(kw in query for kw in ["分析", "评估", "全面", "深入", "详细", "完整"])

    results = []

    if is_comparison:
        if len(stocks) >= 2:
            results.append(format_comparison(
                stocks[0][0], stocks[0][1],
                stocks[1][0], stocks[1][1],
            ))
        elif len(stocks) == 1:
            results.append(format_financial_report(stocks[0][0], stocks[0][1]))
        else:
            results.append("（请指定要对比的公司名称）")

    elif is_quote:
        for code, name in stocks:
            results.append(tencent_format_quote(code, name))

    elif is_trend:
        for code, name in stocks:
            results.append(format_abstract(code, name))
        if is_comparison and len(stocks) >= 2:
            for indicator in ["营业总收入", "归母净利润", "毛利率", "净资产收益率(ROE)"]:
                comp = format_multi_period_comparison(
                    stocks[0][0], stocks[0][1],
                    stocks[1][0], stocks[1][1],
                    indicator,
                )
                if "数据不足" not in comp:
                    results.append(comp)

    elif is_deep:
        for code, name in stocks:
            results.append(format_financial_report(code, name))
            results.append(format_abstract(code, name))
        if len(stocks) >= 2:
            results.append(format_comparison(
                stocks[0][0], stocks[0][1],
                stocks[1][0], stocks[1][1],
            ))

    else:
        for code, name in stocks:
            results.append(format_financial_report(code, name))

    if not results:
        return "（查询未识别到已知的上市公司。当前支持的股票: 300750(SZ) 宁德时代, 002594(SZ) 比亚迪）"

    return "\n\n".join(results)


def search_company_financial(code: str, name: str) -> str:
    """快捷获取公司财务数据。"""
    return format_financial_report(code, name)


def search_stock_quote(code: str, name: str) -> str:
    """快捷获取公司实时行情。"""
    return tencent_format_quote(code, name)
