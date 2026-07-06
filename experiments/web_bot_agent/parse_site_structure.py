#!/usr/bin/env python3
"""
网站结构解析器 — 通用版 v2
================================
输入：任意网站的 HTML（从 URL 或本地文件读取）
输出：带层级结构的树状 Markdown（可折叠），标注各区域名称、级别、子路径

专为 LLM Agent 站内自主导航设计。
"""

import sys
import re
import os
import json
from urllib.parse import urljoin, urlparse, unquote
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, List

try:
    from bs4 import BeautifulSoup, Tag, NavigableString
except ImportError:
    print("需要安装 beautifulsoup4: pip install beautifulsoup4 lxml")
    sys.exit(1)

try:
    import lxml
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


# ============================================================
# 常量
# ============================================================

HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5']

# 角色 → emoji
ROLE_EMOJI = {
    '导航':     '📍',
    '页头':     '🏠',
    '搜索':     '🔍',
    '页脚':     '📌',
    '侧栏':     '📎',
    '内容区':   '📰',
    '横幅':     '🎯',
    '推荐':     '🔥',
    '标签':     '🏷️',
    '面包屑':   '🔗',
    '公告':     '📢',
    '友情链接': '🤝',
    '未分类':   '📄',
    '产品':     '🛠️',
    '活动':     '🎪',
    '视频':     '🎬',
    '数据':     '📊',
    '行情':     '📈',
    '订阅':     '📬',
}

# class/id 关键词 → 角色映射
CLASS_ROLE_MAP = [
    (r'(?:^|[\s_\-])nav(?:[\s_\-]|$)', '导航'),
    (r'(?:^|[\s_\-])navbar(?:[\s_\-]|$)', '导航'),
    (r'(?:^|[\s_\-])menu(?:[\s_\-]|$)', '导航'),
    (r'(?:^|[\s_\-])header(?:[\s_\-]|$)', '页头'),
    (r'(?:^|[\s_\-])topbar(?:[\s_\-]|$)', '页头'),
    (r'(?:^|[\s_\-])footer(?:[\s_\-]|$)', '页脚'),
    (r'(?:^|[\s_\-])foot(?:[\s_\-]|$)', '页脚'),
    (r'(?:^|[\s_\-])search(?:[\s_\-]|$)', '搜索'),
    (r'(?:^|[\s_\-])sidebar(?:[\s_\-]|$)', '侧栏'),
    (r'(?:^|[\s_\-])aside(?:[\s_\-]|$)', '侧栏'),
    (r'(?:^|[\s_\-])content(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])main(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])article(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])section(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])wrapper(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])container(?:[\s_\-]|$)', '内容区'),
    (r'(?:^|[\s_\-])banner(?:[\s_\-]|$)', '横幅'),
    (r'(?:^|[\s_\-])slide(?:[\s_\-]|$)', '横幅'),
    (r'(?:^|[\s_\-])carousel(?:[\s_\-]|$)', '横幅'),
    (r'(?:^|[\s_\-])recommend(?:[\s_\-]|$)', '推荐'),
    (r'(?:^|[\s_\-])hot(?:[\s_\-]|$)', '推荐'),
    (r'(?:^|[\s_\-])headline(?:[\s_\-]|$)', '推荐'),
    (r'(?:^|[\s_\-])trending(?:[\s_\-]|$)', '推荐'),
    (r'(?:^|[\s_\-])breadcrumb(?:[\s_\-]|$)', '面包屑'),
    (r'(?:^|[\s_\-])crumb(?:[\s_\-]|$)', '面包屑'),
    (r'(?:^|[\s_\-])tag(?:[\s_\-]|$)', '标签'),
    (r'(?:^|[\s_\-])category(?:[\s_\-]|$)', '标签'),
    (r'(?:^|[\s_\-])announce(?:[\s_\-]|$)', '公告'),
    (r'(?:^|[\s_\-])notice(?:[\s_\-]|$)', '公告'),
    (r'(?:^|[\s_\-])friend(?:[\s_\-]|$)', '友情链接'),
    (r'(?:^|[\s_\-])product(?:[\s_\-]|$)', '产品'),
    (r'(?:^|[\s_\-])video(?:[\s_\-]|$)', '视频'),
    (r'(?:^|[\s_\-])live(?:[\s_\-]|$)', '视频'),
    (r'(?:^|[\s_\-])quotes(?:[\s_\-]|$)', '行情'),
    (r'(?:^|[\s_\-])stock(?:[\s_\-]|$)', '行情'),
    (r'(?:^|[\s_\-])data(?:[\s_\-]|$)', '数据'),
    (r'(?:^|[\s_\-])activity(?:[\s_\-]|$)', '活动'),
    (r'(?:^|[\s_\-])subscribe(?:[\s_\-]|$)', '订阅'),
    (r'(?:^|[\s_\-])copyright(?:[\s_\-]|$)', '页脚'),
    (r'导航|导航栏', '导航'),
    (r'搜索|搜素', '搜索'),
    (r'页脚|底部|版权', '页脚'),
    (r'侧栏|侧边', '侧栏'),
    (r'内容|主体|正文', '内容区'),
    (r'推荐|热门|头条', '推荐'),
    (r'公告|通知|声明', '公告'),
    (r'友情链接|合作伙伴', '友情链接'),
    (r'面包屑|当前位置', '面包屑'),
    (r'产品|服务|工具', '产品'),
]


