"""
ETL: 券商评级与盈利预测(stg_report_rc, 接口 report_rc)

⚠️ 2026-08-06 起【全面停用】(用户指示): 试用档额度(10次/小时 + 10次/天)因测试耗尽,
    禁止任何调用。恢复条件: 用户明确允许后, 删除下方 DISABLED 保护并参考
    office/demand/report_rc_dev_log_20260806.md 的恢复步骤。

频控(试用档, 已停用): 1次/分钟 + 10次/小时 + 10次/天 — 脚本内以每天调用次数为最硬约束
更新窗口: 每晚 19~22 点更新当日数据

用法(停用期无效):
  python etl_report_rc.py                # 增量: 库内 MAX(report_date)+1 ~ 今天, 全市场
  python etl_report_rc.py --backfill 20260201 [20260806] [--slice-days 14]
                                         # 回填: 按 slice-days 分片(默认14天/片, 片内<3000条),
                                         #   每天调用次数由调度方控制, 脚本不自动节流
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ════════════════════════════════════════════════════════════════
# 停用保护(2026-08-06, 用户指示): 任何入口直接退出, 不触碰 report_rc 接口
# 恢复时删除本块即可(读库/写库逻辑均保留, 仅接口调用被屏蔽)
DISABLED = True
if DISABLED:
    print("etl_report_rc 已停用: report_rc 接口接入暂缓(用户指示 2026-08-06)。"
          "详见 office/demand/report_rc_dev_log_20260806.md")
    sys.exit(0)
# ════════════════════════════════════════════════════════════════

import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager
from utils import setup_logger, batch_id, safe_api_call

PRO = ts.pro_api()
db = DatabaseManager()
logger = setup_logger("etl_report_rc", "etl_report_rc.log")

TABLE = "stg_report_rc"
COLUMNS = ["ts_code", "name", "report_date", "report_title", "report_type",
           "classify", "org_name", "author_name", "quarter",
           "op_rt", "op_pr", "tp", "np", "eps", "pe", "rd", "roe", "ev_ebitda",
           "rating", "max_price", "min_price", "imp_dg", "create_time"]


def fetch_range(start: str, end: str) -> int:
    """全市场拉取 [start, end] 报告区间, 单次调用(上限3000条)

    若达到 3000 截断: 记录告警并返回已入库行数(调用方需缩小切片重试)
    """
    df = safe_api_call(PRO.report_rc, logger=logger, retry_wait=61,
                       start_date=start, end_date=end)
    if df is None or df.empty:
        logger.info(f"  [{start}~{end}] 返回空")
        return 0
    rows = [(
        r["ts_code"], r.get("name", ""), r["report_date"],
        r.get("report_title", ""), r.get("report_type", ""), r.get("classify", ""),
        r["org_name"], r.get("author_name", ""), r["quarter"],
        r.get("op_rt"), r.get("op_pr"), r.get("tp"), r.get("np"),
        r.get("eps"), r.get("pe"), r.get("rd"), r.get("roe"), r.get("ev_ebitda"),
        r.get("rating", ""), r.get("max_price"), r.get("min_price"),
        r.get("imp_dg", ""), r.get("create_time", ""),
    ) for _, r in df.iterrows()]
    n = db.insert_batch(TABLE, COLUMNS, rows, ignore=True)
    logger.info(f"  [{start}~{end}] 拉取 {len(rows)} 行(含重复跳过), 入库 {n}")
    if len(rows) >= 3000:
        logger.warning(f"  ⚠️  切片 [{start}~{end}] 达到 3000 上限疑似截断, 需缩小切片")
    return n


def etl_increment():
    """增量: MAX(report_date)+1 ~ 今天(全市场, 单次调用)"""
    r = db.execute(f"SELECT MAX(report_date) FROM {TABLE}")
    last = r[0][0] if r and r[0][0] else None
    today = datetime.now().strftime("%Y%m%d")
    if last is None:
        # 首次: 先回填近 30 天
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        logger.info(f"  库空, 增量起点放宽为近30天: {start}")
    else:
        start = (datetime.strptime(last, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    if start > today:
        logger.info(f"  已是最新(MAX={last}), 跳过")
        return 0
    s = datetime.now().isoformat()
    try:
        n = fetch_range(start, today)
        db.log_update(batch_id(), "report_rc", TABLE, today, s,
                      datetime.now().isoformat(), "SUCCESS", n, n)
        return n
    except Exception as e:
        db.log_update(batch_id(), "report_rc", TABLE, today, s,
                      datetime.now().isoformat(), "FAILED", 0, 0, str(e))
        logger.error(f"  增量失败: {e}")
        return 0


def etl_backfill(start: str, end: str, slice_days: int = 14):
    """回填: 按 slice_days 分片, 每片 1 次调用

    注意: 受试用档每天 10 次限制, 调用方应分批执行(每天 7-8 片)
    """
    s = datetime.now().isoformat()
    d_start = datetime.strptime(start, "%Y%m%d")
    d_end = datetime.strptime(end, "%Y%m%d")
    total = 0
    cur = d_start
    while cur <= d_end:
        seg_end = min(cur + timedelta(days=slice_days - 1), d_end)
        total += fetch_range(cur.strftime("%Y%m%d"), seg_end.strftime("%Y%m%d"))
        cur = seg_end + timedelta(days=1)
    db.log_update(batch_id(), "report_rc", TABLE, end, s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  回填完成: {start}~{end}, 共 {total} 行")
    return total


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--backfill" in args:
        i = args.index("--backfill")
        _start = args[i + 1]
        _end = args[i + 2] if len(args) > i + 2 and not args[i + 2].startswith("-") else \
            datetime.now().strftime("%Y%m%d")
        _slice = 14
        if "--slice-days" in args:
            _slice = int(args[args.index("--slice-days") + 1])
        etl_backfill(_start, _end, _slice)
    else:
        etl_increment()
