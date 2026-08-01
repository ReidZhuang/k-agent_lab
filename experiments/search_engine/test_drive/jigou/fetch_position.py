#!/usr/bin/env python3
"""同花顺 F10 机构持仓数据抓取 → 可读 markdown 报告

数据源（basic.10jqka.com.cn 公开接口，无鉴权，curl 直连即可）：
  - /basicapi/holder/stock/org_holder/rate       机构持股汇总（各报告期）
  - /basicapi/holder/stock/org_holder/tab        报告期 × 机构类型占比
  - /basicapi/holder/stock/org_holder/detail     机构持仓明细（分页拉全）
  - /basicapi/holder/stock/org_holder/rate_price 基金持股比例 + 对应股价
  - basic.10jqka.com.cn/{code}/position.html     IPO 网下配售结果（GBK 静态页）

用法: python3 fetch_position.py [code] [--ipo-limit N]
输出: results/{code}_position_{YYYYMMDD}.md
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://basic.10jqka.com.cn"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
OUT_DIR = Path(__file__).resolve().parent / "results"


def fetch_json(url: str) -> dict:
    """GET 接口并校验 status_code"""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("status_code") != 0:
        raise RuntimeError(f"接口返回异常: {data.get('status_code')} {url}")
    return data


def fmt_int(s: str) -> str:
    """'16161512' → '16,161,512'"""
    try:
        return f"{int(float(s)):,}"
    except (TypeError, ValueError):
        return s or "-"


def fmt_num(s: str, digits: int = 2) -> str:
    """'5.0976' → '5.10'"""
    try:
        return f"{float(s):.{digits}f}"
    except (TypeError, ValueError):
        return s or "-"


# ── 各接口 → markdown 段 ──────────────────────────────────────

def md_rate(data: list) -> str:
    """机构持股汇总：报告期 / 机构数 / 总持股 / 总市值 / 占比 / 变动"""
    lines = ["## 一、机构持股汇总", "", "| 报告期 | 机构数 | 总持股(股) | 总市值(元) | 占比(%) | 持股变动 | 变动率(%) |",
             "|:-------|:------:|:----------:|:----------:|:-------:|:--------:|:---------:|"]
    for d in data:
        lines.append(f"| {d['date']} | {d['org_num']} | {fmt_int(d['total_holder'])} | "
                     f"{fmt_int(d['total_market_value'])} | {fmt_num(d['total_rate'])} | "
                     f"{fmt_int(d['total_holder_change'])} | {fmt_num(d['total_holder_change_rate'], 2)} |")
    return "\n".join(lines)


def md_tab(data: list) -> str:
    """报告期 × 机构类型占比"""
    lines = ["## 二、机构类型占比（各报告期）", "",
             "| 报告期 | 机构类型 | 占比(%) | 持股数(股) |", "|:-------|:---------|:-------:|:----------:|"]
    for d in data:
        for t in d["tab_list"]:
            mark = " ← 最新" if d.get("is_updating") else ""
            lines.append(f"| {d['date']} | {t['name']} | {fmt_num(t['rate'])} | {fmt_int(t['holder_num'])} |{mark}")
    return "\n".join(lines)


def md_detail(data: list) -> str:
    """机构持仓明细（页面主表格）"""
    lines = ["## 三、机构持仓明细", "",
             "| 序号 | 机构类型 | 机构名称 | 代码 | 持股数(股) | 占比(%) | 环比变动 | 变动类型 | 持股市值(元) |",
             "|:----:|:---------|:---------|:-----|:----------:|:-------:|:--------:|:--------:|:------------:|"]
    for i, d in enumerate(data, 1):
        chg = fmt_int(d.get("change"))
        try:
            chg_v = float(d.get("change") or 0)
        except (TypeError, ValueError):
            chg_v = 0.0
        is_new = "新进" if d.get("is_new") else ("减持" if chg_v < 0 else "增持" if chg_v > 0 else "不变")
        lines.append(f"| {i} | {d['org_type_name']} | {d['org_name']} | {d.get('trade_code','-')} | "
                     f"{fmt_int(d['holder_num'])} | {fmt_num(d['rate'])} | {chg} | {is_new} | "
                     f"{fmt_int(d['holder_market_value'])} |")
    return "\n".join(lines)


def md_rate_price(data: list) -> str:
    """基金持股比例 + 股价历史"""
    lines = ["## 四、基金持股比例与股价", "",
             "| 报告期 | 基金占比(%) | 对应股价(元) |", "|:-------|:----------:|:-----------:|"]
    for d in data:
        mark = " ← 最新" if d.get("is_updating") else ""
        lines.append(f"| {d['date']} | {fmt_num(d['rate'])} | {fmt_num(d['price'])} |{mark}")
    return "\n".join(lines)


def md_ipo(html: str, limit: int = 20) -> str:
    """旧版 position.html（GBK）→ IPO 网下配售结果表"""
    text = re.sub(r"<[^>]+>", "|", html)
    text = re.sub(r"\s+", "", text)  # 去掉全部空白（含换行），避免单元格被拆散
    cells = [c for c in text.split("|") if c]
    # 表头定位：找 "获配数量(股)" 所在的 cell
    try:
        i = next(k for k, c in enumerate(cells) if c.startswith("获配数量"))
    except StopIteration:
        return "## 五、IPO 网下配售\n\n（未找到配售表）"
    cols = cells[i - 2:i + 4]  # 6 列表头：序号 机构名称 获配数量(股) 申购数量(股) 锁定期(月) 机构类型
    rows = []
    j = i + 4  # 数据紧随表头，每 6 个单元格一行
    while j + 6 <= len(cells):
        row = cells[j:j + 6]
        if row[0].isdigit():
            rows.append(row)
        j += 6
    out = ["## 五、IPO 网下配售结果", ""]
    if not rows:
        out.append("（未解析到数据行）")
        return "\n".join(out)
    out.append(f"共 {len(rows)} 家获配机构，展示前 {limit} 行：")
    out.append("")
    out.append("| " + " | ".join(cols) + " |")
    out.append("|" + "|".join(":------:" if k == 0 else "------" for k in range(len(cols))) + "|")
    for row in rows[:limit]:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


# ── 主流程 ─────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="同花顺 F10 机构持仓抓取 → markdown")
    ap.add_argument("code", nargs="?", default="002821", help="股票代码，默认 002821")
    ap.add_argument("--ipo-limit", type=int, default=20, help="IPO 配售表展示行数，默认 20")
    args = ap.parse_args()

    code = args.code
    stock_name = code  # 股票名优先从 position.html title 取

    # 1. rate / tab（汇总类）
    rate = fetch_json(f"{BASE}/basicapi/holder/stock/org_holder/rate?code={code}&limit=8&year=0")["data"]
    tab = fetch_json(f"{BASE}/basicapi/holder/stock/org_holder/tab?code={code}&year=0&limit=5")["data"]

    # 2. detail：取最新报告期（is_updating=1，没有则取第一个）
    latest = next((d for d in tab if d.get("is_updating")), tab[0])
    report_date = latest["report"]
    details, page = [], 1
    while True:
        d = fetch_json(f"{BASE}/basicapi/holder/stock/org_holder/detail?code={code}&date={report_date}&page={page}&size=15&type=all")["data"]
        rows = d.get("data", [])
        details.extend(rows)
        if len(rows) < 15:
            break
        page += 1

    # 3. rate_price
    rp = fetch_json(f"{BASE}/basicapi/holder/stock/org_holder/rate_price?code={code}&cate=fund&limit=8&year=0")["data"]

    # 4. IPO 配售（GBK 静态页）
    r = requests.get(f"{BASE}/{code}/position.html", headers=HEADERS, timeout=20)
    r.encoding = "gbk"
    html = r.text
    m = re.search(r"title>([^(（]+)[(（]", html)
    if m:
        stock_name = m.group(1).strip()

    # ── 组装 markdown ──
    sec = "\n\n".join([md_rate(rate), md_tab(tab), md_detail(details), md_rate_price(rp),
                       md_ipo(html, args.ipo_limit)])
    md = (f"# {stock_name}（{code}）— 机构持仓报告\n\n"
          f"> 数据源：同花顺 F10（basic.10jqka.com.cn 公开接口）\n"
          f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
          f"> 持仓明细报告期：{latest['date']}（{report_date}，共 {len(details)} 条）\n\n"
          f"{sec}\n")

    OUT_DIR.mkdir(exist_ok=True)
    out_file = OUT_DIR / f"{code}_position_{datetime.now():%Y%m%d}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"已生成: {out_file}（{len(md)} 字符）")
    print(f"  - 汇总 {len(rate)} 期 | 类型 {sum(len(d['tab_list']) for d in tab)} 行 | 明细 {len(details)} 条 | 股价 {len(rp)} 期 | IPO 表见文件")


if __name__ == "__main__":
    main()
