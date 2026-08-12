"""
Service Manager — 服务启停管理

功能:
  - 端口监听进程查找与清理
  - 单服务启动/停止/重启
  - 全服务启动/停止/重启（按依赖顺序）
  - 等待服务健康就绪

依赖: yaml, requests, subprocess
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
from pathlib import Path
from typing import Optional

import yaml
import requests

logger = logging.getLogger("commander.service_manager")

# 服务启动依赖顺序（正向 = 先启动的先列出）
SERVICE_START_ORDER = ["mail_tower", "middleman", "reporter", "writer"]
# 服务停止顺序 = 反向依赖
SERVICE_STOP_ORDER = list(reversed(SERVICE_START_ORDER))


# ── 配置加载 ──────────────────────────────────────────

class ServiceConfig:
    """单个服务的配置"""

    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.port = int(cfg["port"])
        self.cwd = cfg["cwd"]
        self.cmd = cfg["cmd"]
        self.health_url = cfg["health_url"]
        self.health_field = cfg.get("health_field", "status")
        self.health_expected = cfg.get("health_expected", "ok")
        self.startup_grace = cfg.get("startup_grace", 5)

    def log_path(self) -> str:
        """服务日志路径"""
        log_dir = f"/tmp/commander_logs"
        return f"{log_dir}/{self.name}.log"

    def __repr__(self):
        return f"<Service {self.name}:{self.port}>"


def load_config(path: str = None) -> dict:
    """加载 commander config.yaml"""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_service_configs(config: dict = None) -> dict[str, ServiceConfig]:
    """从配置解析所有服务定义"""
    if config is None:
        config = load_config()
    services = {}
    for name, cfg in config.get("services", {}).items():
        services[name] = ServiceConfig(name, cfg)
    return services


# ── 端口与进程工具 ──────────────────────────────────

def find_pids_on_port(port: int) -> list[int]:
    """查找监听指定端口的进程 PID 列表

    优先使用 lsof，回退到 ss。
    Returns:
        PID 列表（可能为空）
    """
    pids = set()

    # 方案1: lsof
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                pid = line.strip()
                if pid.isdigit():
                    pids.add(int(pid))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 方案2: ss（lsof 不可用时回退）
    if not pids:
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # ss 输出: State Recv-Q Send-Q Local Address:Port Peer Address:Port  Process
                # Process 列: "users:(("uvicorn",pid=1234,...))"
                for line in result.stdout.splitlines():
                    if "pid=" in line:
                        import re
                        for match in re.finditer(r"pid=(\d+)", line):
                            pids.add(int(match.group(1)))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return sorted(pids)


def kill_processes(pids: list[int], force: bool = False) -> list[int]:
    """终止进程列表

    Args:
        pids: 要终止的 PID 列表
        force: 是否直接 SIGKILL

    Returns:
        仍然存活的 PID 列表（空表示全部终止）
    """
    if not pids:
        return []

    sig = signal.SIGKILL if force else signal.SIGTERM
    surviving = []

    for pid in pids:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            continue  # 已结束
        except PermissionError:
            logger.warning(f"无权限终止 PID {pid}")
            surviving.append(pid)
            continue

    # SIGTERM 后等进程退出
    if not force:
        for _ in range(15):
            time.sleep(0.3)
            still_alive = []
            for pid in pids:
                try:
                    os.kill(pid, 0)
                    still_alive.append(pid)
                except ProcessLookupError:
                    pass
            if not still_alive:
                return []
            pids = still_alive
        # 仍有存活，SIGKILL
        return kill_processes(still_alive, force=True)

    return surviving


def wait_port_free(port: int, timeout: int = 15) -> bool:
    """等待端口释放（无监听进程）"""
    for _ in range(timeout * 2):
        if not find_pids_on_port(port):
            return True
        time.sleep(0.5)
    return False


# ── 服务健康检测 ──────────────────────────────────

def check_service_health(svc: ServiceConfig, timeout: int = 10) -> bool:
    """检查单个服务是否健康

    Args:
        svc: 服务配置
        timeout: 超时秒数

    Returns:
        True 表示健康
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(svc.health_url, timeout=3)
            if resp.ok:
                data = resp.json()
                actual = data.get(svc.health_field, "")
                if actual == svc.health_expected:
                    return True
                logger.debug(
                    f"{svc.name} 健康字段不匹配: "
                    f"期望 {svc.health_expected}, 得到 {actual}"
                )
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            logger.debug(f"{svc.name} 健康检查未就绪: {e}")
        time.sleep(1)
    return False


# ── 服务启停 ──────────────────────────────────────

