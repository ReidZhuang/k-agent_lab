"""
sina_stock_news.py
利用 web_bot_agent/version_1.0 的网页拆解工具，
通过股票代号组装新浪财经个股新闻列表页，提取文章标题 / URL / 发布日期。

用法:
    python3 sina_stock_news.py <股票代号> [-n 页数]
    示例: python3 sina_stock_news.py sz300750 -n 3
    示例: python3 sina_stock_news.py sh600519 -n 1

输出: JSON 文件保存到 rough/ 目录
"""

import sys, os, json, re
from datetime import datetime

# 将 web_bot_agent 加入路径，复用其工具
WEB_BOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "web_bot_agent", "version_1.0")
if WEB_BOT_DIR not in sys.path:
    sys.path.insert(0, WEB_BOT_DIR)

# 直接从 core.py 导入 httpx 和 fetch_and_extract
from core import fetch_and_extract
import httpx


# ============================================================
# 1. 从股票代号组装列表页 URL
# ============================================================
SINA_LIST_URL_TEMPLATE = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{stock_code}.phtml"

# 常见股票代号前缀
EXCHANGE_MAP = {
    "6": "sh",   # 沪市 600/601/603/605...
    "0": "sz",   # 深市 000/001/002...
    "3": "sz",   # 创业板 300/301...
    "4": "bj",   # 北交所 4...
    "8": "bj",   # 北交所 8...
}


def normalize_stock_code(code: str) -> str:
    """统一股票代号格式: 300750 -> sz300750, sh600519 -> sh600519"""
    code = code.strip()
    if len(code) <= 6 and code.isdigit():
        prefix = EXCHANGE_MAP.get(code[0], "sz")
        return f"{prefix}{code}"
    return code


def build_list_url(stock_code: str, page: int = 1) -> str:
    """组装列表页 URL"""
    base = SINA_LIST_URL_TEMPLATE.format(stock_code=stock_code)
    if page > 1:
        return f"{base}?page={page}"
    return base


# ============================================================
# 2. 抓取列表页并解析
# ============================================================
def parse_list_page(html: str) -> list[dict]:
    """
    解析新浪个股新闻列表页 HTML，提取新闻标题、URL、日期。
    页面结构: <tr><td>日期</td><td><a href="...">标题</a></td></tr>

    返回: [{"title": str, "url": str, "date": str}, ...]
    """
    news = []

    # 方法1: 从 <tr> 表格行中解析（主要方法）
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', row)
        date_str = date_match.group(1) if date_match else ""

        link_matches = re.findall(
            r'<a[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>', row, re.DOTALL
        )
        for _, href, text in link_matches:
            text = re.sub(r'<[^>]+>', "", text).strip()
            if not text or len(text) < 4:
                continue
            # 统一日期格式: 2026/07/17 -> 2026-07-17
            date_clean = date_str.replace("/", "-") if date_str else ""
            news.append({
                "title": text,
                "url": href,
                "date": date_clean,
            })

    # 方法2: 如果表格解析没结果，降级到从所有链接中过滤
    if not news:
        all_links = re.findall(
            r'<a[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>', html, re.DOTALL
        )
        for _, href, text in all_links:
            text = re.sub(r'<[^>]+>', "", text).strip()
            if not text or len(text) < 5:
                continue
            if "finance.sina" in href or "cj.sina" in href or "k.sina" in href:
                # 从 URL 提取日期
                date_str = ""
                dm = re.search(r'/(\d{4}-\d{2}-\d{2})/', href)
                if dm:
                    date_str = dm.group(1)
                news.append({
                    "title": text,
                    "url": href,
                    "date": date_str,
                })

    return news


