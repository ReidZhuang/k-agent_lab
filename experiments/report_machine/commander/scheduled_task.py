#!/usr/bin/env python3
"""
定时任务入口 — 交易日 11:40 触发

流程:
  1. 加载配置
  2. 交易日判定 → 非交易日退出
  3. 健康检测 (L0→L1→L2→L3) → 失败退出
  4. 查所有用户股票池 → 合并去重
  5. 第一批: POST Writer API（全部股票）
  6. 第二批: 重试失败的股票
  7. 分发报告: office/output/ → user/{username}/{stock_name}/
  8. 写任务日志到 office/log/
  （2026-07-31 起不再清理 office/output/，历史报告保留）

用法:
    conda run -n stock_agent python3 commander/scheduled_task.py

也可用 --dry-run 预览不执行:
    conda run -n stock_agent python3 commander/scheduled_task.py --dry-run
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import logging
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
import requests

# ── 路径：确保可导入 commander 包 ──
_SCRIPT_DIR = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
for _p in [_REPO_ROOT, _SCRIPT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from commander.health_check import HealthChecker
from commander.service_manager import load_config as load_commander_config

logger = logging.getLogger("commander.scheduled_task")


# ======================================================================
# 配置加载
# ======================================================================

def load_config(config_path: str = None) -> dict:
    """加载 commander 配置 + 用户配置"""
    if config_path is None:
        config_path = os.path.join(_SCRIPT_DIR, "config.yaml")

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # 加载用户配置
    users_cfg_path = cfg.get("commander", {}).get("users_config", "")
    if users_cfg_path and os.path.isfile(users_cfg_path):
        with open(users_cfg_path, "r") as f:
            users_cfg = yaml.safe_load(f)
        cfg["_users"] = users_cfg.get("report_users", [])
    else:
        cfg["_users"] = []
        logger.warning(f"用户配置文件不存在: {users_cfg_path}")

    return cfg


# ======================================================================
# 日志初始化
# ======================================================================

def setup_logging(log_dir: str, today: str):
    """设置日志：同时输出到文件和控制台"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"task_{today}.log")

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    formatter = logging.Formatter(fmt)

    # 文件 handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    # 控制台 handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    root = logging.getLogger("commander")
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    return log_file


# ======================================================================
# 交易日判定
# ======================================================================

def is_trading_day(today: str) -> bool:
    """使用 TradeCalendar 判断今天是否是交易日"""
    try:
        _midday_dir = os.path.normpath(
            os.path.join(_SCRIPT_DIR, "..", "data_fetch", "midday")
        )
        sys.path.insert(0, _midday_dir)
        from trade_calendar import is_trading_day as _cal_is_trading
        return _cal_is_trading(today)
    except Exception as e:
        logger.error(f"交易日历检查失败: {e}")
        # 兜底: 周一到周五视为交易日
        import datetime
        wd = datetime.datetime.now().weekday()
        return wd < 5


# ======================================================================
# 清理旧的 output 文件
# ======================================================================

def clean_old_output(output_dir: str, today: str):
    """清理 output 目录中非今天（yesterday 及更早）的报告文件

    保留当天生成的文件，删除更早的.
    """
    if not os.path.isdir(output_dir):
        logger.debug(f"  output 目录不存在: {output_dir}")
        return

    removed = 0
    for stock_dir in os.listdir(output_dir):
        stock_path = os.path.join(output_dir, stock_dir)
        if not os.path.isdir(stock_path):
            continue
        for fname in os.listdir(stock_path):
            if not fname.startswith(today):
                fpath = os.path.join(stock_path, fname)
                try:
                    os.remove(fpath)
                    removed += 1
                    logger.debug(f"  清理旧报告: {fpath}")
                except OSError as e:
                    logger.warning(f"  清理失败: {fpath} - {e}")

    if removed:
        logger.info(f"  已清理 {removed} 个旧报告文件")


# ======================================================================
# 数据库查询
# ======================================================================

