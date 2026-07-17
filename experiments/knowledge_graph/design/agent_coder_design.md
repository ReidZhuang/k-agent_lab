# Agent Coder 架构设计方案（v2）

## 一、输入输出规格

### 输入（来自 agent_router）

agent_router 输出后，Python 层加工成以下结构送入 agent_coder：

```python
{
    "req_id": "R_001",
    "query_id": "Q_a1b2c3d4",
    # 取数请求（来自 agent_guide）
    "request": {
        "obj": ["宁德时代"],
        "var": "涨跌幅",
        "condition": ["今天"]
    },
    # 路由结果
    "route": {
        "field_id": "FIELD_QUOTE_PCT_CHG",
        "field_name": "个股涨跌幅",
        "api_column": "pct_chg",        # 实际 API 列名
        "data_type": "float",
        "unit": "%",
        "granularity": "实时,个股级别",
        "entity_type": "stock_code",
        "entity_value": "300750.SZ",
        "time_start": "20260716",
        "time_end": "20260716",
        "condition_text": "股票: 300750.SZ\n  指标: pct_chg\n  时间: 今天"
    },
    # 数据源信息（Python 从 Neo4j 查）
    "datasource": {
        "id": "DS_TUSHARE_DAILY",
        "protocol": "tushare",          # → 决定 A/B/C/D/E/F 类
        "prompt_dir": "ds_prompts/DS_TUSHARE_DAILY/",
        "class": "A",                    # 由 Python 按 protocol 分配
    }
}
```

### Python 加工层（Input Processor）

Python 在送入 LLM 之前做以下加工：

```
1. protocol → 分类（A/B/C/D/E/F）
2. 读取 field.md + api.md → 拼接成 prompt
3. 按分类注入该类别的代码模板 + 说明
4. 注入查询条件（格式化后的时间、主体、指标）
5. 准备 boilerplate 代码（按协议注入 import/初始化）
```

### 输出（LLM 产出 + Python 执行）

LLM 产出的是纯取数代码（无 import/无初始化）：

```python
# LLM 只输出这部分：
df = pro.daily(ts_code="300750.SZ", start_date="20260716", end_date="20260716")
if df.empty:
    _result = []
else:
    row = df.iloc[0]
    _result = [row["pct_chg"]]
```

Python 执行后标准化输出：

```python
{
    "req_id": "R_001",
    "query_id": "Q_a1b2c3d4",
    "success": True,
    "result": [2.5],              # _result 列表
    "output": "",                  # print 输出
    "field_id": "FIELD_QUOTE_PCT_CHG",
    "var": "涨跌幅",
    "error": "",
}
```

### 数据流全景

```
agent_guide ─→ [{obj,var,condition}, ...]
                    │
                    ▼
agent_router ─→ {field_id, datasource_id, entity, time...}
                    │
                    ▼
Python Processor ───────→ 查 Neo4j 获 field/datasource 属性
    │                       读 ds_prompts/{ds_id}/*.md
    │                       按 protocol 分配类别
    │                       组装 prompt
    │                       准备 boilerplate
    ▼
LLM (agent_coder prompt) ─→ 核心取数代码
    │
    ▼
Python: compile()语法检查 ─→ 通过？
    │                          ❌ → LLM 重试（3次）
    ▼
Python: merge_with_template(boilerplate + code)
    │
    ▼
Python: execute_code() ─→ 执行成功？
    │                        ❌ → LLM 重试（3次）
    ▼
_result 数据 ← 标准化输出
```

---

## 二、按类别的 Prompt 模板设计

### 通用结构（所有类共用）

每个 prompt 由 5 个部分组成：

```
1. ## 查询条件       ← 本次取数的具体参数（从 route 注入）
2. ## 字段映射       ← field.md 内容（表结构）
3. ## API 说明       ← api.md 内容（函数/接口使用）
4. ## 生成步骤       ← 该类别的步骤说明（告诉 LLM 做什么）
5. ## 示例           ← 该类别的代码示例 + 解释
```

### A 类 — Tushare SDK（60 个数据源）

**生成步骤：**
```
1. 调用 pro.xxx() 获取数据
   - 函数名和参数见 API 说明
   - ts_code ← 查询条件中的股票代码
   - start_date, end_date ← 查询条件中的时间范围
2. 从返回的 DataFrame 中按列名提取指标
   - 列名见字段映射表
3. 将结果按指标顺序存入 _result 列表
4. 空数据时 _result = []
```

**示例：**
```python
# 查询条件中的股票代码 = "000001.SZ"
# 填入 ts_code 参数
df = pro.daily(ts_code="000001.SZ",    # ← 查询主体
               start_date="20260701",   # ← 时间起始
               end_date="20260714")     # ← 时间结束
# 检查返回数据是否为空
if df.empty:
    _result = []                         # 空数据处理
else:
    row = df.iloc[0]                     # 取最新一行
    _result = [row["close"],             # ← 字段映射中的列名
               row["pct_chg"]]           # ← 字段映射中的列名
```

### B 类 — Akshare SDK（8 个数据源）

