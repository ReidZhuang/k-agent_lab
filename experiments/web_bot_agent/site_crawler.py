#!/usr/bin/env python3
"""
网站递归爬取 → 树状结构 Markdown
仿 WebPalm 思路：递归遍历站内链接，输出 URL 树

用法:
  python3 site_crawler.py -u https://www.stcn.com -l 2
"""

import sys
import os
import re
import json
import time
import argparse
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
from collections import defaultdict

try:
    import requests
except ImportError:
    print("需要安装 requests: pip install requests")
    sys.exit(1)

from bs4 import BeautifulSoup


class SiteCrawler:
    """递归网站爬取 + 树结构生成"""

    def __init__(self, start_url: str, max_depth: int = 2, max_pages: int = 50,
                 delay: float = 0.3, timeout: int = 10, user_agent: str = 'chrome'):
        self.start_url = start_url.rstrip('/')
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout

        self.parsed = urlparse(self.start_url)
        self.domain = self.parsed.netloc
        self.base = f'{self.parsed.scheme}://{self.parsed.netloc}'

        self.visited = set()          # 已访问的 URL
        self.failed = set()           # 访问失败的 URL
        self.page_titles = {}         # URL → 页面标题
        self.page_links = {}          # URL → [链接列表]
        self.parents = {}             # URL → 父 URL
        self.children = defaultdict(list)  # URL → [子 URL]

        self.ua_map = {
            'chrome': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'firefox': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
            'safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
        }
        self.ua = self.ua_map.get(user_agent, self.ua_map['chrome'])

    def _normalize(self, url: str, parent: str = '') -> str:
        """规范化 URL：去 fragment、去末尾斜杠"""
        url = urljoin(parent or self.start_url, url)
        url, _ = urldefrag(url)
        url = url.rstrip('/')
        return url

    def _is_internal(self, url: str) -> bool:
        """判断是否站内链接"""
        p = urlparse(url)
        if not p.netloc:
            return True
        return p.netloc == self.domain or p.netloc.endswith('.' + self.domain)

    def _should_fetch(self, url: str) -> bool:
        """判断是否应该抓取此 URL"""
        if url in self.visited or url in self.failed:
            return False
        if len(self.visited) >= self.max_pages:
            return False

        p = urlparse(url)
        # 跳过非网页资源
        skip_ext = {'.pdf', '.zip', '.png', '.jpg', '.jpeg', '.gif',
                    '.svg', '.mp4', '.mp3', '.doc', '.docx', '.xls', '.xlsx',
                    '.css', '.js', '.json', '.xml', '.ico', '.torrent'}
        if any(p.path.lower().endswith(ext) for ext in skip_ext):
            return False
        # 跳过 mailto/tel/javascript
        if p.scheme not in ('http', 'https', ''):
            return False
        return True

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title = soup.find('title')
        if title:
            t = title.get_text(strip=True)
            if t:
                return t[:80]
        h1 = soup.find('h1')
        if h1:
            t = h1.get_text(strip=True)
            if t:
                return t[:80]
        return '(无标题)'

    def _extract_links(self, soup: BeautifulSoup, page_url: str) -> list:
        """提取页面中的所有站内链接"""
        links = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if not href or href.startswith(('javascript:', '#')):
                continue
            abs_url = self._normalize(href, page_url)
            if not abs_url:
                continue
            if self._is_internal(abs_url) and abs_url not in links:
                link_text = a.get_text(strip=True)[:60] or '(链接)'
                links.add((abs_url, link_text))
        return sorted(links, key=lambda x: x[0])

    def crawl(self):
        """开始递归爬取"""
        queue = [(self.start_url, None, 0)]
        while queue and len(self.visited) < self.max_pages:
            url, parent, depth = queue.pop(0)
            if not self._should_fetch(url):
                continue

            print(f"  {'│ ' * depth}├─ [{depth}] {url}", file=sys.stderr)
            self.visited.add(url)
            if parent:
                self.parents[url] = parent
                self.children[parent].append(url)

            try:
                resp = requests.get(url, headers={'User-Agent': self.ua},
                                    timeout=self.timeout)
                if resp.status_code >= 400:
                    self.failed.add(url)
                    self.page_titles[url] = f'[HTTP {resp.status_code}]'
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')
                self.page_titles[url] = self._extract_title(soup)
                links = self._extract_links(soup, url)
                self.page_links[url] = links

                if depth < self.max_depth:
                    for link_url, link_text in links:
                        if self._should_fetch(link_url):
                            queue.append((link_url, url, depth + 1))

                time.sleep(self.delay)

            except Exception as e:
                self.failed.add(url)
                self.page_titles[url] = f'[错误: {e.__class__.__name__}]'

    def build_tree(self) -> dict:
        """构建树状结构"""
        def _build(url):
            node = {
                'url': url,
                'title': self.page_titles.get(url, url),
                'children': [_build(c) for c in self.children.get(url, [])]
            }
            return node

        return _build(self.start_url)

    def to_markdown(self) -> str:
        """输出树状 Markdown"""
        lines = []
        lines.append(f'# 🌳 网站结构树: {self.start_url}')
        lines.append('')
        lines.append(f'> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append(f'> 爬取深度: {self.max_depth} 层')
        lines.append(f'> 总页面: {len(self.visited)} (成功: {len(self.visited) - len(self.failed)}, 失败: {len(self.failed)})')
        lines.append('')
        lines.append('---')
        lines.append('')

        def _write(url, depth):
            indent = '  ' * depth
            title = self.page_titles.get(url, '')
            status = f'[{urlparse(url).path or "/"}]'
            if url in self.failed:
                line = f'{indent}- ❌ **{title or url}**'
            elif depth == 0:
                line = f'{indent}# 📍 {title or url}'
                line += f'  _{status}_'
            else:
                line = f'{indent}- {title}'
                if '?' in urlparse(url).query:
                    line += ' 🔍'
                line += f'  _{status}_'
            lines.append(line)

            for child in self.children.get(url, []):
                _write(child, depth + 1)

        _write(self.start_url, 0)
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('### 📊 页面清单')
        lines.append('')
        lines.append('| 页面 | 标题 | 状态 | 子链接数 |')
        lines.append('| --- | --- | --- | --- |')
        for url in sorted(self.visited, key=lambda u: u.count('/')):
            title = self.page_titles.get(url, '')
            status = '✅' if url not in self.failed else '❌'
            link_count = len(self.page_links.get(url, []))
            lines.append(f'| [{title[:40]}]({url}) | `{urlparse(url).path}` | {status} | {link_count} |')

        return '\n'.join(lines)

    def to_json(self) -> str:
        return json.dumps(self.build_tree(), ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description='网站递归爬取 → 树状结构 Markdown')
    parser.add_argument('-u', '--url', required=True, help='起始 URL')
    parser.add_argument('-l', '--level', type=int, default=2, help='递归深度 (默认: 2)')
    parser.add_argument('--max-pages', type=int, default=50, help='最大页面数 (默认: 50)')
    parser.add_argument('--delay', type=float, default=0.3, help='请求间隔秒数 (默认: 0.3)')
    parser.add_argument('-o', '--output', help='输出文件路径')
    args = parser.parse_args()

    print(f'🔍 开始爬取: {args.url}')
    print(f'   深度: {args.level}, 最大页面: {args.max_pages}')
    print('')

    crawler = SiteCrawler(
        start_url=args.url,
        max_depth=args.level,
        max_pages=args.max_pages,
        delay=args.delay,
    )
    crawler.crawl()

    md = crawler.to_markdown()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f'\n✅ 已保存: {args.output}')
    else:
        print('\n' + md)

    # 同时保存 JSON
    json_path = args.output.replace('.md', '.json') if args.output else 'site_tree.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(crawler.to_json())
    print(f'✅ JSON 已保存: {json_path}')


if __name__ == '__main__':
    main()
