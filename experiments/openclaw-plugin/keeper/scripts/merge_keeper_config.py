#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并 keeper 配置段进全局 ~/.openclaw/openclaw.json（增量、备份、打印 diff 摘要，不打印任何 key 值）。
用法: python merge_keeper_config.py <keeper-config-path> <global-config-path>"""
import json, sys, shutil, datetime

keeper_cfg_path, global_path = sys.argv[1], sys.argv[2]
keep = json.load(open(keeper_cfg_path, encoding='utf-8'))
glob = json.load(open(global_path, encoding='utf-8'))

# 备份
bak = global_path + '.bak-keeper-' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(global_path, bak)
print('backup ->', bak)

# 1) agents.list 追加 keeper
agents = glob.setdefault('agents', {})
lst = agents.setdefault('list', [])
ids = {a.get('id') for a in lst}
if 'keeper' not in ids:
    kagent = next((a for a in keep.get('agents', {}).get('list', []) if a.get('id') == 'keeper'), None)
    if kagent:
        lst.append(kagent)
        print('agents.list: + keeper (workspace=%s)' % kagent.get('workspace'))
    else:
        print('agents.list: keeper entry NOT FOUND in keeper config!')
else:
    print('agents.list: keeper already present, skip')

# 2) plugins.entries 追加 keeper-corpus-compress
pe = glob.setdefault('plugins', {}).setdefault('entries', {})
kce = keep.get('plugins', {}).get('entries', {}).get('keeper-corpus-compress')
if kce:
    existed = 'keeper-corpus-compress' in pe
    pe['keeper-corpus-compress'] = kce
    print('plugins.entries.keeper-corpus-compress: %s' % ('updated' if existed else 'added (hooks=%s, traceDir=%s)' % (sorted(kce.get('hooks', {}).keys()), kce.get('config', {}).get('traceDir', ''))))
else:
    print('plugins.entries: keeper-corpus-compress NOT FOUND in keeper config!')

# 3) skills: 仓库 config 与全局都是 skills.load.extraDirs 列表 → 合并去重
#    （此前版本误取 keep['skills'] 外层导致漏合并，2026-08-28 修复）
sk_load = keep.get('skills', {}).get('load', {})
keep_dirs = sk_load.get('extraDirs', [])
if keep_dirs:
    ski_load = glob.setdefault('skills', {}).setdefault('load', {})
    existing = ski_load.setdefault('extraDirs', [])
    if isinstance(existing, list):
        added = [d for d in keep_dirs if d not in existing]
        existing.extend(added)
        print('skills.load.extraDirs: merged +%d -> total %d dirs' % (len(added), len(existing)))
    else:
        print('skills.load.extraDirs CONFLICT: global shape=%s, not merged' % type(existing).__name__)
else:
    print('skills.load.extraDirs: keeper config has none, skip')

out = json.dumps(glob, ensure_ascii=False, indent=2)
open(global_path, 'w', encoding='utf-8').write(out)
print('written ->', global_path)