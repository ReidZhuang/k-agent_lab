# THS 板块内个股涨幅排名服务 — 接口文档

独立 FastAPI 服务，端口 **8324**。on-demand 按需取数：本地数据库为主，缺的数据（并列时间、主力资金）按需调接口，不预计算全市场板块。

代码位置：`experiments/report_machine/sector_rank/server/`

## 启停

```bash
./sector_rank_server.sh start|stop|restart|status
# 日志: log/sector_rank_server.log
```

## 接口

### 1. GET /health

```bash
curl http://127.0.0.1:8324/health
# {"status":"ok","port":8324,"db":"/home/stockagent/project_space/database/report_market.db"}
```

### 2. GET /api/sector/search?name=白酒

板块名模糊搜索，多结果供调用方选择（重名板块常见）。

```bash
curl -G "http://127.0.0.1:8324/api/sector/search" --data-urlencode "name=白酒"
```

```json
{"total": 3, "items": [
  {"ts_code": "881273.TI", "name": "白酒", "member_count": 19},
  {"ts_code": "884188.TI", "name": "白酒Ⅲ", "member_count": 19},
  {"ts_code": "885525.TI", "name": "白酒概念", "member_count": 48}
]}
```

### 3. GET /api/sector/rank?ts_code=885525.TI&top=20

板块内涨幅排名（推荐用 `ts_code`；`name` 精确匹配可用，重名返回 300 + 候选列表）。

```bash
curl "http://127.0.0.1:8324/api/sector/rank?ts_code=885525.TI"
```

```json
{
  "trade_date": "20260814",
  "sector": {"ts_code": "885525.TI", "name": "白酒概念", "member_count": 48},
  "data_time": "2026-08-14 18:09:04",
  "member_with_snapshot": 48,
  "tie_handled": 5,
  "stocks": [
    {
      "rank": 1,
      "ts_code": "601579.SH",
      "name": "会稽山",
      "chg_pct": 7.05,
      "is_limit_up": false,
      "main_inflow_wan": -2639.08,
      "main_inflow_pct": -2.44,
      "amount_wan": 108155.0,
      "turnover_rate": 8.5
    }
  ]
}
```

参数：`ts_code`（板块代码）/ `name`（板块名精确）/ `top`（默认 20，1~50）。

## 排序规则（三级）

1. **涨幅**（`chg_pct`）降序
2. 涨幅**并列**时：**谁先涨到这个涨幅值，谁排在前面**（内部按"先到达时间"排序，不对外展示）。并列组内有涨停股时触发拉分时计算（涨停 10% 并列最常见）；无涨停股的并列罕见，直接落第 3 级
3. 仍并列：**成交额**（`amount_wan`）降序

取前 `top` 名（默认 20）。

## 字段说明

| 字段 | 来源 | 口径 |
|---|---|---|
| `chg_pct` | 本地快照 `stg_tencent_snapshot` | 当日涨跌幅 % |
| `amount_wan` / `turnover_rate` | 本地快照 | 成交额(万元) / 换手率 % |
| `is_limit_up` | 快照 `price ≈ limit_up` | 是否涨停（limit_up>0 排除退市股占位） |
| `main_inflow_wan` | pysnowball `capital_flow`（雪球） | 当日资金净额（主力口径，万元），末条累计值 |
| `main_inflow_pct` | 自算 | 资金净额 ÷ 当日成交额 × 100（净占比 %） |

## 数据日期说明

- `trade_date` / `data_time` = 最新快照批次（盘中每 30 分钟一次快照自动用最新）
- 盘前/非交易日调用 → 返回最近交易日数据，字段如实标注
- 涨停时间/主力资金接口同样返回最近交易日数据（与快照一致）

## 已知行为

- 板块成分股在快照中缺失则跳过（正常全市场覆盖，不会发生）
- 单只资金流/分时接口失败 → 对应资金/时间字段不影响排名（失败股按成交额兜底），不阻塞整体返回
- 雪球 token 失效时自动刷新（复用 fetcher 的 `snowball_token/refresh_token.py` 机制）
- 响应耗时：概念板块（几十只）~1.5s；全市场超大板块（3000+ 成分）并列涨停组多时 ~5s
