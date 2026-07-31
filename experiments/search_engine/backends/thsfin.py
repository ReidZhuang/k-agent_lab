"""
同花顺 F10 公司大事（thsfin）搜索后端。

从同花顺 F10 页面抓取"近期重要事件"列表。
需要 Playwright 渲染页面。

用法:
    from backends.thsfin import ThsfinBackend
    backend = ThsfinBackend()
    results = backend.search("300395", max_results=10, start_date="2026-07-20")

返回格式:
    [{title, url, snippet, _known_date}, ...]
    - title: 事件类型（如"发布公告"）
    - url: 原文链接（仅发布公告等类型有，无链接留空）
    - snippet: 事件详情
    - _known_date: 事件日期 YYYY-MM-DD
"""
import re, os, sys, threading, time, random
from datetime import datetime, timedelta

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ThsfinBackend:
    """同花顺 F10 公司大事搜索后端。"""

    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行同花顺 F10 公司大事查询。

        Args:
            query: 股票代码（如 "300395"）
            max_results: 最大返回条数
            start_date: 起始日期 YYYY-MM-DD（搜素引擎层日期过滤）
            end_date: 截止日期 YYYY-MM-DD

        Returns:
            [{title, url, snippet, _known_date}, ...]
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "thsfin 引擎需要 playwright: "
                "pip install playwright && playwright install chromium"
            )

        code = re.sub(r'[^0-9]', '', query.strip())
        if not code:
            raise ValueError(f"无法从 '{query}' 中提取股票代码")

        result_holder = []
        _exc_info = []

        def _run():
            for attempt in range(2):
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        )
                        page = context.new_page()

                        url = f"https://basic.10jqka.com.cn/{code}/event.html"
                        page.goto(url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(3000)

                        events = page.evaluate("""() => {
                            const tables = document.querySelectorAll('table');
                            let eventTable = null;
                            for (const t of tables) {
                                const rows = t.querySelectorAll('tr');
                                let dateCount = 0;
                                for (const r of rows) {
                                    const cells = r.querySelectorAll('td');
                                    if (cells.length >= 2) {
                                        const txt = cells[0].innerText.trim();
                                        if (/^\\d{4}-\\d{2}-\\d{2}$/.test(txt)) {
                                            dateCount++;
                                            if (dateCount >= 3) { eventTable = t; break; }
                                        }
                                    }
                                }
                                if (eventTable) break;
                            }
                            if (!eventTable) return [];

                            const rows = eventTable.querySelectorAll('tr');
                            const results = [];
                            let seq = 0;
                            for (const row of rows) {
                                const cells = row.querySelectorAll('td');
                                if (cells.length < 2) continue;
                                const date = cells[0].innerText.trim();
                                if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(date)) continue;

                                const contentCell = cells[1];
                                const fullText = contentCell.innerText.trim().replace(/\\s+/g, ' ');
                                const lines = fullText.split('\\n').map(l => l.trim()).filter(l => l);
                                let title = (lines[0] || '').replace(/[：:]\\s*$/, '');

                                let detail = lines.slice(1).join(' | ').trim();
                                if (!detail) detail = fullText;

                                const anchors = contentCell.querySelectorAll('a');
                                let articleUrl = '';
                                for (const a of anchors) {
                                    const href = a.getAttribute('href') || '';
                                    const text = a.innerText.trim();
                                    if (href.startsWith('http') && !href.includes('javascript')) {
                                        if (!articleUrl) articleUrl = href;
                                        if (/[《（]/.test(text)) { articleUrl = href; break; }
                                    }
                                }
                                if (!articleUrl) {
                                    for (const a of anchors) {
                                        const oc = a.getAttribute('onclick') || '';
                                        const m = oc.match(/https?:\\/\\/[^'"\\s]+/);
                                        if (m) { articleUrl = m[0]; break; }
                                    }
                                }

                                seq++;
                                results.push({
                                    id: `a_${String(seq).padStart(2, '0')}`,
                                    _known_date: date,
                                    title: title,
                                    snippet: detail,
                                    url: articleUrl,
                                });
                            }
                            return results;
                        }""")

                        browser.close()

                        # 日期过滤（搜索引擎层）
                        filtered = self._filter_by_date(events, start_date, end_date)
                        result_holder.extend(filtered[:max_results])
                        return  # success

                except Exception as e:
                    _exc_info.append(e)
                    if attempt == 0:
                        wait = 1 + random.random()
                        print(f"[thsfin] Playwright 失败（{type(e).__name__}），{wait:.1f}s 后重试: {code}", flush=True)
                        time.sleep(wait)
                    else:
                        raise

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=60)
        if not result_holder and _exc_info:
            # 全部重试失败，打印日志但不抛异常（返回空列表）
            print(f"[thsfin] {code} Playwright 全部重试失败: {_exc_info[-1]}", flush=True)
        return result_holder[:max_results]

    @staticmethod
    def _filter_by_date(events: list[dict],
                        start_date: str | None = None,
                        end_date: str | None = None) -> list[dict]:
        """日期过滤：上下界包夹。"""
        if not start_date and not end_date:
            return events

        # 默认到今天
        now = datetime.now()
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else now - timedelta(days=365)
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else now

        # 如果 end_date 只有日期，扩大到当天结束
        if end_date and end_date.strip().replace("T", " ").count(" ") == 0:
            end = end + timedelta(days=1) - timedelta(seconds=1)

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        kept = []
        for e in events:
            d = e.get("_known_date", "")
            if start_str <= d <= end_str:
                kept.append(e)

        return kept