def query_stock_pools(db_path: str, usernames: list[str]) -> dict:
    """从 SQLite 查询所有用户的股票池

    Args:
        db_path: SQLite 数据库路径
        usernames: 用户名列表

    Returns:
        {username: [(stock_name, ts_code), ...]}
    """
    if not usernames:
        return {}

    if not os.path.isfile(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return {}

    placeholders = ",".join(["?"] * len(usernames))
    sql = f"""
        SELECT u.username, s.stock_name, s.ts_code
        FROM stock_pool s
        JOIN user u ON s.user_id = u.id
        WHERE u.username IN ({placeholders})
        ORDER BY u.username, s.stock_name
    """

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(sql, usernames)
        rows = c.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"查询股票池失败: {e}")
        return {}

    result = {}
    for username, stock_name, ts_code in rows:
        result.setdefault(username, []).append((stock_name, ts_code))

    for u in usernames:
        count = len(result.get(u, []))
        logger.info(f"  {u}: {count} 只股票")

    return result


def deduplicate_stocks(all_pools: dict) -> tuple[list[dict], list[dict], dict]:
    """跨用户去重，生成报告时只跑一次，分发到每个用户

    Args:
        all_pools: {username: [(stock_name, ts_code), ...]}

    Returns:
        (deduped_items, all_items, user_stock_map)
        - deduped_items: [{name, ts_code, users: [username]}], 按 ts_code 去重
        - all_items: [{name, ts_code, username}], 为分发保留每位用户
        - user_stock_map: {username: [{name, ts_code}]}
    """
    # 按 ts_code 去重
    seen = {}  # ts_code → {name, ts_code, users: [username]}
    all_items = []
    user_stock_map = {}

    for username, stocks in all_pools.items():
        user_stock_map[username] = []
        for stock_name, ts_code in stocks:
            all_items.append({
                "name": stock_name,
                "ts_code": ts_code,
                "username": username,
            })
            user_stock_map[username].append({
                "name": stock_name,
                "ts_code": ts_code,
            })
            if ts_code not in seen:
                seen[ts_code] = {
                    "name": stock_name,
                    "ts_code": ts_code,
                    "users": [],
                }
            seen[ts_code]["users"].append(username)

    deduped = list(seen.values())
    logger.info(
        f"  去重前: {len(all_items)} 只 (含多用户重复), "
        f"去重后: {len(deduped)} 只"
    )

    return deduped, all_items, user_stock_map


# ======================================================================
# 调用 Writer API
# ======================================================================

def call_writer(
    stock_names: list[str],
    query: str,
    writer_url: str = "http://localhost:8310/api/v1/report",
    timeout: int = 600,
) -> dict:
    """POST Writer API 生成报告

    Returns:
        {"status": "ok"|"error", "total": int, "success": int,
         "failed": [stock_name], "results": [...]}
        失败时返回 {"status": "error", "error": "..."}
    """
    if not stock_names:
        return {"status": "ok", "total": 0, "success": 0, "failed": [], "results": []}

    logger.info(f"  POST {writer_url}")
    logger.info(f"  股票: {stock_names}")

    t0 = time.time()
    try:
        resp = requests.post(
            writer_url,
            json={"stock_names": stock_names, "query": query},
            timeout=timeout,
        )
        elapsed = time.time() - t0
        logger.info(f"  响应: HTTP {resp.status_code}, 耗时 {elapsed:.1f}s")

        if not resp.ok:
            return {
                "status": "error",
                "error": f"Writer 返回 HTTP {resp.status_code}: {resp.text[:300]}",
                "total": len(stock_names),
                "success": 0,
                "failed": stock_names,
                "results": [],
            }

        data = resp.json()
        total = data.get("total", 0)
        success = data.get("success", 0)
        failed = data.get("failed", [])
        logger.info(f"  完成: {success}/{total}, 失败: {len(failed)}")

        return data

    except requests.Timeout:
        elapsed = time.time() - t0
        logger.error(f"  Writer 超时 ({elapsed:.0f}s)")
        return {
            "status": "error",
            "error": f"Writer 超时 ({elapsed:.0f}s)",
            "total": len(stock_names),
            "success": 0,
            "failed": stock_names,
            "results": [],
        }
    except requests.ConnectionError as e:
        logger.error(f"  Writer 连接失败: {e}")
        return {
            "status": "error",
            "error": f"Writer 连接失败: {e}",
            "total": len(stock_names),
            "success": 0,
            "failed": stock_names,
            "results": [],
        }


# ======================================================================
# 错误记录到 DB
# ======================================================================

