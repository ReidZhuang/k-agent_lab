#!/usr/bin/env python3
"""
通用网页正文提取工具
对比 jina_fetch (r.jina.ai) 与 本地 trafilatura 提取的效果

用法:
    python3 extract_articles.py "搜索关键词" [--max-results 5] [--output results/compare.md]
"""

import json
import sys
import os
import argparse
import subprocess
import tempfile
import time
import re
from urllib.parse import urlparse

# ============================================================
# 通用正文提取器（纯本地，不依赖API）
# ============================================================

def extract_with_trafilatura(html: str, url: str = "") -> str:
    """使用 trafilatura 从 HTML 中提取正文"""
    import trafilatura
    result = trafilatura.extract(
        html,
        url=url,
        output_format='markdown',  # markdown / txt
        include_images=False,
        include_links=True,
        include_tables=True,
        no_fallback=False,
        favor_precision=False,     # favor_recall=False 精度优先
    )
    return result or ""


def extract_with_readability(html: str, url: str = "") -> str:
    """使用 readability 作为备选提取方案"""
    try:
        from readability import Document
        doc = Document(html, url=url)
        html_body = doc.summary()
        # 转 markdown
        import html2text
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        text = h.handle(html_body)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    except Exception as e:
        return f"[readability error: {e}]"


