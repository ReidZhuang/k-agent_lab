"""agent_coder 核心引擎

取数代码生成：接收 route result → 按协议分类组装 prompt → LLM 生成代码
→ compile() 语法检查 → 注入 boilerplate → execute() 执行 → 结果返回
"""
import json, os, sys, re, time
from pathlib import Path
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KG_DIR = os.path.dirname(_QA_DIR)
sys.path.insert(0, _KG_DIR)

from core import build_prompt
from neo4j import GraphDatabase
from scripts.executor import execute_code

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
MAX_ROUNDS = 3  # 含重试

NEO4J_DRIVER = GraphDatabase.driver(
    os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.environ.get("NEO4J_USER", "neo4j"),
          os.environ.get("NEO4J_PASS", "kg_route_2026")),
)

DS_PROMPTS_DIR = Path(_KG_DIR) / "ds_prompts"

# ============================================================
# 协议分类
# ============================================================
PROTOCOL_CLASS = {
    "tushare": "A",
    "akshare": "B",
    "levistock": "C",
    "xueqiu": "D",
    "tencent": "E",
    "sina": "E",
    "html_scrape": "F",
    "local_calc": "G",
    "web_search": "G",
    "llm_gen": "G",
}

# ============================================================
# Boilerplate 代码模板（Python 注入，LLM 不写）
# ============================================================
CODE_TEMPLATES = {
    "tushare": (
        "import os, tushare as ts\n"
        "import pandas as pd\n"
        "ts.set_token(os.getenv('TUSHARE_TOKEN'))\n"
        "pro = ts.pro_api()\n"
    ),
    "akshare": "import akshare as ak\nimport pandas as pd\n",
    "levistock": "import levistock as lk\n",
    "xueqiu": (
        "import pysnowball as ball, json\n"
        "_token_file = '/home/stockagent/project_space/research/experiments/knowledge_graph/query_agent_api/config/xueqiu_token.json'\n"
        "if __import__('os').path.exists(_token_file):\n"
        "    with open(_token_file) as _f:\n"
        "        _td = json.load(_f)\n"
        "    ball.set_token(f\"xq_a_token={_td['xq_a_token']}; u={_td['u']}\")\n"
        "\n"
        "def _xq_code(code: str) -> str:\n"
        "    \"\"\"自动转换股票代码为雪球格式（SH/SZ前缀）\"\"\"\n"
        "    c = code.upper().replace('.SH', '').replace('.SZ', '').replace('.BJ', '')\n"
        "    for p in ['SH','SZ','BJ','HK']:\n"
        "        if c.startswith(p):\n"
        "            c = c[2:]\n"
        "            break\n"
        "    if c[0] in ('6','9'): return f\"SH{c}\"\n"
        "    if c[0] in ('0','3'): return f\"SZ{c}\"\n"
        "    if c[0] == '8': return f\"BJ{c}\"\n"
        "    return f\"SH{c}\"\n"
    ),
    "tencent": "import requests\n",
    "sina": (
        "import requests, json, re\n"
        "from bs4 import BeautifulSoup\n"
    ),
    "html_scrape": "import requests\nfrom bs4 import BeautifulSoup\n",
    "local_calc": "",
    "web_search": "",
    "llm_gen": "",
}


# ============================================================
# 按分类的 Prompt 模板
# ============================================================

