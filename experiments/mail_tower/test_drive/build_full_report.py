"""
从 session 文件提取全量数据，生成综合测试报告。
"""
import json, glob, os
from datetime import datetime
from collections import defaultdict

SESSIONS_DIR = '/home/stockagent/project_space/research/experiments/mail_tower/sessions'
OUT_DIR = '/home/stockagent/project_space/research/experiments/mail_tower/test_drive/results'
os.makedirs(OUT_DIR, exist_ok=True)

stock_names = {
    '000001':'平安银行','000002':'万科A','000063':'中兴通讯','000157':'中联重科',
    '000338':'潍柴动力','000799':'酒鬼酒','000895':'双汇发展','000999':'华润三九',
    '002027':'分众传媒','002230':'科大讯飞','002252':'上海莱士','002603':'以岭药业',
    '002491':'通鼎互联','300124':'汇川技术','300122':'智飞生物','300676':'华大基因',
    '300146':'汤臣倍健','300383':'光环新网','601318':'中国平安','601628':'中国人寿',
    '600519':'贵州茅台','600036':'招商银行','600900':'长江电力','600690':'海尔智家',
    '600887':'伊利股份','002714':'牧原股份','300750':'宁德时代','300760':'迈瑞医疗',
    '300059':'东方财富','603259':'药明康德','002594':'比亚迪','300274':'阳光电源',
    '300014':'亿纬锂能','002371':'北方华创','688012':'中微公司','688111':'金山办公',
    '688981':'中芯国际','600276':'恒瑞医药','600196':'复星医药','000661':'长春高新',
    '600438':'通威股份','601012':'隆基绿能','601899':'紫金矿业','603993':'洛阳钼业',
    '000333':'美的集团','000651':'格力电器','600030':'中信证券','600958':'东方证券',
}

def main():
    sessions = []
    for fpath in sorted(glob.glob(os.path.join(SESSIONS_DIR, 's_20260727*.json'))):
        with open(fpath) as f:
            data = json.load(f)
        sessions.append(data)

    by_stock = defaultdict(list)
    for s in sessions:
        by_stock[s['query']].append(s)

    lines = []
    L = lambda s="": lines.append(s)

    L("# 综合并发测试 v6 — 全量数据报告")
    L()
    L(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L()

    # 引擎统计
    engine_articles = defaultdict(lambda: {"total": 0, "ready": 0, "error": 0})
    for s in sessions:
        eng = s.get('engine','')
        preview = s.get('preview', {})
        arts = preview.get('articles', []) if preview else []
        engine_articles[eng]["total"] += len(arts)
        for aid, body in s.get('article_bodies', {}).items():
            if body.get('fetch_error'):
                engine_articles[eng]["error"] += 1
            else:
                engine_articles[eng]["ready"] += 1

    L("## 各引擎统计")
    L()
    L("| 引擎 | 搜索请求 | 文章总数 | body ready | body error |")
    L("|:-----|:-------:|:--------:|:----------:|:---------:|")
    for eng in ['baidufin','sinafin','thsfin','juchao','qnainfo']:
        st = engine_articles[eng]
        L(f"| {eng} | 15 | {st['total']} | {st['ready']} | {st['error']} |")
    L()

    # Phase 1: 全量文章列表
    L("---")
    L("## Phase 1：全量文章列表")
    L()

    for code in sorted(by_stock.keys()):
        stock_sessions = by_stock[code]
        name = stock_names.get(code, code)
        for s in stock_sessions:
            eng = s.get('engine','')
            preview = s.get('preview', {})
            arts = preview.get('articles', []) if preview else []

            L(f"### {name}（{code}）× {eng}")
            L()
            if not arts:
                L("无文章")
                L()
                continue

            for art in arts:
                aid = art.get('id','')
                title = art.get('title','')
                date = art.get('date','')
                snippet = art.get('snippet','')
                avail = art.get('body_avail','')

                L(f"- **{aid}** | {date} | body_avail={avail}")
                L(f"  **标题**: {title}")
                # 摘要：thsfin/sinafin/juchao 的 snippet 是冗余的，输出空
                if snippet and snippet != title and snippet != date and eng not in ("thsfin",):
                    L(f"  **摘要**: {snippet[:150]}")
                else:
                    L(f"  **摘要**:")
            L()

    # Phase 2: 全量文章正文
    L("---")
    L("## Phase 2：全量文章正文")
    L()

    for code in sorted(by_stock.keys()):
        stock_sessions = by_stock[code]
        name = stock_names.get(code, code)
        for s in stock_sessions:
            eng = s.get('engine','')
            bodies = s.get('article_bodies', {})
            preview = s.get('preview', {})
            arts = preview.get('articles', []) if preview else []

            if not bodies:
                continue

            L(f"### {name}（{code}）× {eng}")
            L()

            for art in arts:
                aid = art.get('id','')
                title = art.get('title','')
                body_data = bodies.get(aid, {})
                body_text = body_data.get('body_text', '')
                fetch_err = body_data.get('fetch_error', '')
                truncated = body_data.get('truncated', False)

                if fetch_err:
                    L(f"❌ **{aid}**: {title}")
                    L(f"  **提取失败**: {fetch_err}")
                    L()
                elif body_text:
                    L(f"✅ **{aid}**: {title}（{len(body_text)} 字{'，已截断' if truncated else ''}）")
                    L(f"> {body_text[:200]}")
                    if len(body_text) > 200:
                        L(f"> ...（共 {len(body_text)} 字）")
                    L()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUT_DIR, f"comprehensive_v6_full_{ts}.md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"✅ 全量报告: {path}")
    print(f"共 {len(lines)} 行")

if __name__ == '__main__':
    main()
