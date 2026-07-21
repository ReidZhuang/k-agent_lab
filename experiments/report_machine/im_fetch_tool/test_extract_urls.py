"""
测试：百度资讯原文 URL 能否用 v3.0 的提取管道成功获取正文
"""
import sys, os, json, asyncio

# 让 Python 能找到 v3.0 的模块
V3_DIR = "/home/stockagent/project_space/research/experiments/web_bot_agent/version_3.0"
if V3_DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(V3_DIR))
    sys.path.insert(0, V3_DIR)

from core import _fetch_single, _extract_body_from_html, truncate_body, has_excessive_whitespace, clean_excessive_whitespace

# 从报告里提取的所有原文 URL
TEST_URLS = [
    # 07-21
    ("凯莱英港股涨", "https://stock.stockstar.com/RB2026072100037478.shtml&source=bdgst"),
    ("葛兰发声", "https://emwap.eastmoney.com/info/detail/202607213815528753"),
    # 07-20
    ("机构看好医药", "https://m.10jqka.com.cn/20260720/c678296500.shtml#refCountId=news_5db00164_52"),
    ("券商观点", "https://m.10jqka.com.cn/20260720/c678286768.shtml#refCountId=news_5db00164_52"),
    ("主力资金卖出", "https://stock.stockstar.com/RB2026072000002903.shtml&source=bdgst"),
    # 07-19
    ("杠杆资金买入", "https://stock.stockstar.com/IG2026071900010288.shtml&source=bdnews"),
    ("机构龙虎榜", "https://stock.stockstar.com/SS2026071900001860.shtml&source=bdnews"),
    ("医药周报1", "http://mguba.eastmoney.com/mguba/article/2/AP202607191827111720/"),
    ("医药周报2", "http://mguba.eastmoney.com/mguba/article/2/AP202607191827106326/"),
    # 07-17
    ("Norges减持", "https://m.10jqka.com.cn/20260717/c678259202.shtml#refCountId=news_5db00164_52"),
    ("异常波动", "https://stock.stockstar.com/RB2026071700000085.shtml&source=bdgst"),
    # 07-16
    ("Schroders减持", "https://m.10jqka.com.cn/20260716/c678230833.shtml#refCountId=news_5db00164_52"),
    # 07-15
    ("小摩减持", "https://m.10jqka.com.cn/20260715/c678203040.shtml#refCountId=news_5db00164_52"),
    ("涨停龙虎榜", "https://stock.stockstar.com/IG2026071500034848.shtml&source=bdnews"),
    ("融资净买入", "https://stock.stockstar.com/RB2026071500011049.shtml&source=bdgst"),
    ("异常波动公告", "https://emwap.eastmoney.com/info/detail/202607153807657675"),
    ("一周龙虎榜", "https://m.10jqka.com.cn/20260717/c678263627.shtml#refCountId=news_5db00164_52"),
]

async def test_one(label, url):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"URL: {url[:90]}")

    # 下载
    html, err = await _fetch_single(url)
    if err:
        print(f"  ❌ 下载失败: {err}")
        return {"label": label, "url": url, "status": "fetch_error", "error": err}

    print(f"  下载 OK: {len(html)} bytes")

    # 提取正文
    body_text, meta_date, paragraphs = _extract_body_from_html(html)

    # 空白治理
    if body_text and has_excessive_whitespace(body_text):
        body_text = clean_excessive_whitespace(body_text)
        print(f"  空白治理: 已触发")

    # 截断
    body_text, truncated = truncate_body(body_text)

    word_count = sum(1 for c in body_text if not c.isspace())

    if body_text and word_count >= 20:
        print(f"  ✅ 提取成功: {word_count} 字 (去空白), truncated={truncated}")
        print(f"  正文预览: {body_text[:200]}...")
        return {"label": label, "url": url, "status": "ok", "word_count": word_count, "truncated": truncated}
    else:
        print(f"  ⚠️ 提取内容过少: {word_count} 字")
        return {"label": label, "url": url, "status": "too_short", "word_count": word_count}

async def main():
    results = []
    for label, url in TEST_URLS:
        r = await test_one(label, url)
        results.append(r)

    # 汇总
    ok = sum(1 for r in results if r["status"] == "ok")
    short = sum(1 for r in results if r["status"] == "too_short")
    failed = sum(1 for r in results if r["status"] == "fetch_error")

    print(f"\n{'='*60}")
    print(f"汇总: 总计 {len(results)} 个 URL")
    print(f"  ✅ 成功提取: {ok}")
    print(f"  ⚠️ 内容过少: {short}")
    print(f"  ❌ 下载失败: {failed}")

    # 按来源统计
    from collections import Counter
    domains = Counter()
    for r in results:
        from urllib.parse import urlparse
        domain = urlparse(r["url"]).netloc
        domains[domain] += 1

    print(f"\n来源分布:")
    for d, c in domains.most_common():
        print(f"  {d}: {c} 个 URL")

if __name__ == "__main__":
    asyncio.run(main())
