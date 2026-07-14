"""SQL 生成：路由结果 + ds_prompts -> prompt -> LLM -> 可执行代码

build_sql_prompt() 将路由结果和 ds_prompts 下的内容合并为
一个结构化的取数代码生成任务 prompt。
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DS_PROMPTS_DIR = ROOT / "ds_prompts"
PROMPTS_DIR = ROOT / "prompts"


def load_prompt(path: str | Path) -> str:
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def read_ds_file(ds_id: str, filename: str) -> str:
    fp = DS_PROMPTS_DIR / ds_id / filename
    return load_prompt(fp)


# 协议说明 — 只注入当前协议对应的一条
_PROTOCOL_HINTS = {
    "tencent": "HTTP GET 请求，返回 ~ 分隔的 88 个字段",
    "sina": "HTTP GET 请求，返回 GBK 编码数据",
    "tushare": "使用 tushare SDK（pro.xxx()）",
    "akshare": "使用 akshare SDK（ak.xxx()）",
    "levistock": "使用 levistock SDK（lk.xxx()）",
    "xueqiu": "使用 pysnowball SDK（ball.xxx()）",
    "local_calc": "直接用 Python 表达式计算",
    "web_search": "返回需要搜索的完整 URL 列表",
    "llm_gen": "无需取数，直接生成分析",
    "html_scrape": "从 HTML 页面解析表格数据",
}


def _format_code(code_val: str, protocol: str, entity_type: str) -> str:
    """格式转换：300750.SZ → sz300750（tencent/sina 协议）"""
    if protocol in ("tencent", "sina") and entity_type == "stock_code" and "." in code_val:
        parts = code_val.split(".")
        sym, ex = parts[0], parts[1]
        ex_map = {"SH": "sh", "SZ": "sz"}
        return f"{ex_map.get(ex, ex.lower())}{sym}"
    return code_val


def _conditions_text(cond, protocol: str, target_cols: list[str]) -> str:
    """格式化为结构化查询条件（纯文本描述，避免 LLM 误认为是 Python 字典）"""
    lines = []

    if cond.entity_value:
        code = _format_code(cond.entity_value, protocol, cond.entity_type or "")
        type_label = {"stock_code": "股票", "sector_name": "板块", "index_code": "指数"}.get(
            cond.entity_type or "", "实体")
        lines.append(f"  · {type_label}: {code}")
    else:
        lines.append("  · 主体: 无")

    lines.append(f"  · 指标: {', '.join(target_cols)}")

    if cond.time_range_start:
        scope = f"{cond.time_range_start} ~ {cond.time_range_end}"
        lines.append(f"  · 时间范围: {scope}")
    elif cond.time_range_end:
        lines.append(f"  · 截至: {cond.time_range_end}")

    return "\n".join(lines)


def _steps_and_example(protocol: str) -> str:
    """协议相关的生成步骤 + 完整示例"""
    if protocol == "tencent":
        return """## 生成步骤
1. 将 查询主体.代码 填入 URL 的 {code} 位置
2. 用 requests.get() 发送请求
3. 用 .text.split("~") 分割响应
4. 在字段映射表中找到 查询指标 对应的索引，提取值
5. 将结果按 查询指标 顺序存入 _result 列表

## 示例
查询条件:
  · 股票: sz300750
  · 指标: price, pct_chg

```python
# 【系统注入: import requests】
code = "sz300750"                     # → 查询主体.代码
url = f"https://web.sqt.gtimg.cn/q={code}"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
    timeout=10, allow_redirects=True)
fields = resp.text.split("~")

price = float(fields[3])              # 指标: price → 索引 3
pct_chg = float(fields[32])           # 指标: pct_chg → 索引 32
_result = [price, pct_chg]            # ← 按指标顺序存入
```"""
    elif protocol == "sina":
        return """## 生成步骤
1. 将 查询主体.代码 填入 URL
2. HTTP GET（带 Referer 头），GBK 解码
3. 去掉 "var hq_str_xxx=" 前缀，按逗号 split
4. 按索引提取指标并存入 _result

## 输出规则
- 结果存入 `_result` 列表，顺序与 查询指标 一致
- 系统自动捕获 _result"""
    elif protocol == "tushare":
        return """## 生成步骤
1. 初始化 API 客户端: pro = ts.pro_api()
   - pro 是 tushare 的 API 操作对象，所有接口通过 pro.xxx() 调用
2. 调用 pro.daily(ts_code, start_date, end_date) 获取日线数据
   - ts_code ← 查询主体.代码
   - start_date, end_date ← 查询范围.时间
3. 从返回的 DataFrame 中按列名提取 查询指标
4. 将结果按 查询指标 顺序存入 _result 列表

## 输出规则
- 结果存入 `_result` 列表，顺序与 查询指标 一致
- 空数据: _result = []
- 系统自动捕获 _result

## 示例
查询条件:
  · 股票: 000001.SZ
  · 指标: close, pct_chg
  · 时间范围: 20260701 ~ 20260714

