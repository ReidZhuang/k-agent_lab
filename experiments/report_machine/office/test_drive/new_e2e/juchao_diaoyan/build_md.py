"""
从 fetch_diaoyan.py 的输出目录生成调研记录 md

用法:
    python build_md.py <输出目录> [--top N] [--out path.md]

md 结构:
    # 巨潮调研记录 — <名称>(<代码>)
    - 元信息(数据源/时间范围/生成时间/总条数)
    - 调研记录列表(表格: 序号/日期/标题/PDF链接)
    - 最近 N 篇正文(默认3篇, 取日期最新的 N 条; 演示资料类优先跳过可加 --skip-demo)
"""
import argparse
import json
import os
import re
from datetime import datetime

from fetch_diaoyan import lookup_stock  # 复用 orgId 解析


def build_md(out_dir: str, top: int = 3, skip_demo: bool = False,
             start: str = "", end: str = "") -> str:
    list_path = os.path.join(out_dir, "list.json")
    with open(list_path, encoding="utf-8") as f:
        data = json.load(f)
    stock = data["stock"]
    items = data["items"]

    lines = []
    lines.append(f"# 巨潮调研记录 — {stock['name']}({stock['code']})")
    lines.append("")
    lines.append("- 数据源: 巨潮资讯网 调研页签(tabName=relation)")
    if start and end:
        lines.append(f"- 时间范围: {start} ~ {end}")
    lines.append(f"- 记录总数: {data['total']} 条")
    lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # ── 列表 ──
    lines.append("## 调研记录列表")
    lines.append("")
    if not items:
        lines.append("*最近半年内无调研记录。*")
        lines.append("")
        lines.append("> 说明: 巨潮'调研'分类数据仅深市(A股 00/30 开头)完整;")
        lines.append("> 沪市(60/68 开头)该分类基本无数据(仅有少量2022年前历史记录)。")
        lines.append("> 沪市公司调研记录的正源为上交所互动平台, 如需沪市数据需另接数据源。")
        lines.append("")
    else:
        lines.append("| # | 日期 | 标题 | PDF |")
        lines.append("|---|---|---|---|")
        for i, it in enumerate(items, 1):
            pdf_link = it.get("pdf_url") or (
                f"http://static.cninfo.com.cn/{it['adjunct_url']}" if it.get("adjunct_url") else "")
            link = f"[下载]({pdf_link})" if pdf_link else "-"
            lines.append(f"| {i} | {it['date']} | {it['title']} | {link} |")
        lines.append("")

    # ── 正文 ──
    body_items = [it for it in items if it.get("text_file")]
    if skip_demo:
        body_items = [it for it in body_items
                      if not re.search(r"演示资料|演示材料|幻灯片", it["title"])]
    body_items = sorted(body_items, key=lambda x: x["date"], reverse=True)[:top]

    lines.append(f"## 最近 {len(body_items)} 篇调研正文")
    lines.append("")
    if not body_items:
        lines.append("*无可用正文。*")
        lines.append("")
    for it in body_items:
        title = re.sub(r"^#+\s*", "", it["title"])
        lines.append(f"### {it['date']} {title}")
        lines.append("")
        txt_path = os.path.join(out_dir, it["text_file"])
        if os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8") as f:
                body = f.read()
            # 去掉文件头(标题/日期/来源 3 行)
            body_lines = body.split("\n")
            body = "\n".join(body_lines[3:]).strip()
            lines.append(body)
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成调研记录 md")
    ap.add_argument("out_dir", help="fetch_diaoyan.py 的输出目录")
    ap.add_argument("--top", type=int, default=3, help="正文篇数(默认3)")
    ap.add_argument("--skip-demo", action="store_true", help="跳过演示资料类")
    ap.add_argument("--out", default="", help="输出md路径(默认与out_dir同名)")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    md = build_md(out_dir, top=args.top, skip_demo=args.skip_demo)
    out_path = args.out or os.path.join(os.path.dirname(out_dir), f"{os.path.basename(out_dir)}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[完成] → {out_path}")


if __name__ == "__main__":
    main()
