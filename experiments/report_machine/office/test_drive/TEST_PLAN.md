# Office 报告生成系统 — 完整测试方案

## 测试策略总览

```
第1层: 单元测试 ─── 语法/报文/模型校验
第2层: 单体功能测试 ── 各主体功能完整性
第3层: 通信测试 ─── 主体间报文交互（含边界状态）
第4层: 压力测试 ─── 高并发负载
第5层: Agent Loop 测试 ── DeepSeek 工具调用
第6层: 端到端测试 ─── 全链路集成
```

**测试标的股票（固定）：** `['淮北矿业', '博瑞医药', '凯莱英', '广生堂']`

**测试目录结构：**
```
test_drive/
├── TEST_PLAN.md          # 本文件
├── unit/                 # 第1层：单元测试
│   ├── test_syntax.py
│   ├── test_models.py
│   └── results/
├── integration/          # 第2-3层：单体+通信测试
│   ├── test_fetcher.py
│   ├── test_middleman.py
│   ├── test_writer.py
│   ├── test_reporter.py
│   ├── test_communication.py
│   ├── report_parser.py  # 通用结果解析器
│   └── results/
├── stress/               # 第4层：压力测试
│   ├── test_middleman_stress.py
│   ├── test_reporter_stress.py
│   ├── test_pipeline_stress.py
│   └── results/
├── prompt/               # 第5层：Agent prompt 测试
│   ├── test_prompt.py
│   ├── template_context.json
│   └── results/
├── e2e/                  # 第6层：端到端测试
│   ├── test_e2e.py
│   ├── test_e2e_stress.py
│   └── results/
└── results/              # 汇总报告
```

---

## 第1层：单元测试 — 语法与报文模型

### 目标

检查所有 Python 文件的语法正确性，以及 Pydantic 模型的序列化/反序列化在各种输入下是否正常。

### 测试内容

#### 1.1 语法检查 (`test_syntax.py`)

| 用例 | 方法 | 预期 |
|:----|:-----|:------|
| 所有 .py 文件语法 | `ast.parse()` | 全部通过 |
| 所有 import 解析 | `python3 -c "import ..."` | 无 ImportError |

#### 1.2 报文模型测试 (`test_models.py`)

**覆盖所有请求/响应模型的所有字段组合：**

| 测试用例 | 测试模型 | 正常 | 字段缺失 | 类型错误 | 空值 |
|:---------|:---------|:----:|:--------:|:--------:|:---:|
| ReportRequest | stock_names | ✅ | ✅ | ✅ | ✅ |
| TypeARequest | writer_id, stock_code | ✅ | ✅ | ✅ | ✅ |
| TypeAResponse | writer_id, results | ✅ | ✅ | ✅ | ✅ |
| TypeBRequest | report_id, engine, session_id, article_ids | ✅ | ✅ | ✅ | ✅ |
| TypeBResponse | report_id, engine, session_id, articles, status | ✅ | ✅ | ✅ | ✅ |
| SubWorkerResult | stock_name, success, error | ✅ | ✅ | ✅ | ✅ |
| ReportResponse | report_id, total, success, failed, results | ✅ | ✅ | ✅ | ✅ |
| ReportContext | 全部字段 | ✅ | ✅ | ✅ | ✅ |
| ReporterResponse | report_id, status, output_path, rounds, error | ✅ | ✅ | ✅ | ✅ |

**通信状态组合测试（对每个需要通信的模型对）：**

对于所有成对通信的 Request/Response，需要测试以下状态组合：

```
正常通信:
  OK → 201/200 + 完整返回体
  OK → 空结果（无文章、无数据）

超时状态:
  客户端超时 → reports.Timeout
  服务端超时 → status="timeout" 返回
  部分超时 → 部分 engine 超时 + 部分正常

失败状态:
  400 Bad Request → 缺少必要字段
  404 Not Found → session 不存在
  500 Internal Error → 服务端异常
  503 Service Unavailable → 服务繁忙
  连接拒绝 → 服务未启动

边界状态:
  空列表输入（stock_names=[]）
  超大输入（100个股票名）
  特殊字符（股票名含特殊符号）
  重复股票名
```

---

## 第2层：单体功能测试

### 目标

每个主体独立测试，mock 掉其依赖的下游，验证自身功能完整性。

### 2.1 Fetcher 测试 (`test_fetcher.py`)

**前置条件：** mail_tower 可访问、数据库可访问、能调用 fetch_midday_data/message

