#!/usr/bin/env python3
"""backfill: 对已落盘 stdout.json 的 run 重做报告/usage/trace 提取(不重跑 agent)。
用法: python backfill_v2.py <task> <group> <n>
"""
import json, re, sys
from pathlib import Path

ROOT = Path('/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper')
OUT = ROOT / 'artifacts' / 'comparsion_exp'
LOG_TRACE = ROOT / 'logs' / 'trace.jsonl'
TRACE_PAYLOADS = ROOT / 'logs' / 'trace_payloads'
SERIES = 'comparsion'

def extract_trace(skey):
    prefix = f'session:agent:keeper:{skey}'
    out = []
    if not LOG_TRACE.is_file():
        return out
    for line in open(LOG_TRACE):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        rid = ev.get('runId') or ''
        if not rid.startswith(prefix):
            continue
        ref = ev.get('payload_ref')
        if ref and 'payload' not in ev:
            pf = TRACE_PAYLOADS / f'{ref}.json'
            ev['payload'] = pf.read_text(encoding='utf-8') if pf.is_file() else f'(missing:{pf.name})'
        out.append(json.dumps(ev, ensure_ascii=False))
    return out

def main():
    task, group, n = sys.argv[1], sys.argv[2], sys.argv[3]
    skey = f'{SERIES}_{task}_{group}_{n}'
    d = OUT / f'{task}_{group}_{n}'
    so = d / f'{skey}.stdout.json'
    if not so.is_file():
        raise SystemExit(f'no stdout: {so}')
    proc_stdout = so.read_text()
    try:
        data = json.loads(proc_stdout)
    except Exception:
        raise SystemExit('stdout not json')
    res = data.get('result', data)
    meta = (res.get('meta') or {}).get('agentMeta') or {}
    usage = meta.get('usage') or {}
    text = res.get('finalAssistantVisibleText') or res.get('finalAssistantRawText') or ''
    if not text or len(text.strip()) < 100:
        ws_reports = Path.home() / '.openclaw' / 'workspace' / 'reports'
        for pl in (res.get('payloads') or []):
            pt = (pl.get('text') or '')
            m = re.search(r'([^\s`"\']+\.md)', pt)
            found = False
            if m:
                rel = m.group(1)
                for cand in [Path(rel), ROOT / rel, Path.home() / '.openclaw' / 'workspace' / rel,
                             ws_reports / Path(rel).name, ROOT / 'reports' / Path(rel).name]:
                    if cand.is_file():
                        text = cand.read_text(encoding='utf-8', errors='replace')
                        found = True
                        break
            if not found and len(pt.strip()) > 500 and (
                    re.search(r'\n#{1,3} ', '\n' + pt) or '报告' in pt[:200]):
                text = pt
            if text:
                break
    if not text:
        raise SystemExit('still no text')
    (d / 'report.md').write_text(text, encoding='utf-8')
    usage_json = {'usage': {'prompt_tokens': usage.get('input'),
                            'completion_tokens': usage.get('output'),
                            'total_tokens': usage.get('total')},
                  'last_call': meta.get('lastCallUsage') or {}}
    (d / 'usage.json').write_text(json.dumps(usage_json, ensure_ascii=False, indent=2), encoding='utf-8')
    # tools 从既有 run.json 读,若无则从 stdout 审计(简化: 保留已写 run.json; 补 usage)
    rj = d / 'run.json'
    r = json.loads(rj.read_text()) if rj.is_file() else {'run_tag': skey, 'task': task, 'group': group, 'n': n}
    r['tokens'] = usage_json['usage']
    (d / 'run.json').write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
    trace = extract_trace(skey)
    if group == 'plugin':
        if trace:
            (d / 'trace.jsonl').write_text('\n'.join(trace) + '\n', encoding='utf-8')
            tdir = OUT / 'trace' / f'{task}_{group}_{n}'
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / 'report.md').write_text(text, encoding='utf-8')
            (tdir / 'usage.json').write_text(json.dumps(usage_json, ensure_ascii=False, indent=2), encoding='utf-8')
            (tdir / 'trace.jsonl').write_text('\n'.join(trace) + '\n', encoding='utf-8')
    print(f'OK backfill {skey}: total={usage.get("total")} in={usage.get("input")} out={usage.get("output")} '
          f'report_chars={len(text)} trace_ev={len(trace)}')

if __name__ == '__main__':
    main()