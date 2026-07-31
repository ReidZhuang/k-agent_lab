"""
东方财富股吧（dcfin）搜索后端 — Playwright 全程驱动 + 人类行为模拟。

从东方财富股吧（guba.eastmoney.com）抓取文章列表，支持三个分类：
  - 热门 (tab=99)
  - 资讯 (tab=1)
  - 公告 (tab=3)

行为特征：
  - 全程 Playwright 渲染，不使用裸 HTTP 请求
  - 先访问首页建立 Cookie 会话，再访问目标页面
  - 请求间隔 1.5~3 秒随机（列表页）
  - 详情页停留 5 秒以上
  - 每小时请求总量控制在 2000~3000 次以内

需要安装 playwright：
    pip install playwright && playwright install chromium

用法:
    from search_engine import search
    results = search("300395", engine="dcfin")
    results = search("300395", engine="dcfin",
                     start_date="2026-07-01", end_date="2026-07-22")

返回格式:
    [{title, url, _known_date, _category}, ...]
"""
import re, random, time, threading
from datetime import datetime, timedelta

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


class RateLimiter:
    """每小时请求总量限制器。"""

    def __init__(self, max_per_hour: int = 2500):
        self.max_per_hour = max_per_hour
        self._counts: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """尝试获取请求配额。返回 True 可继续，False 表示已达上限。"""
        with self._lock:
            now = time.time()
            # 清理 1 小时前的记录
            cutoff = now - 3600
            self._counts = [t for t in self._counts if t > cutoff]
            if len(self._counts) >= self.max_per_hour:
                return False
            self._counts.append(now)
            return True

    @property
    def used(self) -> int:
        with self._lock:
            now = time.time()
            self._counts = [t for t in self._counts if t > now - 3600]
            return len(self._counts)

    @property
    def remaining(self) -> int:
        return max(0, self.max_per_hour - self.used)


# 全局速率限制器（进程级别）
_GLOBAL_RATE_LIMITER = RateLimiter(max_per_hour=2500)


def _random_delay(min_s: float = 1.5, max_s: float = 3.0):
    """随机等待，模拟人类操作间隔。"""
    time.sleep(random.uniform(min_s, max_s))


def _seed_guba_session(context) -> None:
    """访问东方财富股吧首页，建立 Cookie 会话。

    必须在访问任何目标页面之前调用，否则文章页可能触发滑块验证码。
    """
    try:
        page = context.new_page()
        page.goto("https://guba.eastmoney.com/", wait_until="load", timeout=15000)
        page.wait_for_timeout(random.uniform(2000, 4000))
        page.close()
    except Exception:
        pass


