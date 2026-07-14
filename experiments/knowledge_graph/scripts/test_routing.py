#!/usr/bin/env python3
"""Phase 3: 路由核心逻辑测试"""
import sys, csv
sys.path.insert(0, "..")

from irkg import Router, RouteCondition

router = Router()
passed = 0
failed = 0

def resolve_attr(obj, path: str):
    """通过点路径获取属性/索引值，如 'fields.0.id' -> result.fields[0].id"""
    current = obj
    for part in path.split("."):
        if isinstance(current, list) and part.lstrip("-").isdigit():
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            current = getattr(current, part, None)
        if current is None:
            break
    return current

def test(name, result, checks: dict):
    global passed, failed
    errors = []
    for key, expected in checks.items():
        actual = resolve_attr(result, key)
        if isinstance(expected, int) and isinstance(actual, list):
            if len(actual) != expected:
                errors.append(f"  {key}: len expected {expected}, got {len(actual)}")
        elif actual != expected:
            errors.append(f"  {key}: expected '{expected}', got '{actual}'")

    if errors:
        failed += 1
        print(f"  FAIL {name}")
        for e in errors: print(e)
    else:
        passed += 1
        print(f"  PASS {name}")

# ========== 加载数据 ==========
print("加载 datafield_new_alias_520_deepseek.txt...")
router.build(alias_csv_path="../data/datafield_new_alias_520_deepseek.txt")
stats = router.matcher.index_stats()
print(f"Alias 索引: simple={stats['simple']}, qualified={stats['qualified']}, "
      f"business_tag={stats['business_tag']}, synonym={stats['synonym']}")
print()

# ========== Test 1: 精确命中 ==========
print("--- Test 1: 精确命中 ---")
r = router.route(["毛利率"], intent_type="fact")
test("1a 毛利率精确匹配", r, {
    "fields.0.id": "FIELD_FIN_GROSS_MARGIN",
    "datasource.id": "DS_TUSHARE_FINA_IND",
})

r = router.route(["净利润"], intent_type="fact")
test("1b 净利润精确匹配", r, {
    "fields.0.id": "FIELD_FS_NET_PROFIT",
})

# qualified 匹配: PE_TTM 在 qualified 层
r = router.route(["PE_TTM"], intent_type="fact")
test("1c PE_TTM qualified匹配", r, {
    "fields.0.match_type": "qualified",
})

# qualified 精确命中: 带限定的全称直接路由
r = router.route(["指数涨跌幅"], intent_type="fact")
test("1d 指数涨跌幅 qualified精准命中", r, {
    "fields.0.id": "FIELD_INDEX_PCT_CHG",
    "fields.0.match_type": "qualified",
})

r = router.route(["个股涨跌幅"], intent_type="fact")
test("1e 个股涨跌幅 qualified精准命中", r, {
    "fields.0.id": "FIELD_QUOTE_PCT_CHG",
    "fields.0.match_type": "qualified",
})

# ========== Test 2: 模糊匹配兜底 ==========
print("--- Test 2: 模糊匹配 ---")
r = router.route(["公司赚了多少钱"], intent_type="fact")
test("2a 模糊匹配兜底", r, {
    "fields.0.match_type": "fuzzy",
})
if len(r.fields) > 0:
    passed += 1
    print(f"  PASS 2b 返回 {len(r.fields)} 个候选字段 (field: {r.fields[0].id})")
else:
    failed += 1
    print(f"  FAIL 2b 模糊匹配未返回结果")

# ========== Test 3: 意图模式 ==========
print("--- Test 3: 意图模式 ---")
r_fact = router.route(["毛利率"], intent_type="fact")
r_analysis = router.route(["毛利率"], intent_type="analysis")
r_explore = router.route(["毛利率"], intent_type="explore")

test("3a fact 模式正常返回", r_fact, {
    "intent_type": "fact",
    "fields.0.id": "FIELD_FIN_GROSS_MARGIN",
})

test("3b analysis 模式正常", r_analysis, {
    "intent_type": "analysis",
})

test("3c explore 模式正常", r_explore, {
    "intent_type": "explore",
})

# 验证扩散层级: explore >= analysis >= fact
if len(r_explore.expanded_fields) >= len(r_analysis.expanded_fields) >= len(r_fact.expanded_fields):
    passed += 1
    print(f"  PASS 3d 扩散层级正确: fact={len(r_fact.expanded_fields)}, analysis={len(r_analysis.expanded_fields)}, explore={len(r_explore.expanded_fields)}")
else:
    failed += 1
    print(f"  FAIL 3d 扩散层级异常")

# ========== Test 4: 数据源反查 ==========
print("--- Test 4: 数据源 ---")
r4 = router.route(["PE_TTM"], intent_type="fact")
test("4a PE_TTM数据源", r4, {
    "datasource.id": "DS_TUSHARE_DAILY_BASIC",
})
test("4b PE_TTM协议", r4, {
    "datasource.protocol": "tushare",
})

r4c = router.route(["市场热度"], intent_type="fact")
test("4c 情绪数据源", r4c, {
    "datasource.id": "DS_LEVISTOCK_EMOTION",
})

# ========== Test 5: 路由输出结构 ==========
print("--- Test 5: 输出结构 ---")
r5 = router.route(["毛利率"], intent_type="analysis", conditions=RouteCondition(
    entity_type="stock_code", entity_value="300750.SZ",
    time_range_start="20250101", time_range_end="20250630"
))
d = r5.to_dict()
# BELONGS_TO_CONCEPT 尚未建，所以 concept_id 为空是预期的
test("5a 输出包含路由字段", r5, {"fields.0.id": "FIELD_FIN_GROSS_MARGIN"})
if d["conditions"]["entity"]["value"] == "300750.SZ":
    passed += 1
    print(f"  PASS 5b 条件实体传递正确")
else:
    failed += 1
    print(f"  FAIL 5b 条件实体传递")
if d["datasource"]["id"]:
    passed += 1
    print(f"  PASS 5c 数据源已解析: {d['datasource']['id']}")
else:
    failed += 1
    print(f"  FAIL 5c 数据源未解析")

# ========== Test 6: 边界情况 ==========
print("--- Test 6: 边界 ---")
# 注: Faiss 永远返回 Top-K 结果，不存在真正"空"的语义搜索
# 但 alias 未命中是预期的
r6 = router.route(["xyz_not_exist_at_all_123"], intent_type="fact")
if r6.fields and r6.fields[0].match_type == "fuzzy":
    passed += 1
    print(f"  PASS 6a 未命中alias, 走Faiss兜底 (top: {r6.fields[0].id})")
else:
    failed += 1
    print(f"  FAIL 6a 路由异常")

r6b = router.route([], intent_type="fact")
test("6b 空关键词返回空", r6b, {"fields": []})

# ========== Test 7: ROE 模糊匹配 ==========
print("--- Test 7: ROE匹配 ---")
r7 = router.route(["净资产收益率"], intent_type="fact")
test("7a ROE中文名精确匹配", r7, {
    "fields.0.match_type": "qualified",
    "fields.0.id": "FIELD_FIN_ROE_WAA",
})

# ========== 汇总 ==========
print(f"\n{'='*40}")
print(f"测试结果: {passed} 通过 / {failed} 失败 / {passed+failed} 总计")
if failed == 0:
    print("Phase 3 路由核心逻辑验证通过!")
else:
    print(f"尚有 {failed} 个测试未通过，需排查")