def log_error_to_db(
    db_path: str,
    module: str = "commander",
    function: str = "",
    level: str = "ERROR",
    stock_name: str = "",
    ts_code: str = "",
    error_msg: str = "",
    error_code: str = "",
):
    """记录异常到 error_log 表"""
    try:
        batch_id = datetime.now().strftime("CMD_%Y%m%d_%H%M%S")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            """INSERT INTO error_log
            (batch_id, timestamp, module, function, level,
             stock_name, ts_code, error_msg, error_code, service_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batch_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                module,
                function,
                level,
                stock_name,
                ts_code or "",
                error_msg[:500],
                error_code,
                "commander",
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"写入 error_log 失败: {e}")


# ======================================================================
# 分发报告
# ======================================================================

def find_report_file(output_dir: str, stock_name: str, today: str) -> Optional[str]:
    """在 output 目录中查找指定股票当天的报告文件

    Returns:
        文件绝对路径，未找到返回 None
    """
    stock_dir = os.path.join(output_dir, stock_name)
    if not os.path.isdir(stock_dir):
        return None

    # 匹配今天日期的文件
    for fname in os.listdir(stock_dir):
        if fname.startswith(today) and fname.endswith(".md"):
            return os.path.join(stock_dir, fname)

    return None


def distribute_reports(
    success_names: list[str],
    user_map: dict,
    output_dir: str,
    user_base_dir: str,
    today: str,
    deduped_items: list[dict],
    db_path: str = "",
) -> dict:
    """将生成的报告从 output 复制到对应用户目录

    Args:
        success_names: 成功的股票名称列表
        user_map: {ts_code: {name, users: [username]}}
        output_dir: office/output/
        user_base_dir: user/
        today: YYYYMMDD
        deduped_items: [{name, ts_code, users: [username]}]

    Returns:
        {username: {stock_name: "ok"|"not_found"|"copy_failed"}}
    """
    results = {}

    for item in deduped_items:
        name = item["name"]
        ts_code = item["ts_code"]
        users = item["users"]

        if name not in success_names:
            for u in users:
                results.setdefault(u, {})[name] = "skipped"
            continue

        # 找报告文件
        report_path = find_report_file(output_dir, name, today)
        if not report_path:
            logger.warning(f"  报告文件未找到: {name}")
            for u in users:
                log_error_to_db(
                    db_path, function="distribute_reports",
                    stock_name=name, ts_code=ts_code,
                    error_msg=f"报告文件未找到: {output_dir}/{name}/",
                    error_code="REPORT_FILE_NOT_FOUND",
                )
                results.setdefault(u, {})[name] = "not_found"
            continue

        # 复制到每个用户目录
        for username in users:
            dst_dir = os.path.join(user_base_dir, username, name)
            os.makedirs(dst_dir, exist_ok=True)

            fname = os.path.basename(report_path)
            dst_path = os.path.join(dst_dir, fname)

            try:
                shutil.copy2(report_path, dst_path)
                logger.info(f"  {username}/{name}/{fname} ✅")
                results.setdefault(username, {})[name] = "ok"
            except (OSError, shutil.Error) as e:
                logger.error(f"  复制失败 {username}/{name}: {e}")
                log_error_to_db(
                    db_path, function="distribute_reports",
                    stock_name=name, ts_code=ts_code,
                    error_msg=f"报告复制失败: {e}",
                    error_code="REPORT_COPY_FAILED",
                )
                results.setdefault(username, {})[name] = "copy_failed"

    return results


# ======================================================================
# 任务摘要
# ======================================================================

def write_task_log(log_dir: str, today: str, summary: dict):
    """写入任务摘要日志（JSON 格式）"""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"summary_{today}.json")

    summary["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"任务摘要已写入: {log_path}")


def print_summary_table(summary: dict):
    """打印可读的任务摘要"""
    # 防止 db_path 未定义
    db_path_local = summary.get("db_path", "")

    print(f"\n{'='*55}")
    print(f"  定时报告任务 — 执行摘要")
    print(f"  日期:     {summary.get('date', '?')}")
    print(f"  状态:     {'✅ 完成' if summary.get('status') == 'completed' else '⚠️ 部分完成' if summary.get('status') == 'partial' else '❌ 失败'}")
    print(f"  耗时:     {summary.get('elapsed', 0):.1f}s")
    print(f"{'='*55}")

    if summary.get("health_check"):
        hc = summary["health_check"]
        print(f"  健康检测: {hc.get('ok', '?')} / {hc.get('total', '?')} 组件通过")

    print(f"  用户:")
    for u, stocks in summary.get("user_stocks", {}).items():
        print(f"    {u}: {stocks} 只")

    print(f"  去重后: {summary.get('deduped_count', 0)} 只股票")

    if summary.get("batch1"):
        b1 = summary["batch1"]
        print(f"  第一批: {b1.get('success', 0)}/{b1.get('total', 0)} 成功")

    if summary.get("batch2"):
        b2 = summary["batch2"]
        print(f"  第二批(重试): {b2.get('success', 0)}/{b2.get('total', 0)} 成功")

    failed = summary.get("final_failed", [])
    if failed:
        print(f"  ❌ 最终失败: {failed}")

    dist = summary.get("distribution", {})
    if dist:
        ok = sum(1 for s in dist.values() for v in s.values() if v == "ok")
        fail = sum(1 for s in dist.values() for v in s.values() if v != "ok")
        print(f"  分发: {ok} 份成功" + (f", {fail} 份失败" if fail else ""))

    print(f"{'='*55}\n")


# ======================================================================
# 主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="定时报告生成任务")
    parser.add_argument("--dry-run", action="store_true",
                       help="预览模式：不实际调用 Writer，不生成报告")
    parser.add_argument("--config", "-c", help="配置文件路径")
    args = parser.parse_args()

    # 加载配置
    cfg = load_config(args.config)
    cmd_cfg = cfg.get("commander", {})
    db_cfg = cfg.get("database", {})
    usernames = cfg.get("_users", [])

    today = datetime.now().strftime(cmd_cfg.get("date_format", "%Y%m%d"))

    log_dir = cmd_cfg.get("log_dir", "")
    output_dir = cmd_cfg.get("output_dir", "")
    user_base_dir = cmd_cfg.get("user_base_dir", "")
    query = cmd_cfg.get("query", "")
    db_path = db_cfg.get("sqlite_path", "")

    # 设置日志
    log_file = setup_logging(log_dir, today)
    logger.info(f"===== 定时报告任务开始 =====")
    logger.info(f"日期: {today}, 用户: {usernames}")
    if args.dry_run:
        logger.info("🔶 预览模式 — 不会实际生成报告")

    t_start = time.time()

    # ── 构建摘要 ──
    summary = {
        "date": today,
        "status": "unknown",
        "elapsed": 0,
        "health_check": {},
        "user_stocks": {u: 0 for u in usernames},
        "deduped_count": 0,
        "batch1": {},
        "batch2": {},
        "final_failed": [],
        "distribution": {},
        "db_path": db_path,
        "log_file": log_file,
    }

    # ── 1. 交易日判定 ──
    logger.info("--- 1. 交易日判定 ---")
    if not is_trading_day(today):
        logger.info(f"  {today} 非交易日，跳过")
        summary["status"] = "skipped_not_trading_day"
        write_task_log(log_dir, today, summary)
        return

    logger.info(f"  {today} 是交易日，继续")

    # ── 2. 健康检测 ──
    logger.info("--- 2. 健康检测 ---")
    hc = HealthChecker(config=cfg)
    hc_result = hc.run()

    hc_summary = {
        "ok": hc_result.ok,
        "total": len(hc_result.components),
        "passed": sum(1 for c in hc_result.components.values() if c.final_ok),
        "level3_triggered": hc_result.level3_triggered,
    }
    summary["health_check"] = hc_summary

    if not hc_result.ok:
        logger.error("健康检测未通过，终止任务")
        summary["status"] = "health_check_failed"
        hc_result.print_report()
        write_task_log(log_dir, today, summary)
        sys.exit(1)

    logger.info("  健康检测全部通过")

    # ── 3. 清理旧的 output（2026-07-31 起停用：不再清理，保留历史报告）──
    # logger.info("--- 3. 清理昨日 output ---")
    # clean_old_output(output_dir, today)

    # ── 4. 查股票池 ──
    logger.info("--- 4. 查询股票池 ---")
    if not usernames:
        logger.warning("  未配置用户，跳过")
        summary["status"] = "no_users"
        write_task_log(log_dir, today, summary)
        return

    all_pools = query_stock_pools(db_path, usernames)

    user_stock_counts = {u: len(all_pools.get(u, [])) for u in usernames}
    summary["user_stocks"] = user_stock_counts

    deduped_items, all_items, user_stock_map = deduplicate_stocks(all_pools)
    summary["deduped_count"] = len(deduped_items)

    if not deduped_items:
        logger.warning("  股票池为空，跳过")
        summary["status"] = "empty_stock_pool"
        write_task_log(log_dir, today, summary)
        return

    # ── 5. 第一批：调用 Writer API ──
    deduped_names = [d["name"] for d in deduped_items]
    logger.info(f"--- 5. 第一批: 生成 {len(deduped_names)} 只股票报告 ---")

    if args.dry_run:
        logger.info(f"  [预览] 将调用 Writer: {deduped_names}")
        batch1_result = {"status": "ok", "total": len(deduped_names),
                         "success": len(deduped_names), "failed": [], "results": []}
    else:
        batch1_result = call_writer(deduped_names, query)

    if batch1_result.get("success", 0) > 0:
        logger.info(f"  第一批成功: {batch1_result['success']} 只")

    summary["batch1"] = {
        "total": batch1_result.get("total", 0),
        "success": batch1_result.get("success", 0),
        "failed": batch1_result.get("failed", []),
    }

    failed_names = batch1_result.get("failed", [])
    first_success = [
        n for n in deduped_names
        if n not in failed_names
    ]

    # ── 6. 第二批：重试 ──
    final_failed = []
    if failed_names:
        logger.info(f"--- 6. 第二批: 重试 {len(failed_names)} 只失败股票 ---")

        # 记录第一批失败到 DB
        for fname in failed_names:
            # 找 ts_code
            fts = next(
                (d["ts_code"] for d in deduped_items if d["name"] == fname),
                ""
            )
            log_error_to_db(
                db_path=db_path,
                function="batch1_writer",
                stock_name=fname,
                ts_code=fts,
                error_msg=f"第一批生成失败",
                error_code="BATCH1_FAILED",
            )
            logger.warning(f"  {fname}: 记录失败")

        if args.dry_run:
            logger.info(f"  [预览] 将重试: {failed_names}")
            batch2_result = {"status": "ok", "total": len(failed_names),
                             "success": len(failed_names), "failed": []}
        else:
            batch2_result = call_writer(failed_names, query)

        summary["batch2"] = {
            "total": batch2_result.get("total", 0),
            "success": batch2_result.get("success", 0),
            "failed": batch2_result.get("failed", []),
        }

        final_failed = batch2_result.get("failed", [])

        # 记录第二批失败
        for fname in final_failed:
            fts = next(
                (d["ts_code"] for d in deduped_items if d["name"] == fname),
                ""
            )
            log_error_to_db(
                db_path=db_path,
                function="batch2_writer",
                stock_name=fname,
                ts_code=fts,
                error_msg=f"第二批(重试)仍失败",
                error_code="BATCH2_FAILED",
            )
            logger.error(f"  {fname}: 重试仍失败")

        second_success = [n for n in failed_names if n not in final_failed]
    else:
        second_success = []
        summary["batch2"] = {"total": 0, "success": 0, "failed": []}

    # ── 所有成功的股票 ──
    all_success = first_success + second_success
    summary["final_failed"] = final_failed

    # ── 7. 分发报告 ──
    if all_success:
        logger.info("--- 7. 分发报告到用户目录 ---")

        if args.dry_run:
            logger.info(f"  [预览] 将分发 {len(all_success)} 只股票到用户目录")
        else:
            dist_results = distribute_reports(
                success_names=all_success,
                user_map={d["ts_code"]: d for d in deduped_items},
                output_dir=output_dir,
                user_base_dir=user_base_dir,
                today=today,
                deduped_items=deduped_items,
                db_path=db_path,
            )
            summary["distribution"] = dist_results

            # 打印分发统计
            dist_ok = 0
            dist_fail = 0
            for u, stocks in dist_results.items():
                for sname, status in stocks.items():
                    if status == "ok":
                        dist_ok += 1
                    else:
                        dist_fail += 1
            logger.info(f"  分发完成: {dist_ok} 份成功" +
                        (f", {dist_fail} 份失败" if dist_fail else ""))
    else:
        logger.warning("  无成功股票，跳过分发")

    # ── 8. 完成 ──
    t_elapsed = time.time() - t_start

    if final_failed:
        summary["status"] = "partial"
    else:
        summary["status"] = "completed"

    summary["elapsed"] = t_elapsed
    summary["log_file"] = log_file

    write_task_log(log_dir, today, summary)
    print_summary_table(summary)

    logger.info(f"===== 任务结束 ({t_elapsed:.1f}s) =====")

    if final_failed:
        logger.error(f"最终失败股票: {final_failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
