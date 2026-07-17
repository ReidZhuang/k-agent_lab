"""Debug: 最高价 codegen failure analysis"""
import os, sys, json
_QA_DIR = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, _QA_DIR)

from openai import OpenAI
from core import build_prompt
from core.coder import build_codegen_prompt, merge_with_template, parse_python_code, syntax_check
from core.entity_resolver import get_resolver
from core.time_parser import parse_conditions_list
from irkg.graph import GraphQuerier
from scripts.executor import execute_code

field_id = 'FIELD_QUOTE_HIGH'
req = {'obj': ['宁德时代'], 'var': '最高价', 'condition': ['今天']}

g = GraphQuerier()
fi = g.get_field_by_id(field_id)
ds = g.get_datasource(field_id)
print(f'Field: {fi.standard_name} ({fi.id})')
print(f'Datasource: {ds.id} ({ds.protocol})')
print(f'api_column: {fi.api_column}')
print(f'field.md api_column: {repr(fi.api_column)}')

resolver = get_resolver()
obj_res = resolver.resolve_obj_list(req['obj'])
ts, te = parse_conditions_list(req['condition'])

# Format entity for Tencent
raw_val = obj_res[0]['value']
fmt_val = f"sz{raw_val.split('.')[0].lower()}" if '.' in raw_val else raw_val
print(f'Entity: {raw_val} → {fmt_val}')

route_result = {
    'req_id': 'R_001', 'query_id': 'test', 'request': req,
    'route': {
        'field_id': field_id, 'field_name': fi.standard_name,
        'api_column': fi.api_column, 'data_type': fi.data_type, 'unit': fi.unit,
        'entity_type': obj_res[0]['type'], 'entity_value': fmt_val,
        'time_start': ts, 'time_end': te,
        'condition_text': f'主体: {fmt_val}\n  指标: {fi.api_column}',
    },
    'datasource': {'id': ds.id, 'protocol': ds.protocol, 'prompt_dir': ds.prompt_dir or ''},
}

task_prompt, protocol = build_codegen_prompt(route_result)
print(f'\n=== Task prompt ({len(task_prompt)} chars) ===')
print(task_prompt)

client = OpenAI(
    base_url=os.environ.get('OLLAMA_HOST', 'http://localhost:11434') + '/v1',
    api_key='ollama',
)
resp = client.chat.completions.create(
    model=os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b'),
    messages=[{'role': 'system', 'content': build_prompt('agent_coder')},
              {'role': 'user', 'content': task_prompt}],
    temperature=0.1, max_tokens=2048,
)
content = resp.choices[0].message.content or ''
print(f'\n=== LLM Response ===\n{content}')

code = parse_python_code(content)
if code:
    print(f'\n=== Code ({len(code)} chars) ===\n{code}')
    full = merge_with_template(code, protocol)
    print(f'\n=== Full code ===\n{full}')

    # 先独立测一下API
    import requests
    url = f"https://web.sqt.gtimg.cn/q={fmt_val}"
    resp_api = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
    fields = resp_api.text.split("~")
    print(f'\n=== Tencent API direct test ===')
    print(f'URL: {url}')
    print(f'Fields count: {len(fields)}')
    print(f'field[33] (high): {fields[33] if len(fields)>33 else "N/A"}')
    print(f'field[34] (low): {fields[34] if len(fields)>34 else "N/A"}')

    ex = execute_code(full)
    print(f'\n=== Execution Result ===\n{json.dumps(ex, ensure_ascii=False, indent=2)}')
else:
    print('\n!!! No code block')
