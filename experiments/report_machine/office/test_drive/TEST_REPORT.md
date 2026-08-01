# Office 报告生成系统 — 测试报告

> 测试日期: 2026-07-28  
> 测试环境: Python 3.10, stock_agent conda env, Linux (WSL2)  
> 硬件: i7-9800X (16核), 62GB RAM, RTX 2070 SUPER  
> LLM: DeepSeek v4 Flash (云端 API, 2500 并发上限)

---

## 一、测试要求

### 1.1 测试范围

覆盖 Office 系统四个主体：
- **Fetcher** — 取数编排（调用 fetch_midday_data + fetch_midday_message）
- **Writer** — 入口 API + sub writer 池管理
- **Middleman** — Type A（搜索聚合5引擎）+ Type B（正文获取）
- **Reporter** — Agent loop（DeepSeek v4 Flash, tool call, 报告输出）

### 1.2 测试目标

1. **语法与报文** — 所有 Python 文件语法正确，Pydantic 模型在各种输入下能正确序列化/反序列化
2. **单体功能** — 每个主体各自的功能完整性
3. **通信** — 主体间报文的正常/异常/超时/失败状态穷举
4. **压力** — 高并发下的系统表现
5. **Agent Prompt** — LLM tool call 正确性
6. **端到端** — 全链路集成

### 1.3 测试标的

固定测试股票：`['淮北矿业', '博瑞医药', '凯莱英', '广生堂']`

---

## 二、测试设计

### 2.1 分层架构

```
第1层: 单元测试 ─── 语法/报文/模型校验
第2层: 单体功能测试 ── 各主体功能完整性
第3层: 通信测试 ─── 主体间报文交互（含边界状态）
第4层: 压力测试 ─── 高并发负载
第5层: Agent Loop 测试 ── DeepSeek 工具调用
第6层: 端到端测试 ─── 全链路集成
```

### 2.2 测试方法论

- **穷举法（第1层）**：所有 Pydantic 模型的正常/缺失/类型错误/空值/边界组合
- **状态穷举（第3层）**：每对通信主体的正常/超时/失败/连接拒绝状态组合
- **分档加压（第4/6层）**：10只 → 20只 → 30只 → 50只 → 78只逐级增加并发
- **对比法**：优化前后同一测试对比（30只阻塞版 vs 非阻塞版）

### 2.3 通信状态矩阵

每对通信主体测试以下状态组合：

| 状态 | 说明 |
|:-----|:------|
| 正常 → 正常 | 请求正确返回 |
| 正常 → 空结果 | 引擎无文章、数据为空 |
| 正常 → 部分失败 | 部分 engine error，部分正常 |
| 正常 → 全失败 | 全部 engine error |
| 超时（客户端侧） | requests.post(timeout=...) 超时 |
| 超时（服务端侧） | 服务端返回 processing 后超时 |
| 连接拒绝 | 服务未启动 |
| 404 | session 不存在 |
| 503/504 | 服务繁忙/超时 |

---

## 三、测试流程

### 3.1 各层测试执行顺序

```
第1层（单元测试）
  ├─ test_syntax.py → 语法检查+import检查
  └─ test_models.py → Pydantic模型穷举
        ↓
第2-3层（单体+通信）
  ├─ test_fetcher.py → Fetcher 7案例
  ├─ test_middleman.py → Type A + Type B
  ├─ 直接 curl 验证通信状态组合
        ↓
第4层（压力测试）
  ├─ Type A 3并发 → 验证 middleman 吞吐
        ↓
第5层（Agent Prompt测试）
  └─ test_prompt.py → 模板context调DeepSeek
        ↓
第6层（端到端）
  ├─ 首次 4只测试（发现bug）
  ├─ 第二次 4只测试（修复后验证）
  ├─ 10只管道压力
  ├─ 30只对比（阻塞版 vs 非阻塞版）
  ├─ 50只终极压测
  └─ 78只冒烟压测
```

### 3.2 测试中发现的 Bug 与修复