```python
# import os/token 由系统自动注入，无需重复写
pro = ts.pro_api()                       # 初始化 tushare API 客户端

df = pro.daily(
    ts_code="000001.SZ",               # ← 查询主体.代码
    start_date="20260701",              # ← 查询范围.时间 起始
    end_date="20260714",                # ← 查询范围.时间 结束
)
if df.empty:
    _result = []                         # 空数据
else:
    row = df.iloc[0]
    _result = [                          # ← 按指标顺序
        row["close"],                    #   指标: close
        row["pct_chg"],                  #   指标: pct_chg
    ]
```"""
    elif protocol == "akshare":
        return """## 生成步骤
1. 调用 ak.xxx() 获取数据，函数名和参数见 API 文档
   - akshare 的接口以 ak.xxx() 形式调用，每个数据源有独立函数
2. 从返回的 DataFrame 中按列名提取 查询指标
3. 将结果按 查询指标 顺序存入 _result 列表

## 输出规则
- _result 顺序与 查询指标 一致
- 空数据: _result = []
- 系统自动捕获 _result

## 示例
```python
# import akshare as ak 由系统自动注入
df = ak.stock_board_industry_spot_em(symbol="小金属")
if df.empty:
    _result = []
else:
    row = df.iloc[0]
    _result = [
        row["板块名称"],
        row["涨跌幅"],
    ]
```"""
    elif protocol == "levistock":
        return """## 生成步骤
1. 调用 lk.xxx() 获取数据，函数名和参数见 API 文档
2. 从返回数据中提取 查询指标
3. 存入 _result

## 输出规则
- _result 顺序与 查询指标 一致
- 系统自动捕获 _result

## 示例
```python
# import levistock as lk 由系统自动注入
data = lk.market_emotion_cls()
_result = [data.get("market_degree", 0)]
```"""
    elif protocol == "xueqiu":
        return """## 生成步骤
1. 调用 ball.xxx() 获取数据，函数名和参数见 API 文档
2. 从返回数据中提取 查询指标
3. 存入 _result

## 输出规则
- _result 顺序与 查询指标 一致
- 系统自动捕获 _result

## 示例
```python
# import pysnowball as ball 由系统自动注入
df = ball.kline(symbol="SH600519", days=1)
if df.empty:
    _result = []
else:
    row = df.iloc[0]
    _result = [row["close"]]
```"""
    elif protocol == "html_scrape":
        return """## 生成步骤
1. 构造 HTML 页面 URL，将 {code} 替换为查询主体.代码
2. 用 requests.get() 获取页面（编码: gb2312）
3. 用 BeautifulSoup 找到数据表格
4. 按行标签找到目标字段所在行，提取对应数据
5. 结果存入 _result

## 输出规则
- _result 顺序与 查询指标 一致
- 系统自动捕获 _result

## 示例
```python
# import requests + BeautifulSoup 由系统自动注入
url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/300750/ctrl/part/displaytype/4.phtml"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
resp.encoding = "gb2312"
soup = BeautifulSoup(resp.text, "html.parser")
for table in soup.find_all("table"):
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if cells and "营业收入" in str(cells[0].get_text()):
            _result = [float(cells[1].get_text().replace(",", ""))]
            break
```"""
    elif protocol == "local_calc":
        return """## 生成步骤
1. 直接用 Python 表达式计算
2. 结果存入 _result

## 示例
```python
# 根据已有数据直接计算
_result = [a_value / b_value * 100]
```"""
    return "## 输出规则\n- 结果存入 `_result` 列表\n- 系统自动捕获 _result\n"


def build_sql_prompt(route_result) -> str:
    """将路由输出 + ds_prompts 组装为 LLM 输入 prompt"""
    ds = route_result.datasource
    if not ds:
        return "错误: 无数据源信息"

    ds_id = ds.id
    protocol = ds.protocol or ""

    # 读取文档
    field_doc = read_ds_file(ds_id, "field.md")       # 字段映射表
    api_doc = read_ds_file(ds_id, "api.md")            # API 调用规则

    # 查询条件（结构化）
    cond = route_result.conditions
    target_cols = [f.api_column or f.id for f in route_result.fields]
    cond_text = _conditions_text(cond, protocol, target_cols)

    # 去掉文档中的标题行
    field_body = re.sub(r'^#.*\n?', '', field_doc, flags=re.MULTILINE).strip()
    api_body = re.sub(r'^#.*\n?', '', api_doc, flags=re.MULTILINE).strip()

    prompt = f"""# 取数代码生成

## 查询条件（本次取数的输入变量）
{cond_text}

## 字段映射（API返回数据中各字段的名称、类型和索引位置）
{field_body}

## API（取数函数的调用方式和参数说明）
{api_body}

{_steps_and_example(protocol)}
"""
    return prompt


# ── 代码模板（协议相关的固定开头，执行前自动注入） ──
CODE_TEMPLATES = {
    "tushare": (
        "import os, tushare as ts\n"
        "ts.set_token(os.getenv('TUSHARE_TOKEN'))\n"
    ),
    "akshare": "import akshare as ak\n",
    "levistock": "import levistock as lk\n",
    "xueqiu": "import pysnowball as ball\n",
    "tencent": "import requests\n",
    "sina": "import requests\n",
    "html_scrape": "import requests\nfrom bs4 import BeautifulSoup\n",
}


def merge_with_template(code: str, protocol: str) -> str:
    """将 LLM 生成的代码与协议模板合并"""
    tmpl = CODE_TEMPLATES.get(protocol, "")
    if not tmpl:
        return code
    return tmpl + "\n" + code


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
