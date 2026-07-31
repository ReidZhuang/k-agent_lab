"""thsnews — 同花顺个股资讯（stockpage news 页）搜索后端

数据源: stockpage.10jqka.com.cn/{code}/news/
  - 列表为 Next.js 页面，需 Playwright 渲染 + 滚动加载懒加载
  - 条目结构: <a href="news.10jqka.com.cn/{date}/c{id}.shtml">
               <h3>标题</h3>
               <span>来源</span><span>相对时间</span>
  - 研报条目 URL 含 /field/sr/ 路径

流程（沿用 thsfin 骨架）:
  - 子线程跑 Playwright，100s 硬超时防卡死
  - 2 次重试（失败等 1~2s 随机延迟）
  - 页面 goto 30s 超时；先确认 h3 渲染再提取（防渲染中断误报空）
  - 全部失败返回空列表（不抛异常）
  - 超时兜底：每次启动用唯一 user-data-dir（/tmp/thsnews_profile_xxx），
    主线程 join 超时后按 profile 精确 pgrep 强杀 chromium 进程，
    timed_out 标志阻止子线程重试，避免孤儿浏览器泄漏
    （线程本身无法终止，杀浏览器使其 Playwright 调用抛异常随即退出）

返回字段:
  - title: 文章标题（来源已剥离）
  - url: 文章链接
  - snippet: ""（留空）
  - _known_date: 绝对时间 "YYYY-MM-DD HH:MM"
  - date_confidence: "high"（真实分钟）| "medium"（相对时间推算）
  - _category: "资讯" | "研报"
"""
import os
import random
import re
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 相对时间正则（按出现频次）
_RE_SEC_AGO = re.compile(r"(\d+)秒前")
_RE_MIN_AGO = re.compile(r"(\d+)分钟前")
_RE_HOUR_AGO = re.compile(r"(\d+)小时前")
_RE_YESTERDAY = re.compile(r"昨天\s*(\d{2}):(\d{2})")
_RE_MMDD = re.compile(r"(\d{2})-(\d{2})\s*(\d{2}):(\d{2})")
# 兜底关键词：解析不出数值但含相对时间标记 → 今天 00:00
_RE_REL_KEYWORD = re.compile(r"秒|分钟|小时")


def _parse_relative_time(text: str, url_date: str | None,
                         now: datetime) -> tuple[str, str]:
    """
    相对时间 → 绝对时间。返回 (datetime_str, confidence)。

    规则:
      - "昨天 HH:MM" / "MM-DD HH:MM" → 真实分钟，high
      - "N分钟前" / "N小时前" / "刚刚" → now - 间隔 推算，medium
      - 推算跨午夜时用 URL 中的发布日期（/20260731/）校正归属日
      - 全部失败 → URL 日期 00:00，medium
    """
    def fmt(d: datetime) -> str:
        return d.strftime("%Y-%m-%d %H:%M")

    m = _RE_YESTERDAY.search(text)
    if m:
        d = (now - timedelta(days=1)).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return fmt(d), "high"
    m = _RE_MMDD.search(text)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        year = now.year
        # MM-DD 晚于今天（跨年残留），归属去年
        if (mm, dd) > (now.month, now.day):
            year -= 1
        d = datetime(year, mm, dd, int(m.group(3)), int(m.group(4)))
        return fmt(d), "high"

    delta = None
    m = _RE_SEC_AGO.search(text)
    if m:
        delta = timedelta(seconds=int(m.group(1)))
    else:
        m = _RE_MIN_AGO.search(text)
        if m:
            delta = timedelta(minutes=int(m.group(1)))
        else:
            m = _RE_HOUR_AGO.search(text)
            if m:
                delta = timedelta(hours=int(m.group(1)))
            else:
                delta = timedelta(0) if "刚刚" in text else None
    if delta is not None:
        d = now - delta
        # 跨午夜校正：推算日期与 URL 发布日不一致时，以 URL 日期为准
        if url_date:
            d_url = datetime.strptime(url_date, "%Y-%m-%d")
            if (d_url - d).days == 1:
                d = d_url.replace(hour=d.hour, minute=d.minute, second=0, microsecond=0)
        return fmt(d), "medium"

    # 兜底：解析不出数值，但文本含相对时间关键词（秒/分钟/小时）→ 今天 00:00
    if _RE_REL_KEYWORD.search(text):
        return f"{now:%Y-%m-%d} 00:00", "medium"

    # 最终兜底：URL 发布日期 + 00:00
    if url_date:
        return f"{url_date} 00:00", "medium"
    return fmt(now), "medium"


