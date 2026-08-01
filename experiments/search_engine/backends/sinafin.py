"""sinafin 搜索后端 — 个股新闻 + 公司公告（新浪财经 httpx 直抓）

数据来源：
  - 资讯：直接抓取新浪财经个股新闻页（vCB_AllNewsStock）
  - 公告：直接抓取新浪财经公司公告页（vCB_AllBulletin）

无需额外服务，httpx 直连新浪。

用法:
    from search_engine import search
    results = search("300750", engine="sinafin")
    results = search("300395", engine="sinafin", start_date="2026-07-20")

返回格式: [{title, url, snippet, _known_date, _category}, ...]
    _category: "资讯" | "公告"
    _known_date: 资讯精确到分钟（YYYY-MM-DD HH:MM），公告仅日期
"""
import re, time, random, os, json
import httpx
from .base import SearchBackend

# ── 新浪财经 URL ──
_NEWS_URL_PAGE1 = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{sina_code}.phtml"
_BULLETIN_URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/{code}.phtml"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 从 mail_tower config.json 读取连接池配置（若存在），否则使用默认值
_MT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "mail_tower", "config", "config.json"
)
_HTTP_POOL_CFG = {"max_keepalive": 10, "max_connections": 50}
_HTTP_TIMEOUT = 15
try:
    with open(_MT_CONFIG_PATH) as _f:
        _mt_cfg = json.load(_f)
    _sinafin_cfg = _mt_cfg.get("search", {}).get("sinafin", {})
    _pool_cfg = _sinafin_cfg.get("http_pool", {})
    _HTTP_POOL_CFG["max_keepalive"] = _pool_cfg.get("max_keepalive_connections", 10)
    _HTTP_POOL_CFG["max_connections"] = _pool_cfg.get("max_connections", 50)
    _HTTP_TIMEOUT = _mt_cfg.get("extraction", {}).get("timeout", 15)
except Exception:
    pass

# 共享连接池（惰性创建，避免 uvicorn fork 后继承半初始化状态）
_HTTP_CLIENT: httpx.Client | None = None

def _get_client() -> httpx.Client:
    """惰性创建共享 httpx 客户端，确保在 worker 进程的 event loop 中初始化。

    trust_env=False 确保不读取代理环境变量：
    - search_engine 中除 DDG 外所有后端都直连国内金融站点
    - 只有 DDG（DuckDuckGo）需要走 Clash 代理
    - 高并发下通过代理访问 sinafin 会导致 ConnectionResetError(104)
    """
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=_HTTP_TIMEOUT,
            trust_env=False,  # 禁用代理，直连 sinafin
            limits=httpx.Limits(
                max_keepalive_connections=_HTTP_POOL_CFG["max_keepalive"],
                max_connections=_HTTP_POOL_CFG["max_connections"],
            ),
        )
    return _HTTP_CLIENT