# ============================================================
# 3. 获取分页信息
# ============================================================
def get_pagination_info(stock_code: str) -> dict:
    """检查列表页共有多少页"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    url = build_list_url(stock_code)
    resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    resp.encoding = "gb2312"
    html = resp.text

    # 找分页链接: 提取所有 page=N 参数
    page_nums = set()
    for m in re.finditer(r"\?page=(\d+)", html):
        page_nums.add(int(m.group(1)))

    # 也看看总条目数
    total_match = re.search(r"(\d+)\s*条记录", html)

    return {
        "max_page": max(page_nums) if page_nums else 1,
        "total_records": total_match.group(1) if total_match else "未知",
    }


# ============================================================
# 4. 批量抓取多页
# ============================================================
def fetch_stock_news(stock_code: str, max_pages: int = 1) -> dict:
    """
    主函数：抓取个股新闻列表，返回结构化结果。

    返回: {
        "stock_code": "sz300750",
        "pages_fetched": 1,
        "total_items": 41,
        "date_range": {"from": "2026-07-17", "to": "2026-07-17"},
        "news": [{"title": ..., "url": ..., "date": ...}, ...]
    }
    """
    code = normalize_stock_code(stock_code)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    all_news = []
    dates_seen = set()

    for page in range(1, max_pages + 1):
        url = build_list_url(code, page)
        print(f"  [第{page}页] 抓取 {url}")

        try:
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            resp.encoding = "gb2312"
            page_news = parse_list_page(resp.text)

            if not page_news:
                print(f"  [第{page}页] 未提取到新闻，停止翻页")
                break

            all_news.extend(page_news)
            for item in page_news:
                if item["date"]:
                    dates_seen.add(item["date"])

            print(f"  [第{page}页] 提取到 {len(page_news)} 条")
        except Exception as e:
            print(f"  [第{page}页] 抓取失败: {e}")
            break

    # 整理结果
    dates_sorted = sorted(dates_seen) if dates_seen else []
    return {
        "stock_code": code,
        "pages_fetched": min(max_pages, len(all_news) // 40 + 1),
        "total_items": len(all_news),
        "date_range": {
            "from": dates_sorted[0] if dates_sorted else "",
            "to": dates_sorted[-1] if dates_sorted else "",
        },
        "date_count": len(dates_sorted),
        "news": all_news,
    }


# ============================================================
# 5. 抓取单篇文章详情（利用 web_bot_agent 的 fetch_and_extract）
# ============================================================
def fetch_article_detail(url: str) -> dict:
    """
    用 web_bot_agent 的 fetch_and_extract 提取单篇文章正文和元数据。

    返回: {"body": str, "date": str, "html_len": int, "success": bool, "error": str}
    """
    print(f"  抓取文章详情: {url[:70]}...")
    try:
        body, date, html_len, paragraphs = fetch_and_extract(url)
        return {
            "success": bool(body and len(body) > 10),
            "body": body[:500] if body else "",
            "date": date,
            "html_len": html_len,
            "paragraph_count": len(paragraphs),
            "error": "",
        }
    except Exception as e:
        return {"success": False, "body": "", "date": "", "html_len": 0,
                "paragraph_count": 0, "error": str(e)}


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="新浪财经个股新闻提取工具")
    parser.add_argument("stock_code", help="股票代号，如 sz300750 或 300750")
    parser.add_argument("-n", "--pages", type=int, default=1, help="抓取页数（默认1页）")
    parser.add_argument("--detail", type=int, nargs="?", const=3,
                        help="同时抓取前 N 篇文章的正文详情（默认前3篇）")
    parser.add_argument("--save", action="store_true", default=True,
                        help="保存结果到 rough/ 目录")
    args = parser.parse_args()

    print(f"股票新闻列表抓取: {normalize_stock_code(args.stock_code)}")
    print(f"{'='*60}")

    # 检查分页
    try:
        page_info = get_pagination_info(args.stock_code)
        print(f"共 {page_info['max_page']} 页, 总记录数: {page_info['total_records']}")
    except Exception as e:
        print(f"分页检测失败: {e}")

    print(f"\n抓取前 {args.pages} 页...")
    result = fetch_stock_news(args.stock_code, max_pages=args.pages)

    print(f"\n{'='*60}")
    print(f"股票: {result['stock_code']}")
    print(f"共抓取 {result['total_items']} 条新闻")
    print(f"日期范围: {result['date_range']['from']} ~ {result['date_range']['to']} ({result['date_count']} 个不同日期)")
    print(f"{'='*60}")

    # 展示结果
    for i, item in enumerate(result["news"][:30], 1):
        print(f"\n【{i}】{item['title'][:70]}")
        print(f"    日期: {item['date']}")
        print(f"    链接: {item['url'][:90]}")

    if result["total_items"] > 30:
        print(f"\n... 还有 {result['total_items'] - 30} 条未显示")

    # 抓取文章详情（可选）
    if args.detail and result["news"]:
        print(f"\n>>> 抓取前 {args.detail} 篇文章详情 <<<")
        for i, item in enumerate(result["news"][:args.detail], 1):
            print(f"\n【详情 {i}】{item['title'][:50]}")
            detail = fetch_article_detail(item["url"])
            if detail["success"]:
                body_preview = detail["body"][:200].replace("\n", " ")
                print(f"  正文预览: {body_preview}...")
                print(f"  提取日期: {detail['date']}")
                print(f"  HTML大小: {detail['html_len']} 字节")
                print(f"  段落数: {detail['paragraph_count']}")
            else:
                print(f"  提取失败: {detail['error']}")

    # 保存结果
    if args.save:
        rough_dir = os.path.dirname(__file__)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        code = result["stock_code"]
        filename = f"sina_{code}_news_{timestamp}.json"
        filepath = os.path.join(rough_dir, filename)

        # 保存完整 JSON（不包含正文详情，避免过大）
        save_data = {
            "stock_code": result["stock_code"],
            "total_items": result["total_items"],
            "date_range": result["date_range"],
            "news": result["news"],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存: {filepath}")