| 测试用例 | 输入 | 预期输出 |
|:---------|:-----|:---------|
| 正常取数 | 4只测试股票 | dict 含 4 个 key + warning key |
| 空列表 | [] | 空 dict |
| 含未识别股票 | ['淮北矿业', '不存在的股票'] | 仅返回已识别的 |
| 单只股票 | ['淮北矿业'] | 单 key dict |
| 重复股票 | ['淮北矿业', '淮北矿业'] | 去重或正常返回 |

**验证指标：**
- 返回的 dict 是否包含 data 和 message 两个部分
- warning 结构是否正确（`{ts_code: {critical:[], non_critical:[]}}`）
- data 文本是否包含所有 9 个数据段（全市场情绪、行业关键词、收盘数据等）
- message 文本是否包含 4 个消息段（今日快讯、热门板块、跌停监控、异动监测）

### 2.2 Middleman 测试 (`test_middleman.py`)

**前置条件：** mail_tower 服务运行中

**Type A 测试：**

| 用例 | 输入 | 预期 |
|:-----|:-----|:------|
| 正常搜索 | stock_code="600985" | 返回 5 个 engine 结果 |
| 含空结果引擎 | 无新闻的股票 | 部分 engine empty=true |
| 不存在股票代码 | stock_code="000000" | 各 engine 返回 empty=true 或 error |
| 全空输入 | stock_code="" | 400 或 error 返回 |

**Type B 测试：**

| 用例 | 输入 | 预期 |
|:-----|:-----|:------|
| 正常取正文 | 先 search 拿到 session_id，再传 article_ids | 返回正文 |
| 请求不存在的 article_id | 传无效 ID | 返回空 |
| 请求无正文的文章 | body_avail=无 的文章 | 返回空 |
| 空 article_ids | [] | 返回空 |

**超时/重试测试：**

可通过暂停 mail_tower 或使用错误的 mail_tower 端口来触发：

| 用例 | 方法 | 预期 |
|:-----|:------|:------|
| mail_tower 连接拒绝 | 改配置到错误端口 | Type A/B 返回 error，请求不挂死 |
| mail_tower 返回 503 | 触发 mail_tower 满负载 | 重试后恢复或返回 error |
| Type B 20s 超时 | 设置短超时 | 超时后 articles=[]，status="timeout" |
| Type B processing | 请求刚提交的 session | 自动轮询直到 ready |

### 2.3 Writer 测试 (`test_writer.py`)

**前置条件：** middleman 和 reporter 运行中（或用 mock）

| 用例 | 输入 | 预期 |
|:-----|:-----|:------|
| 正常提交 | 4只测试股票 | 返回 ReportResponse，success=4 |
| 空列表 | [] | 400 错误 |
| 混合有效/无效 | 部分无效股票名 | success=有效数 |
| mock reporter 超时 | 停止 reporter | 自动保存 fallback |
| 单只股票 | ['淮北矿业'] | success=1 |

### 2.4 Reporter 测试 (`test_reporter.py`)

**前置条件：** DeepSeek API 可访问

| 用例 | 输入 | 预期 |
|:-----|:-----|:------|
| 正常 context | 完整 ReportContext | 返回 reporter output_path |
| 无正文可用 | 所有 body_avail=无 | 正常生成无正文的报告 |
| 含 warning | fetch_warnings 有内容 | 正常处理 |
| 超短 timeout | article_timeout=5s | 超时后继续 |
| 超大输入 | 超长 fetch_data | 正常处理 |

---

## 第3层：通信测试

### 目标

测试所有需要通信的主体对之间的报文交互，穷举状态组合。

### 通信对清单

```
A: Fetcher → Writer        (函数调用，非网络)
B: Writer → Middleman       (HTTP POST Type A)
C: Writer → Reporter        (HTTP POST /generate)
D: Reporter → Middleman     (HTTP POST Type B)
E: Middleman → mail_tower   (HTTP 调用)
```

### 3.1 Writer → Middleman（Type A）

| 状态组合 | Writer 行为 | Middleman 行为 | 预期结果 |
|:---------|:-----------|:---------------|:---------|
| 正常→正常 | 发 TypeARequest | 返回 TypeAResponse | results 包含 5 engine |
| 正常→部分空 | 发请求 | 部分 engine=empty | results 含空结果，无 error |
| 正常→全部空 | 发请求 | 全部 engine=empty | results 全部 empty |
| 正常→部分 error | 发请求 | 部分 engine error | results 含 error 字段 |
| 正常→全部 error | 发请求 | 全部 engine error | results 全部 error |
| 正常→503 | 发请求 | 重试后恢复 | 最终正常 |
| 正常→500 | 发请求 | 重试后恢复 | 最终正常 |
| 正常→连接拒绝 | 发请求 | middleman 停止 | 超时 + sub writer 异常 |
| 空 stock_code→正常 | 发空 code | 返回 error | sub writer 记录异常 |
| 超时→正常 | 短 timeout | 慢响应 | sub writer 超时处理 |

