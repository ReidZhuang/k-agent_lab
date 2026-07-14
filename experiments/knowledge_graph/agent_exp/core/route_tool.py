"""route_tool — Router 工具包装 + fetch_data 取数工具

将 irkg.Router 包装为 LLM 可调用的函数工具。
LLM 每次调用 route_query，执行一次完整的 route 链路。
调用 fetch_data 可执行取数，返回真实数据。
"""
import json, sys, os, requests, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from irkg.router import Router
from irkg.types import RouteCondition
from irkg.sql_gen import build_sql_prompt, parse_llm_output
from irkg.graph import GraphQuerier
from scripts.executor import execute_code


class RouteTool:
    """路由工具：初始化 Router 一次，多次调用查询"""

    def __init__(self):
        self.router = Router()
        alias_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "datafield_new_alias_all.txt")
        )
        self.router.build(alias_csv_path=alias_path)

    def query(self, keywords: list[str], intent_type: str = "fact",
              entity_type: str = "", entity_value: str = "",
              time_start: str = "", time_end: str = "",
              strict: bool = False) -> dict:
        """执行一次路由查询

        Args:
            keywords: 指标关键词列表
            intent_type: fact / analysis / explore
            entity_type: stock_code / sector_name / index_code
            entity_value: 实体值
            time_start: 时间范围起始 YYYYMMDD
            time_end: 时间范围结束 YYYYMMDD
            strict: True=仅alias匹配，跳过Faiss模糊兜底
        """
        cond = RouteCondition(
            entity_type=entity_type,
            entity_value=entity_value,
            time_range_start=time_start,
            time_range_end=time_end,
        )

        result = self.router.route(
            keywords=keywords,
            intent_type=intent_type,
            conditions=cond,
            strict=strict,
        )

        # 格式化输出供 LLM 消化
        field_lines = []
        for i, f in enumerate(result.fields):
            field_lines.append(
                f"  ({i+1}) {f.id}\n"
                f"      alias: {f.match_type}\n"
                f"      data_type: {f.data_type}\n"
                f"      unit: {f.unit}\n"
                f"      granularity: {f.granularity}\n"
                f"      refresh_time: {f.refresh_time}\n"
                f"      datasource: {result.datasource.name if result.datasource else 'N/A'}\n"
                f"      protocol: {result.datasource.protocol if result.datasource else 'N/A'}"
            )

        output = {
            "fields_count": len(result.fields),
            "fields": field_lines,
            "concept_id": result.concept_id,
            "concept_name": result.concept_name,
            "datasource_id": result.datasource.id if result.datasource else "",
            "datasource_name": result.datasource.name if result.datasource else "",
            "datasource_protocol": result.datasource.protocol if result.datasource else "",
            "expanded_fields_count": len(result.expanded_fields),
            "expanded_fields": [{"id": f.id, "name": f.standard_name} for f in result.expanded_fields[:5]],
            "web_search_sites": result.web_search_sites,
            "entity_type": result.conditions.entity_type,
            "entity_value": result.conditions.entity_value,
        }
        return output

    def fetch(self, field_id: str, entity_type: str = "",
               entity_value: str = "", time_start: str = "", time_end: str = "") -> str:
        """路由后取数：根据 field_id 组装 prompt → LLM 生成代码 → 执行返回数据

        Args:
            field_id: 路由选中的 DataField ID
            entity_type: 实体类型
            entity_value: 实体值
            time_start: 时间起始 YYYYMMDD
            time_end: 时间结束 YYYYMMDD
        Returns:
            取数结果的文本描述
        """
        # 重建 RouteResult
        from irkg.types import RouteCondition, RouteResult, FieldInfo
        from irkg.types import DataSourceInfo

        cond = RouteCondition(
            entity_type=entity_type, entity_value=entity_value,
            time_range_start=time_start, time_range_end=time_end,
        )

        # 查 Neo4j 获取 field + datasource 信息
        graph = GraphQuerier()
        field_node = graph.get_field_by_id(field_id)
        if not field_node:
            return f"错误: 字段 {field_id} 不在知识图谱中"

        ds = graph.get_datasource(field_id)
        if not ds:
            return f"错误: 字段 {field_id} 没有关联数据源"

        # 构造 RouteResult
        result = RouteResult(
            intent_type="fact",
            conditions=cond,
            concept_id="",
            datasource=ds,
        )
        result.fields.append(FieldInfo(
            id=field_id,
            standard_name=field_node.standard_name,
            description=field_node.description,
            data_type=field_node.data_type,
            unit=field_node.unit,
            api_column=field_node.api_column,
            granularity=field_node.granularity,
            refresh_time=field_node.refresh_time,
        ))

        # 组装 prompt
        prompt = build_sql_prompt(result)

        # 调用 LLM 生成取数代码（同实验脚本的模型）
        OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

        resp = requests.post(f"{OLLAMA_BASE}/api/generate", json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }, timeout=180)
        data = resp.json()
        llm_output = data.get("response", "")

        # 提取代码
        code = parse_llm_output(llm_output)

        if not code:
            return f"LLM 未生成有效代码，原始输出:\n{llm_output[:300]}"

        # 执行
        exec_result = execute_code(code)

        if exec_result["success"]:
            return f"取数成功:\n{exec_result['output']}"
        else:
            return f"取数失败:\n{exec_result.get('error', '')}\n\n生成代码:\n{code}"

    def to_fetch_tool_schema(self) -> dict:
        """返回 fetch_data 的 OpenAI 工具 schema"""
        return {
            "type": "function",
            "function": {
                "name": "fetch_data",
                "description": "路由后取数。给定 field_id 和实体条件，返回真实数据。需要先调用 route_query 确定 field_id。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {
                            "type": "string",
                            "description": "DataField ID，从 route_query 结果中获取"
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": ["stock_code", "index_code", "sector_name", ""],
                            "description": "实体类型"
                        },
                        "entity_value": {
                            "type": "string",
                            "description": "实体值，如 300750.SZ"
                        },
                        "time_start": {
                            "type": "string",
                            "description": "时间起始 YYYYMMDD"
                        },
                        "time_end": {
                            "type": "string",
                            "description": "时间结束 YYYYMMDD"
                        }
                    },
                    "required": ["field_id"]
                }
            }
        }

    def to_openai_tool(self) -> dict:
        """返回 OpenAI 格式的 function tool schema"""
        return {
            "type": "function",
            "function": {
                "name": "route_query",
                "description": "执行一次知识图谱路由查询。输入指标关键词和条件，返回匹配的 DataField 列表。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "指标关键词列表，如 ['涨跌幅']、['个股涨跌幅']。越精确越好。"
                        },
                        "intent_type": {
                            "type": "string",
                            "enum": ["fact", "analysis", "explore"],
                            "description": "查询意图：fact=事实查询 analysis=分析查询 explore=探索查询"
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": ["stock_code", "index_code", "sector_name", ""],
                            "description": "实体类型"
                        },
                        "entity_value": {
                            "type": "string",
                            "description": "实体值，如 300750.SZ"
                        },
                        "time_start": {
                            "type": "string",
                            "description": "时间范围起始，YYYYMMDD"
                        },
                        "time_end": {
                            "type": "string",
                            "description": "时间范围结束，YYYYMMDD"
                        },
                        "strict": {
                            "type": "boolean",
                            "description": "true=仅alias精确匹配，false=允许Faiss模糊兜底",
                            "default": False
                        }
                    },
                    "required": ["keywords"]
                }
            }
        }


# 单例
_tool: RouteTool | None = None


def get_route_tool() -> RouteTool:
    global _tool
    if _tool is None:
        _tool = RouteTool()
    return _tool
