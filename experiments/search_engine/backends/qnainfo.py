"""
互动易问答（qnainfo）搜索后端 — 从巨潮互动易平台获取上市公司 IRM 问答记录。

数据来源: akshare 接口 `ak.stock_irm_cninfo(symbol='XXXXXX')`
特点:
  - 不支持按时间范围筛选，需全量拉取后按更新时间过滤
  - 只看已回答条目（回答内容不为空）
  - 首次调用即返回完整问答内容（问题、回答者、回答、提问时间、更新时间）
  - 无列表/正文分离 — 无需二次调用
  - body_text = _answer（回答内容），可直接使用

用法:
    from search_engine import search
    results = search("300750", engine="qnainfo")
    results = search("300750", engine="qnainfo",
                     start_date="2026-07-21", end_date="2026-07-24")

返回格式:
    [{title, url="", snippet, _known_date, _category,
      _question, _answerer, _answer, _ask_time, _update_time,
      body_text  ← 回答内容（可直接使用）}, ...]
    _category: "互动易问答"
    _known_date: 更新时间（精确到分钟，用于 filter_days 过滤）
"""
import re
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from .base import SearchBackend


class QnAInfoBackend(SearchBackend):
    """互动易问答搜索后端 — 首次调用即返回完整问答内容。"""

    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行互动易问答搜索。

        特点：首次调用即返回完整问答内容（问题+回答），无需二次 /article 调用。
        body_text = _answer（回答内容），可直接取用。

        Args:
            query: 股票代码（6位纯数字，如 "300750"）
            max_results: 最大返回条数
            start_date: 可选起始日期 YYYY-MM-DD
            end_date:   可选截止日期 YYYY-MM-DD

        Returns:
            [{title, url="", snippet, _known_date, _category,
              _question, _answerer, _answer, _ask_time, _update_time,
              body_text}, ...]
        """
        # 1. 参数校验 — 只接受 6 位数字股票代码
        code = query.strip()
        if not re.match(r'^\d{6}$', code):
            return [{
                "title": f"无效股票代码: '{query}'，互动易问答需要6位数字代码",
                "url": "",
                "snippet": "",
                "_known_date": "",
                "_category": "错误",
            }]

        # 2. 调用 akshare 获取全量问答数据
        # 注意: akshare 对无问答数据的股票（如部分上海主板）会因空 DataFrame 列重命名抛出 KeyError
        try:
            df = ak.stock_irm_cninfo(symbol=code)
        except KeyError:
            # 该股在互动易平台无任何问答记录，返回空
            return []
        except Exception as e:
            return [{
                "title": f"获取互动易问答失败: {e}",
                "url": "",
                "snippet": "",
                "_known_date": "",
                "_category": "错误",
            }]

        if df is None or df.empty:
            return []

        # 3. 过滤：保留已回答的条目（回答内容不为空）
        df = df[df["回答内容"].notna() & (df["回答内容"] != "")].copy()
        if df.empty:
            return []

        # 4. 过滤：更新时间不为空
        df = df[df["更新时间"].notna()].copy()
        if df.empty:
            return []

        # 5. 按时间范围过滤
        df["_update_date"] = pd.to_datetime(df["更新时间"], errors="coerce")
        df = df.dropna(subset=["_update_date"])

        if start_date:
            sd = pd.Timestamp(start_date)
            df = df[df["_update_date"] >= sd]
        if end_date:
            ed = pd.Timestamp(end_date) + pd.Timedelta(days=1)
            df = df[df["_update_date"] < ed]

        if df.empty:
            return []

        # 6. 按更新时间降序排列
        df = df.sort_values("_update_date", ascending=False)

        # 7. 限制返回条数
        df = df.head(max_results)

        # 8. 构建标准输出格式（含 body_text — 可直接使用）
        results = []
        for _, row in df.iterrows():
            question = str(row.get("问题", ""))
            answer = str(row.get("回答内容", ""))
            answerer = str(row.get("回答者", ""))
            ask_time = str(row.get("提问时间", ""))
            update_time = str(row.get("更新时间", ""))

            title = question[:60] + "..." if len(question) > 60 else question
            snippet = answer[:120] + "..." if len(answer) > 120 else answer

            results.append({
                "title": title,
                "url": "",
                "snippet": snippet,
                "_known_date": update_time[:19],  # 精确到秒（如 "2026-07-08 18:03:33"）
                "_category": "互动易问答",
                "_question": question,
                "_answerer": answerer,
                "_answer": answer,
                "_ask_time": ask_time,
                "_update_time": update_time,
                "body_text": answer,       # ⬅ 回答内容直接作为正文
            })

        return results
