#!/usr/bin/env python3
"""同花顺个股资讯（news 页）抓取 → 可读 markdown

数据源：stockpage.10jqka.com.cn/{code}/news/（Next.js 页面，数据需渲染后滚动加载）
  - 列表：Playwright 渲染 + 滚动触发懒加载，提取标题/来源/时间/文章链接
  - 文章详情页 news.10jqka.com.cn/...shtml 为静态 HTML，可用 mail_tower 静态链路提正文

用法: python3 fetch_news.py [code] [--scrolls N] [--news-limit N]
输出: results/{code}_news_{YYYYMMDD}.md
"""
import argparse
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).resolve().parent / "results"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIME_RE = re.compile(r"(刚刚|\d+分钟前|\d+小时前|昨天 \d{2}:\d{2}|\d{2}-\d{2} \d{2}:\d{2}|\d{4}-\d{2}-\d{2} \d{2}:\d{2})")


def parse_item(text: str, href: str) -> dict | None:
    """从 a 标签文本解析 (标题, 来源, 时间)"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None
    # 研报条目前缀形如 "研报\n更多\n标题"，逐行清理取首个真实标题
    title = ""
    for l in lines:
        l = re.sub(r"^(研报|更多)\s*", "", l)
        if l:
            title = l
            break
    if not title or len(title) < 8:
        return None
    # 来源 + 时间：从后往前找时间行（"来源 6小时前" 或独立时间行，来源在其前一行）
    time_str = source = ""
    for i in range(len(lines) - 1, -1, -1):
        tm = TIME_RE.search(lines[i])
        if tm:
            time_str = tm.group(1)
            source = re.sub(TIME_RE, "", lines[i]).strip()
            if not source and i > 0:
                source = lines[i - 1]
            break
    if source == title:
        source = ""
    return {"title": title, "source": source, "time": time_str, "href": href}


def main():
    ap = argparse.ArgumentParser(description="同花顺个股资讯抓取 → markdown")
    ap.add_argument("code", nargs="?", default="002821", help="股票代码，默认 002821")
    ap.add_argument("--scrolls", type=int, default=8, help="滚动次数，默认 8")
    ap.add_argument("--news-limit", type=int, default=50, help="输出条目上限，默认 50")
    args = ap.parse_args()

    code = args.code
    url = f"https://stockpage.10jqka.com.cn/{code}/news/"
    stock_name = code

    # ── Playwright 渲染 + 滚动加载 ──
    items, seen = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=UA)
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(6000)
        m = re.search(r"([^()（）\s]+)\(?\s*" + code, page.title() or "")
        if m:
            stock_name = m.group(1)
        for _ in range(args.scrolls):
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(700)
            if len(seen) >= args.news_limit * 3:
                break
        raw = page.eval_on_selector_all(
            "a",
            """els => els.map(a => ({
                href: a.href,
                text: a.innerText.trim(),
                title: a.getAttribute('title') || ''
            })).filter(x => x.href.includes('news.10jqka.com.cn'))""",
        )
        browser.close()

    # ── 解析 + 去重（滚动可能重复）──
    for r in raw:
        text = r["title"] or r["text"]
        it = parse_item(text, r["href"])
        if not it or it["href"] in seen:
            continue
        seen.add(it["href"])
        items.append(it)
        if len(items) >= args.news_limit:
            break

    # ── 分组：研报（/field/sr/ 路径）vs 新闻 ──
    news, research = [], []
    for it in items:
        (research if "/field/sr/" in it["href"] else news).append(it)

    # ── 组装 markdown ──
    def table(rows, start):
        lines = ["| # | 标题 | 来源 | 时间 | 链接 |",
                 "|--:|:-----|:-----|:-----|:-----|"]
        for i, it in enumerate(rows, start):
            link = f"[查看]({it['href']})"
            lines.append(f"| {i} | {it['title']} | {it['source']} | {it['time']} | {link} |")
        return lines

    parts = [f"# {stock_name}（{code}）— 个股资讯",
             "",
             f"> 数据源：{url}（Playwright 渲染 + 滚动加载）",
             f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
             f"> 共 {len(items)} 条（新闻 {len(news)} + 研报 {len(research)}）",
             "",
             "## 最新资讯", ""]
    parts += table(news, 1)
    if research:
        parts += ["", "## 研报", ""]
        parts += table(research, len(news) + 1)
    md = "\n".join(parts) + "\n"

    OUT_DIR.mkdir(exist_ok=True)
    out_file = OUT_DIR / f"{code}_news_{datetime.now():%Y%m%d}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"已生成: {out_file}（{len(md)} 字符）")
    print(f"  新闻 {len(news)} 条 + 研报 {len(research)} 条")


if __name__ == "__main__":
    main()