class SinaFinBackend(SearchBackend):
    """个股新闻 + 公司公告（新浪财经 httpx 直抓）。"""

    def search(self, query: str, max_results: int = 3,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行个股搜索，返回资讯+公告混合列表。

        Args:
            query: 股票代码（如 "300750"）或新浪格式（如 "sz300750"）
            start_date: 起始时间 YYYY-MM-DD 或 YYYY-MM-DD HH:MM
            end_date: 截止时间同上

        Returns:
            [{title, url, snippet, _known_date, _category}, ...]
        """
        sina_code = self._resolve_code(query.strip())
        code_num = re.sub(r'[a-z]', '', sina_code)

        # 1. 抓取资讯（直接爬新浪新闻页）
        news_list = self._fetch_news(sina_code, start_date, end_date)

        # 2. 抓取公告（直接爬新浪公告页）
        bulletins = self._fetch_bulletins(code_num, start_date, end_date)

        return news_list + bulletins

    # ── 股票代码解析 ──

    @staticmethod
    def _resolve_code(query: str) -> str:
        """转为新浪格式: 300750 → sz300750, sz300750 透传, 300750.SZ → sz300750"""
        q = query.strip()
        if re.match(r'^(sh|sz|bj)\d{6}$', q):
            return q
        if "." in q:
            parts = q.split(".")
            prefix = {"sh": "sh", "sz": "sz", "bj": "bj"}.get(parts[1].lower(), "sz")
            return f"{prefix}{parts[0]}"
        if re.match(r'^\d{6}$', q):
            prefix = {"6": "sh", "0": "sz", "3": "sz"}.get(q[0], "sz")
            return f"{prefix}{q}"
        raise ValueError(f"无法解析股票代码: {query}")

    # ── 资讯抓取 ──

    def _fetch_news(self, sina_code: str,
                    start_date: str | None,
                    end_date: str | None) -> list[dict]:
        """从新浪个股新闻页抓取资讯，返回前 10 条。"""
        url = _NEWS_URL_PAGE1.format(sina_code=sina_code)
        try:
            html = self._fetch_page(url)
            items = self._parse_news_list(html)
        except Exception:
            return []

        results = []
        for item in items:
            full_date = f"{item['date']} {item['time']}".strip()
            if not self._in_range(full_date, start_date, end_date):
                continue
            results.append({
                "title": item["title"],
                "url": item["url"],
                "snippet": full_date,
                "_known_date": full_date,
                "_category": "资讯",
            })
            if len(results) >= 10:
                break
        return results

    def _fetch_page(self, url: str) -> str:
        """用共享连接池抓取页面，失败时重试最多 2 次。

        ConnectionResetError(104) 在高并发时偶发出现，原因是 sinafin 服务端/Clash 代理
        同时处理太多连接会主动 RST。连接池 + 惰性重试可以大幅降低失败率。
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = _get_client().get(url)
                resp.encoding = "gb2312"
                return resp.text
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
                if attempt < max_retries:
                    wait = 1.0 + random.uniform(0, 1.0)
                    print(f"[sinafin] 连接失败（{type(e).__name__}），{wait:.1f}s 后重试第 {attempt+1} 次: {url[:50]}", flush=True)
                    time.sleep(wait)
                else:
                    raise

    @staticmethod
    def _parse_news_list(html: str) -> list[dict]:
        """解析新浪个股新闻页 <div class='datelist'>。"""
        dl = re.search(r'<div\s+class="datelist"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not dl:
            return []
        pat = re.compile(
            r"(\d{4}-\d{2}-\d{2})" r"(?:\s|&nbsp;)+" r"(\d{2}:\d{2})"
            r"(?:\s|&nbsp;)+"
            r'<a\s+[^>]*href=(["\'])(.*?)\3[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        news = []
        for m in pat.finditer(dl.group(1)):
            url = m.group(4)
            title = re.sub(r"<[^>]+>", "", m.group(5)).strip()
            if not title or len(title) < 3:
                continue
            if url.startswith("//"):
                url = "https:" + url
            news.append({"title": title, "url": url, "date": m.group(1), "time": m.group(2)})
        return news

    # ── 公告抓取 ──

    def _fetch_bulletins(self, code: str,
                         start_date: str | None,
                         end_date: str | None) -> list[dict]:
        """从新浪公司公告页抓取公告，返回前 10 条。"""
        url = _BULLETIN_URL.format(code=code)
        try:
            html = self._fetch_page(url)
        except Exception:
            return []

        dl = re.search(r'<div\s+class="datelist"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not dl:
            return []

        pat = re.compile(
            r"(\d{4}-\d{2}-\d{2})" r"(?:&nbsp;|\s)+"
            r"<a\s+[^>]*href=([\"'])(.*?)\2[^>]*>(.*?)</a>", re.DOTALL,
        )

        results = []
        for date, _, url_path, title in pat.findall(dl.group(1)):
            if url_path.startswith("//"):
                url = "https:" + url_path
            elif url_path.startswith("/"):
                url = "https://vip.stock.finance.sina.com.cn" + url_path
            else:
                url = url_path

            if not self._in_range(date, start_date, end_date):
                continue

            results.append({
                "title": title.strip(),
                "url": url,
                "snippet": date,
                "_known_date": date,
                "_category": "公告",
            })
            if len(results) >= 10:
                break
        return results

    # ── 时间过滤 ──

    @staticmethod
    def _in_range(full_date: str,
                  start_date: str | None,
                  end_date: str | None) -> bool:
        """检查日期时间是否在过滤范围内。

        资讯有完整时间（YYYY-MM-DD HH:MM）→ 精确到分钟比较。
        公告仅日期（YYYY-MM-DD）→ 边界带时间时截取日期部分，按天比较。
        """
        if not start_date and not end_date:
            return True
        if not full_date:
            return True

        sd = start_date[:10] if start_date else None
        ed = end_date[:10] if end_date else None

        if " " in full_date and (" " in (start_date or "") or " " in (end_date or "")):
            if start_date and full_date < start_date:
                return False
            if end_date and full_date > end_date:
                return False
            return True

        d = full_date[:10]
        if sd and d < sd:
            return False
        if ed and d > ed:
            return False
        return True
