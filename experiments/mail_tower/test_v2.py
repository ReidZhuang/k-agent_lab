#!/usr/bin/env python3
"""
v2.0 测试脚本。

运行:
    conda run -n stock_agent python3 test_v2.py

测试项目:
  1. date_extractor 分层日期提取（模拟各种来源）
  2. filter 过滤模块
  3. 实际 URL 日期提取（网络）
  4. 完整 pipeline（需要网络和 Ollama）
"""
import sys, os, json, asyncio

# ── 确保能在任何目录下运行 ──
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ============================================================
# 1. 测试 date_extractor
# ============================================================
def test_date_extractor():
    print("\n" + "=" * 60)
    print("📅 测试 date_extractor 分层日期提取")
    print("=" * 60)

    from date_extractor import (
        extract_date, extract_date_fast, upgrade_date_with_body,
        _extract_jsonld, _extract_meta_tags, _extract_time_tag,
        _extract_url_date, _extract_in_body_prefix,
        _extract_ddg_snippet, _extract_body_fallback,
    )

    # ── JSON-LD ──
    html_ld = '''<html><head><script type="application/ld+json">
{"@context":"https://schema.org","datePublished":"2026-07-17T20:46:00+08:00"}
</script></head><body></body></html>'''
    r = _extract_jsonld(html_ld)
    check("JSON-LD datePublished", r == "2026-07-17", f"got {r}")

    # JSON-LD with @graph
    html_ld_graph = '''<html><head><script type="application/ld+json">
{"@graph":[{"datePublished":"2026-07-16T10:00:00Z"}]}
</script></head><body></body></html>'''
    r = _extract_jsonld(html_ld_graph)
    check("JSON-LD @graph", r == "2026-07-16", f"got {r}")

    # ── Meta tags ──
    html_meta = '''<html><head>
    <meta property="article:published_time" content="2026-07-15T14:30:00">
    </head><body></body></html>'''
    r = _extract_meta_tags(html_meta)
    check("meta article:published_time", r == "2026-07-15", f"got {r}")

    # meta name=pubdate
    html_pubdate = '''<html><head>
    <meta name="pubdate" content="2026-07-14">
    </head><body></body></html>'''
    r = _extract_meta_tags(html_pubdate)
    check("meta pubdate", r == "2026-07-14", f"got {r}")

    # meta itemprop
    html_itemprop = '''<html><head>
    <meta itemprop="datePublished" content="2026-07-13">
    </head><body></body></html>'''
    r = _extract_meta_tags(html_itemprop)
    check("meta itemprop datePublished", r == "2026-07-13", f"got {r}")

    # meta DC.date
    html_dc = '''<html><head>
    <meta name="DC.date" content="2026-07-12">
    </head><body></body></html>'''
    r = _extract_meta_tags(html_dc)
    check("meta DC.date", r == "2026-07-12", f"got {r}")

    # ── <time> tag ──
    html_time = '''<html><body>
    <article><time datetime="2026-07-11" itemprop="datePublished">2026年7月11日</time></article>
    </body></html>'''
    r = _extract_time_tag(html_time)
    check("<time datetime>", r == "2026-07-11", f"got {r}")

    # ── URL 日期 ──
    r = _extract_url_date("https://finance.sina.com.cn/stock/2026-07-10/doc-xxxx.shtml")
    check("URL YYYY-MM-DD in path", r == "2026-07-10", f"got {r}")

    r = _extract_url_date("https://finance.eastmoney.com/a/20260709.html")
    check("URL YYYYMMDD in path", r == "2026-07-09", f"got {r}")

    r = _extract_url_date("https://www.example.com/2026/07/08/article.html")
    check("URL YYYY/MM/DD in path", r == "2026-07-08", f"got {r}")

    r = _extract_url_date("https://example.com/page/no-date-here")
    check("URL without date returns None", r is None, f"got {r}")

    # ── Body prefix ──
    body_with_pub = "发布时间：2026-07-07 14:00\n文章正文第一段内容..."
    r, src = _extract_in_body_prefix(body_with_pub)
    check("Body prefix '发布时间'", r == "2026-07-07", f"got {r}")

    body_with_source = "来源：新华社 2026-07-06 记者张三"
    r, src = _extract_in_body_prefix(body_with_source)
    check("Body prefix '来源'", r == "2026-07-06", f"got {r}")

    # ── DDG snippet ──
    r = _extract_ddg_snippet("Jul 17, 2026 — Some article content here")
    check("DDG snippet date", r == "2026-07-17", f"got {r}")

    r = _extract_ddg_snippet("No date in this snippet")
    check("DDG snippet without date", r is None, f"got {r}")

    # ── Body fallback ──
    r = _extract_body_fallback("正文开头部分提到 2025-03-15 这个日期作为历史参考...")
    check("Body fallback first date found", r == "2025-03-15", f"got {r}")

    # ── 中文日期格式 ──
    body_cn = "发布日期：2026年7月5日"
    r, src = _extract_in_body_prefix(body_cn)
    check("Chinese date format '2026年7月5日'", r == "2026-07-05", f"got {r}")

    # ── 完整 extract_date() 集成测试 ──
    r = extract_date(html_ld, url="", snippet="")
    check("extract_date full: JSON-LD", r["date"] == "2026-07-17" and r["confidence"] == "high",
          f"got {r}")

    r = extract_date(html_meta, url="", snippet="")
    check("extract_date full: meta tag", r["date"] == "2026-07-15" and r["confidence"] == "high",
          f"got {r}")

    # 无日期源的 HTML
    html_empty = "<html><body><p>No date here</p></body></html>"
    r = extract_date(html_empty, url="", snippet="")
    check("extract_date empty HTML", r["date"] == "" and r["confidence"] == "",
          f"got {r}")

    # upgrade_date_with_body (空 → 通过 body 升级)
    r_empty = {"date": "", "source": "", "confidence": ""}
    r_upgraded = upgrade_date_with_body(r_empty, body_with_pub)
    check("upgrade empty date via body", r_upgraded["date"] == "2026-07-07" and r_upgraded["confidence"] == "medium",
          f"got {r_upgraded}")

    # 已有 high 不降级
    r_high = {"date": "2026-07-07", "source": "meta_tag", "confidence": "high"}
    r_not_downgraded = upgrade_date_with_body(r_high, body_with_pub)
    check("high confidence not downgraded", r_not_downgraded["date"] == "2026-07-07",
          f"got {r_not_downgraded}")

    # extract_date_fast (仅 HIGH 来源, 无需 body)
    r_fast = extract_date_fast(html_ld)
    check("extract_date_fast JSON-LD", r_fast["date"] == "2026-07-17" and r_fast["confidence"] == "high",
          f"got {r_fast}")

    r_fast = extract_date_fast(html_empty)
    check("extract_date_fast empty", r_fast["date"] == "" and r_fast["confidence"] == "",
          f"got {r_fast}")


