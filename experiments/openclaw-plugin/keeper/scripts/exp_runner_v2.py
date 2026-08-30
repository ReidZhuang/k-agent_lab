#!/usr/bin/env python3
"""keeper 阶段3-v2 对比 runner —— comparsion_ 系列, baseline/plugin 都禁 mx-ds-mcp。

与 exp_runner.py 的差异:
  1. session-key 统一带 comparsion_ 前缀(前端测试列表易检索)。
  2. baseline 与 plugin 均不得使用 mx-ds-mcp__*(工具对齐): 跑完立即审计
     sessionFile(baseline) / trace(plugin) 的实际 toolName 集合, 出现 mx → FAIL 即停, 不重试。
  3. 产物落 artifacts/comparsion_exp/<task>_<group>_<n>/:
     baseline: run.json + usage.json + report.md + stdout.json
     plugin  : 上述 + trace.jsonl(从 keeper/logs/trace.jsonl 按 runId 切出, payload 内联)

用法: python exp_runner_v2.py <task> <group> <n>
"""
import json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path('/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper')
OUT = ROOT / 'artifacts' / 'comparsion_exp'
LOG_TRACE = ROOT / 'logs' / 'trace.jsonl'
TRACE_PAYLOADS = ROOT / 'logs' / 'trace_payloads'
NOW = time.strftime('%Y-%m-%dT%H:%M:%S')
SERIES = 'comparsion'

TASKS = {
    't1': {'stock': '中际旭创(300308)',
           'prompt': '生成 中际旭创(300308) 的今日行情与基本面分析报告, 输出为完整markdown报告: 含一句话定位、今日盘面、基本面、综合前瞻判断、数据缺口说明。'},
    't2': {'stock': '兆易创新(603986)',
           'prompt': '生成 兆易创新(603986) 深度分析报告, 要求同时取今日行情与近一个月公告/事件数据进行分析, 输出完整markdown报告: 含一句话定位、今日盘面、基本面与事件、综合前瞻判断、数据缺口说明。'},
    't3': {'stock': '半导体板块',
           'prompt': '对比 半导体 板块今日涨幅前 5 的公司, 合并分析这些上市公司的共性与差异, 输出完整markdown报告。'},
}


def audit_tools(proc_stdout_json, plugin: bool, skey: str):
    """审计实际工具集合, 出现 mx-ds-mcp__* 即报错(调用方负责停止)。返回审计到的 tool 集合。"""
    tools = set()
    if plugin:
        # 从全局 trace 按 runId 前缀过滤本 run 事件, 收集 toolName
        prefix = f'session:agent:keeper:{skey}'
        if LOG_TRACE.is_file():
            for line in open(LOG_TRACE):
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                rid = ev.get('runId') or ''
                if rid.startswith(prefix):
                    tn = ev.get('toolName') or ev.get('tool')
                    if tn:
                        tools.add(tn)
                    # before_tool_call 事件里的工具名不同命名
                    if ev.get('type') == 'before_tool_call' and ev.get('tool'):
                        tools.add(ev['tool'])
    else:
        data = json.loads(proc_stdout_json)
        sf = ((data.get('meta') or {}).get('agentMeta') or {}).get('sessionFile')
        if sf and Path(sf).is_file():
            for line in open(sf):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('type') == 'message' and isinstance(d.get('message'), dict):
                    m = d['message']
                    if m.get('role') == 'toolResult' and m.get('toolName'):
                        tools.add(m['toolName'])
                    elif m.get('role') == 'assistant' and isinstance(m.get('content'), list):
                        for p in m['content']:
                            if isinstance(p, dict) and p.get('type') == 'toolCall' and p.get('name'):
                                tools.add(p['name'])
    bad = sorted(t for t in tools if 'mx-ds-mcp' in t.lower() or t.lower().startswith('mx_'))
    return tools, bad


def extract_trace(skey):
    """从全局 trace 切出本 run 事件, payload_ref 内联为 payload。返回 TraceLine 列表"""
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
            if pf.is_file():
                try:
                    ev['payload'] = pf.read_text(encoding='utf-8')
                except Exception:
                    pass
            else:
                ev['payload_ref'] = f'{ref}(missing:{pf.name})'
        out.append(json.dumps(ev, ensure_ascii=False))
    return out