_CLASS_STEPS = {
    "A": """## 生成步骤

0. **不要使用 def 定义函数，直接写执行代码**（见下方示例）
1. 调用 pro.xxx() 获取数据
   - 函数名见下方 API 说明
   - **重要：只传查询条件中有提供值的参数**
   - 查询条件中 entity_value="" → 不传 ts_code/股票代码参数
   - 查询条件中 time_start="" → 不传 start_date
   - 查询条件中 time_end="" → 不传 end_date
   - **绝对不要编造任何参数的值**
2. 从返回的 DataFrame 中用**列名**提取指标
   - response 本身就是 DataFrame，**没有 .data 属性**，直接用
   - 列名见字段映射表中**「字段名」**列的值（如 `mkv`、`close`、`pct_chg`）
   - 用 `row["字段名"]` 取值，`row = df.iloc[-1]` 取最新行
   - **必须用字段映射表「字段名」列的英文名**，不要用中文说明列的文字
   - **不要用数字索引**，用列名（更可靠）
   - 不要用 `for row in` 循环遍历
3. 将结果按查询条件的指标顺序存入 _result 列表
4. 空数据时 _result = []

## 示例

查询条件中的指标: pct_chg(索引8)
查询条件中的股票代码: 000001.SZ
时间范围: 20260701 ~ 20260714

```python
# 系统已注入: import tushare + pro 初始化
df = pro.daily(ts_code="000001.SZ",    # ← 查询条件中的股票代码
               start_date="20260701",   # ← 时间起始
               end_date="20260714")     # ← 时间结束
if df.empty:                                 # ← 检查空数据
    _result = []
else:
    row = df.iloc[-1]                        # ← 取最新一行
    _result = [row["pct_chg"]]               # ← 用列名取值
```""",

    "B": """## 生成步骤

0. **不要使用 def 定义函数，直接写执行代码**
   - 不要定义函数，直接把调用 API → 提取数据 → 赋值 _result 的代码写在顶层
1. 调用 ak.xxx() 获取数据
   - 函数名和参数见下方 API 说明
   - **绝对不要给 API 传 API 说明中不存在的参数**
   - 如果 API 说明中没有 symbol 参数，就不要传 symbol
   - 如果 API 说明中有 symbol 参数，从查询条件中的主体获取
2. **注意返回格式**：akshare 有两种返回格式：
   - **格式1（item-value）**：带 symbol 参数的接口（如行业板块行情），返回两列：item（指标名）和 value（指标值）
   - **格式2（标准 DataFrame）**：无参接口（如债券收益率），返回标准的列名 DataFrame
3. 根据 API 说明中的提取示例判断格式：
   - item-value 格式：`df[df["item"] == "指标名"]` → 提取 value
   - 标准 DataFrame：`df.iloc[-1]` → 用 row["列名"] 取值
4. 将结果存入 _result 列表
5. 空数据时 _result = []

## 示例 1：item-value 格式（带 symbol 参数）

```python
# 系统已注入: import akshare as ak
df = ak.stock_board_industry_spot_em(symbol="电池")
if df.empty:
    _result = []
else:
    # 按 item 列匹配字段名，提取 value 列的值
    result_row = df[df["item"] == "涨跌幅"]
    _result = [float(result_row["value"].iloc[0])]
```

## 示例 2：标准 DataFrame 格式（无参）

```python
df = ak.bond_zh_us_rate()
if df.empty:
    _result = []
else:
    row = df.iloc[-1]
    _result = [float(row["中国国债收益率10年"])]
```""",

    "C": """## 生成步骤

0. **不要使用 def 定义函数**，直接写执行代码（见下方示例）
1. 调用 lk.xxx() 获取数据
2. 注意返回值类型（见 API 说明）：
   - dict：直接用 .get() 按 key 提取
   - list[dict]：遍历或按索引取一项，再按 key 提取
   - DataFrame：按列名提取
3. **从字段映射表的「字段名」列获取列名**，用 item.get("列名") 提取
4. 存入 _result 列表

## 示例 1：返回 dict

```python
# 系统已注入: import levistock as lk
data = lk.market_emotion_cls()          # 返回 dict
_result = [data.get("market_degree", 0)]  # market_degree 来自字段映射表
```

## 示例 2：返回 list[dict]

```python
# lk.sector_em() 返回 list[dict]
data_list = lk.sector_em()
if data_list:
    item = data_list[0]
    # 字段映射表中的字段名
    _result = [item.get("字段名", 0)]    # ← 请替换"字段名"为字段映射表里的实际列名
```""",

    "D": """## 生成步骤

0. **不要使用 def 定义函数**，直接写执行代码（见下方示例）
1. 用 `_xq_code(主体代码)` 统一转换股票代码为雪球格式
   - 系统已注入 _xq_code() 函数
   - `_xq_code("300750")` → `"SZ300750"`
   - `_xq_code("600519")` → `"SH600519"`
2. 调用 ball.xxx() 获取数据（传转换后的代码）
3. 注意：雪球 API 返回 dict 格式，需要按 key 提取
4. 通用格式：返回 {"data": {...}, "error_code": 0}
5. 从 response["data"] 中提取需要的指标
6. 存入 _result 列表

## 示例 1：ball.kline() 返回 dict

```python
# _xq_code() 已由系统注入
code = _xq_code("300750")                    # ← 先用 _xq_code() 转换
result = ball.kline(symbol=code, count=3)
# result["data"] 包含列名和数据
# result["data"]["column"] 是列名列表
# result["data"]["item"] 是数据列表（每行一个list）
if result and result.get("data"):
    columns = result["data"]["column"]
    items = result["data"]["item"]
    if items:
        # 取最新一行
        row = items[-1]
        # 找到对应列索引
        idx = columns.index("close")
        _result = [row[idx]]
```

## 示例 2：ball.quotec() 返回 dict

```python
code = _xq_code("300750")                    # ← 先用 _xq_code() 转换
result = ball.quotec(symbols=code)
if result and result.get("data"):
    # data 是 list，每项是一个股票
    item = result["data"][0]
    _result = [item["current"]]
```""",

    "E": """## 生成步骤

0. **不要使用 def 定义函数**，直接写执行代码（见下方示例）
1. 构造 HTTP URL，将查询主体代码填入正确位置
   - **注意**：有些接口要小写前缀（sz300750, sh600519），有些要纯数字（300750）
   - **代码格式必须严格按 API 说明**，不要自己猜
2. 用 requests.get() 发送请求（必须带 User-Agent 等请求头）
3. 按指定编码解码响应
4. **按 API 说明中的格式解析响应**
   - 不同协议格式不同：Tencent 用 ~ 分隔，Sina 实时行情用逗号分隔，Sina K线用 JSONP，Sina财报用HTML
   - 仔细阅读下方 API 说明的"返回格式"和"提取方法"
5. 按字段映射表中的索引或字段名提取指标值
6. 存入 _result 列表

## 示例 1：Tencent（~ 分隔）

```python
# 系统已注入: import requests
# code 取值见上方「查询条件」中的"主体"
code = "sz300750"                    # ← 从查询条件的「主体」获取
url = f"https://web.sqt.gtimg.cn/q={code}"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10, allow_redirects=True)
fields = resp.text.split("~")            # ← ~ 分割
_result = [float(fields[3])]             # ← 字段映射表中的索引
```

## 示例 2：Sina 实时行情（逗号分隔）

```python
code = "sz300750"
url = f"http://hq.sinajs.cn/list={code}"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0",
                    "Referer": "https://finance.sina.com.cn"}, timeout=10)
resp.encoding = "gbk"
content = resp.text.split('=\"')[1].rstrip(';\"')  # 去掉 var hq_str_xxx= 前缀
fields = content.split(",")                         # ← 逗号分割
_result = [float(fields[3])]                        # ← 字段映射表中的索引
```

## 示例 3：Sina K线（JSONP 格式，⚠️ 响应开头可能有脚本注解）

```python
import requests, json, re
code = "sz300750"  # ⚠️ 小写前缀 + 代码
url = "http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData"
resp = requests.get(url, params={"symbol": code, "scale": 240, "ma": "no", "datalen": 5},
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}, timeout=10)
# ⚠️ 响应可能开头有脚本注解，用 re 提取 JSON 数组
import re
match = re.search(r'\[.*\]', resp.text)
if match:
    data = json.loads(match.group())
    if data:
        _result = [float(data[-1]["close"])]  # ← 用 key 提取
```""",

    "F": """## 生成步骤

0. **不要使用 def 定义函数**，直接写执行代码（见下方示例）
1. 构造 HTML 页面 URL
2. 用 requests.get() 获取页面（编码: gb2312）
3. 用 BeautifulSoup 解析 HTML（用 html.parser，不要用 lxml）
4. 遍历表格，按行标签匹配找到目标字段
   - **行标签文字从查询条件的「说明」或「行标签」获取，不要硬编码，不要自己构造**
   - 例如查询条件"行标签: 购建固定资产" → 匹配"购建固定资产"
   - **不要用字段名（如 capex、equity_parent）做行标签匹配！字段名是API列名，不是HTML行标签**
   - **行标签必须从 condition_text 中"行标签:"后面的文字原样复制！**
   - 字段名（如"归母股东权益"）和HTML行标签（如"归属于母公司股东权益合计"）可能不同
5. **如果精确匹配不到，尝试部分匹配**（不同行业报表结构不同）
   - 银行股没有"货币资金"（有"现金及存放中央银行款项"），没有"应收账款"等常规科目
   - 先打印所有行标签做调试参考
   - 用 `if 关键词 in label:` 做模糊匹配
6. **检查单元格值是否为 "--"（无数据）**
   - 如果 `cells[1].get_text(strip=True)` 是 "--"，说明该行当前期无数据，跳过或尝试 cells[2]（上一期）
   - **不要直接 float("--")，会崩溃！**
7. 提取对应列数据（cells[1] 为最新一期，去掉逗号和"--"后转 float）
8. 存入 _result 列表

## 示例

```python
# 系统已注入: import requests + BeautifulSoup
code = "300750"                          # ← 查询主体的代码（不带后缀）
url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml"
resp = requests.get(url,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=15)
resp.encoding = "gb2312"
soup = BeautifulSoup(resp.text, "html.parser")  # ⚠️ 用 html.parser

target_label = "营业收入"  # ← 从查询条件条件中获取的行标签

for table in soup.find_all("table"):
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if cells:
            row_label = str(cells[0].get_text()).strip()
            if target_label in row_label:  # ← 用目标标签匹配
                val = cells[1].get_text(strip=True).replace(",", "").strip()
                if val and val != "--":
                    _result = [float(val)]
                break
```""",

    "G": """## 生成步骤

按 API 说明中的逻辑直接生成代码。输出与其他类相同格式。
```""",
}


