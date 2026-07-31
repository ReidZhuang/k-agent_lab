#!/usr/bin/env python3
"""
抓取同花顺 F10 公司大事（近期重要事件）

用法:
    python3 fetch_10jqka_events.py [股票代码] [-d 天数]

示例:
    python3 fetch_10jqka_events.py 300395       # 默认取前30条
    python3 fetch_10jqka_events.py 300436 -d 3   # 最近3天（上下界包夹）
    python3 fetch_10jqka_events.py 300395 -d 7   # 最近7天
"""
import sys, os, argparse
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

STOCK_NAMES = {
    "300395": "菲利华",
    "300750": "宁德时代",
    "300436": "广生堂",
    "002821": "凯莱英",
}


def parse_args():
    parser = argparse.ArgumentParser(description="抓取同花顺 F10 近期重要事件")
    parser.add_argument("stock", nargs="?", default="300395", help="股票代码")
    parser.add_argument("-d", "--days", type=int, default=0,
                        help="日期过滤天数（上下界包夹，如 3=最近3天，0=不过滤）")
    parser.add_argument("-n", "--max", type=int, default=30,
                        help="最大条数 (默认 30)")
    return parser.parse_args()


def filter_by_days(events: list[dict], days: int) -> list[dict]:
    """日期过滤：上下界包夹，未来日期剔除。"""
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    now_str = now.strftime("%Y-%m-%d")
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    kept = []
    skipped_future = 0
    skipped_old = 0
    for e in events:
        d = e["date"]
        if d < cutoff_str:
            skipped_old += 1
        elif d > now_str:
            skipped_future += 1
        else:
            kept.append(e)

    if skipped_old or skipped_future:
        print(f"  [filter] {len(kept)} kept, {skipped_old} too old, "
              f"{skipped_future} future date (dropped)")
    return kept


async def main():
    args = parse_args()
    stock = args.stock
    filter_days = args.days
    limit = args.max

    OUTPUT = os.path.join(OUTPUT_DIR,
                          f"{stock}_events_{datetime.now().strftime('%Y%m%d')}.md")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        url = f"https://basic.10jqka.com.cn/{stock}/event.html"
        print(f"🔍 抓取: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 提取近期重要事件
        JS_CODE = """() => {
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

                results.push({ date: date, title: title, detail: detail, url: articleUrl });
            }
            return results;
        }"""
        all_events = await page.evaluate(JS_CODE)
        await browser.close()

    # 日期过滤
    if filter_days and filter_days > 0:
        all_events = filter_by_days(all_events, filter_days)
        tag = f"最近{filter_days}天"
    else:
        all_events = all_events
        tag = f"前{limit}条"

    # 取前N条
    events = all_events[:limit]

    name = STOCK_NAMES.get(stock, stock)
    print(f"✅ 共 {len(events)} 条近期重要事件（{tag}）")

    # 生成 Markdown
    lines = [
        f"# {name}({stock}) 近期重要事件（{tag}）\n",
        f"**抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n",
        f"**来源**: [{url}]({url})\n",
    ]

    for i, e in enumerate(events, 1):
        lines.append(f"### {i}. {e['date']} — {e['title']}\n")
        lines.append(f"**详情**: {e['detail']}\n")
        if e['url']:
            lines.append(f"**URL**: {e['url']}\n")
        else:
            lines.append(f"**URL**: 无\n")
        lines.append("")

    md = "\n".join(lines)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ 已保存: {OUTPUT}")

    # 终端打印
    print(f"\n{'='*80}")
    print(f"{name}({stock}) 近期重要事件（{tag}）")
    print(f"{'='*80}")
    for i, e in enumerate(events, 1):
        url_str = e['url'][:60] if e['url'] else '—'
        detail_str = e['detail'][:80] + ('…' if len(e['detail']) > 80 else '')
        print(f"\n{i:2d}. {e['date']} | {e['title']}")
        print(f"    详情: {detail_str}")
        print(f"    URL:  {url_str}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
