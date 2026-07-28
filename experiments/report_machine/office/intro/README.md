# Office 报告生成系统

## 概述

Office 是一个自动化的午间报告生成系统。它从多个数据源获取股票盘中数据和新闻资讯，通过 DeepSeek v4 Flash 大模型生成结构化的分析报告。

## 架构

```
┌──────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
│  Fetcher │───▶│  Writer  │───▶│  Reporter  │───▶│ output/  │
│ (函数)   │    │ (FastAPI) │    │ (FastAPI)  │    │ (.md)    │
└──────────┘    └────┬─────┘    └──────┬─────┘    └──────────┘
                     │                 │
              ┌──────▼──────┐   ┌──────▼──────┐
              │  Middleman  │   │  Middleman  │
              │  Type A     │   │  Type B     │
              │  (/search)  │   │  (/article) │
              └──────┬──────┘   └──────┬──────┘
                     │                 │
              ┌──────▼──────┐   ┌──────▼──────┐
              │  mail_tower │   │  mail_tower │
              │  5 engines  │   │  /article   │
              └─────────────┘   └─────────────┘
```

## 组件

| 组件 | 端口 | 说明 |
|:----|:----:|:-----|
| Writer | 8310 | 入口 API，接收股票列表，管理 sub writer |
| Middleman | 8311 | writer ↔ mail_tower / reporter ↔ mail_tower 中间层 |
| Reporter | 8312 | 接收 context，运行 LLM agent loop，输出 md 报告 |

## 数据流

1. 客户端 POST `/api/v1/report` 到 Writer，传入股票列表
2. Writer 调用 Fetcher（函数）获取盘中数据 + 午间消息
3. Writer 为每只股票启动 Sub Writer（ThreadPoolExecutor）
4. 每个 Sub Writer 并发：解析 fetch 数据 + 调 Middleman Type A（聚合 5 engine 搜索）
5. Sub Writer 组装完整 context，POST 到 Reporter
6. Reporter 进入 Agent Loop（最多 8 轮），使用 DeepSeek v4 Flash
7. 如果 LLM 需要查看文章正文，调用 get_article_body tool → Middleman Type B
8. LLM 输出最终报告 → 保存为 output/{stock_name}/{date}_{stock_name}_midday.md

## 启动

```bash
# 1. 启动 mail_tower（依赖）
cd /home/stockagent/project_space/research/experiments/mail_tower
conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8300

# 2. 启动 middleman
cd /home/stockagent/project_space/research/experiments/report_machine/office
conda run -n stock_agent python -m middleman.server

# 3. 启动 reporter
conda run -n stock_agent python -m reporter.server

# 4. 启动 writer（入口）
conda run -n stock_agent python -m writer.server

# 5. 测试
curl -X POST http://localhost:8310/api/v1/report \
  -H "Content-Type: application/json" \
  -d '{"stock_names": ["宁德时代", "比亚迪"]}'
```

## 配置文件

`office/config/config.yaml` 包含所有组件配置。

## 依赖

- Python 3.10+
- conda 环境 `stock_agent`
- DeepSeek API key（环境变量 `DEEPSEEK_API_KEY`）

## 错误处理

参见 `intro/error_codes.md`。所有组件通过 `database.log_office_error()` 写入数据库 `error_log` 表。

## 失败兜底

Sub writer 连续 3 次联系 Reporter 失败后，context 会被保存到 `fallback/` 目录下。可使用 `retry_fallback.py` 脚本手动重试。