@dataclass
class LinkItem:
    text: str
    href: str
    is_external: bool = False


@dataclass
class Section:
    """一个结构化的区域"""
    label: str
    role: str = '未分类'
    level: int = 0
    tag_info: str = ''
    heading_text: str = ''     # 从页面中提取到的实际标题文本
    sub_sections: list = field(default_factory=list)
    links: list = field(default_factory=list)
    link_count: int = 0
    has_search: bool = False
    search_endpoint: str = ''


# ============================================================
# 主解析器
# ============================================================

class SiteParser:
    """通用网站结构解析器"""

    def __init__(self, source: str, html: Optional[str] = None):
        self.source = source
        self.base_url = self._resolve_base(source)
        self.domain = urlparse(self.base_url).netloc if self.base_url else ''
        self.soup = self._load(source, html)
        self._clean()
        # 最终输出
        self.sections: List[Section] = []

    def _resolve_base(self, source: str) -> str:
        if source.startswith(('http://', 'https://')):
            return source
        return ''

    def _load(self, source: str, html: Optional[str]) -> BeautifulSoup:
        if html:
            parser = 'lxml' if HAS_LXML else 'html.parser'
            return BeautifulSoup(html, parser)
        if source.startswith(('http://', 'https://')):
            import urllib.request
            req = urllib.request.Request(source, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            parser = 'lxml' if HAS_LXML else 'html.parser'
            return BeautifulSoup(raw, parser)
        with open(source, 'r', encoding='utf-8', errors='replace') as f:
            parser = 'lxml' if HAS_LXML else 'html.parser'
            return BeautifulSoup(f.read(), parser)

    def _clean(self):
        for tag in self.soup.find_all(['script', 'style', 'noscript', 'iframe', 'svg']):
            tag.decompose()

    # ---------- 辅助 ----------

    def _text(self, el) -> str:
        return el.get_text(strip=True) if el else ''

    def _cls_id(self, el) -> str:
        parts = []
        if el.get('id'):
            parts.append(f'#{el["id"]}')
        if el.get('class'):
            parts.append('.' + '.'.join(el['class']))
        return ' '.join(parts)

    def _detect_role(self, el) -> str:
        """通过 tag + class/id 检测角色"""
        tag = el.name or ''
        cs = self._cls_id(el).lower()

        # HTML5 语义标签
        tag_role = {
            'nav': '导航', 'main': '内容区', 'article': '内容区',
            'aside': '侧栏', 'header': '页头', 'footer': '页脚',
        }
        if tag in tag_role:
            return tag_role[tag]

        # class/id 关键词匹配
        for pattern, role in CLASS_ROLE_MAP:
            if re.search(pattern, cs):
                return role
        return '未分类'

    def _detect_label(self, el) -> str:
        """提取此区域的实际名称"""
        # 1. aria-label
        aria = el.get('aria-label', '')
        if aria:
            return aria.strip()
        # 2. title 属性
        title_attr = el.get('title', '')
        if title_attr:
            return title_attr.strip()
        # 3. 内部的标题标签 h1-h5
        for hn in HEADING_TAGS:
            h = el.find(hn)
            if h:
                t = self._text(h)
                if t and len(t) < 60:
                    return t
        # 4. 第一个有文字且具描述性的 <a> 子元素
        for a in el.find_all('a', href=True, limit=10):
            t = self._text(a)
            if t and len(t) > 1 and len(t) < 30:
                return t
        return ''

    def _norm_url(self, href: str) -> str:
        if not href or href.startswith('javascript:') or href.startswith('#'):
            return ''
        if self.base_url:
            return urljoin(self.base_url, href)
        return href

    def _is_internal(self, href: str) -> bool:
        if not href:
            return False
        p = urlparse(href)
        if not p.netloc:
            return True
        if self.domain and self.domain in p.netloc:
            return True
        return False

    # ---------- 提取 ----------

    def parse(self) -> List[Section]:
        """主流程"""
        self._from_semantic_tags()
        self._from_heuristic_classes()
        self._from_heading_division()
        self._find_search()
        self._deduplicate_and_sort()
        return self.sections

    def _from_semantic_tags(self):
        """第一轮：语义 HTML5 标签"""
        for tag in ['nav', 'main', 'article', 'aside', 'header', 'footer']:
            for el in self.soup.find_all(tag):
                sec = self._make_section(el, f'<{tag}>')
                if sec and sec.link_count >= 2:
                    self.sections.append(sec)

    def _from_heuristic_classes(self):
        """第二轮：class/id 启发式"""
        seen_selectors = set()

        for pattern, role in CLASS_ROLE_MAP:
            # 查找 id
            el = self.soup.find(id=re.compile(pattern, re.I))
            if el and el.name not in ['nav', 'main', 'article', 'aside', 'header', 'footer']:
                sel = f'#{el.get("id","")}'
                if sel not in seen_selectors:
                    seen_selectors.add(sel)
                    sec = self._make_section(el, sel)
                    if sec and sec.link_count >= 2:
                        # 检查是否与已有 section 重叠
                        if not self._is_duplicate(sec):
                            self.sections.append(sec)

            # 查找 class（只取第一个有链接的）
            class_els = self.soup.find_all(class_=re.compile(pattern, re.I))
            for cel in class_els:
                if cel.name in ['nav', 'main', 'article', 'aside', 'header', 'footer']:
                    continue
                sel = '.' + pattern
                if sel in seen_selectors:
                    continue
                seen_selectors.add(sel)
                sec = self._make_section(cel, sel)
                if sec and sec.link_count >= 2 and not self._is_duplicate(sec):
                    self.sections.append(sec)
                    break  # 每个 pattern 只取第一个

    def _from_heading_division(self):
        """第三轮：按页面中的标题文本划分区块

        门户网站常见结构：
          <div class="section"> <h2>标题</h2> <ul>...</ul> </div>
          <span class="title">标题</span> <div class="list">...</div>

        扫描页面中所有"短文本 + 链接列表"组合，识别为独立区块
        """
        # 寻找子容器级别的标题→内容分组
        # 策略：找 body 下的直接 div 子元素，看它们是否包含标题文本+链接列表
        body = self.soup.find('body')
        if not body:
            body = self.soup

        # 找所有可能分组的容器
        containers = []
        for tag in ['div', 'section', 'ul', 'ol']:
            # 找 body 的直接子元素中的容器
            if body:
                for child in body.find_all(tag, recursive=False):
                    containers.append(child)
            # 也找深一层的关键容器
            for el in self.soup.find_all(tag, class_=re.compile(r'section|block|module|list|wrap|area', re.I)):
                if el not in containers:
                    containers.append(el)

        seen_sigs = set()
        for container in containers:
            # 跳过已被覆盖的大块区域
            if container.find_parent(['nav', 'footer', 'header']):
                continue
            if self._is_already_section(container):
                continue

            heading = self._find_heading_text(container)
            links = self._extract_links(container)

            if heading and len(links) >= 3:
                # 过滤：标题太长的可能是文章正文，不是区块标题
                if len(heading) > 16:
                    continue
                # 过滤：标题也在链接文本中出现过 → 可能是"查看更多"类
                link_texts = {l.text[:10] for l in links}
                if heading[:6] in link_texts:
                    continue
                # 检查是否有意义（标题不是链接文本的一部分）
                sig = heading[:15] + str(len(links))
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    sec = Section(
                        label=heading,
                        role='内容区',
                        tag_info=f'<{container.name}> (标题划分)',
                        heading_text=heading,
                        links=links,
                        link_count=len(links),
                    )
                    if not self._is_duplicate(sec):
                        self.sections.append(sec)

    def _find_heading_text(self, container) -> str:
        """尝试从容器中提取区块标题文本"""
        # 黑名单：这些词不作为区块标题
        BLACKLIST = {'更多', '查看更多', '更多链接', '全部', '全部链接',
                     '详细', '详情', '相关', '相关内容', '最新', '最新文章',
                     '热门', '推荐', '今日热点', '点击进入'}

        # 1. 显式标题标签
        for hn in HEADING_TAGS:
            h = container.find(hn)
            if h:
                t = self._text(h)
                if t and 1 < len(t) < 30 and t not in BLACKLIST:
                    return t

        # 2. class 含 title/name/header 的元素
        title_els = container.find_all(class_=re.compile(r'title|name|header|caption|label|tit|bt[_-]', re.I))
        for te in title_els:
            t = self._text(te)
            if t and 1 < len(t) < 30 and t not in BLACKLIST:
                return t

        # 3. strong/b 标签包裹的短文本
        for strong in container.find_all(['strong', 'b']):
            t = self._text(strong)
            if t and 1 < len(t) < 20 and t not in BLACKLIST:
                return t

        # 4. 图片 alt 文本（如 信披+、 热门公告 等）
        for img in container.find_all('img', alt=True):
            alt = img['alt'].strip()
            if alt and 1 < len(alt) < 20 and alt not in BLACKLIST:
                if not alt.startswith(('Image', 'image', 'icon', 'logo', 'img')):
                    return alt

        return ''

    def _is_already_section(self, container) -> bool:
        """检查此容器是否被已有 section 覆盖"""
        for sec in self.sections:
            for l in sec.links:
                # 如果容器内的链接大部份已被提取，跳过
                container_links = {l.href for l in self._extract_links(container)}
                sec_links = {l.href for l in sec.links}
                if container_links and sec_links:
                    overlap = len(container_links & sec_links) / len(container_links)
                    if overlap > 0.7:
                        return True
        return False

    def _make_section(self, el, tag_info: str) -> Optional[Section]:
        """从 DOM 元素生成 Section"""
        role = self._detect_role(el)
        label = self._detect_label(el) or role
        links = self._extract_links(el)

        if not links:
            return None

        sec = Section(
            label=label,
            role=role,
            tag_info=tag_info,
            heading_text=label,
            links=links,
            link_count=len(links),
        )
        return sec

    def _extract_links(self, container) -> List[LinkItem]:
        """提取区域内的重要链接"""
        seen = set()
        items = []
        for a in container.find_all('a', href=True):
            href = self._norm_url(a.get('href', ''))
            text = self._text(a)
            if not href or not text:
                continue
            if href in seen:
                continue
            seen.add(href)
            # 过滤无意义链接
            if re.match(r'^\d+$', text):
                continue
            items.append(LinkItem(
                text=text[:80],
                href=href,
                is_external=not self._is_internal(href),
            ))
        return items

    def _is_duplicate(self, sec: Section) -> bool:
        """检查与已有 section 是否重叠（URL 交集过大）"""
        for existing in self.sections:
            existing_hrefs = {l.href for l in existing.links}
            new_hrefs = {l.href for l in sec.links}
            if not existing_hrefs or not new_hrefs:
                continue
            intersection = existing_hrefs & new_hrefs
            overlap = len(intersection) / min(len(existing_hrefs), len(new_hrefs))
            if overlap > 0.6:
                return True
        return False

    def _find_search(self):
        """检测搜索功能"""
        # form 搜索
        for form in self.soup.find_all('form'):
            action = form.get('action', '')
            inputs = form.find_all('input', type=re.compile(r'text|search', re.I))
            if inputs or 'search' in action.lower():
                endpoint = self._norm_url(action) if action else '/search'
                sec = Section(
                    label='搜索',
                    role='搜索',
                    tag_info='<form>',
                    has_search=True,
                    search_endpoint=endpoint,
                    link_count=0,
                )
                self.sections.append(sec)
                return

        # a 链接搜索
        for a in self.soup.find_all('a', href=re.compile(r'(search|so\.|s\?|kw=)', re.I)):
            href = self._norm_url(a.get('href', ''))
            if href:
                sec = Section(
                    label='搜索',
                    role='搜索',
                    tag_info='<a>',
                    has_search=True,
                    search_endpoint=href,
                    link_count=0,
                )
                self.sections.append(sec)
                return

    def _deduplicate_and_sort(self):
        """去重+排序+空节点过滤"""
        # 过滤空节点
        self.sections = [s for s in self.sections if s.link_count > 0 or s.has_search]

        # 按角色排序
        role_order = {'导航': 0, '页头': 1, '搜索': 2, '横幅': 3, '推荐': 4,
                     '面包屑': 5, '行情': 6, '内容区': 7, '视频': 8,
                     '公告': 9, '数据': 10, '标签': 11, '产品': 12,
                     '活动': 13, '侧栏': 14, '友情链接': 15, '订阅': 16,
                     '页脚': 17, '未分类': 18}

        def sort_key(s):
            return (role_order.get(s.role, 99), -s.link_count)

        self.sections.sort(key=sort_key)


# ============================================================
# Markdown 输出
# ============================================================

class MarkdownWriter:
    """将 sections 输出为可折叠树状 Markdown"""

    def __init__(self, max_links_per=30):
        self.max_links = max_links_per

    def write(self, sections: List[Section], domain: str) -> str:
        lines = []
        lines.append(f'# 🌐 网站结构: {domain}')
        lines.append('')
        import datetime
        lines.append(f'> 生成时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append(f'> 区域数: {len(sections)}')
        total_links = sum(s.link_count for s in sections)
        lines.append(f'> 总链接数: {total_links}')
        # 列出所有可用子路径
        all_paths = set()
        for s in sections:
            for l in s.links:
                p = urlparse(l.href).path
                if p and p != '/':
                    all_paths.add(p)
        if all_paths:
            lines.append(f'> 检测到子路径: {len(all_paths)} 条')
        lines.append('')
        lines.append('---')
        lines.append('')

        for i, sec in enumerate(sections):
            self._write_section(lines, sec, i)

        return '\n'.join(lines)

    def _write_section(self, lines, sec: Section, idx: int):
        emoji = ROLE_EMOJI.get(sec.role, '📄')
        label = sec.label if len(sec.label) < 60 else sec.label[:57] + '...'
        summary = f'{emoji} **{label}**'

        if sec.role != '未分类':
            summary += f'  `[{sec.role}]`'
        if sec.link_count > 0:
            summary += f'  ({sec.link_count} 条)'
        if sec.tag_info:
            tag = sec.tag_info.replace('(?:^|[\\s_\\-])', '').replace('(?:[\\s_\\-]|$)', '')
            tag = tag.replace('(?:[\\s_\\-])', '')
            if len(tag) > 30:
                tag = tag[:28] + '..'
            summary += f'  _{tag}_'

        if sec.has_search:
            lines.append(f'## 🔍 搜索')
            lines.append('')
            lines.append(f'| 字段 | 内容 |')
            lines.append(f'| --- | --- |')
            lines.append(f'| 端点 | `{sec.search_endpoint}` |')
            lines.append(f'| 用法 | `{sec.search_endpoint}?q=关键词` |')
            lines.append('')
            return

        # 用 <details> 实现折叠（链接数 > 5 或包含子项时折叠）
        fold = sec.link_count > 5
        if fold:
            lines.append(f'<details>')
            lines.append(f'<summary>{summary}</summary>')
            lines.append('')
        else:
            lines.append(f'### {summary}')
            lines.append('')

        # 链接列表
        for item in sec.links[:self.max_links]:
            external = ' 🌐' if item.is_external else ''
            lines.append(f'- [{item.text}]({item.href}){external}')

        if sec.link_count > self.max_links:
            lines.append(f'- ... _还有 {sec.link_count - self.max_links} 条_')

        if fold:
            lines.append('')
            lines.append('</details>')
        lines.append('')


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='解析网站 HTML 生成树状结构 Markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  %(prog)s -u https://www.stcn.com -o structure.md
  %(prog)s -f page.html
  %(prog)s -u https://example.com --max-links 50'''
    )
    parser.add_argument('-u', '--url', help='目标网站 URL')
    parser.add_argument('-f', '--file', help='本地 HTML 文件')
    parser.add_argument('-o', '--output', help='输出 Markdown 路径')
    parser.add_argument('--max-links', type=int, default=30)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    if not args.url and not args.file:
        parser.print_help()
        print('\n错误: 必须指定 --url 或 --file')
        sys.exit(1)

    source = args.url or args.file
    print(f'🔍 正在解析: {source}')

    parser_obj = SiteParser(source)
    sections = parser_obj.parse()

    writer = MarkdownWriter(max_links_per=args.max_links)
    md = writer.write(sections, parser_obj.domain or source)

    # 输出路径
    if args.output:
        out_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(script_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)
        domain = parser_obj.domain or 'website'
        out_path = os.path.join(results_dir, f'site_structure_{domain}.md')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f'✅ 已保存: {out_path}')
    print(f'   区域: {len(sections)}, 链接: {sum(s.link_count for s in sections)}')

    if args.debug:
        for s in sections:
            print(f'  [{s.role}] {s.label} ({s.link_count} links) '
                  f'{f"🔍{s.search_endpoint}" if s.has_search else ""}')


if __name__ == '__main__':
    main()
