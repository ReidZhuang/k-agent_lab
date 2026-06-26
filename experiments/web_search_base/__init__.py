"""web_search_base — 稳定的上市公司信息获取后端

数据源:
  - eastmoney: 东方财富数据中心 API（财务数据主表，165 字段）
  - akshare_em: akshare 封装的东方财富财务摘要（80 指标 × 多期）
  - sina: 新浪财经实时行情（股价、涨跌幅）
  - tencent: 腾讯财经实时行情（股价、估值、市值）

用法:
    from web_search_base import search
    result = search("宁德时代 2025 年营收净利润")
"""

from .search import search, search_company_financial, search_stock_quote
