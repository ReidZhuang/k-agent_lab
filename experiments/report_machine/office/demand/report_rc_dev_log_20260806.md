# report_rc 接口开发记录与停用/恢复指南 (2026-08-06)

> 本文档记录 report_rc(券商评级与盈利预测)接口的完整开发状态、2026-08-06 停用原因、
> 停用修改清单(含删除代码原文)、以及未来重启接入的全盘计划。
> **原则: 没有用户明确允许, 任何代码/脚本/cron 不得调用 report_rc 接口。**

---

## 1. 接口概览与限制(实测结论)

| 项 | 内容 |
|---|---|
| 接口 | `report_rc` 券商(卖方)每天研报的盈利预测数据, 2010 年至今, 每晚 19~22 点更新当日 |
| 试用档(2000积分) | 官方文档: **每天 10 次(自然日 0 点重置)+ 分钟级频控**; 实测: 报错出现 "10次/天" 与 "10次/小时" 两种窗口, **请求到达即计数, 失败也算** |
| ⚠️ 窗口行为实测差异 | 官方文档称"按自然日 0 点重置"; 但 2026-08-06 上午(距 8/5 最后调用未满 24h)仍报 "10次/天" 超限 → 实际疑似**自然日 + 滚动窗口叠加, 任一窗口满即拒绝**。重启时机以【单次探测】实测为准, 不依赖文档口径 |
| 正式档(8000积分) | 每天 100000 次, 10000 积分以上无总量限制(无小时/天瓶颈, 建议升级) |
| 单次上限 | 3000 条, 可分页(offset/limit)循环 |
| 全市场批量 | **已实测确认**: 不传 `ts_code`, 传 `start_date/end_date` 区间 → 一次返回全市场多股票多研报(2 周 3158 行/661 只)。**严禁按股票逐只调用**(10 次额度撑不住); `report_date` 单日也可全市场 |
| 实测 | `month` 参数无效; 多值 `ts_code` 不支持; 1次/分钟 级频控(密集调用触发) |
| 表 | `stg_report_rc`, 累积型(IF NOT EXISTS 不重建), 唯一键 `UNIQUE(ts_code, report_date, org_name, quarter)` 幂等 |

---

## 2. 停用前已完成的开发(恢复后直接可用)

- **ETL**: `etl/etl_report_rc.py` — 增量(断点续传 MAX(report_date))、回填(--backfill 分片)、幂等
- **报告侧**: `data_fetch/endday/fetch_endday_data.py::fetch_report_rc` — 读库近 12 月统计:
  评级分布 / 目标价共识(max_price) / 分季度净利·EPS 共识 / 最新 3 份研报
- **报告节**: `## 【券商评级与盈利预测】`(endday 第 18 节), 19:30 报告用昨日入库数据(标注)
- **cron**: 原 22:00 `etl_report_rc.py`(2026-08-06 已移除, 见 4.3)

---

## 3. 停用原因与经过 (2026-08-06)

1. **8/5 测试耗尽 10次/天**: 截断点研究消耗了当日全部试用额度
2. **8/6 事故**: 单股 E2E(13:37)+ 10 只全量 E2E(13:51)运行时, `fetch_report_rc` 的
   **实时回退逻辑对每只股票无脑重试**(单股 1 次 + 全量 10 次), 加上手动探测 5 次,
   合计 16 次请求全部落在小时窗口内。**失败请求也按到达计数**, 把 10次/小时 窗口打满,
   且 `10次/天` 也被消耗 → 用户试用额度实际被烧光。
3. **用户指示(2026-08-06)**: 全面停用该接口; 没有用户允许不得调用; **回退逻辑删除(不需要回退)**;
   做好记录, 未来数据恢复后再改回来。

**教训**: 有硬频控的接口, 代码中任何"自动重试/回退"路径都必须先做额度预算与失败冷却,
绝不能依赖异常来终止。

---

## 4. 停用修改清单(逐文件, 含恢复方法)

