# Agent 三层架构设计

## 1. 总体架构

```
User Query (NL)
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  STEP 1: agent_guide (Query Parser)                      │
│  单一 LLM 调用，将 NL query → 结构化 request 列表        │
│  输出: {"query_id": "Q_xxx", "requests": [{...}, ...]}   │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  STEP 2: Pipeline Orchestrator                           │
│  将 requests 列表通过 Semaphore(4) 并发调度              │
│  每个 request 走: agent_router → agent_coder 的顺序      │
│  (router 和 coder 共享 4 个并发 LLM 槽位)                │
└──────────────────────┬───────────────────────────────────┘
                       │
           ┌───────────┼───────────┐            (并发，max 4 slots)
           ▼           ▼           ▼
      ┌─────────┐ ┌─────────┐ ┌─────────┐
      │ req #1  │ │ req #2  │ │ req #N  │
      │ router  │ │ router  │ │ router  │
      │ → coder │ │ → coder │ │ → coder │
      └────┬────┘ └────┬────┘ └────┬────┘
           │           │           │
           ▼           ▼           ▼
┌──────────────────────────────────────────────────────────┐
│  STEP 3: Result Merger                                   │
│  按 query_id 汇集所有 request 的结果                     │
│  当 collected == total 时，输出完整结果                   │
└──────────────────────────────────────────────────────────┘
                       │
                       ▼
                Final Answer (JSON)
```

## 2. 核心数据结构

### 2.1 Query Request（agent_guide 输出）

```python
{
    "query_id": "Q_a1b2c3d4",        # 一次用户查询的唯一 ID
    "requests": [
        {
            "req_id": "R_001",        # 请求内唯一
            "obj": ["宁德时代"],       # 取数对象列表（可多个主体合并）
            "var": "最高价",           # 取数指标（单一值）
            "condition": ["今天"]      # 条件列表
        },
        {
            "req_id": "R_002",
            "obj": ["宁德时代"],
            "var": "最低价",
            "condition": ["今天"]
        }
    ]
}
```

### 2.2 Route Result（agent_router 输出）

```python
{
    "req_id": "R_001",
    "query_id": "Q_a1b2c3d4",
    "field_id": "FIELD_QUOTE_HIGH",
    "field_name": "最高价",
    "datasource_id": "DS_TUSHARE_DAILY",
    "datasource_name": "Tushare日线",
    "protocol": "tushare",
    "api_column": "high",
    "entity_type": "stock_code",
    "entity_value": "300750.SZ",
    "time_start": "20260715",
    "time_end": "20260715",
    "condition_text": "股票: 300750.SZ\n  指标: high\n  时间范围: 20260715 ~ 20260715",
}
```

### 2.3 CodeGen Result（agent_coder 输出）

```python
{
    "req_id": "R_001",
    "query_id": "Q_a1b2c3d4",
    "success": True,
    "result": [31.5],          # _result 列表值
    "output": "...",
    "field_id": "FIELD_QUOTE_HIGH",
    "var": "最高价",
    "obj": ["宁德时代"],
}
```

## 3. 组件详细设计

### 3.1 agent_guide（新建）

**目录结构：**
```
agent_guide/
├── SOUL.md          — 角色定义：NL query 解析专家
├── AGENTS.md        — 工作流程：语义拆分原则、示例
├── PREFERENCES.md   — 解析偏好：合并/拆分规则
└── skills/
    └── parser_expert/
        └── SKILL.md — 解析专业知识
```

**核心任务：** 读取自然语言 query，输出结构化 request 列表

**输出格式控制：** 通过 prompt 示例 + 约束描述让 LLM 输出固定格式的 JSON。

**关键规则（来自用户需求总结）：**
1. 每个指标（var）不同 → 独立 request
2. 每个无交织的条件组合 → 独立 request（如"今天收盘和上周收盘的换手率"→ 2 个 request）
3. 相同 var + 相同 condition 的主体尽量合并到一个 request
4. obj 的范围限制 → 放到 condition 中，obj 保留朴素主体
5. 默认条件：无时间条件时默认"当天/最近一个交易日"

**难点与应对策略：**
- LLM 可能输出不规范的 JSON → prompt 中给严格的格式约束 + 示例
- 可能错误拆分 → prompt 中强化"无交织"的判断逻辑
- 本地 LLM 可能输出格式跑偏 → 需要多轮 prompt engineering 测试

### 3.2 agent_router（改造）

**当前状态（experiment.py）：**
- 单 agent 直接处理 NL query
- 通过 tool_calls 自迭代路由
- 集成了 query 解析 + 路由 + 取数引导

**改造为：**
- 输入不再是 NL query，而是 agent_guide 输出的单个 request dict
- 输出确定的路由结果：field_id + datasource + 条件格式化
- 不再需要自迭代路由的复杂性（因为 var 是明确的关键词）
- 但仍需处理：obj 类型识别（stock_code / sector_name / index_code）、条件形式化

**简化后的路由流程：**
```
输入 request: {obj, var, condition}
1. 识别 obj 类型：股票? 板块? 指数?
2. 从 condition 提取时间范围
3. 用 var 作为关键词 route_query
4. 输出确定的 RouteResult
```

### 3.3 agent_coder（改造）

**当前状态（experiment_codegen.py）：**
- 给定 field_id + 实体信息 → 生成代码 → 编译→执行→重试

**改造需要：**
- 接收结构化的 route result，而不是单独的参数
- 输出标准化的 CodeGenResult
- 保持现有的 codegen loop（编译检查 + 执行 + 重试）