# ============================================================
# Prompt 组装
# ============================================================

def _read_ds_file(dir_name: str, filename: str) -> str:
    """读取 ds_prompts/{dir_name}/{filename} 中的组件内容"""
    fp = DS_PROMPTS_DIR / dir_name / filename
    if fp.exists():
        return fp.read_text(encoding="utf-8").strip()
    return f"（{filename} 未找到）"


def _get_class_and_docs(datasource: dict) -> tuple[str, str, str, str]:
    """获取协议分类 + field.md + api.md"""
    protocol = datasource.get("protocol", "")
    ds_id = datasource.get("id", "")
    cls = PROTOCOL_CLASS.get(protocol, "G")

    # prompt_dir 为空时走 ds.id 对应的目录
    prompt_dir = datasource.get("prompt_dir", "") or ""
    effective_dir = prompt_dir.strip() if prompt_dir.strip() else ds_id

    field_doc = _read_ds_file(effective_dir, "field.md")
    api_doc = _read_ds_file(effective_dir, "api.md")

    # 清理 doc 中的标题
    field_body = re.sub(r'^#.*\n?', '', field_doc, flags=re.MULTILINE).strip()
    api_body = re.sub(r'^#.*\n?', '', api_doc, flags=re.MULTILINE).strip()

    return cls, field_body, api_body, protocol