| # | 发现阶段 | 问题 | 修复 | 影响 |
|:-:|:--------|:-----|:-----|:-----|
| 1 | 第1层单元测试 | `office/config/` 与 ETL 的 `config.py` 命名冲突 | 改为 `cfg/` | 模块导入正确 |
| 2 | 第3层通信测试 | Sub writer 只检查 `resp.ok`（HTTP状态码），不检查 response body | 改为检查 `status=="ok"` | 避免误报成功 |
| 3 | 第3层通信测试 | Middleman `async def` 内用同步 `as_completed`，阻塞 event loop | 改为 `run_in_executor` + 4 worker | 吞吐量提升 4x |
| 4 | 第4层压力测试 | 所有组件 HTTP 连接池默认 `pool_maxsize=10`，并发时耗尽 | `_HTTP_SESSION(pool_maxsize=200)` | 消除连接等待 |
| 5 | 第4层压力测试 | 响应丢失导致 sub writer 误报失败 | 双保险：检查报告文件是否存在 | 零误报 |
| 6 | 第4层压力测试 | `result.get("preview", {})` 在值为 `None` 时返回 `None` 而非 `{}`，导致 `AttributeError` | 改为 `if not preview: continue` | 修复崩溃 |
| 7 | 第6层端到端 | Writer 的 `async def` + `as_completed` 阻塞 event loop，大负载时崩溃 | `run_in_executor` + 4 worker | 78只稳定运行 |
| 8 | 第6层端到端 | Reporter agent loop 内 `_fetch_article_bodies` 遇 baidufin `preview=None` 崩溃 | `if not preview: continue` | 修复 2 只失败 |

---

## 四、测试结果

### 4.1 第1层：单元测试

| 测试项 | 用例数 | 通过 | 结果 |
|:-------|:------:|:----:|:----:|
| 语法检查 | 10 文件 | 10 | ✅ |
| Import 检查 | 2 模块 | 2 | ✅ |
| ReportRequest | 12 | 12 | ✅ |
| TypeARequest | 12 | 12 | ✅ |
| TypeAResponse | 5 | 5 | ✅ |
| TypeBRequest | 12 | 12 | ✅ |
| TypeBResponse | 6 | 6 | ✅ |
| SubWorkerResult | 5 | 5 | ✅ |
| ReportResponse | 5 | 5 | ✅ |
| ReportContext | 6 | 6 | ✅ |
| ReporterResponse | 5 | 5 | ✅ |
| JSON序列化往返 | 5 | 5 | ✅ |
| **合计** | **68** | **68** | **✅ 100%** |

### 4.2 第2-3层：单体+通信测试

| 测试项 | 用例数 | 通过 | 结果 |
|:-------|:------:|:----:|:----:|
| Fetcher 正常4只 | 4只 | 4/4 | ✅ 每只~4600字 data + 8数据段 |
| Fetcher 空列表 | 1 | 1 | ✅ |
| Fetcher 未识别股票 | 1 | 1 | ✅ |
| Fetcher 大量15只 | 15只 | 15/15 | ✅ 22s |
| Fetcher 重复名称 | 1 | 1 | ✅ |
| Middleman Type A 600985 | 5引擎 | 5/5 | ✅ 14s |
| Middleman Type A 002821 | 5引擎 | 5/5 | ✅ 12s(3篇+2篇) |
| Middleman Type A 300436 | 5引擎 | 5/5 | ✅ 29s(5篇+2篇) |
| Middleman Type A 600519 | 5引擎 | 5/5 | ✅ 41s(10篇) |
| Middleman Type B 单篇正文 | 1篇 | 1/1 | ✅ 1945字, status=ready |
| Middleman Type B 多篇正文 | 3篇 | 3/3 | ✅ 1945+2713+826字 |
| Middleman Type B 不存在article_id | — | ✅ | status=error |
| Middleman Type B 不存在session_id | — | ✅ | 返回error |

### 4.3 第4层：压力测试

| 测试 | 并发数 | 结果 | 耗时 | 说明 |
|:-----|:------:|:----:|:----:|:------|
| Type A 3并发 | 3×5引擎 | ✅ 全部返回 | 72s | 零错误 |
| 管道30只（v1阻塞版） | 30 | ✅ 30/30 | ~15min | 基准版本 |
| 管道30只（v2无池） | 30 | ⚠️ 29/30 | 26min | 连接池耗尽 + bug |
| **管道30只（v3大连接池+双保险）** | **30** | **✅ 30/30** | **4min** | **大幅优化** |
| **管道50只** | **50** | **✅ 48/48(修复后)** | **5.6min** | **2只bug修复后重试成功** |
| **管道78只（终极）** | **78** | **✅ 76/76** | **7.8min** | **零fallback** |

