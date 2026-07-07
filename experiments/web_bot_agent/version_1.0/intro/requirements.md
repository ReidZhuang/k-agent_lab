# bot_search API 需求说明书

## 1. 需求来源

```mermaid
graph LR
  subgraph Problem["痛点"]
    P1["文章太多<br/>手动读不过来"]
    P2["搜索结果是列表<br/>不是结构化情报"]
    P3["同一主题的段落<br/>散落在文章各处"]
  end

  subgraph Desire["期望"]
    D1["输入关键词<br/>→ 自动搜 + 自动读"]
    D2["输出结构化结果<br/>文章→分组→要点"]
    D3["支持两种粒度<br/>分段分组 / 整篇摘要"]
  end

  subgraph Constraint["硬约束"]
    C1["纯本地运行<br/>不依赖外部API"]
    C2["8GB VRAM显卡<br/>消费级硬件"]
    C3["国产模型优先<br/>GLM4 / DeepSeek"]
  end

  Problem -->|催生| Desire
  Desire -->|受限于| Constraint
  Constraint -->|定义边界| REQ["需求: bot_search API"]
```

**一句话需求**：输入搜索词 → 自动搜文章 → 本地 LLM 处理 → 输出 JSON，全程 8GB VRAM 硬件上跑，支持段落分组和整篇摘要两种模式。

---

## 2. 需求树

```mermaid
graph TB
  REQ["bot_search API"] --> FUNC["功能需求"]
  REQ --> NONFUNC["非功能需求"]
  REQ --> LIMIT["边界与限制"]

  FUNC --> F1["搜索（网络）"]
  FUNC --> F2["提取（正文）"]
  FUNC --> F3["LLM处理"]
  FUNC --> F4["输出（结构化JSON）"]
  FUNC --> F5["API（RESTful）"]

  F1 --> F1a["web-forager 调用<br/>DuckDuckGo 引擎"]
  F1 --> F1b["代理适配<br/>HTTP/HTTPS"]
  F1 --> F1c["结果上限控制<br/>max_results≤10"]

  F2 --> F2a["网页抓取<br/>HTTP GET + headers"]
  F2 --> F2b["正文提取<br/>trafilatura 做主"]
  F2 --> F2c["降级方案<br/>readability 兜底"]
  F2 --> F2d["段落切分<br/>双换行分割"]

  F3 --> F3a["自动分块<br/>超2000tk切分"]
  F3 --> F3b["LLM推理<br/>Ollama /api/generate"]
  F3 --> F3c["segments模式<br/>按段落分组+要点+概括+关键字"]
  F3 --> F3d["summary模式<br/>整篇摘要+相关摘要+核心要点"]
  F3 --> F3e["跨块处理<br/>LLM合并概括+硬合并要点/摘要"]

  F4 --> F4a["articles{}<br/>文章元信息+处理结果"]
  F4 --> F4b["segments{}<br/>分组要点（segments模式）"]
  F4 --> F4c["_texts{}<br/>原文+要点→块映射"]

  F5 --> F5a["POST /search<br/>发起异步任务"]
  F5 --> F5b["GET /poll<br/>轮询结果"]
  F5 --> F5c["POST /segment<br/>查分组原文"]
  F5 --> F5d["POST /point-text<br/>查要点原文（summary模式）"]
  F5 --> F5e["GET /status<br/>查概览"]
  F5 --> F5f["POST /close<br/>清理会话"]

  NONFUNC --> NF1["异步非阻塞<br/>搜索不等待"]
  NONFUNC --> NF2["确定性输出<br/>temperature=0"]
  NONFUNC --> NF3["两阶段并行<br/>提取→LLM→合并全并行"]
  NONFUNC --> NF4["会话隔离<br/>互不干扰"]
  NONFUNC --> NF5["自动过期<br/>TTL=60min"]
  NONFUNC --> NF6["容错优先<br/>部分失败不影响整体"]

  LIMIT --> L1["模型: GLM4:9b<br/>~6.3GB VRAM"]
  LIMIT --> L2["上下文: ~5k字/块<br/>实测有效窗口"]
  LIMIT --> L3["不包含Stage2/3<br/>本版本不做LLM二次合并/精炼"]
  LIMIT --> L4["无前端UI<br/>纯JSON API"]
  LIMIT --> L5["无持久化存储<br/>内存+过期"]
```

---

## 3. 数据流逻辑

```mermaid
flowchart TB
  subgraph Input["输入"]
    QUERY["搜索词 + 关键字"]
    MODE["mode: segments / summary"]
  end

  subgraph Phase1["Phase1: 并行提取+切块"]
    S["搜索 → URL列表"]
    E["并行提取正文"]
    P["超2000tk则切块"]
    CU["产出ChunkUnit池"]
  end

  subgraph Phase2["Phase2: 并行LLM推理"]
    INF["全量块并行送入Ollama"]
    SEG["segments: 分组+要点+概括"]
    SUM["summary: 客观概括+相关摘要+要点"]
  end

  subgraph Phase3["Phase3: 并行合并"]
    GP["按文章分组"]
    MS["合并各块结果"]
  end

  subgraph Output["输出"]
    A["articles{}"]
    SE["segments{} / key_points[]"]
  end

  Input --> Phase1
  Phase1 --> Phase2
  Phase2 --> Phase3
  Phase3 --> Output

  style Phase1 fill:#e3f2fd
  style Phase2 fill:#fff3e0
  style Phase3 fill:#e8f5e9
```

---

## 4. 状态与交互逻辑

