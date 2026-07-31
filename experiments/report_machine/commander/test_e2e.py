#!/usr/bin/env python3
"""
端到端测试 — 模拟定时任务触发

流程:
  1. 前置检查: 服务状态、数据库、交易日历
  2. 查股票池（从 SQLite 读取配置用户的股票）
  3. 调用 Writer API 生成午间报告
  4. 验证 output 文件是否生成
  5. 执行分发到用户目录
  6. 验证用户目录文件是否到位
  7. 输出测试报告

用法:
    conda run -n stock_agent python3 commander/test_e2e.py

默认跳过健康检测中的 Level 2/3（重启服务），如需完整检测加 --full-hc:
    conda run -n stock_agent python3 commander/test_e2e.py --full-hc
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
import requests

# ── 路径 ──
_SCRIPT_DIR = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
for _p in [_REPO_ROOT, _SCRIPT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("commander.test_e2e")

# ── 测试状态 ──
PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"


# ======================================================================
# 配置
# ======================================================================

def load_config() -> dict:
    path = os.path.join(_SCRIPT_DIR, "config.yaml")
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    users_cfg_path = cfg.get("commander", {}).get("users_config", "")
    if users_cfg_path and os.path.isfile(users_cfg_path):
        with open(users_cfg_path, "r") as f:
            users_cfg = yaml.safe_load(f)
        cfg["_users"] = users_cfg.get("report_users", [])
    else:
        cfg["_users"] = []
    return cfg


# ======================================================================
# 测试步骤
# ======================================================================

class E2ETest:
    """端到端测试"""

    def __init__(self, full_hc: bool = False):
        self.cfg = load_config()
        self.cmd_cfg = self.cfg.get("commander", {})
        self.db_cfg = self.cfg.get("database", {})
        self.services = self.cfg.get("services", {})
        self.usernames = self.cfg.get("_users", [])
        self.full_hc = full_hc

        self.today = datetime.now().strftime(
            self.cmd_cfg.get("date_format", "%Y%m%d")
        )
        self.output_dir = self.cmd_cfg.get("output_dir", "")
        self.user_base_dir = self.cmd_cfg.get("user_base_dir", "")
        self.query = self.cmd_cfg.get("query", "")
        self.db_path = self.db_cfg.get("sqlite_path", "")

        # 测试结果收集
        self.results = []
        self.start_time = time.time()

    def log_step(self, step: str, status: str, detail: str = ""):
        icon = PASS if status == "pass" else (FAIL if status == "fail" else SKIP)
        logger.info(f"  {icon} [{step}] {detail}")
        self.results.append({
            "step": step,
            "status": status,
            "detail": detail,
        })

    def run(self):
        logger.info("=" * 55)
        logger.info(f"  端到端测试 — 模拟定时任务触发")
        logger.info(f"  日期: {self.today}, 用户: {self.usernames}")
        logger.info("=" * 55)

        # ── 1. 前置检查 ──
        self._check_prerequisites()

        # ── 2. 健康检测 ──
        self._check_health()

        # ── 3. 清理旧 output ──
        self._clean_output()

        # ── 4. 查股票池 ──
        stocks = self._query_stock_pool()

        # ── 5. 调用 Writer API ──
        writer_ok, failed = self._call_writer(stocks)

        # ── 6. 验证 output 文件 ──
        success_stocks = [s for s in stocks if s not in failed]
        verified = self._verify_output(success_stocks)

        # ── 7. 分发报告 ──
        self._distribute_reports(success_stocks)

        # ── 8. 验证用户目录 ──
        self._verify_user_dirs(success_stocks)

        # ── 报告 ──
        self._print_report()

    # ── 1. 前置检查 ────────────────────────────

    def _check_prerequisites(self):
        logger.info("--- 1. 前置检查 ---")

        # trade_calendar
        try:
            _midday = os.path.normpath(os.path.join(_REPO_ROOT, "data_fetch", "midday"))
            sys.path.insert(0, _midday)
            from trade_calendar import is_trading_day
            trading = is_trading_day(self.today)
            self.log_step("交易日判定", "pass" if trading else "skip",
                          f"{self.today} {'是' if trading else '不是'}交易日")
        except Exception as e:
            self.log_step("交易日判定", "fail", str(e))

        # SQLite
        if os.path.isfile(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("SELECT 1 FROM stock_pool LIMIT 1")
                conn.close()
                self.log_step("SQLite", "pass", f"数据库可读: {self.db_path}")
            except Exception as e:
                self.log_step("SQLite", "fail", str(e))
        else:
            self.log_step("SQLite", "fail", f"数据库文件不存在: {self.db_path}")

        # 服务 HTTP 可达性
        for name, svc_cfg in self.services.items():
            url = svc_cfg.get("health_url", "")
            if not url:
                continue
            try:
                resp = requests.get(url, timeout=3)
                ok = resp.ok
                self.log_step(f"服务-{name}", "pass" if ok else "fail",
                              f"{url} → HTTP {resp.status_code}")
            except requests.RequestException as e:
                self.log_step(f"服务-{name}", "fail", f"{url} → {e}")

    # ── 2. 健康检测 ────────────────────────────

    def _check_health(self):
        logger.info("--- 2. 健康检测 ---")
        try:
            from commander.health_check import HealthChecker
            hc = HealthChecker(config=self.cfg)
            if self.full_hc:
                result = hc.run()
            else:
                # 先初始化 results，再运行 L0+L1
                from commander.health_check import ComponentResult
                hc.results = {}
                for _n in self.cfg.get("services", {}):
                    hc.results[_n] = ComponentResult(name=_n)
                for _n in ["neo4j", "sqlite", "trade_cal"]:
                    hc.results.setdefault(_n, ComponentResult(name=_n))
                hc._level0_pre_check()
                hc._level1_health_check()
                for comp in hc.results.values():
                    comp.final_ok = comp.level1_ok
                result = hc._finalize(time.time())

            if result.ok:
                self.log_step("健康检测", "pass", "全部通过")
            else:
                fails = [n for n, c in result.components.items() if not c.final_ok]
                self.log_step("健康检测", "fail", f"失败: {fails}")
                # 打印详细
                result.print_report()

            # 保存临时结果以便 _finalize 引用
            self._hc_result = result

        except Exception as e:
            self.log_step("健康检测", "fail", str(e))

    # ── 3. 清理 ────────────────────────────────

    def _clean_output(self):
        """清空 office/output/ 中的所有报告（含文件夹），模拟定时任务首次触发的干净状态"""
        logger.info("--- 3. 清空 output ---")
        if not os.path.isdir(self.output_dir):
            self.log_step("清理", "skip", f"output 目录不存在")
            return
        removed = 0
        for sdir in os.listdir(self.output_dir):
            spath = os.path.join(self.output_dir, sdir)
            if not os.path.isdir(spath) or sdir.startswith("."):
                continue
            try:
                shutil.rmtree(spath)
                removed += 1
            except OSError as e:
                logger.warning(f"  清理 {sdir} 失败: {e}")
        self.log_step("清理", "pass", f"清空了 {removed} 个股票文件夹")

    # ── 4. 查股票池 ────────────────────────────

    def _query_stock_pool(self) -> list[str]:
        logger.info("--- 4. 查询股票池 ---")
        if not self.usernames:
            self.log_step("股票池", "skip", "未配置用户")
            return []

        try:
            placeholders = ",".join(["?"] * len(self.usernames))
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f"""
                SELECT u.username, s.stock_name, s.ts_code
                FROM stock_pool s
                JOIN user u ON s.user_id = u.id
                WHERE u.username IN ({placeholders})
                ORDER BY u.username, s.stock_name
            """, self.usernames)
            rows = c.fetchall()
            conn.close()

            # 去重
            seen = {}
            for username, stock_name, ts_code in rows:
                if ts_code not in seen:
                    seen[ts_code] = {"name": stock_name, "users": []}
                seen[ts_code]["users"].append(username)

            names = [v["name"] for v in seen.values()]
            self.log_step("股票池", "pass",
                          f"{len(names)} 只 (去重后): {names}")
            return names

        except Exception as e:
            self.log_step("股票池", "fail", str(e))
            return []

    # ── 5. 调 Writer ────────────────────────────

    def _call_writer(self, stocks: list[str]) -> tuple[bool, list[str]]:
        logger.info("--- 5. 调用 Writer API ---")
        if not stocks:
            self.log_step("Writer API", "skip", "股票列表为空")
            return True, []

        url = "http://localhost:8310/api/v1/report"
        try:
            t0 = time.time()
            resp = requests.post(
                url,
                json={"stock_names": stocks, "query": self.query},
                timeout=600,
            )
            elapsed = time.time() - t0

            if resp.ok:
                data = resp.json()
                total = data.get("total", 0)
                success = data.get("success", 0)
                failed = data.get("failed", [])
                self.log_step("Writer API", "pass" if not failed else "fail",
                              f"{success}/{total} 成功, 耗时 {elapsed:.1f}s"
                              + (f", 失败: {failed}" if failed else ""))
                return success > 0, failed
            else:
                self.log_step("Writer API", "fail",
                              f"HTTP {resp.status_code}: {resp.text[:200]}")
                return False, stocks

        except requests.Timeout:
            self.log_step("Writer API", "fail", "超时 (>600s)")
            return False, stocks
        except requests.ConnectionError as e:
            self.log_step("Writer API", "fail", f"连接失败: {e}")
            return False, stocks

    # ── 6. 验证 output ──────────────────────────

    def _verify_output(self, stocks: list[str]) -> list[str]:
        logger.info("--- 6. 验证 output 文件 ---")
        verified = []
        for name in stocks:
            report_path = os.path.join(self.output_dir, name,
                                       f"{self.today}_{name}_午间收盘报告.md")
            if os.path.isfile(report_path):
                size = os.path.getsize(report_path)
                verified.append(name)
                self.log_step(f"  output-{name}", "pass",
                              f"{(size/1024):.1f}KB")
            else:
                self.log_step(f"  output-{name}", "fail",
                              f"文件不存在: {report_path}")

        return verified

    # ── 7. 分发报告 ────────────────────────────

    def _distribute_reports(self, stocks: list[str]):
        logger.info("--- 7. 分发报告 ---")
        if not stocks:
            self.log_step("分发", "skip", "无成功股票")
            return

        copied = 0
        for name in stocks:
            src = os.path.join(self.output_dir, name,
                               f"{self.today}_{name}_午间收盘报告.md")
            if not os.path.isfile(src):
                continue

            # 找出哪些用户有这个股票
            for username in self.usernames:
                dst_dir = os.path.join(self.user_base_dir, username, name)
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, f"{self.today}_{name}_午间收盘报告.md")
                try:
                    shutil.copy2(src, dst)
                    copied += 1
                    logger.info(f"    {username}/{name}/ ✅")
                except (OSError, shutil.Error) as e:
                    self.log_step(f"  分发-{username}/{name}", "fail", str(e))

        self.log_step("分发", "pass", f"复制了 {copied} 份报告到用户目录")

    # ── 8. 验证用户目录 ──────────────────────────

    def _verify_user_dirs(self, stocks: list[str]):
        logger.info("--- 8. 验证用户目录 ---")
        found = 0
        for username in self.usernames:
            for name in stocks:
                dst = os.path.join(self.user_base_dir, username, name,
                                   f"{self.today}_{name}_午间收盘报告.md")
                if os.path.isfile(dst):
                    size = os.path.getsize(dst)
                    found += 1
                    self.log_step(f"  user-{username}/{name}", "pass",
                                  f"{(size/1024):.1f}KB")
                else:
                    self.log_step(f"  user-{username}/{name}", "fail",
                                  f"文件不存在: {dst}")

        if not stocks:
            self.log_step("用户目录", "skip", "无股票可验证")
        elif found == len(stocks) * len(self.usernames):
            self.log_step("用户目录完整性", "pass",
                          f"{found}/{len(stocks)*len(self.usernames)} 份到位")
        else:
            self.log_step("用户目录完整性", "fail",
                          f"仅 {found}/{len(stocks)*len(self.usernames)} 份到位")

    # ── 报告 ────────────────────────────────────

    def _print_report(self):
        elapsed = time.time() - self.start_time
        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")
        skipped = sum(1 for r in self.results if r["status"] == "skip")
        total = len(self.results)

        print(f"\n{'='*55}")
        print(f"  E2E 测试报告")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  结果: {PASS if failed==0 else FAIL} "
              f"{passed}/{total} 通过"
              + (f", {failed} 失败" if failed else "")
              + (f", {skipped} 跳过" if skipped else ""))
        print(f"{'='*55}")

        for r in self.results:
            icon = PASS if r["status"] == "pass" else (FAIL if r["status"] == "fail" else SKIP)
            print(f"  {icon} {r['step']:30s} {r['detail']}")

        print(f"{'='*55}\n")

        return failed == 0


# ======================================================================
# CLI
# ======================================================================

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    import argparse
    parser = argparse.ArgumentParser(description="端到端测试")
    parser.add_argument("--full-hc", action="store_true",
                        help="包含完整健康检测（含服务重启）")
    args = parser.parse_args()

    test = E2ETest(full_hc=args.full_hc)
    test.run()


if __name__ == "__main__":
    main()
