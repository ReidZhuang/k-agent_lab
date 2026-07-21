"""
实验：百度股市通个股资讯爬取
输入股票代码 → 爬取今日全部资讯 → 输出结构化文档（JSON + Markdown）

用法：
    python3 baidu_stock_news.py 300436          # 今日资讯
    python3 baidu_stock_news.py 300436 2026-07-21 2026-07-21  # 指定日期
    python3 baidu_stock_news.py 600519 --report  # 生成 Markdown 报告
"""
import sys, json, os, argparse
from datetime import datetime, date
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"

def fetch_stock_news(code: str, page_limit: int = 3) -> list[dict]:
    """用 Playwright 打开百度股市通个股页，提取全部资讯"""
    url = f"https://finance.baidu.com/stock/ab-{code}"
    all_news = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # 拦截 sentimentlist API 响应
        def on_response(resp):
            if "sentimentlist" in resp.url:
                try:
                    data = resp.json()
                    items = (data.get("Result", [{}])[0].get("TplData", {})
                             .get("aiSentimentXcxListInfo", {})
                             .get("sentimentListInfo", []))
                    if items:
                        all_news.extend(items)
                        print(f"  → 捕获 API page，新增 {len(items)} 条，累计 {len(all_news)}")
                except Exception as e:
                    print(f"  ⚠ API 解析: {e}")

        page.on("response", on_response)

        # 访问页面
        print(f"[1/3] 访问 {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # 点"资讯"标签
        print("[2/3] 点击「资讯」标签")
        clicked = False
        for tab in page.query_selector_all("a, span, div[class*=tab]"):
            if (tab.inner_text() or "").strip() == "资讯":
                tab.click()
                clicked = True
                page.wait_for_timeout(5000)
                break
        if not clicked:
            print("  ⚠ 未找到「资讯」标签")

        # 尝试翻页获取更多（模拟点击「下一页」或滚动）
        print(f"[3/3] 尝试翻页 (最多 {page_limit} 次)")
        for pn in range(1, page_limit):
            # 先看看是否有"加载更多"按钮
            load_more = None
            for btn in page.query_selector_all("button, a, span, div[class*=more]"):
                t = (btn.inner_text() or "").strip()
                if any(k in t for k in ["更多", "下一页", "加载"]):
                    load_more = btn
                    break
            if load_more:
                try:
                    load_more.click()
                    page.wait_for_timeout(3000)
                    print(f"  → 点击「{load_more.inner_text().strip()}」")
                except Exception:
                    # 如果没有按钮，滚动到底部触发无限加载
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(3000)
                    print(f"  → 滚动第 {pn} 次")
            else:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)
                print(f"  → 滚动第 {pn} 次")

        browser.close()

    return all_news


def filter_by_date(news: list[dict], start: date, end: date) -> list[dict]:
    """按日期范围过滤"""
    filtered = []
    for n in news:
        ts = n.get("publishTime")
        if ts:
            try:
                pub_date = datetime.fromtimestamp(int(ts)).date()
            except (ValueError, TypeError):
                print(f"  ⚠ 跳过无法解析的日期: {ts}")
                continue
            if start <= pub_date <= end:
                filtered.append(n)
    return filtered


def beautify(news: list[dict]) -> list[dict]:
    """标准化输出字段，去重"""
    benefit_map = {0: "中性", 1: "利好", 2: "利空"}
    seen = set()
    result = []
    for n in news:
        nid = n.get("news_id", "")
        if nid in seen:
            continue
        seen.add(nid)
        ts = n.get("publishTime")
        if ts:
            try:
                pub_time = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pub_time = "未知"
        else:
            pub_time = "未知"
        bt = n.get("benefitType", -1)
        # benefitType 可能是字符串
        try:
            bt_int = int(bt)
        except (ValueError, TypeError):
            bt_int = -1
        result.append({
            "title": n.get("title", ""),
            "abstract": n.get("abstract", ""),
            "provider": n.get("provider", ""),
            "publish_time": pub_time,
            "sentiment": benefit_map.get(bt_int, "未知"),
            "source_url": n.get("originUrl", ""),
            "news_id": nid,
        })
    return result


def generate_report(code: str, news: list[dict], report_path: str):
    """生成可读 Markdown 报告"""
    lines = []
    lines.append(f"# {code} 个股资讯报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"资讯总数: {len(news)}")
    lines.append("")

    # 按日期分组
    by_date = {}
    for n in news:
        d = n.get("publish_time", "未知")[:10]
        by_date.setdefault(d, []).append(n)

    for d in sorted(by_date.keys(), reverse=True):
        items = by_date[d]
        lines.append(f"## {d} ({len(items)} 条)")
        lines.append("")
        for n in items:
            lines.append(f"### {n['title']}")
            lines.append(f"")
            lines.append(f"- **来源**: {n['provider']}")
            lines.append(f"- **时间**: {n['publish_time']}")
            lines.append(f"- **影响**: {n['sentiment']}")
            lines.append(f"- **原文**: {n['source_url']}")
            lines.append(f"")
            lines.append(f"{n['abstract']}")
            lines.append(f"")
            lines.append("---")
            lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  📄 Markdown 报告: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="百度股市通个股资讯爬取实验")
    parser.add_argument("stock_code", help="股票代码，如 300436")
    parser.add_argument("start_date", nargs="?", help="起始日期 YYYY-MM-DD，默认今天")
    parser.add_argument("end_date", nargs="?", help="截止日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--pages", type=int, default=3, help="翻页尝试次数 (默认 3)")
    parser.add_argument("--report", action="store_true", help="同时生成 Markdown 报告")
    args = parser.parse_args()

    code = args.stock_code
    today = date.today()
    start = date.fromisoformat(args.start_date) if args.start_date else today
    end = date.fromisoformat(args.end_date) if args.end_date else today

    print(f"🔍 {code} | {start} ~ {end}")

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 第1步：爬取
    print("\n=== 第1步：爬取原始数据 ===")
    raw_news = fetch_stock_news(code, page_limit=args.pages)
    print(f"\n原始数据合计: {len(raw_news)} 条")

    # 第2步：日期过滤
    print("\n=== 第2步：日期过滤 ===")
    filtered = filter_by_date(raw_news, start, end)
    print(f"日期范围内: {len(filtered)} 条")

    # 第3步：格式化
    print("\n=== 第3步：格式化输出 ===")
    news = beautify(filtered)

    # 第4步：保存 JSON
    json_path = os.path.join(OUTPUT_DIR, f"{code}_{start}_{end}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "stock_code": code,
            "date_range": f"{start} ~ {end}",
            "total": len(news),
            "news": news,
        }, f, ensure_ascii=False, indent=2)
    print(f"  📊 JSON 数据: {json_path}")

    # 第5步：可选 Markdown
    if args.report or not args.start_date:
        md_path = os.path.join(OUTPUT_DIR, f"{code}_{start}_{end}_report.md")
        generate_report(code, news, md_path)

    # 终端摘要
    print(f"\n=== 摘要 ===")
    for n in news[:5]:
        print(f"  [{n['sentiment']}] {n['title'][:60]}")
        print(f"    {n['provider']} | {n['publish_time']}")
    if len(news) > 5:
        print(f"  ... 还有 {len(news)-5} 条")

    print(f"\n✅ 完成! 共 {len(news)} 条资讯")


if __name__ == "__main__":
    main()
