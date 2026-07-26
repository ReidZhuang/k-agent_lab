#!/usr/bin/env python3
"""DDG 博瑞医药 - 提取 a_03 a_08 a_10 a_16 正文"""
import uvicorn, threading, time, requests, json, os

def start():
    uvicorn.run('api:app', host='0.0.0.0', port=8393, log_level='warning')

t = threading.Thread(target=start, daemon=True)
t.start()
time.sleep(3)
base = 'http://localhost:8393'

# 搜索
r = requests.post(f'{base}/search', json={
    'query': '博瑞医药', 'engine': 'ddg', 'mode': 'list',
    'max_results': 30, 'timelimit': 'm', 'filter_days': 7,
    'site': 'news.10jqka.com.cn',
})
sid = r.json()['session_id']

outdir = '/home/stockagent/project_space/research/experiments/web_bot_agent/version_3.0/results/test3'
ids = ['a_03', 'a_08', 'a_10', 'a_16']
for aid in ids:
    r = requests.post(f'{base}/article', json={'session_id': sid, 'article_id': aid})
    d = r.json()
    body = d.get('body_text', '')
    err = d.get('fetch_error', '')
    print(f'=== {aid} ===')
    print(f'Status: {d["status"]} | Body: {len(body)} chars | Error: {err}')
    print(body[:400])
    print()
    fp = f'{outdir}/{aid}_博瑞医药_正文.md'
    with open(fp, 'w') as f:
        f.write(f'# {aid} 博瑞医药 正文\n\n**来源**: {d.get("url","")}\n\n{body or "(正文为空)"}')
    print(f'Saved: {fp}')
