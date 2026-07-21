"""
文章过滤模块 — 按时间范围和标题正则过滤搜索结果。

用法:
    from filter import ArticleFilter

    f = ArticleFilter()
    filtered = f.apply(articles, days=7, title_pattern="光刻机")
"""
import re
from datetime import datetime, timedelta


class ArticleFilter:
    """
    过滤搜索结果。

    两个维度（可同时启用，取交集）:
      - 时间范围: filter_days=N → 只保留 N 天内的文章
      - 标题过滤: filter_title=pattern → 标题包含 pattern（字符串匹配或正则）
    """

    @staticmethod
    def apply(articles: list[dict],
              days: int | None = None,
              title_pattern: str | None = None) -> list[dict]:
        """
        对文章列表执行过滤。返回原列表的引用，不修改原列表。

        Args:
            articles: article_list，每项需含 title/date 字段
            days: 保留 N 天内的文章（基于 date 字段，如 "" 则不过滤）
            title_pattern: 标题包含/匹配此模式（None 则不过滤）

        Returns:
            过滤后的文章列表
        """
        result = articles

        # 1. 时间范围过滤
        if days is not None and days > 0:
            result = ArticleFilter._filter_by_days(result, days)

        # 2. 标题过滤
        if title_pattern:
            result = ArticleFilter._filter_by_title(result, title_pattern)

        return result

    @staticmethod
    def _filter_by_days(articles: list[dict], days: int) -> list[dict]:
        """
        只保留 days 天内发布的文章。
        没有日期信息的文章: 保留（无法判断是否超期）。
        """
        if not articles:
            return []

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        kept = []
        skipped_no_date = 0
        for art in articles:
            date_str = art.get("date", "").strip()
            if not date_str:
                # 无日期信息 → 保留（宽松策略）
                skipped_no_date += 1
                kept.append(art)
                continue

            if date_str >= cutoff_str:
                kept.append(art)

        if skipped_no_date:
            print(f"  [filter] {skipped_no_date} articles without date info (kept by default)")

        return kept

    @staticmethod
    def _filter_by_title(articles: list[dict], pattern: str) -> list[dict]:
        """
        只保留标题匹配 pattern 的文章。
        pattern 作为普通关键词（不区分大小写），如果含正则特殊字符则视为正则。
        """
        if not articles or not pattern:
            return articles

        # Check if pattern contains regex special characters
        has_regex = bool(re.search(r'[.+*?^$\[\](){}|\\]', pattern))

        kept = []
        for art in articles:
            title = art.get("title", "")
            if has_regex:
                try:
                    if re.search(pattern, title, re.IGNORECASE):
                        kept.append(art)
                except re.error:
                    # Invalid regex → fall back to plain substring match
                    if pattern.lower() in title.lower():
                        kept.append(art)
            else:
                # Plain substring match
                if pattern.lower() in title.lower():
                    kept.append(art)

        return kept