def _format_condition_text(route: dict) -> str:
    """格式化查询条件"""
    condition = route.get("condition_text", "")
    # 如果有结构化的 entity/time，拼成标准格式
    parts = []
    entity = route.get("entity_value", "")
    if entity:
        parts.append(f"  主体: {entity}")
    cols = route.get("api_column", "")
    if cols:
        parts.append(f"  指标: {cols}")
    ts = route.get("time_start", "")
    te = route.get("time_end", "")
    if ts or te:
        parts.append(f"  时间: {ts or '?'} ~ {te or '?'}")
    return "\n".join(parts) if parts else condition


def build_codegen_prompt(route_result: dict) -> tuple[str, str]:
    """组装 agent_coder 的完整 prompt

    Args:
        route_result: agent_router 的输出 + Python 补充的 datasource 信息

    Returns:
        (prompt_text, protocol)
    """
    route = route_result.get("route", {})
    ds = route_result.get("datasource", {})
    req = route_result.get("request", {})

    cls, field_body, api_body, protocol = _get_class_and_docs(ds)

    cond_text = _format_condition_text(route)
    target_cols = [route.get("api_column", route.get("field_name", ""))]

    steps_and_example = _CLASS_STEPS.get(cls, _CLASS_STEPS["G"])

    prompt = f"""# 取数代码生成

## 查询条件（本次取数的输入变量）
{cond_text}

## 字段映射（API 返回数据中各字段的名称、类型和索引）
{field_body}

## API 说明（取数函数的调用方式和参数说明）
{api_body}

{steps_and_example}
"""
    return prompt, protocol


# ============================================================
# LLM 调用 + 语法检查 + 执行 + 重试
# ============================================================

def parse_python_code(text: str) -> str | None:
    """从 LLM 回复中提取 ```python 代码块"""
    m = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def syntax_check(code: str) -> str | None:
    """compile() 语法检查"""
    try:
        compile(code, '<codegen>', 'exec')
        return None
    except SyntaxError as e:
        return f"语法错误: 行{e.lineno}: {e.msg}\n{e.text}"


def merge_with_template(code: str, protocol: str) -> str:
    """将 LLM 生成的代码与协议 boilerplate 合并"""
    tmpl = CODE_TEMPLATES.get(protocol, "")
    if not tmpl:
        return code
    return tmpl + "\n" + code


