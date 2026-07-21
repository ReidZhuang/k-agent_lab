"""baidufin 搜索后端 — 通过百度股市通获取个股新闻（Playwright 浏览器）

需要安装 playwright：
    pip install playwright && playwright install chromium

用法：
    from search_engine import search
    results = search("300436", engine="baidufin")
    results = search("300436", engine="baidufin", start_date="2026-07-20", end_date="2026-07-21")

返回格式: [{title, url, snippet, _known_date, _baidu_sentiment, _baidu_provider, _baidu_abstract}, ...]
    _known_date: 百度返回的精确发布日期
    _baidu_abstract: 新闻摘要（可作正文预览）
    _baidu_sentiment: 情绪分类（利好/中性/利空）
    _baidu_provider: 来源（证券之星/东方财富网/同花顺）
"""
import re, threading
from datetime import datetime
from typing import Optional

from .base import SearchBackend

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


class BaidufinBackend(SearchBackend):
    """通过百度股市通获取个股新闻（Playwright 浏览器）"""

    BENEFIT_MAP = {0: "中性", 1: "利好", 2: "利空"}

    # ── 实际抓取逻辑（在独立线程中执行，避免 asyncio 冲突）──
    @staticmethod
    def _scrape(code: str, pages: int, max_results: int,
                ts_start: Optional[int], ts_end: Optional[int]) -> list[dict]:
        benefit_map = BaidufinBackend.BENEFIT_MAP
        results = []
        seen_ids = set()

        url = f"https://finance.baidu.com/stock/ab-{code}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            def on_response(resp):
                if "sentimentlist" not in resp.url or len(results) >= max_results:
                    return
                try:
                    data = resp.json()
                    items = (data.get("Result", [{}])[0].get("TplData", {})
                             .get("aiSentimentXcxListInfo", {})
                             .get("sentimentListInfo", []))
                except Exception:
                    return

                for item in items:
                    if len(results) >= max_results:
                        break
                    nid = item.get("news_id", "")
                    if nid in seen_ids:
                        continue
                    seen_ids.add(nid)

                    ts = item.get("publishTime")
                    try:
                        ts_int = int(ts)
                    except (ValueError, TypeError):
                        continue

                    # 日期过滤
                    if ts_start is not None and ts_int < ts_start:
                        continue
                    if ts_end is not None and ts_int > ts_end:
                        continue

                    bt = item.get("benefitType", -1)
                    try:
                        bt_int = int(bt)
                    except (ValueError, TypeError):
                        bt_int = -1

                    pub_dt = datetime.fromtimestamp(ts_int)
                    date_str = pub_dt.strftime("%Y-%m-%d")

                    origin_url = item.get("originUrl", "")
                    results.append({
                        "title": item.get("title", ""),
                        "url": origin_url,
                        "snippet": item.get("abstract", ""),
                        "_known_date": date_str,
                        "_baidu_sentiment": benefit_map.get(bt_int, "未知"),
                        "_baidu_provider": item.get("provider", ""),
                        "_baidu_abstract": item.get("abstract", ""),
                        "_baidu_ts": ts_int,
                    })

            page.on("response", on_response)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # 点击"资讯"标签（有超时保护，防止无效代码卡死）
            try:
                for tab in page.query_selector_all("a, span, div[class*=tab]"):
                    if (tab.inner_text() or "").strip() == "资讯":
                        tab.click(timeout=5000)
                        page.wait_for_timeout(5000)
                        break
            except Exception:
                pass  # 页面可能没有资讯标签（如无效代码），忽略

            # 滚动翻页
            for _ in range(pages - 1):
                if len(results) >= max_results:
                    break
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(3000)
                except Exception:
                    break

            browser.close()

        return results[:max_results]

    def search(self, query: str, max_results: int = 20,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行个股新闻搜索。

        Args:
            query: 股票代码（如 "300436" 或 "600519"）
            max_results: 最大返回条数（默认 20，最大 100）
            start_date: 起始日期过滤 YYYY-MM-DD
            end_date: 截止日期过滤 YYYY-MM-DD

        Returns:
            [{title, url, snippet, _known_date, _baidu_*}, ...]
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "baidufin 引擎需要 playwright: "
                "pip install playwright && playwright install chromium"
            )

        code = re.sub(r'[^0-9]', '', query.strip())
        if not code:
            raise ValueError(f"无法从 '{query}' 中提取股票代码")

        pages = max(1, min(5, (max_results + 19) // 20))

        ts_start = None
        ts_end = None
        if start_date:
            ts_start = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        if end_date:
            ts_end = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() + 86399)

        # 在独立线程中运行 playwright（兼容 async 调用方）
        result_holder = []

        def _run():
            try:
                r = self._scrape(code, pages, max_results, ts_start, ts_end)
                result_holder.extend(r)
            except Exception as e:
                result_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join()

        if result_holder and isinstance(result_holder[-1], Exception):
            raise result_holder[-1]

        return result_holder
