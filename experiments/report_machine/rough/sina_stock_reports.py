"""
提取新浪个股研报列表页 → 结构化 MD 报告
URL: https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol=300750&t1=all
"""

import httpx, re, json, os
from datetime import datetime

def fetch_reports(stock_code: str, max_pages: int = 1):
    """
    抓取新浪个股研报列表页
    stock_code: 纯数字，如 300750
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    all_reports = []

    for page in range(1, max_pages + 1):
        url = f'https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol={stock_code}&t1=all'
        if page > 1:
            url += f'&page={page}'

        print(f'[第{page}页] {url}')
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.encoding = 'gb2312'
        html = resp.text

        # 解析表格行
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        page_reports = []

        for row in rows:
            # 提取标题 + 链接
            link_match = re.search(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', row, re.DOTALL)
            if not link_match:
                continue
            href = link_match.group(1)
            title = re.sub(r'<[^>]+>', '', link_match.group(2)).strip()
            if not title or len(title) < 5:
                continue

            # 提取所有 <td> 文本
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            td_texts = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
            td_texts = [t for t in td_texts if t]

            # 标准格式: 序号 | 标题(含链接) | 报告类型 | 日期 | 机构 | 研究员
            # td_texts 可能是 ["1", "宁德时代...", "创业板", "2026-05-16", "华泰证券", "刘俊/边文姣..."]
            report_type = td_texts[2] if len(td_texts) > 2 else ""
            date = td_texts[3] if len(td_texts) > 3 else ""
            institution = td_texts[4] if len(td_texts) > 4 else ""
            analyst = td_texts[5] if len(td_texts) > 5 else ""

            # 完整 URL
            if href.startswith('//'):
                href = 'https:' + href

            page_reports.append({
                'title': title,
                'url': href,
                'date': date.replace('/', '-'),
                'report_type': report_type,
                'institution': institution,
                'analyst': analyst,
            })

        print(f'  提取到 {len(page_reports)} 条研报')
        all_reports.extend(page_reports)

        # 如果这页少于 25 条，说明没下一页了
        if len(page_reports) < 25:
            break

    return all_reports


def generate_md_report(reports, stock_code):
    """生成可读性强的 MD 报告"""
    # 去重（相同标题+机构视为重复）
    seen = set()
    unique = []
    for r in reports:
        key = (r['title'], r['institution'])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # 统计
    dates = sorted(set(r['date'] for r in unique if r['date']))
    institutions = {}
    for r in unique:
        inst = r['institution'] or '未知'
        institutions[inst] = institutions.get(inst, 0) + 1

    # 按日期分组
    by_date = {}
    for r in unique:
        d = r['date'] or '未知日期'
        by_date.setdefault(d, []).append(r)

    md = f"""# 宁德时代 (300750) — 券商研报汇总

**抓取日期**: 2026-07-17
**数据来源**: 新浪财经个股研报列表页
**研报总数**: {len(unique)} 条（去重后）
**时间跨度**: {dates[0] if dates else ""} ~ {dates[-1] if dates else ""}

---

## 研报概览

### 覆盖机构

| 机构 | 研报数 |
|------|:------:|
"""
    # 机构排名
    for inst, cnt in sorted(institutions.items(), key=lambda x: -x[1]):
        md += f"| {inst} | {cnt} |\n"

    md += f"\n### 时间分布\n\n| 月份 | 研报数 |\n|------|:------:|\n"
    month_count = {}
    for r in unique:
        if r['date']:
            m = r['date'][:7]
            month_count[m] = month_count.get(m, 0) + 1
    for m, cnt in sorted(month_count.items()):
        bar = '█' * cnt
        md += f"| {m} | {cnt} {bar} |\n"

    md += "\n---\n\n## 研报详情\n\n"

    # 按日期倒序排列
    for date in sorted(by_date.keys(), reverse=True):
        items = by_date[date]
        md += f"### {date}（{len(items)} 条）\n\n"
        for i, r in enumerate(items, 1):
            analyst_str = f"（{r['analyst']}）" if r['analyst'] else ""
            md += f"**{i}.** [{r['title']}]({r['url']})  \n"
            md += f"   - **机构**: {r['institution']} {analyst_str}\n\n"
        md += "---\n\n"

    return md


if __name__ == '__main__':
    stock_code = '300750'

    print(f'抓取研报列表: 宁德时代 ({stock_code})')
    print('=' * 60)

    reports = fetch_reports(stock_code, max_pages=3)

    print(f'\n共抓取 {len(reports)} 条研报')

    md = generate_md_report(reports, stock_code)

    # 保存
    rough_dir = os.path.dirname(__file__)
    output_path = os.path.join(rough_dir, f'sina_{stock_code}_reports_20260717.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'\n已保存: {output_path}')

    # 也存一份 JSON
    json_path = output_path.replace('.md', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    print(f'已保存: {json_path}')
