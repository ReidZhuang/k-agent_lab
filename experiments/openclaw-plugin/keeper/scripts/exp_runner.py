#!/usr/bin/env python3
"""keeper 阶段3 实验 runner —— 单 run 调用 + 产物提取 + 落盘。
用法:  python runner.py <task> <group> <n>   # 单发; 失败返回非0, 不重试
产物落 artifacts/e2e_exp/<task>_<group>_<n>/
  baseline: run.json + usage.json + report.md
  plugin  : 上述 + 从 keeper/logs 搬 trace(如果 traceDir 落在这)
"""
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path('/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper')
OUT = ROOT / 'artifacts' / 'e2e_exp'
NOW = time.strftime('%Y-%m-%dT%H:%M:%S')

TASKS = {
    't1': {'stock': '中际旭创(300308)',
           'prompt': '生成 中际旭创(300308) 的今日行情与基本面分析报告, 输出为完整markdown报告: 含一句话定位、今日盘面、基本面、综合前瞻判断、数据缺口说明。'},
    't2': {'stock': '兆易创新(603986)',
           'prompt': '生成 兆易创新(603986) 深度分析报告, 要求同时取今日行情与近一个月公告/事件数据进行分析, 输出完整markdown报告: 含一句话定位、今日盘面、基本面与事件、综合前瞻判断、数据缺口说明。'},
    't3': {'stock': '半导体板块',
           'prompt': '对比 半导体 板块今日涨幅前 5 的公司, 合并分析这些上市公司的共性与差异, 输出完整markdown报告。'},
}

def main():
    task, group, n = sys.argv[1], sys.argv[2], sys.argv[3]
    if group == 'baseline':
        # 基线必须真·无压缩: gateway 所有 agent 全局加载 keeper 插件(无 per-agent 开关),
        # 故用 --local embedded runner(不加载 gateway 插件链, 且自带 OPENCODE_GO_API_KEY)。
        agent_args = ['--local']
    elif group == 'plugin':
        agent_args = ['--agent', 'keeper']
    else:
        raise SystemExit(f'bad group {group}')
    spec = TASKS[task]
    skey = f"exp-{task}-{group}-{n}"
    cmd = ['openclaw', 'agent', '--json', '--session-key', skey, *agent_args, '-m', spec['prompt']]
    print(f'[{NOW}] run {skey}: {cmd}')
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print(f'ERROR rc={proc.returncode} stderr={proc.stderr[-800:]}')
        raise SystemExit(1)
    d = OUT / f'{task}_{group}_{n}'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'{skey}.stdout.json').write_text(proc.stdout, encoding='utf-8')  # 原始输出留档,便于诊断
    try:
        data = json.loads(proc.stdout)
        res = data.get('result', data)
        meta = (res.get('meta') or {}).get('agentMeta') or {}
        usage = meta.get('usage') or {}
        text = res.get('finalAssistantVisibleText') or res.get('finalAssistantRawText') or ''
        # 交付消息(gateway 口径不一: ①全文落文件给路径 ②路径相对 reports/ ③全文直接内联)。
        if not text or len(text.strip()) < 100:
            import re as _re
            ws_reports = Path.home() / '.openclaw' / 'workspace' / 'reports'
            for pl in (res.get('payloads') or []):
                pt = (pl.get('text') or '')
                m = _re.search(r'([^\s`"\']+\.md)', pt)
                found = False
                if m:
                    rel = m.group(1)
                    for cand in [Path(rel), Path.home() / '.openclaw' / 'workspace' / rel, ws_reports / Path(rel).name]:
                        if cand.is_file():
                            text = cand.read_text(encoding='utf-8', errors='replace')
                            found = True
                            break
                if not found and len(pt.strip()) > 500 and _re.search(r'\n#{1,3} ', '\n' + pt):
                    # 无有效文件路径(或仅有文本中的 .md 字样)但正文直接内联 → 视为全文
                    text = pt
                if text:
                    break
    except Exception as e:
        print(f'PARSE ERROR {e}: stdout head={proc.stdout[:400]}')
        raise SystemExit(1)
    if not text:
        print('ERROR: empty assistant text; stop. stdout head=', proc.stdout[:400])
        raise SystemExit(1)
    (d / 'report.md').write_text(text, encoding='utf-8')
    usage_json = {'usage': {'prompt_tokens': usage.get('input'),
                            'completion_tokens': usage.get('output'),
                            'total_tokens': usage.get('total')},
                  'last_call': meta.get('lastCallUsage') or {}}
    (d / 'usage.json').write_text(json.dumps(usage_json, ensure_ascii=False, indent=2), encoding='utf-8')
    run_json = {'run_tag': skey, 'task': task, 'group': group, 'n': n,
                'stock': spec['stock'], 'prompt': spec['prompt'], 'ts': NOW,
                'tokens': usage_json['usage']}
    (d / 'run.json').write_text(json.dumps(run_json, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'OK {skey}: total={usage.get("total")} in={usage.get("input")} out={usage.get("output")} report_chars={len(text)}')
    print(f'    -> {d}')

if __name__ == '__main__':
    main()