def start_service(svc: ServiceConfig) -> bool:
    """启动单个服务

    流程:
      1. 检查端口是否已被占用 → 清理
      2. 创建日志目录
      3. 启动进程
      4. 等待健康就绪

    Returns:
        True 表示启动成功
    """
    # 1. 清理已有进程
    existing = find_pids_on_port(svc.port)
    if existing:
        logger.warning(f"{svc.name} 端口 {svc.port} 已被占用 (PID {existing})，先清理")
        kill_processes(existing)
        if not wait_port_free(svc.port):
            logger.error(f"{svc.name} 端口 {svc.port} 无法释放")
            return False

    # 2. 准备日志
    log_path = svc.log_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # 3. 启动
    # 注意: cmd 本身已含完整 conda 路径(如 /home/stockagent/miniforge3/bin/conda run -n stock_agent ...),
    # 直接执行,不再拼接前缀(历史 bug: 曾与 CONDA_CMD 前缀拼成 `conda conda run` 导致启动必失败)
    full_cmd = f"cd {svc.cwd} && nohup {svc.cmd} > {log_path} 2>&1 &"
    logger.info(f"启动 {svc.name}: {full_cmd[:120]}...")

    try:
        subprocess.run(
            full_cmd,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        # nohup 后台进程通常不会因 timeout 失败
        pass
    except Exception as e:
        logger.error(f"{svc.name} 启动命令执行失败: {e}")
        return False

    # 4. 等待就绪
    time.sleep(svc.startup_grace)
    ok = check_service_health(svc, timeout=30)
    if ok:
        logger.info(f"{svc.name} 启动成功 (:{svc.port})")
    else:
        logger.error(f"{svc.name} 启动后健康检查未通过")
    return ok


def stop_service(svc: ServiceConfig, force: bool = False) -> bool:
    """停止单个服务

    Returns:
        True 表示端口已释放
    """
    pids = find_pids_on_port(svc.port)
    if not pids:
        logger.info(f"{svc.name} 未在运行")
        return True

    logger.info(f"停止 {svc.name} (PID {pids})")
    surviving = kill_processes(pids, force=force)
    if surviving:
        logger.error(f"{svc.name} 部分进程未能终止: {surviving}")

    released = wait_port_free(svc.port)
    if released:
        logger.info(f"{svc.name} 已停止")
    else:
        logger.error(f"{svc.name} 端口 {svc.port} 仍未释放")
    return released


def restart_service(svc: ServiceConfig) -> bool:
    """重启单个服务"""
    stop_service(svc)
    time.sleep(1)
    return start_service(svc)


# ── 批量启停 ──────────────────────────────────────

def start_all_services(services: dict[str, ServiceConfig]) -> dict[str, bool]:
    """按依赖顺序启动所有服务

    Args:
        services: 服务名 → ServiceConfig

    Returns:
        {服务名: 是否成功}
    """
    results = {}
    for name in SERVICE_START_ORDER:
        svc = services.get(name)
        if not svc:
            logger.warning(f"未知服务: {name}")
            continue
        results[name] = start_service(svc)
    return results


def stop_all_services(services: dict[str, ServiceConfig], force: bool = False) -> dict[str, bool]:
    """按依赖逆序停止所有服务

    Args:
        services: 服务名 → ServiceConfig
        force: 是否强制 SIGKILL

    Returns:
        {服务名: 端口是否释放}
    """
    results = {}
    for name in SERVICE_STOP_ORDER:
        svc = services.get(name)
        if not svc:
            continue
        results[name] = stop_service(svc, force=force)
    return results


def restart_all_services(services: dict[str, ServiceConfig]) -> dict[str, bool]:
    """重启所有服务（停全部 → 启全部）"""
    logger.info("===== 全体重启 =====")
    stop_all_services(services)
    time.sleep(2)
    results = start_all_services(services)
    logger.info("===== 全体重启完成 =====")
    return results


# ── CLI ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="服务管理器")
    parser.add_argument("action", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--service", "-s", help="服务名，不指定则操作全部")
    args = parser.parse_args()

    cfg = load_config()
    services = get_service_configs(cfg)

    if args.service:
        svc = services.get(args.service)
        if not svc:
            print(f"未知服务: {args.service}，可用: {list(services.keys())}")
            sys.exit(1)
        if args.action == "start":
            ok = start_service(svc)
        elif args.action == "stop":
            ok = stop_service(svc)
        elif args.action == "restart":
            ok = restart_service(svc)
        elif args.action == "status":
            pids = find_pids_on_port(svc.port)
            healthy = check_service_health(svc)
            print(f"{svc.name}:{svc.port}  PID={pids}  healthy={healthy}")
            ok = True
        sys.exit(0 if ok else 1)
    else:
        if args.action == "start":
            results = start_all_services(services)
        elif args.action == "stop":
            results = stop_all_services(services)
        elif args.action == "restart":
            results = restart_all_services(services)
        elif args.action == "status":
            for name in SERVICE_START_ORDER:
                svc = services.get(name)
                pids = find_pids_on_port(svc.port)
                healthy = check_service_health(svc)
                print(f"  {svc.name}:{svc.port}  PID={pids}  healthy={healthy}")
            sys.exit(0)

        all_ok = all(results.values())
        for name, ok in results.items():
            print(f"  {name}: {'✅' if ok else '❌'}")
        sys.exit(0 if all_ok else 1)