def main():
    task, group, n = sys.argv[1], sys.argv[2], sys.argv[3]
    if group == 'baseline':
        agent_args = ['--local']
    elif group == 'plugin':
        agent_args = ['--agent', 'keeper']
    else:
        raise SystemExit(f'bad group {group}')
    spec = TASKS[task]
    skey = f'{SERIES}_{task}_{group}_{n}'
    trace = []  # 仅 plugin 组填充;baseline 组为空列表,避免下方 if trace: 误判
    cmd = ['openclaw', 'agent', '--json', '--session-key', skey, *agent_args, '-m', spec['prompt']]
    print(f'[{NOW}] run {skey}: {" ".join(cmd)}', flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print(f'ERROR rc={proc.returncode} stderr={proc.stderr[-800:]}', flush=True)
        raise SystemExit(1)

    d = OUT / f'{task}_{group}_{n}'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'{skey}.stdout.json').write_text(proc.stdout, encoding='utf-8')

    # ---- 工具对齐审计(mx 必须零出现) ----
    tools, bad = audit_tools(proc.stdout, group == 'plugin', skey)
    print(f'    audit tools[{len(tools)}]: {", ".join(sorted(tools)[:12])}', flush=True)
    if bad:
        print(f'AUDIT-FAIL {skey}: 出现 mx MCP 工具 -> {bad}', flush=True)
        raise SystemExit(2)

    # ---- 提取报告/usage ----
    try:
        data = json.loads(proc.stdout)
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
                # inline 兜底: payload 长 且 含 markdown 标题 或 报告特征词
                if not found and len(pt.strip()) > 500 and (
                        re.search(r'\n#{1,3} ', '\n' + pt) or '报告' in pt[:200]):
                    text = pt
                if text:
                    break
    except Exception as e:
        print(f'PARSE ERROR {e} stdout head={proc.stdout[:400]}', flush=True)
        raise SystemExit(1)
    if not text:
        print(f'ERROR {skey}: empty assistant text; head={proc.stdout[:400]}', flush=True)
        raise SystemExit(1)

    (d / 'report.md').write_text(text, encoding='utf-8')
    usage_json = {'usage': {'prompt_tokens': usage.get('input'),
                            'completion_tokens': usage.get('output'),
                            'total_tokens': usage.get('total')},
                  'last_call': meta.get('lastCallUsage') or {}}
    (d / 'usage.json').write_text(json.dumps(usage_json, ensure_ascii=False, indent=2), encoding='utf-8')
    run_json = {'run_tag': skey, 'series': SERIES, 'task': task, 'group': group, 'n': n,
                'stock': spec['stock'], 'prompt': spec['prompt'], 'ts': NOW,
                'tokens': usage_json['usage'], 'tools': sorted(tools)}
    (d / 'run.json').write_text(json.dumps(run_json, ensure_ascii=False, indent=2), encoding='utf-8')

    if group == 'plugin':
        trace = extract_trace(skey)
        if trace:
            (d / 'trace.jsonl').write_text('\n'.join(trace) + '\n', encoding='utf-8')
        else:
            print(f'WARN {skey}: 全局 trace 未找到本 run 事件(prefix={skey})', flush=True)

    # 拷贝 usage.json 到对应 trace 目录(compare trace 布局读取)
    tdir = OUT / 'trace' / f'{task}_{group}_{n}'
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / 'report.md').write_text(text, encoding='utf-8')
    (tdir / 'usage.json').write_text(json.dumps(usage_json, ensure_ascii=False, indent=2), encoding='utf-8')
    if trace:
        (tdir / 'trace.jsonl').write_text('\n'.join(trace) + '\n', encoding='utf-8')
    print(f'OK {skey}: total={usage.get("total")} in={usage.get("input")} out={usage.get("output")} '
          f'report_chars={len(text)} tools={len(tools)} -> {d}', flush=True)


if __name__ == '__main__':
    main()