#!/usr/bin/env python3
"""把 iwencai 研报搜索原始响应转成结构化研报列表。

流程:
1. 读搜索接口原始响应（raw_*.json，本目录下的原始保存文件）
2. 按 uid 去重（同一篇研报的多个段落合并）
3. 对每篇研报调用 notice-detail 详情接口，补充完整正文 + PDF 路径
4. 输出 reports_list.json（全字段）+ reports_list.csv

字段说明:
- 保留搜索响应每条记录的**所有**原始字段（title/url/summary/source_original/extra/stock_infos/score 等）
- paragraphs: 该研报所有段落片段（source_original 拼接）
- detail: notice-detail 详情接口返回（content 完整正文 / path PDF 路径 / organize / researcher 等）
- pdf_url: https://ms.10jqka.com.cn/<path>（可能已失效，见 README 坑位）
"""

import csv
import json
import re
import sys
import urllib.error
import urllib.request

DETAIL_URL = "https://ms.10jqka.com.cn/gateway/unified-wap/v1/information/notice-detail"
PDF_BASE = "https://ms.10jqka.com.cn/"


def load_raw(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_detail(uid: str) -> dict:
    """调用 notice-detail 详情接口，返回 wordData 或 {}。"""
    form = "type=report&duid={}&query_source=guide&query=*:*".format(uid)
    req = urllib.request.Request(
        DETAIL_URL,
        data=form.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
        return resp.get("data", {}).get("wordData", {}) or {}
    except Exception as e:
        print(f"  [warn] 详情接口失败 uid={uid}: {e}", file=sys.stderr)
        return {}


def build_report_list(raw) -> list:
    data = raw.get("data", [])
    by_uid = {}
    for rec in data:
        uid = rec.get("uid", "")
        by_uid.setdefault(uid, []).append(rec)

    reports = []
    for uid, recs in by_uid.items():
        # 以段落得分最高的记录为基座，保留全部字段
        base = max(recs, key=lambda r: r.get("score", 0) or 0)
        report = dict(base)  # 全字段保留（含 url/summary/extra/stock_infos/score/trace_info...）
        report["paragraphs"] = [
            {
                "para_index": r.get("para_index"),
                "source_original": r.get("source_original", ""),
                "score": r.get("score"),
            }
            for r in sorted(recs, key=lambda x: x.get("para_index", 0))
        ]
        report["full_text"] = "\n".join(
            p["source_original"] for p in report["paragraphs"] if p["source_original"]
        )
        # 详情补充
        detail = fetch_detail(uid)
        if detail:
            report["detail"] = detail
            report["content_full"] = detail.get("content", "")
            report["pdf_path"] = detail.get("path", "")
            report["pdf_url"] = PDF_BASE + detail.get("path", "") if detail.get("path") else ""
            report["detail_publish_date"] = detail.get("pubtime", "")
            report["detail_org"] = detail.get("organize", "")
            report["detail_author"] = detail.get("researcher", "")
        else:
            report["detail"] = {}
            report["content_full"] = ""
            report["pdf_path"] = ""
            report["pdf_url"] = ""
        reports.append(report)
    return reports


def write_csv(reports, path):
    keys = [
        "uid", "title", "url", "publish_date", "publish_time",
        "organization", "author", "rating", "cat_names", "industries",
        "summary", "full_text", "content_full", "pdf_url", "stock_infos", "score",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in reports:
            extra = r.get("extra", {}) or {}
            row = {
                "uid": r.get("uid"),
                "title": r.get("title"),
                "url": r.get("url"),
                "publish_date": r.get("publish_date"),
                "publish_time": r.get("publish_time"),
                "organization": extra.get("organization"),
                "author": extra.get("author"),
                "rating": extra.get("rating"),
                "cat_names": json.dumps(extra.get("cat_names"), ensure_ascii=False),
                "industries": json.dumps(extra.get("industries"), ensure_ascii=False),
                "summary": r.get("summary"),
                "full_text": r.get("full_text"),
                "content_full": r.get("content_full"),
                "pdf_url": r.get("pdf_url"),
                "stock_infos": json.dumps(r.get("stock_infos"), ensure_ascii=False),
                "score": r.get("score"),
            }
            w.writerow(row)


def main():
    if len(sys.argv) < 2:
        print("用法: python transform_reports.py <raw响应.json> [--no-detail]", file=sys.stderr)
        return 2
    raw_path = sys.argv[1]
    no_detail = "--no-detail" in sys.argv
    raw = load_raw(raw_path)
    print(f"原始片段数: {len(raw.get('data', []))} | total: {raw.get('total')}")
    reports = build_report_list(raw)
    if no_detail:
        # 不调详情接口，只保留搜索字段
        for r in reports:
            r.update({"detail": {}, "content_full": "", "pdf_path": "", "pdf_url": ""})
    out_json = "reports_list.json"
    out_csv = "reports_list.csv"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    write_csv(reports, out_csv)
    print(f"研报数(去重): {len(reports)}")
    for r in reports:
        print(f"  {r.get('publish_date')} | {r.get('title','')[:40]} | {r.get('url')} | pdf:{r.get('pdf_url')}")
    print(f"输出: {out_json} / {out_csv}")


if __name__ == "__main__":
    raise SystemExit(main())