### 3.2 Writer → Reporter

| 状态组合 | Writer 行为 | Reporter 行为 | 预期结果 |
|:---------|:-----------|:--------------|:---------|
| 正常→正常 | POST context | 返回 output_path | success |
| 正常→LLM 异常 | POST context | DeepSeek API 异常 | error + log |
| 正常→超时 | POST | 处理>30s | 重试 3 次后保存 fallback |
| 连接拒绝 | POST | reporter 未启动 | 保存 fallback + log |
| 空 context | POST 空数据 | 返回 error | writer 记录异常 |
| 超大 context | POST 长篇 | 正常处理 | 成功 |

### 3.3 Reporter → Middleman（Type B）

| 状态组合 | Reporter 行为 | Middleman 行为 | 预期结果 |
|:---------|:-------------|:---------------|:---------|
| 正常→正常 | 发 TypeBRequest | 返回正文 | 注入上下文 |
| 正常→部分正文就绪 | 发请求 | 部分 article=processing | 等 polling 后返回 |
| 正常→全部空 | 发请求 | 全部无正文 | 返回空 articles |
| 正常→部分 error | 发请求 | 部分 error | 返回部分 error |
| 正常→全部 error | 发请求 | 全部 error | articles=[] |
| 正常→timeout | 发请求 | >120s | 超时填空 |
| 404 session→正常 | 无效 session_id | 404 | 返回 error |
| 空 article_ids | [] | 返回空 | 正常 |

### 3.4 Middleman → mail_tower

| 状态组合 | Middleman 行为 | mail_tower 行为 | 预期 |
|:---------|:--------------|:----------------|:-----|
| 正常→200 list_ready | /search + /poll | 返回结果 | 聚合成功 |
| 正常→200 done | /search | 立即就绪 | 直接取 preview |
| 正常→200 empty | /search | empty=true | preview=null |
| 正常→503 | /search | 503 | 重试 3 次 |
| 正常→504 | /search | 504 | 重试 2 次 |
| 正常→500(网络) | /search | ConnectionReset | 重试 3 次 |
| 正常→500(参数) | /search | 无法解析 | 不重试 |
| 正常→连接失败 | /search | 无响应 | 重试 3 次后返回 error |
| 正常→200 processing(article) | /article | processing | 轮询最多 120s |
| 正常→200 ready(article) | /article | 正文就绪 | 返回正文 |
| 正常→200 error(article) | /article | 提取失败 | 返回 error |
| 正常→404(article) | /article | session 过期 | 返回 error |

---

## 第4层：压力测试

### 4.1 Middleman Type A 压力测试

**目标：** 测试 middleman 在大量并发请求下的表现。

**方法：**
```python
STOCKS = 30-50 只随机股票
MAX_WORKERS = 64
# 并发发起 Type A 请求
# 记录：
#   - 总耗时
#   - 成功率
#   - 平均/中位数/P95/P99 响应时间
#   - 单个 engine 失败率
#   - 异常类型分布
```

**测试档次：**

| 档次 | 并发股票数 | 预期行为 |
|:----|:----------:|:---------|
| 轻载 | 10 | 全部正常，1-3min |
| 中载 | 20 | 可能有个别排队，3-5min |
| 重载 | 30 | 明显排队，5-8min |
| 极限 | 50 | 部分超时，需分析瓶颈 |

### 4.2 Reporter 压力测试

**目标：** 测试 DeepSeek 并发调用能力。

**方法：**
```python
CONCURRENT = [8, 16, 32, 64]
# 模拟发送 64 个并发 ReportContext（可用 mock 数据）
# 记录：
#   - LLM API 调用成功率
#   - 平均响应时间
#   - 429 限流频率
#   - 工具调用成功率
```

### 4.3 Writer → Middleman → Reporter 管道压力测试

**目标：** 测试全链条在高并发下的表现。

**方法：**
```python
# 使用真实数据（或缓存好的 fetch 数据）
# 并发提交 N 只股票到 Writer
# N = 10, 20, 30
```

---

## 第5层：Agent Prompt 测试

### 目标

验证 DeepSeek v4 Flash 是否能正确理解 prompt 并调用 get_article_body 工具。

### 测试准备