```mermaid
stateDiagram-v2
  [*] --> IDLE: 服务启动

  IDLE --> PROCESSING: POST /search
  PROCESSING --> DONE: 全部处理完成
  PROCESSING --> ERROR: 搜索/LLM/提取异常

  DONE --> CLOSED: POST /close / 过期
  ERROR --> CLOSED: POST /close / 过期
  CLOSED --> [*]: 清理线程删除

  note right of PROCESSING
    耗时: summary 15~60s
          segments 30~120s
  end note
```

### 客户端交互流程

```mermaid
sequenceDiagram
  actor U as 使用者
  participant API as API
  participant SYS as 后台系统

  U->>API: POST /search {query, keyword, mode}
  API-->>U: session_id + status:"processing"
  API->>SYS: 后台线程执行

  loop 轮询（每5秒）
    U->>API: GET /poll/{session_id}
    alt 处理中
      API-->>U: status:"processing"
    else 完成
      API-->>U: status:"done" + 全量数据
    else 出错
      API-->>U: status:"error" + 错误信息
    end
  end

  opt summary模式看要点原文
    U->>API: POST /point-text {article_id, point_indices}
    API-->>U: 原文段落
  end

  opt segments模式看分组原文
    U->>API: POST /segment {article_id, segment_id}
    API-->>U: 分组原文
  end

  U->>API: POST /close/{session_id}
  API-->>U: status:"closed"
```

---

## 5. 约束与验收

### 硬件约束

```mermaid
graph LR
  subgraph Hardware["硬件边界"]
    H1["GPU: ≥6GB VRAM<br/>实测 ~6.3GB 占用"]
    H2["RAM: ≥16GB<br/>推荐 32GB"]
    H3["磁盘: ≥10GB 空闲<br/>模型文件 ~4GB"]
  end

  subgraph Model["模型边界"]
    M1["GLM4:9b-chat-q4_K_M<br/>默认模型"]
    M2["有效注意力 ~5000字<br/>实测非标称值"]
    M3["temperature=0 硬要求<br/>否则结果不可复现"]
  end

  subgraph Network["网络边界"]
    N1["需代理访问外网<br/>搜索+抓页"]
    N2["Ollama 本地通信<br/>localhost:11434"]
    N3["不依赖外部AI API<br/>纯本地推理"]
  end

  Hardware -->|决定了| M2
  M2 -->|决定了分块策略| N4["max_tokens=2000<br/>安全余量分块"]
```

### 验收标准

| # | 验收项 | 标准 | 优先级 |
|---|---|---|---|
| 1 | 搜索可用 | `POST /search` 返回 session_id | P0 |
| 2 | 轮询可用 | `GET /poll` 最终返回 done + 数据 | P0 |
| 3 | segments模式 | 每篇所有段落都被分配到某个分组 | P0 |
| 4 | summary模式 | 每篇产出 summary + summary_relevant + key_points | P0 |
| 5 | 确定性 | 同一篇正文连续调用 3 次，结果一致 | P1 |
| 6 | 长文本处理 | ≥8000 字文章不崩溃、不超时、不空输出 | P1 |
| 7 | 多块合并 | summary模式多块文章的概括合并正确 | P1 |
| 8 | 要点定位 | POST /point-text 能准确定位到原文段落 | P1 |
| 9 | 并发 | 连续两次搜索，两个 session 独立 | P1 |
| 10 | 自动过期 | 60 分钟后 session 自动 closed | P2 |
| 11 | 降级能力 | trafilatura 失败时 readability 兜底 | P2 |

### 版本边界

| 包含于本版本 | 不包含于本版本 |
|---|---|
| ✅ segments: LLM 分组（要点+概括+关键字） | ❌ Stage 2: LLM 跨块二次合并 |
| ✅ summary: LLM 整篇摘要+相关摘要+要点 | ❌ Stage 3: LLM 精炼复核 |
| ✅ 跨块 LLM 概括合并 | ❌ 前端 UI |
| ✅ 要点→原文反向定位（POST /point-text） | ❌ 数据库持久化 |
| ✅ 两阶段并行架构 | ❌ 多模型自动切换 |
| ✅ RESTful API + 会话管理 | ❌ 流式输出（stream） |
| ✅ token 估算 + 自动分块 | |

---

## 6. 关键设计决策图谱

```mermaid
flowchart TB
  Q1["问题: 长文本超过模型有效窗口?"]
  Q1 --> A1["代码层分块<br/>max_tokens=2000"]
  A1 --> Q2["块内段落编号怎么设计?"]
  Q2 --> A2["P1-Pn局部编号<br/>LLM只看一块"]
  A2 --> Q3["块间段落号怎么还原?"]
  Q3 --> A3["偏移量累加<br/>纯加法运算"]

  Q4["问题: LLM输出不稳定?"]
  Q4 --> A4["temperature=0<br/>确定性输出"]
  A4 --> Q5["LLM漏了段落怎么办?"]
  Q5 --> A5["代码补充[补充]标记<br/>不送回LLM"]

  Q6["问题: 多块分组怎么合并?"]
  Q6 --> A6["代码合并相邻重叠<br/>segments模式"]
  Q6 --> A7["LLM合并概括<br/>summary模式"]

  Q8["问题: 串行太慢?"]
  Q8 --> A8["两阶段并行<br/>提取→LLM→合并<br/>全量asyncio.gather"]

  Q9["问题: 要点想查原文?"]
  Q9 --> A9["kp_chunk_map追踪<br/>→ 单块LLM定位<br/>→ 返回原文"]
```

---

**原则总结**：LLM 只做语义判断，数字运算和流程编排由代码完成。所有 LLM 调用并行化，按两阶段组织。
