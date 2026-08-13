"""
巨潮(www.cninfo.com.cn) 调研记录爬取实验脚本

输入股票代码或名称 → 解析 orgId → 拉取调研(投资者关系活动记录)列表
→ 下载 PDF → 提取正文 → 输出 JSON 列表 + 正文文本文件

用法:
    python fetch_diaoyan.py 002821
    python fetch_diaoyan.py 凯莱英
    python fetch_diaoyan.py 002821 --max 5          # 只取最新5条
    python fetch_diaoyan.py 002821 --no-pdf          # 只要列表,不下载PDF
    python fetch_diaoyan.py 002821 --start 2026-01-01 --end 2026-12-31

输出目录: office/output/juchao_diaoyan/<code>_<name>/
    list.json        调研列表(标题/日期/PDF链接)
    pdfs/<n>_<标题>.pdf   下载的原始 PDF
    texts/<n>_<标题>.txt  提取的正文

接口说明(2026-08 实测):
    1. orgId 解析: POST /new/information/topSearch/query {keyWord, maxNum, plate:""}
       → [{"code","orgId","zwjc",...}]   (plate 必须留空,带值返回空列表)
    2. 调研列表:   POST /new/hisAnnouncement/query {tabName:"relation", stock:"<code>,<orgId>"}
       → announcements[] (调研页签即 tabName=relation, 不是 category 参数)
    3. PDF 直链:   http://static.cninfo.com.cn/<adjunctUrl>
    4. 正文:       pypdf 提取
"""
import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from pypdf import PdfReader

CNINFO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.cninfo.com.cn/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}

BASE = "https://www.cninfo.com.cn"
REQ_INTERVAL = 0.3          # 请求间隔,避免给巨潮压力
PAGE_SIZE = 30              # 每页条数
MAX_TEXT_CHARS = 10000      # 正文截断上限(字符)