### 4.1 `etl/etl_report_rc.py` — 加禁用保护(代码未删, 屏蔽)

- **位置**: 文件头部 docstring 之后、`import tushare` 之前
- **内容**:
```python
# ════════════════════════════════════════════════════════════════
# 停用保护(2026-08-06, 用户指示): 任何入口直接退出, 不触碰 report_rc 接口
# 恢复时删除本块即可(读库/写库逻辑均保留, 仅接口调用被屏蔽)
DISABLED = True
if DISABLED:
    print("etl_report_rc 已停用: report_rc 接口接入暂缓(用户指示 2026-08-06)。"
          "详见 office/demand/report_rc_dev_log_20260806.md")
    sys.exit(0)
# ════════════════════════════════════════════════════════════════
```
- **效果**: 任何入口(含 cron/手动)直接打印提示并 exit(0), 不触碰接口
- **保留**: 下方全部 ETL 逻辑(增量/回填/分片/写库)未动
- **恢复**: 删除 DISABLED 保护块(约 9 行), 脚本立即恢复可用

### 4.2 `data_fetch/endday/fetch_endday_data.py` — 删除实时回退(代码已删, 见附录 A)

- **修改 1**: `fetch_report_rc` 函数中的实时回退整段**已删除**(库空 → 直接 error 提示, 不调用接口)
- **修改 2**: 新增模块级常量(函数前):
```python
_REPORT_RC_DISABLED_MSG = "评级数据缺失(报告侧不实时拉取): 等待 ETL 回填/增量入库"
```
- **保留**: 读库 + 统计逻辑完整(库有数据时正常输出)
- **恢复**: 用户已明确**不需要回退**, 建议永久不回退(库空就显示提示)。
  如未来确实需要回退功能, 用附录 A 的原文恢复(注意必须加失败冷却, 见 §5.4)

### 4.3 crontab — 移除 22:00 调度

- **删除行**(原文):
```
0 22 * * * /bin/bash /home/stockagent/project_space/research/experiments/report_machine/etl/run_if_trading_day.sh etl_report_rc.py && /bin/bash /home/stockagent/project_space/research/experiments/report_machine/etl/run_if_trading_day.sh etl_block_trade.py
```
- **现状**: 22:00 只剩 `etl_block_trade.py`
- **恢复**: 数据恢复且用户允许后, 将 `etl_report_rc.py` 加回同一 cron 行(在 etl_block_trade.py 之前)
  - 注意: `run_if_trading_day.sh etl_report_rc.py` 会自动把日志写到 `etl/logs/etl_report_rc.log`

### 4.4 探测脚本(临时文件, 随会话清理)

- `/home/stockagent/.claude/jobs/e231042d/tmp/probe_reportrc.py`(61 分钟间隔自动探测, **未运行过**)
- 恢复探测时按 §5.2 步骤 1 手写即可, 不需要恢复该文件

### 4.5 主 checkout 同步状态

- `etl/etl_report_rc.py`(禁用版)、`data_fetch/endday/fetch_endday_data.py`(无回退版)
  需同步到主 checkout(报告链路运行主 checkout 代码)

---

## 5. 未来重启计划

### 5.1 前置条件(两个都要满足)

1. **用户明确允许**(口头/消息授权)
2. **额度可用**, 满足其一:
   - 试用档额度确认恢复(单次探测成功, 见 5.2-1), 或
   - 升级正式权限(8000 积分: 每天 100000 次, 无小时/天瓶颈, **推荐**——10次/天 的回填与增量永远够用)

### 5.2 重启步骤(建议顺序, 每步都先与用户确认)

1. **单次探测**(1 次调用, 唯一权威的额度判断): 拉近 6 个月全市场
   (`start_date=20260206, end_date=今天`, 不传 ts_code)
   - 成功 → 记录: 返回行数 / 日期覆盖 / 是否 3000 截断 → 进入步骤 2
   - 失败(频限) → 说明窗口未开(自然日/滚动叠加), 等用户决定再试时机, **不自动重试**