**生成步骤：**
```
1. 调用 ak.xxx() 获取数据
   - 函数名和参数见 API 说明
   - symbol 参数从查询条件中获取
2. 从返回的 DataFrame 中按中文列名提取指标
3. 存入 _result
```

**示例：**
```python
# symbol 参数 = "半导体"（从查询条件的主体获取）
df = ak.stock_board_industry_spot_em(symbol="半导体")
if df.empty:
    _result = []
else:
    row = df.iloc[0]
    _result = [row["板块名称"],
               row["涨跌幅"]]
```

### C 类 — Levistock SDK（6 个数据源）

**生成步骤：**
```
1. 调用 lk.xxx() 获取数据
2. 从返回的 dict 或 DataFrame 中按 key 或列名提取
3. 存入 _result
```

**示例：**
```python
# lk.market_emotion_cls() 返回 dict
data = lk.market_emotion_cls()
_result = [data.get("market_degree", 0)]
```

### D 类 — Xueqiu SDK（3 个数据源）

**生成步骤：**
```
1. 调用 ball.xxx() 获取数据
2. 从返回数据中提取指标
3. 存入 _result
```

**示例：**
```python
# ball.kline() 返回 DataFrame
df = ball.kline(symbol="SH600519", days=1)
if df.empty:
    _result = []
else:
    row = df.iloc[0]
    _result = [row["close"]]
```

### E 类 — HTTP GET（2 个数据源）

**生成步骤：**
```
1. 构造 URL，将查询主体代码填入 {code} 位置
2. 用 requests.get() 发送 HTTP 请求
3. 解码响应文本（GBK/UTF-8）
4. 按分隔符分割文本
5. 按索引位置提取指标值
6. 存入 _result
```

**示例（Tencent）：**
```python
# 构造 URL
code = "sz300750"                       # ← 查询主体的代码格式
url = f"https://web.sqt.gtimg.cn/q={code}"
# 发送请求（必须 allow_redirects=True）
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10, allow_redirects=True)
# 按 ~ 分割
fields = resp.text.split("~")
# 字段映射表中找到指标的索引位置
price = float(fields[3])               # 最新价 → 索引 3
_result = [price]
```

### F 类 — HTML Scrape（3 个数据源）

**生成步骤：**
```
1. 构造 HTML 页面 URL
2. 用 requests.get() 获取页面
3. BeautifulSoup 解析 HTML
4. 按行标签匹配找到目标字段
5. 提取对应数据列
6. 存入 _result
```

**示例：**
```python
# 构造 URL（code = 股票代码，不含后缀）
url = f"https://.../stockid/300750/..."
# 获取页面
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
resp.encoding = "gb2312"
soup = BeautifulSoup(resp.text, "html.parser")
# 遍历表格，按行标签匹配
for table in soup.find_all("table"):
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if cells and "营业收入" in str(cells[0].get_text()):
            # 取对应列的数据
            _result = [float(cells[1].get_text().replace(",", ""))]
            break
```

---

## 三、Boilerplate 代码模板

Python 端按协议自动注入，LLM 不需要写这部分：

```python
CODE_TEMPLATES = {
    "tushare": (
        "import os, tushare as ts\n"
        "import pandas as pd\n"
        "ts.set_token(os.getenv('TUSHARE_TOKEN'))\n"
        "pro = ts.pro_api()\n"
    ),
    "akshare": "import akshare as ak\nimport pandas as pd\n",
    "levistock": "import levistock as lk\n",
    "xueqiu": "import pysnowball as ball\n",
    "tencent": "import requests\n",
    "sina": "import requests\n",
    "html_scrape": "import requests\nfrom bs4 import BeautifulSoup\n",
    "local_calc": "",
    "web_search": "",
    "llm_gen": "",
}
```

---

## 四、执行与重试逻辑

沿用 `experiment_codegen.py` 的模式：

```
Round 1: LLM 生成代码
    → compile() 语法检查 → fail? → 报错信息 + 重试
    → execute_code()    → fail? → 运行时错误 + 重试
    → success           → 返回 _result

Round 2-3: 最多重试 3 次
    每次将前次的错误信息 + 代码注入 prompt
    让 LLM 分析错误原因并修复

成功 → [FINAL_ANSWER] + _result
失败 3 次 → 返回错误信息
```

---

## 五、开发步骤

### Phase 3a：填充 prompt_dir 到 DataSource
遍历所有 DataSource，对有 ds_prompts 的写入 prompt_dir 属性

### Phase 3b：补充缺失的 ds_prompts
53 个缺 ds_prompts 的数据源（主要是 60 个 tushare 中未被覆盖的），逐个补充

### Phase 3c：实现分类 Prompt 模板
按 A/B/C/D/E/F 实现 6 个 prompt 模板，每个模板包含步骤说明 + 示例

### Phase 3d：实现 Agent Coder 主流程
- Input Processor（读取 route result → 查 Neo4j → 组装 prompt）
- Code Executor（compile + execute + retry loop）
- Output Formatter（_result 提取）

### Phase 3e：分级别测试
- L1 简单取数 → 测试全部通过
- L2-L5 逐步增加复杂度
- 随测试修改 prompt