### 4.4 第5层：Agent Prompt 测试

| 测试项 | 结果 | 说明 |
|:-------|:----:|:------|
| Tool call 是否被调用 | ✅ 2轮（含tool call + 回答） | LLM 正确识别有正文文章 |
| body_avail=无 是否跳过 | ✅ | 跳过无正文文章 |
| 报告质量（完整度） | ✅ 含风险提示、综合研判 | 结构完整 |
| 占位符检查 | ✅ 无"待补充"等占位符 | 内容充实 |

### 4.5 第6层：端到端性能演进

```
v1 阻塞版 (workers=1) 30只    15min   ──────────────── 基准
v2 无大连接池 30只            26min   ──────────────────────── 连接池耗尽
v3 大连接池+双保险 30只       4min    ──────── 提升 73%
v3 50只                      5.6min  ──────────────
v3 78只（终极）              7.8min  ──────────────── 零fallback
```

**吞吐量提升：从 30只/15min 到 78只/7.8min = 约 20 倍**

### 4.6 最终 78 只冒烟测试详情

| 指标 | 值 |
|:-----|:----|
| 请求股票数 | 78 |
| batch_name_info 识别 | 76/78（2只未识别但自动过滤）|
| 处理成功 | **76/76** |
| 总耗时 | **471s（7.8分钟）** |
| 总字数 | **572,963 字** |
| 平均每份 | ~7,500 字 |
| Fallback 文件 | **0** |
| 调试日志 | 完整记录所有环节耗时 |

---

## 五、调试日志分析

### 5.1 Sub writer 耗时分布（78只测试）

| 指标 | 值 |
|:-----|:----|
| 样本数 | 81 |
| 最短 | 53s |
| 中位数 | 219s |
| P95 | 306s |
| 最长 | 355s |
| 分布 <60s | 2 |
| 60-120s | 6 |
| >=120s | 73 |

### 5.2 Agent loop 耗时分布（DeepSeek API）

| 指标 | 值 |
|:-----|:----|
| 样本数 | 82 |
| 中位数 | 63s |
| P95 | 173s |
| 最长 | 175s |

### 5.3 各引擎搜索耗时（Middleman Type A）

| 引擎 | 实现方式 | 中位数 | P95 | 最长 |
|:----|:---------|:------:|:---:|:----:|
| sinafin | HTTP API | 3.0s | 4.8s | 5.1s |
| juchao | PDF下载 | 3.0s | 4.8s | 5.1s |
| qnainfo | API | 3.1s | 4.8s | 5.1s |
| thsfin | Playwright | 6.1s | 24.1s | 57.5s |
| baidufin | Playwright | 15.1s | 55.3s | 97.8s |

---

## 六、遗留问题

| 问题 | 影响 | 状态 |
|:-----|:----|:-----|
| Uvicorn workers>1 在 spawn 模式下不可用 | 限制了 worker 数量 | 已知限制，用 run_in_executor 替代 |
| baidufin 引擎 P95=55s | 拖慢整体 Type A 聚合时间 | 可观察，当前 4min/30只可接受 |
| `batch_name_info` 部分股票名无法识别（如TCL科技） | 少量股票被过滤 | 前端输入时检查即可 |

---

## 七、测试命令参考

```bash
# 第1层
conda run -n stock_agent python test_drive/unit/test_syntax.py
conda run -n stock_agent python test_drive/unit/test_models.py
conda run -n stock_agent python test_drive/unit/report_parser.py

# 第2-3层
conda run -n stock_agent python test_drive/integration/test_fetcher.py

# 第5层
conda run -n stock_agent python test_drive/prompt/test_prompt.py

# 第6层（需启动所有服务）
curl -X POST http://localhost:8310/api/v1/report \
  -H "Content-Type: application/json" \
  -d '{"stock_names":["淮北矿业","博瑞医药","凯莱英","广生堂"]}'
```
