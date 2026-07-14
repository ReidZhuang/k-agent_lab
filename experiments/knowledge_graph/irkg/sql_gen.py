"""SQL 生成：路由结果 + ds_prompts -> prompt -> LLM -> 可执行代码"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DS_PROMPTS_DIR = ROOT / "ds_prompts"
PROMPTS_DIR = ROOT / "prompts"


def load_prompt(path: str | Path) -> str:
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"(文件 {p.name} 未找到)"


def read_ds_file(ds_id: str, filename: str) -> str:
    fp = DS_PROMPTS_DIR / ds_id / filename
    return load_prompt(fp)


def build_sql_prompt(route_result) -> str:
    """将路由输出 + ds_prompts 组装为 LLM 输入 prompt"""
    ds = route_result.datasource
    if not ds:
        return "错误: 无数据源信息"

    ds_id = ds.id
    field_doc = read_ds_file(ds_id, "field.md")
    table_doc = read_ds_file(ds_id, "table.md")
    api_doc = read_ds_file(ds_id, "api.md")

    def fmt_field(f):
        col = f" -> API列: {f.api_column}" if f.api_column else ""
        return f"{f.standard_name}{col}"

    field_list = [fmt_field(f) for f in route_result.fields]
    if route_result.expanded_fields:
        field_list += [fmt_field(f) for f in route_result.expanded_fields]

    cond = route_result.conditions
    cond_parts = []
    if cond.entity_value:
        code_val = cond.entity_value
        proto = ds.protocol or ""
        if proto in ("tencent", "sina") and cond.entity_type == "stock_code" and "." in code_val:
            sym, ex = code_val.split(".")[0], code_val.split(".")[1]
            ex_map = {"SH": "sh", "SZ": "sz"}
            code_val = f"{ex_map.get(ex, ex.lower())}{sym}"
        cond_parts.append(f"实体: {cond.entity_type}={code_val}")
    if cond.time_range_start:
        cond_parts.append(f"时间: {cond.time_range_start} ~ {cond.time_range_end}")

    # 根据 protocol 选择代码生成说明
    protocol = ds.protocol if ds.protocol else ""
    lang_hints = {
        "tushare": "使用 Python 调用 tushare SDK（pro.xxx()），不要使用 SQL",
        "akshare": "使用 Python 调用 akshare SDK（ak.xxx()），不要使用 SQL",
        "levistock": "使用 Python 调用 levistock SDK（lk.xxx()），不要使用 SQL",
        "xueqiu": "使用 Python 调用 pysnowball SDK（ball.xxx()），不要使用 SQL",
        "tencent": "使用 Python requests 库发送 HTTP GET 请求",
        "sina": "使用 Python requests 库发送 HTTP GET 请求，注意 GBK 编码",
        "local_calc": "使用 Python 表达式直接计算",
        "web_search": "返回需要搜索的完整站点 URL 列表",
        "llm_gen": "无需取数，LLM 直接生成分析",
    }
    lang_hint = lang_hints.get(protocol, "生成 Python 取数代码")

    prompt = f"""
# 取数代码生成任务

## 生成要求
{lang_hint}

## 要取的数据
字段: {', '.join(field_list)}
数据源: {ds_id} ({ds.name})

## 查询条件
{chr(10).join(cond_parts) if cond_parts else '无特殊条件'}

## 可用字段
{field_doc}

## 表/接口结构
{table_doc}

## API 调用规则
{api_doc}
"""
    return prompt


def parse_llm_output(text: str) -> str:
    """从 LLM 回复中提取可执行代码"""
    patterns = [
        r"```python\n(.*?)```",
        r"```\n(.*?)```",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text.strip()
