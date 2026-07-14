#!/usr/bin/env python3
"""Phase 7: 测试 SQL prompt 装配"""
import sys, json
sys.path.insert(0, "..")

from irkg import Router, RouteCondition
from irkg.sql_gen import build_sql_prompt, parse_llm_output

router = Router()
router.build(alias_csv_path="../data/datafield_new_alias_520_deepseek.txt")

print("=" * 60)
print("Phase 7: SQL 生成链路测试")
print("=" * 60)

# Test 1
print("\n[Test 1] 事实查询: 贵州茅台PE_TTM")
r = router.route(["PE_TTM"], intent_type="fact",
    conditions=RouteCondition(entity_type="stock_code", entity_value="600519.SH"))
prompt = build_sql_prompt(r)
print(f"Prompt ({len(prompt)} chars):")
print(prompt[:800])
print("...")

# Test 2
print("\n[Test 2] 财务分析: 宁德时代毛利率、净利率")
r2 = router.route(["毛利率", "净利率"], intent_type="analysis",
    conditions=RouteCondition(entity_type="stock_code", entity_value="300750.SZ",
                              time_range_start="20250101", time_range_end="20250630"))
prompt2 = build_sql_prompt(r2)
print(f"Prompt ({len(prompt2)} chars):")
print(prompt2[:800])
print("...")

# Test 3
print("\n[Test 3] 市场情绪")
r3 = router.route(["市场热度"], intent_type="fact", conditions=RouteCondition())
prompt3 = build_sql_prompt(r3)
print(f"Prompt ({len(prompt3)} chars):")
print(prompt3[:600])
print("...")

# Test 4
print("\n[Test 4] LLM 输出解析")
test_out = "```python\nimport tushare as ts\npro = ts.pro_api()\ndf = pro.daily_basic(ts_code='600519.SH')\n```"
parsed = parse_llm_output(test_out)
print(f"解析: {parsed[:150]}...")

print(f"\n{'='*60}")
print("Prompt 装配测试完成!")
