"""
新浪财经研报列表抓取(httpx 直抓,仿 mail_tower sinafin 风格)

数据源: https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol={sina_code}&t1=all
symbol 格式: sz002821 / sh688166 / 002821(自动补前缀) / 002821.SZ

字段: 标题 / 报告类型 / 发布日期 / 机构 / 研究员 / 详情URL

用法:
    python fetch_reports.py sz002821                    # 全部研报
    python fetch_reports.py sz002821 --start 2026-02-10 # 发布日期过滤(最近6个月)
    python fetch_reports.py sz002821 --start 2026-02-10 --max 50
    python fetch_reports.py sz002821 --pages 3          # 固定翻3页

输出: 打印列表 + 保存 JSON 到 output/sina_report/<symbol>_<起始日>_<截止日>.json
"""
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta

import httpx

_REPORT_URL = ("https://stock.finance.sina.com.cn/stock/go.php/"
               "vReport_List/kind/search/index.phtml")
_PAGE_SIZE = 20          # 每页条数(实测)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://stock.finance.sina.com.cn/",
}

# ── 共享连接池(仿 sinafin: trust_env=False 直连, 重试抗 ConnectionReset) ──
_HTTP_CLIENT: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=15,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )
    return _HTTP_CLIENT


def fetch_page(url: str) -> str:
    """抓取页面(gbk 解码),失败重试最多 2 次

    注意: 必须用 GBK 而非 GB2312 — 研报页研究员名含 GB2312 外的生僻字(如 琎),gb2312 会解码成乱码
    """
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            resp = _get_client().get(url)
            resp.encoding = "gbk"
            return resp.text
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
            if attempt < max_retries:
                wait = 1.0 + random.uniform(0, 1.0)
                print(f"[sina_report] 连接失败({type(e).__name__}), {wait:.1f}s 后重试第 {attempt+1} 次", flush=True)
                time.sleep(wait)
            else:
                raise


def resolve_code(symbol: str) -> str:
    """转为新浪格式: 002821 → sz002821; sz002821 透传; 002821.SZ → sz002821"""
    q = symbol.strip()
    if re.match(r'^(sh|sz|bj)\d{6}$', q):
        return q
    if "." in q:
        parts = q.split(".")
        prefix = {"sh": "sh", "sz": "sz", "bj": "bj"}.get(parts[1].lower(), "sz")
        return f"{prefix}{parts[0]}"
    if re.match(r'^\d{6}$', q):
        prefix = {"6": "sh", "0": "sz", "3": "sz"}.get(q[0], "sz")
        return f"{prefix}{q}"
    raise ValueError(f"无法解析股票代码: {symbol}")


# ── 解析 ──

_ROW_PAT = re.compile(
    r"<tr>\s*<td>(\d+)</td>\s*"
    r'<td class="tal f14">\s*<a target="_blank" title="([^"]*)" href="([^"]*)"[^>]*>\s*(?:.*?)</a>\s*</td>\s*'
    r"<td>([^<]*)</td>\s*"          # 报告类型
    r"<td>(\d{4}-\d{2}-\d{2})</td>\s*"  # 发布日期
    r'<td>\s*<a[^>]*>\s*<div class="fname\d*"><span>([^<]*)</span></div>\s*</a>\s*</td>\s*'  # 机构
    r'<td><div class="fname"><span>([^<]*)</span></div></td>',  # 研究员
    re.DOTALL,
)


def parse_reports(html: str) -> list[dict]:
    """解析研报表行: 序号/标题/URL/类型/日期/机构/研究员"""
    items = []
    for m in _ROW_PAT.finditer(html):
        title = m.group(2).strip()
        url = m.group(3).strip()
        if url.startswith("//"):
            url = "https:" + url
        items.append({
            "title": title,
            "url": url,
            "type": m.group(4).strip(),
            "date": m.group(5),
            "org": m.group(6).strip(),
            "researcher": m.group(7).strip(),
        })
    return items


def fetch_reports(sina_code: str, start_date: str = "", end_date: str = "",
                  max_items: int | None = None, max_pages: int | None = None) -> list[dict]:
    """翻页抓取研报列表,按发布日期过滤

    翻页终止条件: 该页无数据 / 该页最后一条日期 < start_date(已过界)
    """
    items: list[dict] = []
    page = 1
    while True:
        url = f"{_REPORT_URL}?symbol={sina_code}&t1=all&p={page}"
        try:
            html = fetch_page(url)
        except Exception as e:
            print(f"[sina_report] 第{page}页抓取失败: {e}", flush=True)
            break
        page_items = parse_reports(html)
        if not page_items:
            break
        for it in page_items:
            if start_date and it["date"] < start_date:
                continue
            if end_date and it["date"] > end_date:
                continue
            items.append(it)
            if max_items and len(items) >= max_items:
                return items
        # 过界判断: 本页最后一条(按原始顺序最后一行)已早于 start_date → 停
        if start_date and page_items[-1]["date"] < start_date:
            break
        if len(page_items) < _PAGE_SIZE:
            break
        if max_pages and page >= max_pages:
            break
        page += 1
        time.sleep(0.5)
    return items


def main():
    ap = argparse.ArgumentParser(description="新浪研报列表抓取")
    ap.add_argument("symbol", help="新浪格式代码,如 sz002821(002821/sz002821/002821.SZ 均可)")
    ap.add_argument("--start", default="", help="起始日期 YYYY-MM-DD(按发布日期过滤)")
    ap.add_argument("--end", default="", help="截止日期 YYYY-MM-DD(默认今天)")
    ap.add_argument("--max", type=int, default=None, help="最多取N条")
    ap.add_argument("--pages", type=int, default=None, help="最多翻N页")
    args = ap.parse_args()

    sina_code = resolve_code(args.symbol)
    if not args.end:
        args.end = datetime.now().strftime("%Y-%m-%d")
    print(f"[研报] {sina_code} 日期范围 {args.start or '(全部)'} ~ {args.end}")

    items = fetch_reports(sina_code, args.start, args.end, args.max, args.pages)
    print(f"[列表] 共 {len(items)} 条研报\n")

    for i, it in enumerate(items, 1):
        print(f"  {i}. [{it['date']}] {it['type']} | {it['org']} | {it['researcher']}")
        print(f"     {it['title']}")
        print(f"     {it['url']}")

    # 保存 JSON
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                           "output", "sina_report")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{sina_code}_{args.start or 'all'}_{args.end}.json"
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
        json.dump({"symbol": sina_code, "start": args.start, "end": args.end,
                   "total": len(items), "items": items},
                  f, ensure_ascii=False, indent=2)
    print(f"\n[输出] → {os.path.join(out_dir, fname)}")


if __name__ == "__main__":
    main()
