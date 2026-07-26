"""
10 只新股票 × qnainfo × 最近 10 天测试。

显示完整问题全文和回答内容。

用法:
    conda run -n stock_agent python3 test_drive/test_qnainfo_v2.py
"""
import requests, time, os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8300"
START_DATE = "2026-07-14"
END_DATE = "2026-07-24"
MAX_RESULTS = 20

STOCKS = [
    ("美的集团", "000333"),
    ("格力电器", "000651"),
    ("五粮液", "000858"),
    ("牧原股份", "002714"),
    ("迈瑞医疗", "300760"),
    ("东方财富", "300059"),
    ("立讯精密", "002475"),
    ("阳光电源", "300274"),
    ("爱尔眼科", "300015"),
    ("万华化学", "600309"),
]

REPORT = []
def log(s=""):
    REPORT.append(s)
    print(s)

def search_one(name, code, idx):
    t0 = time.time()
    try:
        r = requests.post(f"{API_BASE}/search", json={
            "query": code, "engine": "qnainfo", "mode": "list",
            "max_results": MAX_RESULTS,
            "start_date": START_DATE, "end_date": END_DATE,
        }, timeout=120)
        http = r.status_code
        j = r.json() if r.ok else {}
    except Exception as e:
        return (idx, name, code, 0, "ERR", 0, [], str(e)[:60])
    p = j.get("preview", {})
    return (idx, name, code, http, j.get("status", "?"),
            p.get("total", 0), p.get("articles", []), "")

log("# qnainfo 测试 — 10 只新股票 × 最近 10 天")
log()
log(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log(f"**引擎**: qnainfo（互动易问答）")
log(f"**时间范围**: {START_DATE} ~ {END_DATE}（最近 10 天）")
log(f"**显示内容**: 问题全文 + 回答全文")
log()

# ── 并发搜索 ──
log("## 搜索结果概览")
log()
log("| # | 股票 | 代码 | HTTP | 状态 | 耗时(s) | 条数 |")
log("|---|------|------|:----:|:----:|:-------:|:----:|")

all_results = []
t_all = time.time()
with ThreadPoolExecutor(10) as pool:
    fmap = {pool.submit(search_one, n, c, i): i for i, (n, c) in enumerate(STOCKS)}
    for f in as_completed(fmap):
        all_results.append(f.result())
all_results.sort()
wall = round(time.time() - t_all, 2)

total_arts = 0
for idx, name, code, http, status, total, arts, err in all_results:
    total_arts += total
    log(f"| {idx+1} | {name} | {code} | {http} | {status} | {round(time.time()-t_all,2) if idx==0 else ''} | {total} |")

log()
log(f"> 总计: **{total_arts}** 篇 | 有数据的股票: {sum(1 for r in all_results if r[5]>0)} 只 | "
    f"空结果: {sum(1 for r in all_results if r[5]==0)} 只 | 并发耗时: **{wall}s**")
log()

# ── 详情 ──
log("---")
log("## 各股票问答详情")
log()

for idx, name, code, http, status, total, arts, err in all_results:
    if not arts:
        continue
    log(f"### {idx+1}. {name}（{code}）— {total} 条问答")
    log()
    for a in arts:
        q = a.get("_question", a.get("title", ""))
        ans = a.get("_answer", "")
        log(f"**问题（ID: {a['id']}）**")
        log(f"- 更新时间: `{a.get('date','')}`")
        log(f"- 提问时间: `{a.get('_ask_time','')}`")
        log(f"- 回答者: **{a.get('_answerer','')}**")
        log()
        log(f"**问题全文:**")
        log(f"> {q}")
        log()
        log(f"**回答内容:**")
        log(f"> {ans}")
        log()
        log("---")
        log()
    log()

# 无数据的
nodata = [r for r in all_results if r[5] == 0]
if nodata:
    log("---")
    log("## 无数据的股票")
    log()
    for idx, name, code, *_ in nodata:
        log(f"- {name}（{code}）— 该时间段内无已回答问答记录")
    log()

log("---")
log(f"**测试结束**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

out_dir = "test_drive/results"
os.makedirs(out_dir, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
path = os.path.join(out_dir, f"qnainfo_10stocks_10d_{ts}.md")
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(REPORT))
print(f"\n✅ 报告: {path}")