def codegen_loop(route_result: dict) -> dict:
    """完整的代码生成循环

    Args:
        route_result: 路由结果（包含 route + datasource + request）

    Returns:
        {"success": bool, "result": list, "output": str, "error": str}
    """
    # 1. 组装 prompt
    system_prompt = build_prompt("agent_coder")
    task_prompt, protocol = build_codegen_prompt(route_result)
    print(f"  📋 Task prompt ({len(task_prompt)} chars), protocol={protocol}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt},
    ]

    error_count = 0
    final_answer = None

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n  🔄 Round {round_num}/{MAX_ROUNDS}")

        t0 = time.time()
        try:
            resp = _client.chat.completions.create(
                model=MODEL, messages=messages,
                temperature=0.1, max_tokens=2048,
            )
        except Exception as e:
            return {"success": False, "result": [], "output": "", "error": f"API异常: {e}"}

        elapsed = time.time() - t0
        msg = resp.choices[0].message
        usage = resp.usage
        print(f"     ⏱ {elapsed:.1f}s | tokens: {usage.prompt_tokens if usage else '?'}→{usage.completion_tokens if usage else '?'}")

        content = msg.content or ""

        # FINAL_ANSWER
        if "[FINAL_ANSWER]" in content:
            final_answer = content
            print(f"     ✅ [FINAL_ANSWER]")
            break

        # 提取代码
        code = parse_python_code(content)
        if not code:
            print(f"     ⚠️ 未找到代码块")
            error_count += 1
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "请将代码放在 ```python 代码块中输出。"})
            continue

        print(f"     📝 代码 ({len(code)} chars)")

        # 语法检查
        err = syntax_check(code)
        if err:
            print(f"     ❌ 语法错误: {err[:100]}")
            error_count += 1
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"代码语法错误:\n{err}\n\n修正后重新生成。"})
            continue

        print(f"     ✅ 语法检查通过")

        # 注入 boilerplate + 执行（带网络重试）
        full_code = merge_with_template(code, protocol)
        exec_result = execute_code(full_code)

        # 网络错误时自动重试，不给 LLM 看
        if not exec_result["success"]:
            err_msg = exec_result.get("error", "")
            if any(kw in err_msg for kw in ["Connection", "RemoteDisconnected", "Timeout", "timeout"]):
                print(f"     ⚠️ 网络错误，自动重试...")
                import time as _t
                for _retry in range(2):
                    _t.sleep(3)
                    exec_result = execute_code(full_code)
                    if exec_result["success"]:
                        break
                    print(f"     ⚠️ 网络重试 {_retry+1} 次后仍失败")

        if exec_result["success"]:
            result_data = exec_result.get("result", [])
            output_text = exec_result.get("output", "")
            if result_data:
                print(f"     ✅ 执行成功: _result = {result_data}")
                return {
                    "success": True,
                    "result": result_data,
                    "output": output_text,
                    "error": "",
                }
            else:
                # 执行成功但无数据 → 重试
                err_msg = f"代码执行成功但返回空数据"
                print(f"     ⚠️ {err_msg}")
                error_count += 1
                if error_count >= MAX_ROUNDS:
                    print(f"     ⏹ 连续 {error_count} 次失败，终止")
                    return {
                        "success": False,
                        "result": [],
                        "output": output_text,
                        "error": f"取数失败（已重试{error_count}次）:\n{err_msg}",
                    }
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"代码执行成功但返回了空数据（_result = []）。\n可能原因：1) 行标签匹配失败 2) API未返回数据 3) 代码格式错误。\n检查行标签是否和HTML中完全一致，尝试部分匹配，修复后重新生成代码。"})
        else:
            err_msg = exec_result.get("error", "未知错误")
            print(f"     ❌ 执行失败: {err_msg[:150]}")
            error_count += 1
            if error_count >= MAX_ROUNDS:
                print(f"     ⏹ 连续 {error_count} 次失败，终止")
                return {
                    "success": False,
                    "result": [],
                    "output": "",
                    "error": f"取数失败（已重试{error_count}次）:\n{err_msg}",
                }
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"代码执行报错:\n{err_msg}\n\n分析错误原因并修复代码。"})

    if final_answer:
        # 从 FINAL_ANSWER 中提取代码
        code = parse_python_code(final_answer)
        if code:
            err = syntax_check(code)
            if not err:
                full_code = merge_with_template(code, protocol)
                exec_result = execute_code(full_code)
                if exec_result["success"]:
                    return {
                        "success": True,
                        "result": exec_result.get("result", []),
                        "output": exec_result.get("output", ""),
                        "error": "",
                    }
    return {"success": False, "result": [], "output": "", "error": "未生成有效代码"}