class DcfinBackend:
    """东方财富股吧搜索后端（Playwright 驱动 + 人类行为模拟）。"""

    CATEGORIES = [
        ("热门", "99", "j"),
        ("资讯", "1", "f"),
        ("公告", "3", "f"),
    ]

    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    def search(self, query: str, **kwargs) -> list[dict]:
        """
        执行东方财富股吧搜索。

        Args:
            query: 股票代码（如 "300395"）
            start_date: 起始日期 YYYY-MM-DD（可选，支持 YYYY-MM-DD HH:MM）
            end_date: 截止日期 YYYY-MM-DD（可选，支持 YYYY-MM-DD HH:MM）

        Returns:
            [{title, url, _known_date, _category}, ...]
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "dcfin 引擎需要 playwright: "
                "pip install playwright && playwright install chromium"
            )

        # 速率限制检查
        if not _GLOBAL_RATE_LIMITER.acquire():
            print("[dcfin] 速率上限已到（2500次/小时），跳过本次搜索", flush=True)
            return []

        # 从 kwargs 提取日期过滤参数
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        code = re.sub(r'[^0-9]', '', query.strip())
        if not code:
            raise ValueError(f"无法从 '{query}' 中提取股票代码")

        # 每类固定抓 15 条，最终用 _sort_and_truncate 截断到 10 条
        scrape_per_category = 15

        result_holder = []

        def _run():
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self.UA,
                )

                # 首页建立 Cookie 会话（绕过反爬的关键）
                _seed_guba_session(context)

                all_articles = []
                for cat_name, tab, sort in self.CATEGORIES:
                    # 请求间隔 1.5~3 秒随机
                    if all_articles:  # 第一个分类前已经在 seed 中等待过
                        _random_delay(1.5, 3.0)

                    url = f"https://guba.eastmoney.com/list,{code},{tab},{sort}.html"
                    try:
                        page = context.new_page()
                        page.goto(url, wait_until="load", timeout=30000)
                        # 页面停留 2~4 秒模拟阅读
                        page.wait_for_timeout(random.uniform(2000, 4000))

                        articles = page.evaluate(f"""() => {{
                            const rows = document.querySelectorAll('tr.listitem');
                            const results = [];
                            let count = 0;
                            for (const row of rows) {{
                                if (count >= {scrape_per_category}) break;

                                const titleDiv = row.querySelector('div.title');
                                const updateDiv = row.querySelector('div.update');

                                if (!titleDiv || !updateDiv) continue;

                                const a = titleDiv.querySelector('a');
                                const title = a ? a.innerText.trim() : titleDiv.innerText.trim();
                                let href = a ? (a.getAttribute('href') || '') : '';

                                if (href.startsWith('//')) href = 'https:' + href;
                                else if (href.startsWith('/')) href = 'https://guba.eastmoney.com' + href;

                                const rawDate = updateDiv.innerText.trim();

                                count++;
                                results.push({{
                                    title: title,
                                    url: href,
                                    raw_date: rawDate,
                                }});
                            }}
                            return results;
                        }}""")

                        for a in articles:
                            full_date = self._infer_full_date(a["raw_date"])
                            all_articles.append({
                                "title": a["title"],
                                "url": a["url"],
                                "_known_date": full_date,
                                "_category": cat_name,
                            })

                        page.close()
                    except Exception as e:
                        print(f"[dcfin] {cat_name} 抓取失败: {e}", flush=True)
                        continue

                browser.close()
                result_holder.extend(all_articles)

        # 独立线程运行 Playwright（兼容 asyncio 调用方）
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=120)
        if t.is_alive():
            print("[dcfin] 搜索超时（>120s）", flush=True)

        # 上下界时间范围筛选
        filtered = self._filter_by_date(result_holder, start_date, end_date)

        # 排序截断：类别优先级 资讯>热门>公告，同类别按时间倒序，最多10条
        filtered = self._sort_and_truncate(filtered, max_total=10)

        return filtered

    @staticmethod
    def _infer_full_date(raw_date: str) -> str:
        """将 MM-DD HH:MM 补全为 YYYY-MM-DD HH:MM。"""
        raw = raw_date.strip()
        if not raw:
            return ""
        now = datetime.now()
        if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
            return raw
        try:
            dt_str = f"{now.year}-{raw}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
            except ValueError:
                return ""
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=now.year - 1)
        return dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _filter_by_date(articles: list[dict],
                        start_date: str | None = None,
                        end_date: str | None = None) -> list[dict]:
        """上下界时间范围筛选（精确到分钟）。"""
        if not start_date and not end_date:
            return articles
        now = datetime.now()

        def _parse_bound(text: str, is_end: bool = False) -> datetime | None:
            if not text:
                return None
            text = text.strip().replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(text, fmt)
                    if is_end and text.count(" ") == 0 and text.count("T") == 0:
                        dt = dt + timedelta(days=1) - timedelta(seconds=1)
                    return dt
                except ValueError:
                    continue
            return None

        start = _parse_bound(start_date)
        end = _parse_bound(end_date, is_end=True)
        if start is None:
            start = now - timedelta(days=365)
        if end is None:
            end = now
        if end > now:
            end = now

        kept = []
        for art in articles:
            date_str = art.get("_known_date", "")
            if not date_str:
                kept.append(art)
                continue
            art_dt = _parse_bound(date_str)
            if art_dt is None:
                kept.append(art)
                continue
            if start <= art_dt <= end:
                kept.append(art)
        return kept

    @staticmethod
    def _sort_and_truncate(articles: list[dict], max_total: int = 10) -> list[dict]:
        """按类别优先级 + 时间倒序排序，截断到 max_total 条。

        类别优先级：资讯(0) > 热门(1) > 公告(2)
        同类别内：按时间倒序（最新优先）
        """
        if not articles:
            return []

        CAT_PRIORITY = {"资讯": 0, "热门": 1, "公告": 2}

        def _sort_key(art):
            cat = art.get("_category", "公告")
            priority = CAT_PRIORITY.get(cat, 99)
            date_str = art.get("_known_date", "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    dt = datetime.min
            return (priority, -dt.timestamp())

        sorted_arts = sorted(articles, key=_sort_key)
        return sorted_arts[:max_total]