2. **定分片**: 若截断 → 日均行数 = 总行数/报告日数, 分片天数 = 3000/日均 × 0.7(安全系数),
   得到每片天数与总调用次数
3. **回填近 6 个月**: 每天 ≤ 8 次调用(留 2 次余量给增量/重试), 分 2 天
   - 命令: `python etl_report_rc.py --backfill 20260206 <今天> --slice-days <分片天数>`
   - 片间间隔 ≥ 61s(分钟级频控); 幂等: INSERT OR IGNORE, 中断可重跑
4. **恢复 22:00 cron 增量**: 加回 §4.3 的 cron 行(每天 1 次, 全市场当天 ≈1200-1600 行 < 3000, 一次拉全)
5. **删除 etl_report_rc.py 的 DISABLED 保护**(§4.1)
6. **验证**:
   - 报告评级节出现真实数据(读库路径)
   - 次日 22:00 增量自动入库(查 `stg_report_rc` 行数与最新 report_date)
   - 连续 3 天增量正常后, 接入视为稳定

### 5.3 停用期报告表现(现状)

- 评级节显示: `❌ 券商评级: 评级数据缺失(报告侧不实时拉取): 等待 ETL 回填/增量入库`
- 其余 18 节不受影响; 报告完整性 warning 会提示"券商评级"缺失(non_critical)

### 5.4 若恢复回退功能(不推荐, 用户已否定)

必须同时满足:
- 模块级失败冷却 ≥ 1 小时(失败后整批跳过)
- 每天回退总调用预算 ≤ 3 次(超出直接放弃)
- 回退成功数据写回 `stg_report_rc`(幂等), 避免重复消耗

---

## 附录 A: fetch_report_rc 已删除的实时回退代码(完整原文, 恢复参考)

> 以下为 2026-08-06 从 `data_fetch/endday/fetch_endday_data.py::fetch_report_rc` 删除的
> 实时回退整段(原位于"读库为空"分支内, 现在该分支直接 `continue`)。恢复时替换为:
> 库空 → 执行此段 → 继续统计。

```python
                # 实时回退: 单股拉取 + 写回库
                df = PRO.report_rc(ts_code=tc, start_date=start, end_date=end)
                if df is None or df.empty:
                    info["error"] = "库空且实时拉取无数据"
                    result[tc] = info
                    continue
                rows2 = [(
                    r["ts_code"], r.get("name", ""), r["report_date"],
                    r.get("report_title", ""), r.get("report_type", ""), r.get("classify", ""),
                    r["org_name"], r.get("author_name", ""), r["quarter"],
                    r.get("op_rt"), r.get("op_pr"), r.get("tp"), r.get("np"),
                    r.get("eps"), r.get("pe"), r.get("rd"), r.get("roe"), r.get("ev_ebitda"),
                    r.get("rating", ""), r.get("max_price"), r.get("min_price"),
                    r.get("imp_dg", ""), r.get("create_time", ""),
                ) for _, r in df.iterrows()]
                db.insert_batch("stg_report_rc",
                    ["ts_code", "name", "report_date", "report_title", "report_type",
                     "classify", "org_name", "author_name", "quarter",
                     "op_rt", "op_pr", "tp", "np", "eps", "pe", "rd", "roe", "ev_ebitda",
                     "rating", "max_price", "min_price", "imp_dg", "create_time"],
                    rows2, ignore=True)
                log_error(function="fetch_report_rc", level="WARNING", ts_code=tc,
                          api_name="report_rc_db_fallback",
                          error_msg=f"库空, 已实时回退并写回 {len(rows2)} 行")
                rows = [(r["ts_code"], r.get("name", ""), r["report_date"], r.get("report_title", ""),
                         r["org_name"], r["quarter"], r.get("np"), r.get("eps"),
                         r.get("rating", ""), r.get("max_price"), r.get("min_price"))
                        for r in df.to_dict("records")]
```
