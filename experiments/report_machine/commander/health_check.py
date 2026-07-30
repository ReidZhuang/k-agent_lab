"""
Health Check — 三级健康检测

Level 0: 端口归属校验（清理残留/错位/僵尸进程）
Level 1: 服务健康检测（HTTP / Neo4j / SQLite / 交易日历）
Level 2: 定向重启（只重启失败的服务）
Level 3: 全体重启兜底

可作为库调用或独立 CLI 运行。

用法:
    from commander.health_check import HealthChecker
    hc = HealthChecker()
    result = hc.run()
    if not result.ok:
        sys.exit(1)
"""

import os
import sys
import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import yaml
import requests

from commander.service_manager import (
    load_config, get_service_configs, ServiceConfig,
    find_pids_on_port, check_service_health,
    start_service, restart_service, restart_all_services,
    SERVICE_START_ORDER,
)

logger = logging.getLogger("commander.health_check")


# ── 数据结构 ──────────────────────────────────────

@dataclass
class ComponentResult:
    """单个组件的检测结果"""
    name: str
    level0_ok: bool = True
    level0_detail: str = ""
    level1_ok: bool = False
    level1_detail: str = ""
    level2_action: str = ""   # "none" / "restarted" / "failed"
    level3_triggered: bool = False
    final_ok: bool = False


@dataclass
class HealthCheckResult:
    """全套检测结果"""
    ok: bool = False
    timestamp: str = ""
    elapsed: float = 0.0
    components: dict[str, ComponentResult] = field(default_factory=dict)
    level3_triggered: bool = False
    error: str = ""

    @property
    def summary(self) -> str:
        """返回一行摘要文本"""
        ok_count = sum(1 for c in self.components.values() if c.final_ok)
        total = len(self.components)
        status = "✅ 通过" if self.ok else "❌ 未通过"
        return (f"[{self.timestamp}] {status} "
                f"({ok_count}/{total} 组件正常, "
                f"耗时 {self.elapsed:.1f}s)"
                f"{' [触发了全体重启]' if self.level3_triggered else ''}")

    def print_report(self):
        """打印详细检测报告"""
        print(f"\n{'='*55}")
        print(f"  Health Check Report")
        print(f"  时间: {self.timestamp}")
        print(f"  耗时: {self.elapsed:.1f}s")
        print(f"  结果: {'✅ 全部通过' if self.ok else '❌ 有失败'}")
        if self.level3_triggered:
            print(f"  ⚠️  触发了 Level 3 全体重启")
        print(f"{'='*55}")

        for name in SERVICE_START_ORDER + ["neo4j", "sqlite", "trade_cal"]:
            comp = self.components.get(name)
            if not comp:
                continue
            icon = "✅" if comp.final_ok else "❌"
            l0 = "✔" if comp.level0_ok else "✘"
            l1 = "✔" if comp.level1_ok else "✘"
            print(f"  {icon} {comp.name:12s}  L0={l0} L1={l1}  {comp.level1_detail}")
            if comp.level2_action and comp.level2_action != "none":
                print(f"       Level 2: {comp.level2_action}")

        if self.error:
            print(f"\n  错误: {self.error}")

        print(f"{'='*55}")
        return self.ok


# ── Health Checker ──────────────────────────────