class ThsnewsBackend:
    """同花顺个股资讯搜索后端（thsfin 骨架 + 滚动加载新闻流）。"""

    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行同花顺个股资讯查询。

        Args:
            query: 股票代码（如 "002821"）
            max_results: 最大返回条数
            start_date: 起始日期 YYYY-MM-DD（搜索引擎层日期过滤）
            end_date: 截止日期 YYYY-MM-DD

        Returns:
            [{title, url, snippet, _known_date, date_confidence, _category}, ...]
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "thsnews 引擎需要 playwright: "
                "pip install playwright && playwright install chromium"
            )

        code = re.sub(r'[^0-9]', '', query.strip())
        if not code:
            raise ValueError(f"无法从 '{query}' 中提取股票代码")

        # 滚动轮数随 max_results 增长（每轮约 3~4 条），上限 15 轮保底
        scrolls = min(15, max(5, max_results // 3 + 2))

        result_holder = []
        _exc_info = []
        # 主/子线程共享状态：browser_tag 供超时后按 profile 精确强杀；
        # timed_out 阻止子线程超时后重试
        shared = {"browser_tag": None, "timed_out": False}

        def _run():
            for attempt in range(2):
                if shared["timed_out"]:
                    return  # 主线程已超时放弃，不再重试
                try:
                    # 唯一 user-data-dir：超时后主线程可按目录精确杀自己的浏览器
                    profile = f"/tmp/thsnews_profile_{uuid.uuid4().hex[:8]}"
                    shared["browser_tag"] = profile
                    print(f"[thsnews] {code} 启动浏览器（profile={profile}）", flush=True)
                    with sync_playwright() as p:
                        context = p.chromium.launch_persistent_context(
                            profile,
                            headless=True,
                            viewport={"width": 1920, "height": 1080},
                            user_agent=UA,
                        )
                        page = context.pages[0] if context.pages else context.new_page()
                        url = f"https://stockpage.10jqka.com.cn/{code}/news/"
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)

                        # 防渲染中断：确认新闻容器（h3）出现，未出现等一轮
                        for _ in range(2):
                            n_h3 = page.evaluate(
                                "document.querySelectorAll('h3').length")
                            if n_h3 > 0:
                                break
                            page.wait_for_timeout(3000)

                        # 滚动触发懒加载
                        for _ in range(scrolls):
                            page.mouse.wheel(0, 1800)
                            page.wait_for_timeout(700)

                        items = page.evaluate(f"""() => {{
                            const seen = new Set();
                            const results = [];
                            let seq = 0;
                            for (const a of document.querySelectorAll('a')) {{
                                const href = a.href || '';
                                if (!href.includes('news.10jqka.com.cn')) continue;
                                if (seen.has(href)) continue;
                                seen.add(href);
                                const h3 = a.querySelector('h3');
                                if (!h3) continue;
                                // 时间统一在 div.text-muted-foreground 里（新闻/研报为
                                // "来源 时间"两段，公告条目为纯时间），整段交给正则匹配
                                const metaDiv = a.querySelector('div.text-muted-foreground');
                                const timeText = (metaDiv ? metaDiv.innerText : '').trim();
                                const title = h3.innerText.trim().replace(/\\s+/g, ' ');
                                if (!title || title.length < 8) continue;
                                seq++;
                                results.push({{
                                    id: `a_${{String(seq).padStart(2, '0')}}`,
                                    title: title,
                                    time_text: timeText,
                                    url: href,
                                }});
                                if (seq >= {max(max_results * 2, 20)}) break;
                            }}
                            return results;
                        }}""")
                        context.close()
                        print(f"[thsnews] {code} 提取 {len(items)} 条原始条目（滚动 {scrolls} 轮）", flush=True)

                        # 时间换算 + 分类 + 字段组装
                        now = datetime.now()
                        out = []
                        for it in items:
                            m = re.search(r"/(\d{8})/", it["url"])
                            url_date = (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
                                        if m else None)
                            ts, conf = _parse_relative_time(it["time_text"], url_date, now)
                            # URL 路径分流：sr=研报流，sn=公告流，其余为资讯
                            if "/field/sr/" in it["url"]:
                                category = "研报"
                            elif "/field/sn/" in it["url"]:
                                category = "公告"
                            else:
                                category = "资讯"
                            out.append({
                                "id": it["id"],
                                "_known_date": ts,
                                "date_confidence": conf,
                                "title": it["title"],
                                "snippet": "",
                                "url": it["url"],
                                "_category": category,
                            })

                        # 日期过滤（搜索引擎层）
                        filtered = self._filter_by_date(out, start_date, end_date)
                        result_holder.extend(filtered[:max_results])
                        return  # success

                except Exception as e:
                    if shared["timed_out"]:
                        return  # 主线程已放弃且已杀浏览器，直接退出
                    _exc_info.append(e)
                    if attempt == 0:
                        wait = 1 + random.random()
                        print(f"[thsnews] Playwright 失败（{type(e).__name__}），{wait:.1f}s 后重试: {code}", flush=True)
                        time.sleep(wait)
                    else:
                        raise

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=100)
        if t.is_alive():
            # 超时：子线程仍卡在后台。线程本身无法强制终止，但可以按唯一
            # user-data-dir（profile）精确杀掉它启动的 chromium 进程 ——
            # 杀掉后子线程的 Playwright 调用会抛异常，配合 timed_out 标志
            # 直接退出，避免孤儿 chromium 泄漏
            profile = shared.get("browser_tag")
            killed = 0
            if profile:
                try:
                    out = subprocess.run(["pgrep", "-f", profile],
                                         capture_output=True, text=True, timeout=5)
                    for pid in out.stdout.strip().splitlines():
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                            killed += 1
                        except (OSError, ValueError):
                            pass
                except Exception:
                    pass
            shared["timed_out"] = True
            print(f"[thsnews] {code} join 超时(100s)，已强杀 {killed} 个浏览器进程（profile={profile or 'unknown'}），返回空列表", flush=True)
            return []
        if not result_holder and _exc_info:
            # 全部重试失败，打印日志但不抛异常（返回空列表）
            print(f"[thsnews] {code} Playwright 全部重试失败: {_exc_info[-1]}", flush=True)
        return result_holder[:max_results]

    @staticmethod
    def _filter_by_date(events: list[dict],
                        start_date: str | None = None,
                        end_date: str | None = None) -> list[dict]:
        """日期过滤：上下界包夹（_known_date 为 "YYYY-MM-DD HH:MM"）。"""
        if not start_date and not end_date:
            return events

        now = datetime.now()
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else now - timedelta(days=365)
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else now

        # 如果 end_date 只有日期，扩大到当天结束
        if end_date and end_date.strip().replace("T", " ").count(" ") == 0:
            end = end + timedelta(days=1) - timedelta(seconds=1)

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d %H:%M:%S")

        kept = []
        for e in events:
            d = e.get("_known_date", "")
            if start_str <= d <= end_str:
                kept.append(e)

        return kept
