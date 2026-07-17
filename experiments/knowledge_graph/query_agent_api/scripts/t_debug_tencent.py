"""Debug Tencent quote codegen - force Tencent datasource"""
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

# Force the specific case: FIELD_QUOTE_PCT_CHG → DS_TENCENT_QUOTE
field_id = 'FIELD_QUOTE_PCT_CHG'
req = {'obj': ['宁德时代'], 'var': '涨跌幅', 'condition': ['今天']}

g = GraphQuerier()
fi = g.get_field_by_id(field_id)
ds = g.get_datasource(field_id)
print(f'Field: {fi.standard_name} ({fi.id})')
print(f'Datasource: {ds.id} ({ds.protocol})')
print(f'api_column: {fi.api_column}')

resolver = get_resolver()
obj_res = resolver.resolve_obj_list(req['obj'])
ts, te = parse_conditions_list(req['condition'])
print(f'Entity: {obj_res[0]["value"]} ({obj_res[0]["type"]})')
print(f'Time: {ts} ~ {te}')

# Build route_result with format expected by codegen
route_result = {
    'req_id': 'R_001', 'query_id': 'test', 'request': req,
    'route': {
        'field_id': field_id, 'field_name': fi.standard_name,
        'api_column': fi.api_column, 'data_type': fi.data_type, 'unit': fi.unit,
        'entity_type': obj_res[0]['type'], 'entity_value': obj_res[0]['value'],
        'time_start': ts, 'time_end': te,
        'condition_text': f'股票: {obj_res[0]["value"]}\n  指标: {fi.api_column}',
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
    err = syntax_check(code)
    if err:
        print(f'Syntax error: {err}')
    else:
        full = merge_with_template(code, protocol)
        print(f'\n=== Full code ===\n{full}')
        ex = execute_code(full)
        print(f'\nResult: {json.dumps(ex, ensure_ascii=False)}')
else:
    print('\n!!! No code block')