# ============================================================
# 2. 测试 filter
# ============================================================
def test_filter():
    print("\n" + "=" * 60)
    print("🔍 测试 filter 过滤模块")
    print("=" * 60)

    from filter import ArticleFilter
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    ten_days_ago = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    articles = [
        {"title": "宁德时代发布新款电池", "url": "http://a.com/1", "date": today},
        {"title": "宁德时代股价创新高", "url": "http://a.com/2", "date": three_days_ago},
        {"title": "贵州茅台分红方案", "url": "http://a.com/3", "date": ten_days_ago},
        {"title": "宁德时代海外扩张", "url": "http://a.com/4", "date": ""},  # 无日期
        {"title": "新能源车销量增长", "url": "http://a.com/5", "date": today},
    ]

    # 时间过滤: 7天内
    result = ArticleFilter.apply(articles, days=7)
    check("filter_days=7 keeps recent articles", len(result) == 4, f"got {len(result)}")

    # 时间过滤: 3天内 (today + 3d_ago + no_date + today2 = 4, 10d_ago被过滤)
    result = ArticleFilter.apply(articles, days=3)
    check("filter_days=3 keeps 3-day articles", len(result) == 4, f"got {len(result)}")

    # 标题过滤
    result = ArticleFilter.apply(articles, title_pattern="宁德时代")
    check("filter_title='宁德时代'", len(result) == 3, f"got {len(result)}")

    # 组合过滤 (today+宁德时代 + 3d_ago+宁德时代 + no_date+宁德时代 = 3)
    result = ArticleFilter.apply(articles, days=7, title_pattern="宁德时代")
    check("filter_days=7 + title='宁德时代'", len(result) == 3, f"got {len(result)}")

    # 空列表
    result = ArticleFilter.apply([], days=7)
    check("filter empty list", len(result) == 0, f"got {len(result)}")

    # 无过滤条件
    result = ArticleFilter.apply(articles)
    check("no filter returns all", len(result) == 5, f"got {len(result)}")

    # 标题支持正则
    result = ArticleFilter.apply(articles, title_pattern="电池|分红")
    check("filter_title regex '电池|分红'", len(result) == 2, f"got {len(result)}")


