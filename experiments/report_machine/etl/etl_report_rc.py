"""
ETL: 券商评级与盈利预测(stg_report_rc, 接口 report_rc)

⚠️ 停用/恢复记录: 2026-08-06 因试用额度耗尽被用户要求全面停用; 2026-08-10 用户授权恢复
    (22:00 cron 恢复)。记录文档: office/demand/report_rc_dev_log_20260806.md

频控(试用档): 1次/分钟 + 10次/小时 + 10次/天 — 请求到达即计数, 失败也算
更新窗口: 每晚 19~22 点更新当日数据(22:00 运行可能遇到当天数据未发布完,
          晚到数据由次日增量重叠回补, 见 etl_increment)

用法:
  python etl_report_rc.py                # 增量: 库内 MAX(report_date)-2 ~ 今天, 全市场(2天重叠回补晚到数据)
  python etl_report_rc.py --backfill 20260201 [20260806] [--slice-days 14] [--paginate]
                                         # 回填: 按 slice-days 分片(默认14天/片, 片内<3000条),
                                         #   --paginate: 同区间内用 offset 分页循环拉全(每页3000)
                                         #   每天调用次数由调度方控制, 脚本不自动节流
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

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


def fetch_range(start: str, end: str, paginate: bool = False) -> int:
    """全市场拉取 [start, end] 报告区间

    Args:
        paginate: True 时同区间内 offset 分页循环(每页 3000, 直到拉全);
                  分页防死循环: 若某页 report_date 集合与上一页完全相同, 视为 offset 无效中止
    """
    total = 0
    offset = 0
    prev_dates = None
    while True:
        # 分钟级频控(1次/分钟, 实测 2026-08-06): 页间必须等待 ≥61s, 否则第2页即被拒
        if offset > 0:
            time.sleep(62)
        # 单次调用, 失败即停不重试(用户要求 2026-08-06): 试用档额度是稀缺资源, 重试消耗窗口计数
        try:
            df = PRO.report_rc(start_date=start, end_date=end, offset=offset, limit=3000)
        except Exception as e:
            logger.error(f"  [{start}~{end}] 页{offset//3000} report_rc 调用失败(不再重试): {e}")
            break
        if df is None or df.empty:
            logger.info(f"  [{start}~{end}] 页{offset//3000} 返回空, 结束")
            break
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
        total += n
        logger.info(f"  [{start}~{end}] 页{offset//3000}: 拉取 {len(rows)}, 入库 {n}(累计 {total})")
        if not paginate or len(rows) < 3000:
            # 满页防御: 非分页模式恰好 3000 条 = 疑似截断(区间内可能还有数据), 告警不静默丢
            if len(rows) == 3000 and not paginate:
                logger.warning(f"  ⚠️ [{start}~{end}] 页0 恰好满 3000 条, 疑似未拉全; "
                               f"如需全量请用 --paginate 或缩小日期区间")
            break
        # 分页防死循环: 本页日期集合与上页相同 → offset 对该区间无效(如按日排序 offset 被忽略)
        dates = tuple(sorted(df["report_date"].unique()))
        if prev_dates is not None and dates == prev_dates:
            logger.error(f"  ⚠️  offset 分页疑似无效(页{offset//3000}日期集合与上页相同), 中止; "
                         f"改用 --slice-days 按日期分片")
            break
        prev_dates = dates
        offset += 3000
    if paginate and total >= 3000:
        logger.info(f"  ✅ [{start}~{end}] 分页完成, 共 {total} 行")
    return total


def etl_increment():
    """增量: MAX(report_date)-2 ~ 今天(全市场, 单次调用)

    起点带 2 天重叠(2026-08-10 修复): 研报接口每晚 19~22 点更新当日数据, 22:00 运行时
    当天及前一天的部分研报可能尚未发布, 若不重叠, 晚到数据随 MAX 前移而永久丢失。
    重叠 2 天重拉可自动回补(INSERT OR IGNORE 幂等, 重复行不重复入库);
    每天 22:00 一次调用, 相对 10次/天 额度充裕。
    """
    OVERLAP_DAYS = 2
    r = db.execute(f"SELECT MAX(report_date) FROM {TABLE}")
    last = r[0][0] if r and r[0][0] else None
    today = datetime.now().strftime("%Y%m%d")
    if last is None:
        # 首次: 先回填近 30 天
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        logger.info(f"  库空, 增量起点放宽为近30天: {start}")
    else:
        start = (datetime.strptime(last, "%Y%m%d") - timedelta(days=OVERLAP_DAYS)).strftime("%Y%m%d")
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


def etl_backfill(start: str, end: str, slice_days: int = 14, paginate: bool = False,
                 overlap_days: int = 2):
    """回填: 自动跳过已入库区间, 只拉缺口; 缺口按 slice_days 分片

    断点续传(2026-08-07 用户要求, 避免重复拉取): 先查库内已入库日期覆盖 [lo, hi],
    目标区间 [start, end] 与之求差得到缺口区间列表, 仅拉缺口部分,
    不再重拉已入库数据(接口额度是稀缺资源, 重复拉取 = 白花调用次数)。
    overlap_days: 缺口边界向库内重叠 N 天——截断页的边界日期(库内 MIN/MAX 那天)
                  可能只入库了一部分, 重叠重拉可补齐当天缺失行(INSERT OR IGNORE 幂等,
                  多拉的行不重复入库)。默认 2 天。
    注意: 仅处理头部/尾部缺口; 若库中存在中间空洞, 需人工分区间回填。

    用法:
      python etl_report_rc.py --backfill 20260206 [20260806] [--slice-days 14] [--paginate] [--overlap-days 2]
    """
    s = datetime.now().isoformat()
    r = db.execute(f"SELECT MIN(report_date), MAX(report_date) FROM {TABLE}")
    lo, hi = (r[0][0], r[0][1]) if r and r[0][0] else (None, None)

    # 缺口 = [start, end] \ [lo, hi](区间差, 边界各向库内重叠 overlap_days 天)
    gaps = [(start, end)]
    if lo and hi:
        ov = timedelta(days=overlap_days)
        lo_d = datetime.strptime(lo, "%Y%m%d")
        hi_d = datetime.strptime(hi, "%Y%m%d")
        if end < lo or start > hi:
            gaps = [(start, end)]  # 无重叠
        else:
            gaps = []
            if start < lo:
                # 头部缺口: [start, lo-1+overlap](重叠 lo 起 overlap 天)
                head_end = (lo_d - timedelta(days=1) + ov).strftime("%Y%m%d")
                gaps.append((start, min(end, head_end)))
            if end > hi:
                # 尾部缺口: [hi+1-overlap, end](重叠 hi 起 overlap 天)
                tail_start = (hi_d + timedelta(days=1) - ov).strftime("%Y%m%d")
                gaps.append((max(start, tail_start), end))
    if not gaps:
        logger.info(f"  已入库覆盖 {lo}~{hi}, 目标 {start}~{end} 完全在库内, 无缺口, 跳过")
        return 0

    total = 0
    for gs, ge in gaps:
        logger.info(f"  缺口区间: {gs}~{ge}(库内覆盖 {lo}~{hi}, 边界重叠 {overlap_days} 天)")
        d_start = datetime.strptime(gs, "%Y%m%d")
        d_end = datetime.strptime(ge, "%Y%m%d")
        cur = d_start
        while cur <= d_end:
            seg_end = min(cur + timedelta(days=slice_days - 1), d_end)
            total += fetch_range(cur.strftime("%Y%m%d"), seg_end.strftime("%Y%m%d"), paginate)
            cur = seg_end + timedelta(days=1)
    db.log_update(batch_id(), "report_rc", TABLE, end, s,
                  datetime.now().isoformat(), "SUCCESS", total, total)
    logger.info(f"  回填完成: {start}~{end}(缺口已拉), 共 {total} 行")
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
        _paginate = "--paginate" in args
        _overlap = 2
        if "--overlap-days" in args:
            _overlap = int(args[args.index("--overlap-days") + 1])
        etl_backfill(_start, _end, _slice, _paginate, _overlap)
    else:
        etl_increment()
