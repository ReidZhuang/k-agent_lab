"""orchestrator — 全链路执行编排

端到端流程: 用户 NL query → agent_guide 解析 → agent_router 选字段 →
Neo4j 补全信息 + entity/time 解析 → agent_coder 生成执行代码 → 返回结果

支持 chain 链式请求、多主体合并、多指标拆分。
"""
import json, os, sys, re, time, uuid
from typing import Any
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KG_DIR = os.path.dirname(_QA_DIR)
sys.path.insert(0, _KG_DIR)

from core import build_prompt
from core.route_tool import get_route_tool
from core.coder import codegen_loop
from core.entity_resolver import get_resolver
from core.time_parser import parse_conditions_list
from irkg.graph import GraphQuerier

# ── LLM 客户端 ──
_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


# ============================================================
# LLM 调用辅助
# ============================================================

def _call_llm(system_prompt: str, user_prompt: str,
              max_tokens: int = 2048, temperature: float = 0.1) -> tuple[str | None, dict]:
    """调用 LLM 并返回 (content, info)"""
    t0 = time.time()
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        return None, {"error": str(e)}

    elapsed = time.time() - t0
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    info = {
        "elapsed": round(elapsed, 2),
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }
    return content, info


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON"""
    # ```json ... ```
    m = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 最外层 {}
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _validate_guide_output(data: dict) -> list[str]:
    """校验 agent_guide 输出格式"""
    errors = []
    if not isinstance(data, dict):
        return ["输出不是 dict"]
    requests = data.get("requests", [])
    if not isinstance(requests, list) or len(requests) == 0:
        errors.append("requests 缺失或为空")
        return errors
    chain = data.get("chain")
    if chain not in (True, False):
        errors.append("chain 必须为 true/false")
    for i, req in enumerate(requests):
        if not isinstance(req, dict):
            errors.append(f"requests[{i}] 不是 dict")
            continue
        if not re.match(r'^R_\d{3}$', req.get("req_id", "")):
            errors.append(f"requests[{i}].req_id 格式不符")
        if not isinstance(req.get("obj"), list) or len(req["obj"]) == 0:
            errors.append(f"requests[{i}].obj 不是非空列表")
        if not req.get("var"):
            errors.append(f"requests[{i}].var 缺失")
    return errors


# ============================================================
# agent_guide — NL 查询解析
# ============================================================

def agent_guide_parse(query: str, max_retries: int = 3) -> dict:
    """调用 LLM 解析自然语言查询 → 结构化请求

    Returns:
        {"chain": bool, "requests": [{"req_id": "R_001", "obj": [...], "var": "...", "condition": [...]}]}
        或 {"error": "..."}
    """
    system_prompt = build_prompt("agent_guide", {"parser_expert"})

    last_error = ""
    for attempt in range(1, max_retries + 1):
        raw, info = _call_llm(system_prompt, query)
        if raw is None:
            last_error = f"LLM 调用失败: {info.get('error')}"
            continue

        parsed = _extract_json(raw)
        if parsed is None:
            last_error = f"第{attempt}次: 无法从回复提取 JSON"
            continue

        errors = _validate_guide_output(parsed)
        if errors:
            last_error = f"第{attempt}次: {'; '.join(errors)}"
            continue

        # 注入 query_id
        parsed["query_id"] = uuid.uuid4().hex[:12]
        parsed["_raw"] = raw
        parsed["_info"] = info
        return parsed

    return {"error": last_error, "chain": False, "requests": []}


# ============================================================
# agent_router — 候选路由 + LLM 选字段
# ============================================================

def agent_router_select(req: dict) -> dict:
    """对单个 request 做路由选字段

    Args:
        req: {"obj": [...], "var": "...", "condition": [...]}

    Returns:
        {"field_id": "FIELD_XXX", "candidates": [...], "request": req, "info": {...}}
        或 {"error": "..."}
    """
    var = req.get("var", "")
    if not var:
        return {"error": "无 var 字段"}

    # 1. Python 双检索
    route_tool = get_route_tool()
    candidates = route_tool.hybrid_query([var])

    if not candidates:
        return {"error": f"路由未命中: var={var}", "candidates": [], "request": req}

    # 2. LLM 筛选
    system_prompt = build_prompt("agent_router", {"route_expert"})
    user_prompt = (
        f"## 取数请求\n"
        f"```json\n{json.dumps(req, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 路由候选字段\n"
        f"```json\n{json.dumps(candidates, ensure_ascii=False, indent=2)}\n```\n\n"
        f"请从以上候选字段中选出一个最匹配的，只输出字段 ID。"
    )

    raw, info = _call_llm(system_prompt, user_prompt, max_tokens=256, temperature=0.1)
    if raw is None:
        return {"error": f"LLM 调用失败: {info.get('error')}", "candidates": candidates, "request": req}

    # 3. 提取 field_id
    field_ids = re.findall(r'FIELD_[A-Z_]+', raw)
    chosen = field_ids[0] if field_ids else ""

    if not chosen:
        return {"error": f"LLM 未输出 field_id: {raw[:100]}", "candidates": candidates, "request": req}

    # 4. 校验 field_id 是否在候选列表中
    valid_ids = {c["id"] for c in candidates}
    if chosen not in valid_ids:
        # 容错：如果 LLM 输出的 field_id 合法但不在当前候选列表，仍然接受
        pass

    return {
        "field_id": chosen,
        "candidates": candidates,
        "request": req,
        "info": info,
        "_raw": raw,
    }


# ============================================================
# 补全：Neo4j 字段信息 + 实体解析 + 时间解析
# ============================================================

def _format_entity_code(value: str, etype: str, protocol: str) -> str:
    """根据协议转换实体代码格式

    Tushare: 300750.SZ
    Tencent: sz300750
    Sina:    sz300750
    """
    if etype != "stock_code" or "." not in value:
        return value
    if protocol in ("tencent", "sina"):
        parts = value.split(".")
        sym, ex = parts[0], parts[1]
        ex_map = {"SH": "sh", "SZ": "sz"}
        return f"{ex_map.get(ex, ex.lower())}{sym}"
    return value


def _format_condition_text(obj_resolved: list[dict], var: str,
                           api_column: str, time_start: str, time_end: str) -> str:
    """构建可读的查询条件文本（供 LLM 查看）"""
    parts = []
    # 主体
    entity_strs = []
    for o in obj_resolved:
        if o["type"] == "stock_code":
            entity_strs.append(f"{o['name']}({o['value']})")
        elif o["type"] == "sector_name":
            entity_strs.append(f"板块: {o['value']}")
        elif o["type"] == "index_code":
            entity_strs.append(f"指数: {o['value']}")
        else:
            entity_strs.append(o["value"])
    parts.append(f"  主体: {', '.join(entity_strs)}")
    parts.append(f"  指标: {api_column}")
    if time_start or time_end:
        parts.append(f"  时间: {time_start or '?'} ~ {time_end or '?'}")
    return "\n".join(parts)


def enrich_route(router_result: dict) -> dict:
    """补全 route_result：Neo4j 查字段/数据源信息 + 实体解析 + 时间解析

    Args:
        router_result: agent_router_select() 的输出
                       {"field_id": "FIELD_XXX", "request": {"obj": [...], "var": "...", "condition": [...]}}

    Returns:
        完整的 route_result dict（codegen_loop 的输入格式）
    """
    field_id = router_result.get("field_id", "")
    req = router_result.get("request", {})
    if not field_id:
        return {"error": "无 field_id", **router_result}

    # 1. Neo4j 查字段 + 数据源
    graph = GraphQuerier()
    field_info = graph.get_field_by_id(field_id)
    if not field_info:
        return {"error": f"Neo4j 未找到字段 {field_id}", **router_result}

    ds_info = graph.get_datasource(field_id)

    # 2. 实体解析
    resolver = get_resolver()
    obj_resolved = resolver.resolve_obj_list(req.get("obj", []))
    # 取第一个实体的 type 作为 entity_type
    primary_entity = obj_resolved[0] if obj_resolved else {"value": "", "type": ""}

    # 2a. 根据 protocol 转换代码格式
    protocol = ds_info.protocol if ds_info else ""
    raw_value = primary_entity["value"]
    formatted_value = _format_entity_code(raw_value, primary_entity["type"], protocol)

    # 3. 时间解析
    conditions = req.get("condition", [])
    time_start, time_end = parse_conditions_list(conditions)

    # 4. 构建 api_column（取 field 的 api_column）
    api_column = field_info.api_column or field_id

    # 5. 构建 condition_text（使用格式化后的代码）
    obj_for_text = list(obj_resolved)
    if obj_for_text:
        obj_for_text[0] = dict(obj_for_text[0])
        obj_for_text[0]["value"] = formatted_value

    condition_text = _format_condition_text(
        obj_for_text,
        req.get("var", ""),
        api_column,
        time_start,
        time_end,
    )

    route_result = {
        "req_id": req.get("req_id", "R_001"),
        "query_id": router_result.get("query_id", ""),
        "request": req,
        "route": {
            "field_id": field_id,
            "field_name": field_info.standard_name or "",
            "api_column": api_column,
            "data_type": field_info.data_type or "",
            "unit": field_info.unit or "",
            "entity_type": primary_entity["type"],
            "entity_value": formatted_value,  # ← 格式转换后的值
            "time_start": time_start,
            "time_end": time_end,
            "condition_text": condition_text,
        },
        "datasource": {
            "id": ds_info.id if ds_info else "",
            "protocol": ds_info.protocol if ds_info else "",
            "prompt_dir": ds_info.prompt_dir if ds_info else "",
        },
    }
    return route_result


# ============================================================
# 链式请求处理
# ============================================================

def _replace_res_refs(obj_list: list[str], chain_results: list[dict]) -> list[str]:
    """替换 obj 中的 resN 引用为前序结果的实际值

    Args:
        obj_list: ["res0"] 或 ["res0", "宁德时代"]
        chain_results: [{"result": ["电池"]}, ...] 按索引排列的前序结果

    Returns:
        替换后的 obj list
    """
    replaced = []
    for o in obj_list:
        m = re.match(r'^res(\d+)$', o)
        if m:
            idx = int(m.group(1))
            if idx < len(chain_results):
                prev = chain_results[idx]
                prev_data = prev.get("result", [])
                if prev_data:
                    # 取第一个结果的字符串值
                    val = str(prev_data[0]) if prev_data else o
                    replaced.append(val)
                else:
                    replaced.append(o)
            else:
                replaced.append(o)
        else:
            replaced.append(o)
    return replaced


# ============================================================
# 主编排器
# ============================================================

class Orchestrator:
    """全链路编排器"""

    def __init__(self):
        self.graph = GraphQuerier()

    def answer(self, query: str, verbose: bool = True,
               run_coder: bool = True) -> dict:
        """端到端执行：NL query → 结构化结果

        Args:
            query: 自然语言查询，如 "宁德时代今天的涨跌幅"
            verbose: 是否打印详细日志
            run_coder: False = 只跑 guide+router，不执行取数（快速验证路由）

        Returns:
            {"query": "...", "success": bool, "chain": bool,
             "requests": [{"req_id": "...", "result": [...], "error": "", ...}],
             "error": ""}
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"  用户查询: {query}")
            print(f"{'='*60}")

        # ── Phase 1: agent_guide 解析 ──
        if verbose:
            print(f"\n  ▶ Phase 1: agent_guide 解析")

        guide = agent_guide_parse(query)

        if "error" in guide:
            if verbose:
                print(f"    ❌ {guide['error']}")
            return {"query": query, "success": False, "error": guide["error"]}

        requests = guide.get("requests", [])
        chain = guide.get("chain", False)
        query_id = guide.get("query_id", "")

        if verbose:
            print(f"    ✓ chain={chain}, requests={len(requests)}")
            for i, req in enumerate(requests):
                print(f"      R{i+1}: obj={req['obj']}, var={req['var']}, cond={req['condition']}")

        # ── Phase 2-4: 逐 request 处理（支持 chain） ──
        processed = []
        chain_results = []  # 保存前序结果，用于 chain 的 resN 替换

        for i, req in enumerate(requests):
            req_id = req.get("req_id", f"R_{i+1:03d}")
            if verbose:
                print(f"\n  ▶ [{req_id}] Phase 2-4: 路由→补全→取数")

            # 2a: chain 依赖替换
            if chain and i > 0:
                obj_replaced = _replace_res_refs(req.get("obj", []), chain_results)
                req = dict(req)
                req["obj"] = obj_replaced
                if verbose:
                    print(f"      chain 替换: {req['obj']}")

            # 2b: 路由选字段
            router_result = agent_router_select(req)
            if "error" in router_result:
                if verbose:
                    print(f"      ❌ 路由失败: {router_result['error']}")
                processed.append({
                    "req_id": req_id, "request": req,
                    "success": False, "error": router_result["error"],
                })
                continue

            if verbose:
                field_id = router_result.get("field_id", "")
                print(f"      ✓ 路由: {field_id}")

            # 3: 补全
            enriched = enrich_route(router_result)
            enriched["query_id"] = query_id
            if "error" in enriched:
                if verbose:
                    print(f"      ❌ 补全失败: {enriched['error']}")
                processed.append({
                    "req_id": req_id, "request": req,
                    "success": False, "error": enriched["error"],
                })
                continue

            if verbose:
                ds_info = enriched.get("datasource", {})
                entity = enriched["route"]["entity_value"]
                ts = enriched["route"]["time_start"]
                te = enriched["route"]["time_end"]
                print(f"      ✓ 补全: entity={entity} time={ts}~{te} ds={ds_info.get('id','')}")

            # 4: 取数代码生成 + 执行
            if run_coder:
                if verbose:
                    print(f"      ▶ agent_coder 取数...")
                code_result = codegen_loop(enriched)
                step_result = {
                    "req_id": req_id,
                    "request": req,
                    "success": code_result.get("success", False),
                    "result": code_result.get("result", []),
                    "output": code_result.get("output", ""),
                    "error": code_result.get("error", ""),
                    "field_id": enriched["route"]["field_id"],
                    "datasource": enriched["datasource"],
                    "entity_value": enriched["route"]["entity_value"],
                    "time_start": enriched["route"]["time_start"],
                    "time_end": enriched["route"]["time_end"],
                }
                if step_result["success"]:
                    if verbose:
                        print(f"      ✓ 取数成功: _result = {step_result['result']}")
                else:
                    if verbose:
                        print(f"      ❌ 取数失败: {step_result.get('error', '')[:120]}")

                chain_results.append(step_result)
                processed.append(step_result)
            else:
                # 仅路由验证模式
                step_result = {
                    "req_id": req_id,
                    "request": req,
                    "success": True,
                    "result": [],
                    "output": "",
                    "error": "",
                    "field_id": enriched["route"]["field_id"],
                    "datasource": enriched["datasource"],
                    "entity_value": enriched["route"]["entity_value"],
                    "time_start": enriched["route"]["time_start"],
                    "time_end": enriched["route"]["time_end"],
                }
                chain_results.append(step_result)
                processed.append(step_result)

        # ── 汇总 ──
        success_count = sum(1 for p in processed if p["success"])
        total = len(processed)

        if verbose:
            print(f"\n{'='*60}")
            print(f"  结果: {success_count}/{total} 成功")
            if chain:
                for p in processed:
                    status = "✅" if p["success"] else "❌"
                    print(f"    {status} [{p['req_id']}] {p.get('field_id','')}: {p.get('result', p.get('error',''))}")
            print(f"{'='*60}")

        return {
            "query": query,
            "success": success_count > 0,
            "chain": chain,
            "guide_raw": guide.get("_raw", ""),
            "requests": processed,
            "summary": f"{success_count}/{total} requests succeeded",
            "error": "",
        }


# ── 快捷函数 ──
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