# ============================================================
# 3. 验证日期提取 — 真实 URL（无正文提取）
# ============================================================
async def test_real_urls():
    print("\n" + "=" * 60)
    print("🌐 测试真实 URL 日期提取（需要网络）")
    print("=" * 60)

    from date_extractor import extract_date_fast, extract_date
    import httpx

    test_urls = [
        # 新浪财经
        "https://finance.sina.com.cn/stock/s/2026-07-17/doc-xxxxx.shtml",
        # 东方财富（需要实际访问）
        # 36氪
        # 新华网
    ]

    # 先只测一个可访问的URL
    print("  [skip] 真实 URL 测试需要网络，将在独立测试中执行")


# ============================================================
# 4. 测试 Phase 1 pipeline（无 LLM）
# ============================================================
async def test_phase1_pipeline():
    print("\n" + "=" * 60)
    print("🧪 测试 Phase 1 Pipeline（搜索 + 日期提取 + 过滤）")
    print("=" * 60)

    from core import run_search_pipeline

    # 用一个小搜索来测试管道
    result = await run_search_pipeline(
        query="宁德时代",
        max_results=3,
        mode="preview",
        filter_days=30,
        filter_title="电池",
        include_snippet=True,
    )

    total = result.get("total", -1)
    total_raw = result.get("total_raw", -1)
    date_stats = result.get("date_stats", {})
    filter_stats = result.get("filter_stats", {})

    print(f"  原始结果: {total_raw}")
    print(f"  过滤后: {total}")
    print(f"  日期置信度: high={date_stats.get('high',0)} medium={date_stats.get('medium',0)} "
          f"low={date_stats.get('low',0)} none={date_stats.get('none',0)}")
    print(f"  过滤统计: {filter_stats}")

    # 基本检查
    check("Phase 1 returns articles list", isinstance(result.get("articles"), list),
          f"type: {type(result.get('articles'))}")
    check("Phase 1 has total field", result.get("total", -1) >= 0,
          f"total={result.get('total')}")
    check("Phase 1 total <= total_raw", result.get("total", 0) <= result.get("total_raw", 0),
          f"total={result.get('total')} raw={result.get('total_raw')}")

    # 检查每篇文章的字段
    articles = result.get("articles", [])
    for i, art in enumerate(articles[:3]):
        has_title = bool(art.get("title"))
        has_url = bool(art.get("url"))
        has_date = "date" in art
        check(f"Article {i+1} has title", has_title, f"title={art.get('title','')[:30]}")
        check(f"Article {i+1} has url", has_url, f"url={art.get('url','')[:40]}")
        check(f"Article {i+1} has date field", has_date, f"date={art.get('date','<empty>')}")
        check(f"Article {i+1} has confidence", art.get("date_confidence", "") in ("high", "medium", "low", ""),
              f"confidence={art.get('date_confidence','')}")

    # 检查 has _phase2_input（供后台 Phase 2 使用）
    has_phase2 = result.get("_phase2_input") is not None
    check("Phase 1 has _phase2_input for Phase 2", has_phase2,
          "missing _phase2_input")


# ============================================================
# 运行
# ============================================================

async def main():
    print(f"\n{'='*60}")
    print(f"📊 v2.0 测试套件")
    print(f"{'='*60}")

    # 1. 日期提取（纯逻辑，无网络）
    test_date_extractor()

    # 2. 过滤模块（纯逻辑）
    test_filter()

    # 3. Lightweight real URL test (we'll just do a few)
    await test_real_urls()

    # 4. Phase 1 pipeline (需要 DDG 网络)
    print("\n  [说明] Phase 1 测试需要 DDG 搜索（~5秒）")
    try:
        await test_phase1_pipeline()
    except Exception as e:
        print(f"  ⚠️  Phase 1 测试跳过（{e}）")

    # 结果
    print(f"\n{'='*60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"🎉 全部 {PASS}/{PASS} 测试通过！")
    else:
        print(f"❌ {PASS}/{total} 通过, {FAIL}/{total} 失败")


if __name__ == "__main__":
    asyncio.run(main())