创建模板 context JSON：
```json
{
  "stock_name": "凯莱英",
  "ts_code": "002821.SZ",
  "fetch_data": "## 凯莱英 (002821.SZ)\n\n【今日11:30收盘数据】...",
  "fetch_message": "## 凯莱英 (002821.SZ)\n\n【今日快讯】...",
  "articles": {
    "sinafin": {
      "session_id": "s_test_001",
      "preview": {
        "articles": [
          {"id": "a_01", "title": "凯莱英涨停分析", "body_avail": "有",
           "snippet": "今日凯莱英强势涨停...", "date": "2026-07-28"}
        ],
        "total": 1
      }
    }
  }
}
```

### 测试场景

| 场景 | 输入 | 预期行为 |
|:-----|:-----|:---------|
| 有正文可调用 | body_avail=有的文章 | LLM 调用 get_article_body |
| 无正文可调用 | 所有 body_avail=无 | LLM 不调用工具，直接分析 |
| 信息充足不调用 | 摘要已包含足够信息 | LLM 自行决定不调用 |
| 多 engine 有正文 | 多个 engine 均有正文 | LLM 选择性调用 |
| 重复文章 | 标题相似的多篇 | LLM 按去重提示只调 1 篇 |

**目的：** 确保 prompt 中的规则被 LLM 遵守，工具定义的 schema 正确。

---

## 第6层：端到端测试

### 6.1 基础 E2E

```bash
curl -X POST http://localhost:8310/api/v1/report \
  -H "Content-Type: application/json" \
  -d '{"stock_names": ["淮北矿业", "博瑞医药", "凯莱英", "广生堂"]}'
```

**验证清单：**
- [ ] 请求成功返回（success=4）
- [ ] 4 个 output 目录各生成一个 md 文件
- [ ] md 文件内容完整（包含所有章节）
- [ ] 没有意外的 error_log 记录
- [ ] 耗时在合理范围内

### 6.2 E2E 压力测试

| 档次 | 股票数 | 预计耗时 | 关注点 |
|:----|:------:|:--------:|:-------|
| 轻载 | 4 | ~3-5min | 基础 E2E |
| 中载 | 10 | ~5-10min | 排队 + 并发 |
| 重载 | 20 | ~10-20min | 资源瓶颈 |
| 极限 | 30 | ~15-30min | 极限情况 |

**记录指标：**
```
每个档次的:
  - 总耗时
  - 成功率
  - 各阶段耗时分布
  - 错误类型统计
  - CPU/RAM 使用峰值
  - mail_tower 负载情况
  - DeepSeek API 调用统计
```

---

## 测试脚本与报告规范

### 脚本结构

每个测试脚本遵循统一结构：
```python
"""
测试说明
"""
import ...

STOCKS = ['淮北矿业', '博瑞医药', '凯莱英', '广生堂']

class TestSuite:
    def setup(self): ...
    def test_case_1(self): ...
    ...

def save_result(name, data):
    """保存原始结果到 results/"""
    ...

if __name__ == "__main__":
    suite = TestSuite()
    suite.setup()
    ...
```

### 解析脚本

每个测试目录的 `report_parser.py` 负责：
1. 读取 results/ 下的原始结果
2. 统计成功率、耗时分布
3. 生成可读的 md 报告
4. 保存到 results/ 下

### 测试流程

```
1. 写测试脚本 → test_drive/{layer}/{test_name}.py
2. 运行测试 → 生成原始结果到 results/
3. 解析结果 → report_parser.py → results/{test_name}_report.md
4. debug 修复 → 更新代码
5. 更新文档 → 如发现文档错误，同步修正
6. 重测 → 复用脚本，只改配置
```

---

## 测试环境要求

```bash
# 1. 启动 mail_tower
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300

# 2. 启动 middleman
cd /home/stockagent/project_space/research/experiments/report_machine/office
conda run -n stock_agent python -m middleman.server

# 3. 启动 reporter
conda run -n stock_agent python -m reporter.server

# 4. 启动 writer
conda run -n stock_agent python -m writer.server

# 5. 环境变量
export DEEPSEEK_API_KEY=sk-...
```

---

## 测试通过标准

| 层级 | 标准 |
|:-----|:------|
| 第1层 | 全部语法通过，模型序列化/反序列化 100% 覆盖 |
| 第2层 | 每个主体的功能用例 90%+ 通过，主要流程 100% |
| 第3层 | 通信状态组合 80%+ 通过，核心状态 100% |
| 第4层 | 轻载无失败，中载失败率<5%，重载记录瓶颈 |
| 第5层 | LLM 能正确调用 tool，prompt 规则被遵守 |
| 第6层 | 基础 E2E 成功，压力测试有完整记录 |
