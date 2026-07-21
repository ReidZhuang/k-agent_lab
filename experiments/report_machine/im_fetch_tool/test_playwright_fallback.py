"""
测试：用 Playwright 抓同花顺/股吧页面正文
"""
import sys, json
from playwright.sync_api import sync_playwright

TEST_URLS = [
    ("同花顺-机构看好医药", "https://m.10jqka.com.cn/20260720/c678296500.shtml"),
    ("同花顺-券商观点", "https://m.10jqka.com.cn/20260720/c678286768.shtml"),
    ("同花顺-Norges减持", "https://m.10jqka.com.cn/20260717/c678259202.shtml"),
    ("同花顺-Schroders减持", "https://m.10jqka.com.cn/20260716/c678230833.shtml"),
    ("同花顺-小摩减持", "https://m.10jqka.com.cn/20260715/c678203040.shtml"),
    ("同花顺-龙虎榜", "https://m.10jqka.com.cn/20260717/c678263627.shtml"),
    ("东方财富股吧-医药周报1", "http://mguba.eastmoney.com/mguba/article/2/AP202607191827111720/"),
    ("东方财富股吧-医药周报2", "http://mguba.eastmoney.com/mguba/article/2/AP202607191827106326/"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )

    for label, url in TEST_URLS:
        print(f"\n{'='*60}")
        print(f"[{label}]")
        print(f"URL: {url}")
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # 尝试获取正文：多种策略
            body = ""

            # 策略1: 常见的正文容器
            for sel in [
                "article",
                "div.article-body",
                "div[class*='content']",
                "div[class*='article']",
                "div[class*='detail']",
                "div[class*='main-text']",
                "div[class*='text']",
                "div[class*='rich_media']",
                ".main",
                "#content",
            ]:
                el = page.query_selector(sel)
                if el:
                    t = el.inner_text().strip()
                    if len(t) > 100:
                        body = t
                        print(f"  找到正文 (选择器: {sel}), {len(t)} 字")
                        break

            # 策略2: 取 body 全部文本
            if not body:
                body = page.inner_text("body").strip()
                print(f"  取 body 全文, {len(body)} 字")

            # 策略3: 取可见文本（去掉空白/脚本）
            if not body or len(body) < 50:
                body = page.evaluate("""() => {
                    const clone = document.body.cloneNode(true);
                    // 去掉 script/style
                    clone.querySelectorAll('script,style,nav,footer,header,aside').forEach(e => e.remove());
                    return clone.innerText.trim();
                }""")
                print(f"  取 cleaned body, {len(body) if body else 0} 字")

            # 输出
            word_count = sum(1 for c in body if not c.isspace())
            if body and word_count >= 20:
                print(f"  ✅ {word_count} 字")
                # 显示前200字
                preview = body[:200].replace('\n', ' ').strip()
                print(f"  预览: {preview}...")
            else:
                print(f"  ⚠️ 内容过少: {word_count} 字")

        except Exception as e:
            print(f"  ❌ 错误: {e}")
        finally:
            page.close()

    browser.close()
