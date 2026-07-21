"""
测试新浪财经个股新闻列表页：提取文章标题、URL、发布日期
股票代号模板: sz300750 -> https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/sz300750.phtml
"""

import httpx, re
from datetime import datetime

def fetch_stock_news(stock_code: str, max_pages: int = 1):
    """
    抓取新浪财经个股新闻列表页，提取文章标题、URL、发布日期
    stock_code: 如 sz300750（深市）或 sh600519（沪市）
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    all_news = []

    for page in range(1, max_pages + 1):
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{stock_code}.phtml'
        if page > 1:
            url += f'?page={page}'

        print(f'[抓取] {url}')
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.encoding = 'gb2312'  # 新浪很多页面用 gb2312/gbk
        html = resp.text

        # ========== 1. 找新闻列表区域 ==========
        # 新浪的新闻列表通常在 <ul> 或 <table> 中，链接包含 .shtml 或 /doc- 等
        # 方式1: 用正则提取所有链接和标题
        # 典型的新闻行: <a href="https://finance.sina.com.cn/..." target="_blank">标题</a>
        # 日期通常在同一行的 <span> 或 <td> 中

        # 尝试从 datelist 区域提取
        # 先定位新闻列表的容器区域
        news_items = []

        # 方法A: 找 <a> 标签，过滤出新闻链接（包含特定关键词的url）
        all_links = re.findall(r'<a[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>', html, re.DOTALL)

        for _, href, text in all_links:
            text = re.sub(r'<[^>]+>', '', text).strip()
            if not text or len(text) < 4:
                continue
            # 过滤：只保留新浪财经的新闻链接（含 finance.sina 或特定路径）
            if ('finance.sina' in href or '/doc-' in href or 'roll' in href) and len(text) > 5:
                news_items.append((text, href))

        print(f'  初步提取到 {len(news_items)} 个新闻链接')

        # ========== 2. 尝试提取日期 ==========
        # 方式2: 用 trafilatura 提取结构化数据（对列表页效果可能不好）
        # 方式3: 直接从 HTML 中按行匹配日期和链接

        # 更好的方式：按行解析表格
        # 新浪的新闻列表是 <tr><td>日期</td><td><a>标题</a></td></tr>
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        print(f'  找到 {len(rows)} 个表格行')

        news_from_rows = []
        for row in rows:
            # 找日期: 各种格式 2025-01-15 或 2025/01/15 或 01-15
            date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', row)
            date_str = date_match.group(1) if date_match else ''

            # 找链接和标题
            link_matches = re.findall(r'<a[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>', row, re.DOTALL)
            for _, href, text in link_matches:
                text = re.sub(r'<[^>]+>', '', text).strip()
                if text and len(text) > 4:
                    news_from_rows.append({
                        'title': text,
                        'url': href,
                        'date': date_str
                    })

        if news_from_rows:
            print(f'  从表格行提取到 {len(news_from_rows)} 条')
            all_news.extend(news_from_rows)
        else:
            # 降级: 用基础链接列表
            for title, href in news_items:
                all_news.append({
                    'title': title,
                    'url': href,
                    'date': ''
                })

    return all_news


def extract_date_from_url(url: str) -> str:
    """尝试从新浪新闻URL中提取日期（如 /2026-07-17/doc-... 或 /20260717/...）"""
    m = re.search(r'/(\d{4}-\d{2}-\d{2})/', url)
    if m:
        return m.group(1)
    m = re.search(r'/(\d{8})/', url)
    if m:
        d = m.group(1)
        return f'{d[:4]}-{d[4:6]}-{d[6:8]}'
    return ''


def check_pagination(stock_code: str):
    """检查总页数和日期分布"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{stock_code}.phtml'
    resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    resp.encoding = 'gb2312'
    html = resp.text

    # 找分页链接
    page_nums = set()
    for m in re.finditer(r'\?page=(\d+)', html):
        page_nums.add(int(m.group(1)))
    max_page = max(page_nums) if page_nums else 1
    print(f'共 {max_page} 页')

    # 检查各页日期范围
    for page in [1, 2, 3, max_page]:
        pg_url = url + (f'?page={page}' if page > 1 else '')
        resp = httpx.get(pg_url, headers=headers, timeout=15, follow_redirects=True)
        resp.encoding = 'gb2312'
        html2 = resp.text

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html2, re.DOTALL)
        dates = []
        for row in rows:
            dm = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', row)
            if dm:
                dates.append(dm.group(1))
        dates = sorted(set(dates))
        print(f'  第{page}页: {len(dates)} 个不同日期, [{dates[0] if dates else ""} ~ {dates[-1] if dates else ""}]')


if __name__ == '__main__':
    stock_code = 'sz300750'  # 宁德时代

    # 检查分页
    print('>>> 分页信息 <<<')
    check_pagination(stock_code)

    # 抓取第一页详细结果
    print(f'\n>>> 第1页详细结果 <<<')
    news = fetch_stock_news(stock_code, max_pages=1)

    print(f'\n{"="*60}')
    print(f'股票: {stock_code} - 共 {len(news)} 条新闻')
    print(f'{"="*60}')

    for i, item in enumerate(news[:30], 1):
        date = item['date'] or extract_date_from_url(item['url'])
        print(f'\n【{i}】{item["title"][:70]}')
        print(f'    日期: {date}')
        print(f'    链接: {item["url"][:90]}')