def lookup_stock(keyword: str) -> dict | None:
    """按代码或名称查巨潮证券信息,返回 {code, orgId, name}"""
    r = requests.post(
        f"{BASE}/new/information/topSearch/query",
        data={"keyWord": keyword, "maxNum": 10, "plate": ""},
        headers=CNINFO_HEADERS, timeout=20,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        return None
    # 优先精确匹配代码或名称
    for it in items:
        if it.get("code") == keyword or it.get("zwjc") == keyword:
            return {"code": it["code"], "orgId": it["orgId"], "name": it.get("zwjc")}
    it = items[0]
    return {"code": it["code"], "orgId": it["orgId"], "name": it.get("zwjc")}


def infer_column(code: str) -> tuple[str, str]:
    """按代码段推断巨潮 (column, plate)

    实测: 沪市(column=sse)必须带 plate=sh 才有数据;深市(column=szse) plate 留空即可
    """
    if code.startswith(("60", "68", "90")):
        return "sse", "sh"
    if code.startswith(("00", "30", "20")):
        return "szse", "sz"
    if code.startswith(("8", "4", "92")):
        return "bj", "bj"
    return "szse", "sz"


def fetch_diaoyan_list(stock: dict, start: str = "", end: str = "",
                       max_items: int | None = None) -> list[dict]:
    """分页拉取调研列表

    Returns: [{title, date, adjunct_url, pdf_url}]
    """
    column, plate = infer_column(stock["code"])
    se_date = f"{start}~{end}" if start and end else ""
    items: list[dict] = []
    page = 1
    while True:
        data = {
            "pageNum": page, "pageSize": PAGE_SIZE,
            "column": column, "tabName": "relation",
            "plate": plate, "stock": f'{stock["code"]},{stock["orgId"]}',
            "searchkey": "", "secid": "", "category": "", "trade": "",
            "seDate": se_date, "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        r = requests.post(f"{BASE}/new/hisAnnouncement/query",
                          data=data, headers=CNINFO_HEADERS, timeout=20)
        r.raise_for_status()
        j = r.json()
        anns = j.get("announcements") or []
        for a in anns:
            ts = a.get("announcementTime")
            date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""
            items.append({
                "title": a.get("announcementTitle", ""),
                "date": date,
                "adjunct_url": a.get("adjunctUrl", ""),
                "pdf_url": a.get("pdfUrl") or "",
            })
        total = j.get("totalAnnouncement", 0)
        if page * PAGE_SIZE >= total or not anns:
            break
        if max_items and len(items) >= max_items:
            break
        page += 1
        time.sleep(REQ_INTERVAL)
    if max_items:
        items = items[:max_items]
    return items


def fetch_pdf_text(item: dict, pdf_dir: str, index: int) -> tuple[str, str]:
    """下载 PDF 并提取正文,返回 (正文文本, 本地PDF路径)"""
    if item["adjunct_url"]:
        pdf_url = f"http://static.cninfo.com.cn/{item['adjunct_url']}"
    else:
        pdf_url = item["pdf_url"]
    if not pdf_url:
        return "", ""

    r = requests.get(pdf_url, headers=CNINFO_HEADERS, timeout=30)
    r.raise_for_status()
    if "application/pdf" not in r.headers.get("Content-Type", "") and \
       "octet-stream" not in r.headers.get("Content-Type", ""):
        return "", ""

    safe_title = re.sub(r'[\\/:*?"<>|\s]+', "_", item["title"])[:60]
    pdf_path = os.path.join(pdf_dir, f"{index:02d}_{safe_title}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(r.content)

    reader = PdfReader(io.BytesIO(r.content))
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t.strip())
    text = "\n\n".join(parts)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[截断]"
    return text, pdf_path


def main():
    ap = argparse.ArgumentParser(description="巨潮调研记录爬取")
    ap.add_argument("keyword", help="股票代码或名称,如 002821 / 凯莱英")
    ap.add_argument("--max", type=int, default=None, help="最多取N条(默认全部)")
    ap.add_argument("--start", default="", help="开始日期 YYYY-MM-DD")
    ap.add_argument("--end", default="", help="结束日期 YYYY-MM-DD")
    ap.add_argument("--no-pdf", action="store_true", help="只列列表不下载PDF")
    args = ap.parse_args()

    stock = lookup_stock(args.keyword)
    if not stock:
        print(f"[错误] 未找到证券: {args.keyword}")
        sys.exit(1)
    print(f"[证券] {stock['name']}({stock['code']}) orgId={stock['orgId']}")

    items = fetch_diaoyan_list(stock, args.start, args.end, args.max)
    print(f"[列表] 共 {len(items)} 条调研记录")

    if not items:
        return

    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                           "output", "juchao_diaoyan",
                           f"{stock['code']}_{stock['name']}")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    for i, it in enumerate(items, 1):
        print(f"  {i}. [{it['date']}] {it['title']}")

    with open(os.path.join(out_dir, "list.json"), "w", encoding="utf-8") as f:
        json.dump({"stock": stock, "total": len(items), "items": items},
                  f, ensure_ascii=False, indent=2)
    print(f"[输出] 列表 → {os.path.join(out_dir, 'list.json')}")

    if args.no_pdf:
        return

    pdf_dir = os.path.join(out_dir, "pdfs")
    text_dir = os.path.join(out_dir, "texts")
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    ok = 0
    for i, it in enumerate(items, 1):
        try:
            text, pdf_path = fetch_pdf_text(it, pdf_dir, i)
            if text:
                safe_title = re.sub(r'[\\/:*?"<>|\s]+', "_", it["title"])[:60]
                txt_path = os.path.join(text_dir, f"{i:02d}_{safe_title}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"标题: {it['title']}\n日期: {it['date']}\n"
                            f"来源: 巨潮资讯 调研\n\n{text}")
                it["text_file"] = os.path.relpath(txt_path, out_dir)
                it["pdf_file"] = os.path.relpath(pdf_path, out_dir) if pdf_path else ""
                ok += 1
                print(f"  ✓ [{i}] 正文 {len(text)} 字")
            else:
                print(f"  ✗ [{i}] 无正文内容")
        except Exception as e:
            print(f"  ✗ [{i}] 下载/提取失败: {e}")
        time.sleep(REQ_INTERVAL)

    with open(os.path.join(out_dir, "list.json"), "w", encoding="utf-8") as f:
        json.dump({"stock": stock, "total": len(items), "items": items},
                  f, ensure_ascii=False, indent=2)
    print(f"[完成] 成功提取 {ok}/{len(items)} 条 → {out_dir}")


if __name__ == "__main__":
    main()
