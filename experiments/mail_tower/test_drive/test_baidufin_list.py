#!/usr/bin/env python3
"""
baidufin + mode=list 测试脚本

输入:
    --query / -q    股票代码 (默认: 300436)
    --start         开始时间 "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM" (默认: 当天)
    --end           结束时间 (默认: 当天)
    --max / -n      最大条数 (默认: 10)
    --url / -u      API 地址 (默认: http://localhost:8300)
    --extract / -e  需要提取正文的 article_id (逗号分隔，可选)
    --session / -s  复用已有 session_id（跳过搜索，配合 -e 提取正文）

输出:
    results/<stock>_baidufin_<date>.json     — 原始 API 响应
    results/<stock>_baidufin_<date>.md       — 格式化报告
    results/<stock>_baidufin_<date>/<id>_正文.md  — 提取的正文 (-e 时)

baidufin 特有字段:
    sentiment — 情绪 (利好/中性/利空)
    provider  — 来源名称 (证券之星/东方财富网/同花顺)
    snippet   — 摘要 (百度 API 返回的 abstract)
"""
import argparse, json, os, sys, time
from datetime import date
from urllib.parse import urlparse

import requests

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def find_session_dir(session_id: str) -> str | None:
    """在 results/ 中查找包含指定 session_id 的结果目录。"""
    for root, dirs, files in os.walk(RESULTS_DIR):
        if "raw.json" in files:
            try:
                with open(os.path.join(root, "raw.json")) as f:
                    data = json.load(f)
                if data.get("session_id") == session_id:
                    return root
            except Exception:
                continue
    return None


def save_json(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_md(articles: list[dict], params: dict, raw: dict, path: str):
    lines = []
    lines.append(f"# baidufin 个股资讯报告\n")
    lines.append(f"**股票**: {params['query']}  ")
    lines.append(f"**时间范围**: {params['start']} ~ {params['end']}  ")
    lines.append(f"**引擎**: baidufin | **模式**: list\n")
    lines.append(f"---\n")
    lines.append(f"## 结果汇总\n")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 状态 | {raw.get('status','?')} |")
    lines.append(f"| 总条数 | **{raw.get('preview',{}).get('total',0)}** |")
    lines.append(f"| 原始条数 | {raw.get('preview',{}).get('total_raw',0)} |")
    lines.append(f"| empty | {raw.get('empty','?')} |")
    lines.append(f"| Session | `{raw.get('session_id','')}` |\n")

    if not articles:
        lines.append("*该时间段内无相关资讯。*\n")
    else:
        lines.append("## 文章列表\n")
        for a in articles:
            lines.append(f"### {a['id']}. {a['title']}\n")
            lines.append(f"- **时间**: {a.get('date','')}")
            lines.append(f"- **来源**: {a.get('provider','')}")
            lines.append(f"- **情绪**: {a.get('sentiment','')}")
            lines.append(f"- **摘要**: {a.get('snippet','')[:300]}")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def save_body(session_id: str, article_id: str, base_url: str, outdir: str):
    r = requests.post(f"{base_url}/article", json={
        "session_id": session_id, "article_id": article_id,
    })
    d = r.json()
    status = d.get("status", d.get("detail", "unknown"))
    body = d.get("body_text", "")
    fetch_error = d.get("fetch_error", "")
    fp = os.path.join(outdir, f"{article_id}_正文.md")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"# {article_id} 正文\n\n")
        f.write(f"**状态**: {status}\n")
        f.write(f"**字数**: {len(body)}\n")
        if fetch_error:
            f.write(f"**错误**: {fetch_error}\n")
        f.write(f"\n---\n\n")
        f.write(body if body else "(正文为空)")
    print(f"  → {article_id}: {status} ({len(body)} 字)" +
          (f" error={fetch_error}" if fetch_error else ""))


def main():
    today = date.today().isoformat()
    parser = argparse.ArgumentParser(description="baidufin + mode=list 测试")
    parser.add_argument("-q", "--query", default="300436", help="股票代码")
    parser.add_argument("--start", default=today, help=f"开始时间 (默认: {today})")
    parser.add_argument("--end", default=today, help=f"结束时间 (默认: {today})")
    parser.add_argument("-n", "--max", type=int, default=10, help="最大条数 (默认: 10)")
    parser.add_argument("-u", "--url", default="http://localhost:8300", help="API 地址")
    parser.add_argument("-e", "--extract", help="提取正文的 ID，逗号分隔 如 a_01,a_03")
    parser.add_argument("-s", "--session",
                        help="复用已有 session_id（跳过搜索，配合 -e 提取正文）")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    # ── 分支：复用已有 session / 新搜索 ──
    if args.session:
        session_id = args.session
        outdir = find_session_dir(session_id)
        if not outdir:
            outdir = os.path.join(RESULTS_DIR, f"session_{session_id[:20]}")
            os.makedirs(outdir, exist_ok=True)

        print(f"🔁 复用 session: {session_id}")
        r = requests.get(f"{base_url}/poll/{session_id}")
        if r.status_code != 200:
            print(f"  ❌ session 不存在或已关闭 ({r.status_code})")
            sys.exit(1)
        data = r.json()

        articles = data.get("preview", {}).get("articles",
                   data.get("_list_articles", []))
        print(f"  Status: {data.get('status','?')} | Total: {data.get('preview',{}).get('total',0)}")
        for a in articles:
            print(f"    {a['id']} | [{a.get('sentiment','?')}] {a['title'][:55]}")
    else:
        tag = f"{args.query}_baidufin_{args.start.replace(' ','_').replace(':','')}"
        outdir = os.path.join(RESULTS_DIR, tag)
        os.makedirs(outdir, exist_ok=True)

        # 搜索
        print(f"🔍 baidufin search: {args.query} [{args.start} ~ {args.end}]")
        payload = {
            "query": args.query, "engine": "baidufin", "mode": "list",
            "max_results": args.max,
            "start_date": args.start, "end_date": args.end,
        }
        r = requests.post(f"{base_url}/search", json=payload, timeout=180)
        data = r.json()
        save_json(data, os.path.join(outdir, "raw.json"))
        print(f"  Status: {data.get('status','?')}")
        print(f"  Total: {data.get('preview',{}).get('total',0)}")

        articles = data.get("preview", {}).get("articles", [])
        for a in articles:
            print(f"    {a['id']} | [{a.get('sentiment','?')}] {a['title'][:55]}")

        # 保存 MD
        save_md(articles, {"query": args.query, "start": args.start, "end": args.end},
                data, os.path.join(outdir, "report.md"))
        print(f"  📄 report.md")

        session_id = data.get("session_id", "")

    # ── 提取正文 ──
    if args.extract:
        ids = [x.strip() for x in args.extract.split(",")]
        # baidufin 需要先等后台提取完成
        if not args.session:
            if session_id:
                for i in range(15):
                    time.sleep(2)
                    r = requests.get(f"{base_url}/poll/{session_id}")
                    st = r.json().get("status")
                    if st == "done":
                        print(f"  ✅ 后台提取完成 (poll {i})")
                        break
                else:
                    print(f"  ⚠ 后台提取未在 30s 内完成")

        print(f"\n📝 提取正文: {ids}")
        for aid in ids:
            save_body(session_id, aid, base_url, outdir)
    elif not args.session:
        print("💡 后台自动提取中，使用 -e a_01,a_02,... 保存正文")

    print(f"\n📁 结果目录: {outdir}")


if __name__ == "__main__":
    main()
