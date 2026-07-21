"""
Sina Finance stock news scraper.

Fetches news article listings from Sina Finance's per-stock news page.
Handles pagination (Page 1 uses a different URL from Page 2+).

Usage:
    from sina_scraper import SinaNewsScraper

    scraper = SinaNewsScraper()
    news = scraper.fetch_news("sz300750", pages=3)
    # → [{"title": ..., "url": ..., "date": "2026-07-17", "time": "20:46"}, ...]
"""
import re, csv, io
from datetime import datetime

import httpx

from config import (
    SINA_LIST_URL_PAGE1,
    SINA_LIST_URL_PAGEN,
    REQUEST_TIMEOUT,
    HEADERS,
)


class SinaNewsScraper:
    """Scrape news article listings from Sina Finance's stock news page."""

    def __init__(self):
        self._client = httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True)

    # ── Public API ──

    def fetch_news(self, sina_code: str, pages: int = 3,
                   start_date: str | None = None,
                   end_date: str | None = None) -> list[dict]:
        """
        Fetch news list from Sina stock news page.

        Args:
            sina_code: e.g. 'sz300750' or 'sh600519'
            pages: Number of pages to scrape (default 3)
            start_date: Earliest date filter (YYYY-MM-DD), inclusive.
                        Pages are in reverse chronological order, so once a
                        page's newest article is < start_date, we stop early.
            end_date: Latest date filter (YYYY-MM-DD), inclusive.

        Returns:
            List of dicts: [{"title": str, "url": str, "date": str, "time": str}, ...]
            Sorted newest-first by (date, time).
        """
        all_news = []
        seen = set()  # URL dedup

        for page in range(1, pages + 1):
            url = self._build_url(sina_code, page)
            print(f"  [Page {page}] {url}")

            try:
                html = self._fetch(url)
                page_news = self._parse_news_list(html)
            except Exception as e:
                print(f"  [Page {page}] ERROR: {e}")
                break

            if not page_news:
                print(f"  [Page {page}] No articles found, stopping.")
                break

            # ── Early break: pages are newest-first; if this page's latest
            #    article is before start_date, subsequent pages are even older.
            if start_date is not None:
                page_dates = [n["date"] for n in page_news if n.get("date")]
                if page_dates:
                    newest_on_page = max(page_dates)
                    if newest_on_page < start_date:
                        print(f"  [Page {page}] Newest article ({newest_on_page}) < start_date ({start_date}), stopping.")
                        break

            # Dedup across pages
            new_count = 0
            for item in page_news:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    all_news.append(item)
                    new_count += 1

            print(f"  [Page {page}] Got {len(page_news)} items, {new_count} new.")
            if new_count == 0:
                break

        # ── Filter by date range ──
        if start_date is not None or end_date is not None:
            filtered = []
            for item in all_news:
                d = item.get("date", "")
                if not d:
                    filtered.append(item)  # no date info → keep
                    continue
                if start_date is not None and d < start_date:
                    continue
                if end_date is not None and d > end_date:
                    continue
                filtered.append(item)
            print(f"  [Date filter] {len(all_news)} → {len(filtered)} items (start={start_date}, end={end_date})")
            all_news = filtered

        # Sort newest-first by (date, time)
        all_news.sort(key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)

        return all_news

    def to_csv(self, news: list[dict]) -> str:
        """Convert news list to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["标题", "URL", "日期", "时间"])
        for item in news:
            writer.writerow([
                item.get("title", ""),
                item.get("url", ""),
                item.get("date", ""),
                item.get("time", ""),
            ])
        return output.getvalue()

    def to_csv_file(self, news: list[dict], filepath: str):
        """Save news list to a CSV file."""
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            f.write(self.to_csv(news))

    # ── URL building ──

    def _build_url(self, sina_code: str, page: int) -> str:
        """Build the appropriate Sina URL for the given page number."""
        if page == 1:
            return SINA_LIST_URL_PAGE1.format(sina_code=sina_code)
        else:
            return SINA_LIST_URL_PAGEN.format(sina_code=sina_code, page=page)

    # ── Fetching ──

    def _fetch(self, url: str) -> str:
        """Fetch and decode a Sina page (GB2312 encoded)."""
        resp = self._client.get(url, headers=HEADERS)
        resp.encoding = "gb2312"
        return resp.text

    # ── Parsing ──

    def _parse_news_list(self, html: str) -> list[dict]:
        """
        Parse the Sina stock news listing page HTML.

        Structure (inside a <div class="datelist"><ul>):
            &nbsp;&nbsp;&nbsp;&nbsp;2026-07-17&nbsp;20:46&nbsp;&nbsp;
            <a target='_blank' href='URL'>Title</a> <br>

        We locate the datelist div and extract all <a> tags with preceding date/time.
        """
        news = []

        # Find the datelist section
        dl_match = re.search(r'<div\s+class="datelist"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not dl_match:
            # Fallback: look for the whole content section
            dl_match = re.search(r'<div\s+id="con02-7"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not dl_match:
            print("    WARNING: Could not find datelist div in HTML")
            return news

        list_html = dl_match.group(1)

        # Pattern: optional non-breaking spaces + YYYY-MM-DD + HH:MM + <a ...>title</a>
        # Each news item looks like:
        # &nbsp;&nbsp;&nbsp;&nbsp;2026-07-17&nbsp;20:46&nbsp;&nbsp;<a ...>title</a> <br>
        pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2})"         # date group 1
            r"(?:\s|&nbsp;)+"
            r"(\d{2}:\d{2})"               # time group 2
            r"(?:\s|&nbsp;)+"
            r'<a\s+[^>]*href=(["\'])(.*?)\3[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        for m in pattern.finditer(list_html):
            date_str = m.group(1)
            time_str = m.group(2)
            url = m.group(4)
            title = re.sub(r"<[^>]+>", "", m.group(5)).strip()

            if not title or len(title) < 3:
                continue

            # Normalize URL (relative → absolute)
            if url.startswith("//"):
                url = "https:" + url

            news.append({
                "title": title,
                "url": url,
                "date": date_str,
                "time": time_str,
            })

        return news