### 3.4 Pipeline Orchestrator（新建）

```
pipeline.py
├── class PipelineOrchestrator
│   ├── __init__()          — 初始化 semaphore(4)、agent 目录等
│   ├── run(query)          — 入口：执行完整流程
│   ├── _parse_query()      — 调用 agent_guide
│   ├── _fan_out()          — 并发调度 requests
│   ├── _route_request()    — 调用 agent_router（acquire semaphore）
│   ├── _codegen_request()  — 调用 agent_coder（acquire semaphore）
│   └── _merge_results()    — 按 query_id 合并
```

**并发控制：**
```python
_llm_semaphore = asyncio.Semaphore(4)
# 每个 LLM 调用前 acquire()，完成后 release()
# 适用场景：agent_guide / agent_router / agent_coder 都走同一个 semaphore
```

但注意：由于我们用的是同步的 OpenAI SDK（requests 调用 ollama），asyncio 不太适用。可以用 `concurrent.futures.ThreadPoolExecutor` + `threading.Semaphore` 实现。

或者更简单的：用 `queue.Queue` + 工作线程池。

实际上，考虑到本地 LLM 调用是同步的，最简单的并发模型是：
1. 用 `ThreadPoolExecutor(max_workers=4)` 作为全局线程池
2. 每个 LLM 调用 submit 到线程池
3. 所有三个 agent 共享这 4 个线程

但每个 request 内部 router → coder 是串行的（coder 依赖 router 的输出）。所以：
- 对 N 个 requests，每个都 submit 一个 pipeline 任务到线程池
- 每个 pipeline 任务内部：router(LLM) → coder(LLM)，串行
- 线程池大小 = 4，所以最多 4 个 pipeline 同时运行

这样设计更清晰，一个 request 占一个线程，线程池限制并发。

```
ThreadPoolExecutor(max_workers=4)
  ├─ Thread 1: req_1 → agent_router → agent_coder
  ├─ Thread 2: req_2 → agent_router → agent_coder
  ├─ Thread 3: req_3 → agent_router → agent_coder
  └─ Thread 4: req_4 → agent_router → agent_coder
```

如果有 N > 4 个 requests，多余的排队等待。

**结果收集：**
- 用一个 thread-safe 的 dict 存储中间结果
- 每个 request 完成后写入结果
- 主线程等待所有 request 完成

## 4. 数据流追踪

```
query_id: Q_a1b2        req_id: R_001        req_id: R_002
                                        
agent_guide────► [R_001, R_002]              
                    │                           
R_001 ─────────────► router ──► coder ──► {result}  
R_002 ─────────────► router ──► coder ──► {result}  
                                              │
                                         merger
                                              │
                                        Final Output
```

## 5. 开发步骤

### Phase 1: agent_guide 开发与测试
1. 创建 agent_guide/ 目录 + prompt 文件
2. 编写独立的测试脚本 `test_agent_guide.py`
3. 用多个测试 query 反复调优 prompt
4. 测试覆盖：简单 query / 多指标 / 多主体 / 多条件 / 复杂绕法

### Phase 2: agent_router 改造与测试
1. 从现有 agent_router prompt 中剥离 query 解析部分
2. 改造为接受结构化 request dict 输入
3. 编写独立测试脚本 `test_agent_router.py`
4. 测试覆盖：各协议 / 各实体类型

### Phase 3: agent_coder 改造与测试
1. 改造为接受结构化 route result
2. 保持现有 codegen loop 不变
3. 测试覆盖：各协议代码生成

### Phase 4: Pipeline Orchestrator 开发
1. 实现 pipeline.py
2. 集成三个 agent
3. 实现并发控制 + 结果合并

### Phase 5: 端到端测试
1. 完整流程测试
2. 错误处理测试

## 6. 测试计划

### agent_guide 测试用例
```
1. "宁德时代今天的涨跌幅"
   → [{"obj":["宁德时代"], "var":"涨跌幅", "condition":["今天"]}]

2. "宁德时代今天的最高价和最低价"
   → [{"obj":["宁德时代"], "var":"最高价", "condition":["今天"]},
      {"obj":["宁德时代"], "var":"最低价", "condition":["今天"]}]

3. "宁德时代所在的版块今天的涨跌幅"
   → [{"obj":["版块"], "var":"涨跌幅", "condition":["今天","宁德时代所在的板块"]}]

4. "我想知道比亚迪和宁德时代今天中午收盘的股价"
   → [{"obj":["宁德时代","比亚迪"], "var":"股价", "condition":["今天中午收盘"]}]

5. "给我查一下宁德时代在今天收盘和上周收盘的换手率"
   → [{"obj":["宁德时代"], "var":"换手率", "condition":["今天收盘"]},
      {"obj":["宁德时代"], "var":"换手率", "condition":["一周前收盘"]}]

6. "查一下上证指数今天的涨跌幅和成交量"
   → [{"obj":["上证指数"], "var":"涨跌幅", "condition":["今天"]},
      {"obj":["上证指数"], "var":"成交量", "condition":["今天"]}]

7. "茅台和五粮液今天的股价谁高？"
   → [{"obj":["茅台","五粮液"], "var":"股价", "condition":["今天"]}]

8. "最近一个月北向资金流向"
   → [{"obj":["北向资金"], "var":"资金流向", "condition":["最近一个月"]}]
```

### agent_router 测试用例
针对每个 request dict，验证能否正确路由到对应的 field

### agent_coder 测试用例
针对每个 field 验证代码生成+执行成功