def fetch_html(url: str, proxy: str) -> str:
    """通过代理抓取 HTML"""
    import httpx
    try:
        with httpx.Client(proxy=proxy, timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        return f""


def extract_article(url: str, proxy: str, methods: list) -> dict:
    """对单个URL运行所有提取方法"""
    print(f"  ⏳ 抓取: {url}", file=sys.stderr)
    html = fetch_html(url, proxy)
    if not html:
        return {"url": url, "error": "抓取失败", "results": {}}

    results = {}
    for method in methods:
        try:
            if method == "trafilatura":
                text = extract_with_trafilatura(html, url)
            elif method == "readability":
                text = extract_with_readability(html, url)
            else:
                text = ""
            results[method] = text
        except Exception as e:
            results[method] = f"[提取异常: {e}]"

    return {"url": url, "html_len": len(html), "results": results}


# ============================================================
# Jina fetch 调用
# ============================================================

def jina_fetch(url: str, proxy: str) -> str:
    """通过 web-forager jina_fetch 获取 Jina 转换结果"""
    try:
        env = os.environ.copy()
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy
        result = subprocess.run(
            ["timeout", "30", "web-forager", "fetch", url],
            capture_output=True, text=True, timeout=35, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        return ""


# ============================================================
# 搜索
# ============================================================

def search(query: str, max_results: int, proxy: str) -> list:
    """通过 web-forager 搜索"""
    env = os.environ.copy()
    env["http_proxy"] = proxy
    env["https_proxy"] = proxy
    result = subprocess.run(
        ["web-forager", "search", query, "--max-results", str(max_results)],
        capture_output=True, text=True, timeout=20, env=env
    )
    return json.loads(result.stdout)


# ============================================================
# 评分函数
# ============================================================

def rate_content(text: str) -> dict:
    """评价正文提取质量"""
    if not text or len(text) < 50:
        return {"score": 0, "len": 0, "lines": 0, "judgment": "❌ 无内容"}

    lines = text.strip().split('\n')
    non_empty = [l for l in lines if l.strip()]

    # 判断是否包含大量导航/侧栏特征
    nav_indicators = [
        '首页', '快讯', '新闻', '要闻', '评论', '产经',
        '关于我们', '服务条例', '联系我们', '版权声明',
        '网站地图', '备案号', '举报', '热榜', '热搜', '视频',
        '登录', '注册', '评论', '点赞', '分享', '微信', '微博',
        '用户评论', '暂无评论', '换一换', '加载更多',
    ]
    nav_count = sum(1 for line in non_empty
                    for ind in nav_indicators if line.startswith(ind) and len(line) < 20)
    nav_ratio = nav_count / len(non_empty) if non_empty else 0

    # 判断是否包含行情/结构化数据
    stock_indicators = ['开盘价', '昨收盘', '最高', '最低', '换手率', '市盈率', '流通股本']
    stock_match = sum(1 for ind in stock_indicators if ind in text)

    # 判断是否来自非文章页面
    is_stock_page = stock_match >= 3

    if is_stock_page:
        return {"score": 0, "len": len(text), "lines": len(non_empty),
                "judgment": "❌ 行情页面非文章"}
    if nav_ratio > 0.3:
        return {"score": 1, "len": len(text), "lines": len(non_empty),
                "judgment": f"⚠️ 含大量导航杂质 (nav_ratio={nav_ratio:.0%})"}
    if len(text) < 200:
        return {"score": 1, "len": len(text), "lines": len(non_empty),
                "judgment": "⚠️ 正文过短"}

    return {"score": 2, "len": len(text), "lines": len(non_empty),
            "judgment": "✅ 正文纯净"}


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="通用网页正文提取对比")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--output", default="results/compare.md")
    args = parser.parse_args()

    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    with open(config_path) as f:
        cfg = json.load(f)
    proxy = cfg["proxy"]["http"]

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # 1. 搜索
    print("🔍 搜索中...", file=sys.stderr)
    results = search(args.query, args.max_results, proxy)
    print(f"📝 共 {len(results)} 条结果\n", file=sys.stderr)

    # 2. 提取 + Jina 对比
    all_data = []
    for i, item in enumerate(results, 1):
        url = item["url"]
        title = item["title"]
        print(f"[{i}/{len(results)}] {title}", file=sys.stderr)

        # 本地提取
        local = extract_article(url, proxy, methods=["trafilatura", "readability"])

        # Jina fetch
        jina_text = jina_fetch(url, proxy)

        all_data.append({
            "idx": i,
            "title": title,
            "url": url,
            "snippet": item.get("snippet", ""),
            "local": local,
            "jina": jina_text,
        })
        time.sleep(1)

    # 3. 输出对比报告
    report = "# 正文提取方式对比\n\n"
    report += f"> **搜索词:** `{args.query}`\n"
    report += f"> **时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"> HTML原始大小 vs trafilatura(本地) vs readability(本地) vs jina_fetch(r.jina.ai)\n\n"
    report += "---\n\n"

    for d in all_data:
        report += f"## {d['idx']}. {d['title']}\n\n"
        report += f"**URL:** {d['url']}\n\n"
        report += f"**搜索摘要:** {d['snippet']}\n\n"

        # 评分对比表
        local_traf = d["local"]["results"].get("trafilatura", "")
        local_read = d["local"]["results"].get("readability", "")
        jina_text = d["jina"]

        local_err = d["local"].get("error", "")
        if local_err:
            report += f"> ⚠️ 本地抓取失败: {local_err}\n\n"

        ratings = {
            "trafilatura": rate_content(local_traf),
            "readability": rate_content(local_read),
            "jina_fetch":  rate_content(jina_text),
        }

        # 对比概况
        html_size = d["local"].get("html_len", 0)
        report += "| 方法 | 状态 | 提取长度 | 行数 |\n"
        report += "|---|---|---|---|\n"
        report += f"| 原始HTML | — | {html_size:,} bytes | — |\n"
        for method_name, r in ratings.items():
            report += f"| {method_name} | {r['judgment']} | {r['len']:,} chars | {r['lines']} lines |\n"
        report += "\n"

        # 如果 trafilatura 有内容，展示
        if local_traf and ratings["trafilatura"]["score"] >= 1:
            report += "### trafilatura (本地提取)\n\n"
            report += "```markdown\n"
            report += local_traf[:3000]
            if len(local_traf) > 3000:
                report += f"\n... (剩余 {len(local_traf)-3000} chars)\n"
            report += "\n```\n\n"

        # 展示 readability
        if local_read and ratings["readability"]["score"] >= 1:
            report += "### readability (本地提取)\n\n"
            report += "```markdown\n"
            report += local_read[:3000]
            if len(local_read) > 3000:
                report += f"\n... (剩余 {len(local_read)-3000} chars)\n"
            report += "\n```\n\n"

        # 展示 Jina
        if jina_text:
            # 去掉 Jina 自己的 meta header
            jina_clean = re.sub(r'^Title:.+\nURL Source:.+\nMarkdown Content:\n', '', jina_text)
            report += "### jina_fetch (r.jina.ai)\n\n"
            report += "```markdown\n"
            report += jina_clean[:3000]
            if len(jina_clean) > 3000:
                report += f"\n... (剩余 {len(jina_clean)-3000} chars)\n"
            report += "\n```\n\n"

        report += "---\n\n"

    # 4. 汇总对比
    report += "# 汇总对比\n\n"
    report += "| # | 标题 | trafilatura | readability | jina_fetch |\n"
    report += "|---|---|---|---|---|\n"
    for d in all_data:
        local_traf = d["local"]["results"].get("trafilatura", "")
        local_read = d["local"]["results"].get("readability", "")
        jina_text = d["jina"]
        report += (
            f"| {d['idx']} "
            f"| {d['title'][:30]}... "
            f"| {rate_content(local_traf)['judgment']} "
            f"| {rate_content(local_read)['judgment']} "
            f"| {rate_content(jina_text)['judgment']} |\n"
        )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 对比报告已保存: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
