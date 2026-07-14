#!/usr/bin/env python3
"""Phase 7: 端到端测试 - 路由 -> prompt -> LLM -> 解析"""
import sys, json, requests
sys.path.insert(0, "..")

from irkg import Router, RouteCondition
from irkg.sql_gen import build_sql_prompt, parse_llm_output

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "glm4:9b-chat-q3_K_M"

router = Router()
router.build(alias_csv_path="../data/datafield_new_alias_520_deepseek.txt")


def call_llm(prompt):
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL, "prompt": prompt,
        "stream": False, "temperature": 0.1, "num_predict": 1024,
    }, timeout=120)
    return resp.json().get("response", "")


def test_route(keywords, intent="fact", entity_type="", entity_value="",
               time_start="", time_end=""):
    cond = RouteCondition(entity_type=entity_type, entity_value=entity_value,
                          time_range_start=time_start, time_range_end=time_end)
    r = router.route(keywords, intent_type=intent, conditions=cond)
    prompt = build_sql_prompt(r)

    print(f"\n{'='*60}")
    print(f"路由: {keywords}")
    print(f"数据源: {r.datasource.id if r.datasource else 'N/A'}")
    print(f"Prompt: {len(prompt)} 字符")
    print(f"{'='*60}")

    print("\n=== LLM 输出 ===")
    try:
        output = call_llm(prompt)
        print(output[:500])
        code = parse_llm_output(output)
        if code:
            print(f"\n=== 提取代码 ===")
            print(code[:300])
    except Exception as e:
        print(f"LLM 调用失败: {e}")


if __name__ == "__main__":
    test_route(["PE_TTM"], intent="fact",
               entity_type="stock_code", entity_value="600519.SH")

    test_route(["毛利率", "净利率"], intent="analysis",
               entity_type="stock_code", entity_value="300750.SZ",
               time_start="20240101", time_end="20240630")

    test_route(["市场热度", "涨停家数"], intent="fact")