class HealthChecker:
    """三级健康检测器"""

    def __init__(self, config_path: str = None, config: dict = None):
        if config is None:
            config = load_config(config_path)
        self.config = config
        self.services = get_service_configs(config)
        self.db_cfg = config.get("database", {})
        self.cfg = config.get("commander", {})
        self.results: dict[str, ComponentResult] = {}

    def run(self) -> HealthCheckResult:
        """执行全套健康检测 L0 → L1 → L2 → L3"""
        t0 = time.time()
        logger.info("===== 开始健康检测 =====")

        # 初始化结果
        self.results = {}
        for name in SERVICE_START_ORDER:
            self.results[name] = ComponentResult(name=name)
        self.results["neo4j"] = ComponentResult(name="neo4j")
        self.results["sqlite"] = ComponentResult(name="sqlite")
        self.results["trade_cal"] = ComponentResult(name="trade_cal")

        try:
            # Level 0: 预检查
            self._level0_pre_check()

            # Level 1: 健康检测
            self._level1_health_check()

            # 判断是否需要 Level 2
            failed = [n for n, c in self.results.items() if not c.level1_ok]
            if failed:
                logger.warning(f"Level 1 检测到 {len(failed)} 个组件异常: {failed}")
                self._level2_selective_restart(failed)

                # 判断是否需要 Level 3
                still_failed = [n for n, c in self.results.items() if not c.final_ok]
                if still_failed:
                    logger.error(f"Level 2 后仍有 {len(still_failed)} 个异常: {still_failed}")
                    self._level3_full_restart()

        except Exception as e:
            logger.error(f"健康检测异常: {e}", exc_info=True)
            result = self._finalize(t0, error=str(e))
            return result

        result = self._finalize(t0)
        logger.info(result.summary)
        return result

    def _finalize(self, t0: float, error: str = "") -> HealthCheckResult:
        """生成最终结果"""
        elapsed = time.time() - t0
        level3 = any(c.level3_triggered for c in self.results.values())
        all_ok = all(c.final_ok for c in self.results.values())

        return HealthCheckResult(
            ok=all_ok,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            elapsed=elapsed,
            components=self.results,
            level3_triggered=level3,
            error=error,
        )

    # ── Level 0: 预检查 ──────────────────────────

    def _level0_pre_check(self):
        """端口归属校验 — 清理残留/错位/僵尸进程

        对每个服务端口:
          1. 找出所有 PIDs
          2. 用 /proc/{pid}/cwd + cmdline 验证是否属于预期服务
          3. 错位的进程 → kill
          4. 如果所有进程都被清理 → 标记为需要重启
        """
        logger.info("--- Level 0: 端口预检查 ---")

        for svc in self.services.values():
            comp = self.results.get(svc.name)
            pids = find_pids_on_port(svc.port)

            if not pids:
                comp.level0_ok = True
                comp.level0_detail = "端口无监听进程（服务未运行）"
                continue

            # 验证每个 PID 是否属于预期服务
            legitimate = []
            orphaned = []

            for pid in pids:
                if self._is_expected_process(pid, svc):
                    legitimate.append(pid)
                else:
                    orphaned.append(pid)

            if orphaned:
                logger.warning(
                    f"{svc.name} 发现 {len(orphaned)} 个非预期进程: "
                    f"PID {orphaned}，准备清理"
                )
                from commander.service_manager import kill_processes
                kill_processes(orphaned)
                comp.level0_detail = f"清理了 {len(orphaned)} 个非预期进程"

            if not legitimate:
                comp.level0_ok = False
                comp.level0_detail += "；无合法进程在监听"
                logger.warning(f"{svc.name} 端口 {svc.port} 无合法进程")
            else:
                comp.level0_ok = True
                comp.level0_detail = f"端口正常，{len(legitimate)} 个合法进程"

    @staticmethod
    def _parse_proc_pid(proc_path) -> str:
        try:
            return os.readlink(f"{proc_path}")
        except (OSError, FileNotFoundError):
            return ""

    def _is_expected_process(self, pid: int, svc: ServiceConfig) -> bool:
        """判断一个 PID 是否属于预期服务"""
        try:
            # 检查 cwd
            proc_cwd = self._parse_proc_pid(f"/proc/{pid}/cwd")
            expected_cwd = os.path.normpath(svc.cwd)
            if proc_cwd == expected_cwd:
                return True

            # 检查 cmdline
            try:
                with open(f"/proc/{pid}/cmdline", "r") as f:
                    cmdline = f.read().replace("\0", " ")
            except (OSError, FileNotFoundError):
                cmdline = ""

            # 根据服务特征判断
            if svc.name == "mail_tower":
                if "api:app" in cmdline and "port=8300" in cmdline.replace(" ", ""):
                    return True
            elif svc.name == "middleman":
                if "server:app" in cmdline and "port=8311" in cmdline.replace(" ", ""):
                    return True
            elif svc.name == "reporter":
                if "server.py" in cmdline:
                    return True
            elif svc.name == "writer":
                if "server.py" in cmdline:
                    return True

            # 最后一招：健康检查
            try:
                resp = requests.get(svc.health_url, timeout=2)
                if resp.ok:
                    data = resp.json()
                    if data.get(svc.health_field) == svc.health_expected:
                        return True
            except requests.RequestException:
                pass

            return False

        except Exception:
            return False

    # ── Level 1: 健康检测 ──────────────────────────

    def _level1_health_check(self):
        """检测所有组件的健康状况"""
        logger.info("--- Level 1: 健康检测 ---")

        for svc in self.services.values():
            ok = self._check_http_service(svc)
            comp = self.results[svc.name]
            comp.level1_ok = ok
            comp.level1_detail = (
                f"HTTP {svc.health_url} → {'ok' if ok else '失败'}"
            )
            # Level 1 通过 → 暂定为 final_ok（Level 2/3 可能覆盖）
            comp.final_ok = ok
            logger.info(f"  {svc.name}: {'✅' if ok else '❌'}")

        # Neo4j
        neo4j_ok = self._check_neo4j()
        self.results["neo4j"].level1_ok = neo4j_ok
        self.results["neo4j"].final_ok = neo4j_ok
        self.results["neo4j"].level1_detail = (
            f"Neo4j bolt://localhost:7687 → {'ok' if neo4j_ok else '连接失败'}"
        )
        logger.info(f"  neo4j: {'✅' if neo4j_ok else '❌'}")

        # SQLite
        sqlite_ok = self._check_sqlite()
        self.results["sqlite"].level1_ok = sqlite_ok
        self.results["sqlite"].final_ok = sqlite_ok
        self.results["sqlite"].level1_detail = (
            f"SQLite {self.db_cfg.get('sqlite_path', '')} → {'ok' if sqlite_ok else '不可读'}"
        )
        logger.info(f"  sqlite: {'✅' if sqlite_ok else '❌'}")

        # Trade Calendar
        cal_ok = self._check_trade_cal()
        self.results["trade_cal"].level1_ok = cal_ok
        self.results["trade_cal"].final_ok = cal_ok
        self.results["trade_cal"].level1_detail = (
            f"交易日历 → {'ok' if cal_ok else '不可用'}"
        )
        logger.info(f"  trade_cal: {'✅' if cal_ok else '❌'}")

    def _check_http_service(self, svc: ServiceConfig) -> bool:
        """HTTP 服务健康检测"""
        # Level 0 已经清理过端口了，这里直接做短超时检查
        return check_service_health(svc, timeout=5)

    def _check_neo4j(self) -> bool:
        """Neo4j 连通性检测"""
        try:
            from neo4j import GraphDatabase
            uri = self.db_cfg.get("neo4j_uri", "bolt://localhost:7687")
            user = self.db_cfg.get("neo4j_user", "neo4j")
            password = self.db_cfg.get("neo4j_password", "")
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                result = session.run("MATCH (s:Stock) RETURN count(s) as cnt")
                row = result.single()
                count = row["cnt"] if row else 0
                logger.debug(f"Neo4j 连接正常，{count} 只股票")
            driver.close()
            return count > 0
        except Exception as e:
            logger.warning(f"Neo4j 检测失败: {e}")
            return False

    def _check_sqlite(self) -> bool:
        """SQLite 数据库可读性检测"""
        try:
            import sqlite3
            db_path = self.db_cfg.get("sqlite_path", "")
            if not db_path or not os.path.isfile(db_path):
                logger.warning(f"SQLite 数据库文件不存在: {db_path}")
                return False
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT 1 FROM stock_pool LIMIT 1")
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"SQLite 检测失败: {e}")
            return False

    def _check_trade_cal(self) -> bool:
        """交易日历可用性检测"""
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(__file__), "..", "data_fetch", "midday"
            ))
            from trade_calendar import is_trading_day
            today = datetime.now().strftime("%Y%m%d")
            result = is_trading_day(today)
            logger.debug(f"交易日历正常，今天{'是' if result else '不是'}交易日")
            return True
        except Exception as e:
            logger.warning(f"交易日历检测失败: {e}")
            return False

    # ── Level 2: 定向重启 ────────────────────────

    def _level2_selective_restart(self, failed_names: list[str]):
        """定向重启：只重启失败的服务

        提取失败的 HTTP 服务，逐一重启。
        neo4j / sqlite / trade_cal 不重启（基础设施）。
        """
        logger.info(f"--- Level 2: 定向重启 ---")

        service_failures = [
            n for n in failed_names
            if n in self.services
        ]

        if not service_failures:
            # 没有 HTTP 服务失败（只有基础设施失败）
            logger.warning(f"基础设施组件异常（无需重启）: {failed_names}")
            return

        for name in service_failures:
            svc = self.services[name]
            comp = self.results[name]
            logger.info(f"  重启 {name} ...")

            ok = restart_service(svc)
            comp.level2_action = "restarted" if ok else "failed"

            if ok:
                # 重新做 Level 1 检测
                l1_ok = self._check_http_service(self.services[name])
                comp.level1_ok = l1_ok
                comp.level1_detail = f"重启后检测 → {'ok' if l1_ok else '仍失败'}"
                comp.final_ok = l1_ok
            else:
                comp.final_ok = False

    # ── Level 3: 全体重启 ────────────────────────

    def _level3_full_restart(self):
        """全体重启兜底

        杀全部 → 启全部 → 重新 Level 1 检测
        """
        logger.info("--- Level 3: 全体重启 ---")

        for comp in self.results.values():
            if not comp.final_ok:
                comp.level3_triggered = True

        results = restart_all_services(self.services)
        time.sleep(3)

        # 对所有 HTTP 服务重新做 Level 1
        for svc in self.services.values():
            ok = self._check_http_service(svc)
            comp = self.results[svc.name]
            comp.level1_ok = ok
            comp.level1_detail = f"全体重启后 → {'ok' if ok else '仍失败'}"
            comp.final_ok = ok

        # Neo4j / SQLite / trade_cal 不再重检（不受重启影响）
        for name in ["neo4j", "sqlite", "trade_cal"]:
            comp = self.results.get(name)
            if comp:
                comp.final_ok = comp.level1_ok


# ── 独立 CLI ────────────────────────────────────

def main():
    """CLI 入口: python -m commander.health_check"""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="健康检测")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--quiet", "-q", action="store_true", help="只输出最终结果")
    args = parser.parse_args()

    hc = HealthChecker(config_path=args.config)
    result = hc.run()

    if not args.quiet:
        result.print_report()
    else:
        print(result.summary)

    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
