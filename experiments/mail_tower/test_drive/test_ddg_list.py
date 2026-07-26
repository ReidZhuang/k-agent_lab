#!/usr/bin/env python3
"""
DDG + mode=list 测试脚本

输入:
    --query / -q    搜索关键词 (默认: 广生堂)
    --max / -n      最大条数 (默认: 10)
    --site          站内限定域名 (可选)
    --timelimit     时间限制 d/w/m/y (可选)
    --filter_days   正文提取后日期过滤天数 (可选)
    --filter_title  标题关键词过滤 (可选)
    --url / -u      API 地址 (默认: http://localhost:8300)
    --extract / -e  需要取正文的 article_id (逗号分隔)
    --session / -s  复用已有 session_id（跳过搜索，配合 -e 提取正文）

输出:
    results/<query>_ddg_<date>.json          — 原始 API 响应
    results/<query>_ddg_<date>.md            — 格式化报告
    results/<query>_ddg_<date>/<id>_正文.md  — 提取的正文 (-e 时)

DDG 特点:
    - 正文在搜索时已自动提取完毕，/article 立即可取
    - 预览含 word_count (去空白字数)、snippet、date
    - 支持 filter_days / filter_title 二次过滤
    - PDF 公告页后台异步提取（15s 超时），首次调用可能返回 processing
"""
import argparse, json, os, sys, time
from datetime import date

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
    lines.append(f"# DDG 通用搜索报告\n")
    lines.append(f"**关键词**: {params['query']}  ")
    if params.get('site'):
        lines.append(f"**站内**: {params['site']}  ")
    if params.get('timelimit'):
        lines.append(f"**时间限制**: {params['timelimit']}  ")
    if params.get('filter_days'):
        lines.append(f"**日期过滤**: {params['filter_days']} 天  ")
    lines.append(f"**引擎**: ddg | **模式**: list\n")
    lines.append(f"---\n")
    lines.append(f"## 结果汇总\n")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 状态 | {raw.get('status','?')} |")
    lines.append(f"| 总条数 | **{raw.get('preview',{}).get('total',0)}** |")
    lines.append(f"| 原始条数 | {raw.get('preview',{}).get('total_raw',0)} |")
    fs = raw.get('preview',{}).get('filter_stats', {})
    if fs:
        lines.append(f"| 过滤丢弃 | {fs.get('dropped_count',0)} |")
    lines.append(f"| empty | {raw.get('empty','?')} |")
    lines.append(f"| Session | `{raw.get('session_id','')}` |\n")

    if not articles:
        lines.append("*无匹配结果。*\n")
    else:
        lines.append("## 文章列表\n")
        for a in articles:
            lines.append(f"### {a['id']}. {a['title']}\n")
            lines.append(f"- **日期**: {a.get('date','')}")
            lines.append(f"- **来源**: {a.get('source','')}")
            lines.append(f"- **字数**: {a.get('word_count',0)}")
            lines.append(f"- **摘要**: {a.get('snippet','')[:200]}")
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
    parser = argparse.ArgumentParser(description="DDG + mode=list 测试")
    parser.add_argument("-q", "--query", default="广生堂", help="搜索关键词")
    parser.add_argument("-n", "--max", type=int, default=10, help="最大条数 (默认: 10)")
    parser.add_argument("--site", help="站内限定域名")
    parser.add_argument("--timelimit", help="时间限制 d/w/m/y")
    parser.add_argument("--filter_days", type=int, help="日期过滤天数")
    parser.add_argument("--filter_title", help="标题关键词过滤")
    parser.add_argument("-u", "--url", default="http://localhost:8300", help="API 地址")
    parser.add_argument("-e", "--extract",
                        help="提取正文的 ID，逗号分隔 如 a_01,a_03")
    parser.add_argument("-s", "--session",
                        help="复用已有 session_id（跳过搜索，配合 -e 提取正文）")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    # ── 分支：复用已有 session / 新搜索 ──
    if args.session:
        session_id = args.session
        # 找已有结果目录
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
            print(f"    {a['id']} | wc={a.get('word_count','?')} | {a['title'][:55]}")
    else:
        ts = today
        tag = f"{args.query}_ddg_{ts}"
        outdir = os.path.join(RESULTS_DIR, tag)
        os.makedirs(outdir, exist_ok=True)

        # 搜索
        print(f"🔍 DDG search: {args.query}")
        payload = {
            "query": args.query, "engine": "ddg", "mode": "list",
            "max_results": args.max,
        }
        if args.site: payload["site"] = args.site
        if args.timelimit: payload["timelimit"] = args.timelimit
        if args.filter_days: payload["filter_days"] = args.filter_days
        if args.filter_title: payload["filter_title"] = args.filter_title

        r = requests.post(f"{base_url}/search", json=payload, timeout=180)
        data = r.json()
        save_json(data, os.path.join(outdir, "raw.json"))
        print(f"  Status: {data.get('status','?')}")
        print(f"  Total: {data.get('preview',{}).get('total',0)}")

        articles = data.get("preview", {}).get("articles", [])
        for a in articles:
            print(f"    {a['id']} | wc={a.get('word_count','?')} | {a['title'][:55]}")

        # 保存 MD
        params = {k: getattr(args, k) for k in ['query','site','timelimit','filter_days']}
        save_md(articles, params, data, os.path.join(outdir, "report.md"))
        print(f"  📄 report.md")

        session_id = data.get("session_id", "")

    # ── 提取正文 ──
    if args.extract:
        ids = [x.strip() for x in args.extract.split(",")]
        print(f"\n📝 取正文: {ids}")
        for aid in ids:
            save_body(session_id, aid, base_url, outdir)
    elif not args.session:
        print("\n💡 使用 -e a_01,a_02,... 提取正文")
        print("   或 -s <session_id> -e a_01,... 复用已有 session")

    print(f"\n📁 结果目录: {outdir}")


if __name__ == "__main__":
    main()
