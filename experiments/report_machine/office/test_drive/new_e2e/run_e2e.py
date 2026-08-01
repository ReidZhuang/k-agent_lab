#!/usr/bin/env python3
"""
端到端测试 — 午间/日终报告全链路(10只股票, 三份 context 全保存)

流程:
  1. 重启 writer/reporter(注入 E2E_SAVE_DIR / E2E_SUBWRITER_DIR 环境变量)
  2. 调 Writer API 生成报告(report_type 可选 endday/noon)
  3. 收集三份输出:
     - 01_pre_llm/    : reporter 组装好 prompts 后、调用 LLM 前的完整 context(每轮一份)
     - 02_subwriter/  : sub writer 组装好的每只股票数据+资讯(context sample)
     - 03_output/     : 最终报告

用法:
    conda run -n stock_agent python3 run_e2e.py --type endday --stocks 平安银行 比亚迪 宁德时代 凯莱英 广生堂 淮北矿业 博瑞医药 绿的谐波 风华高科 天虹股份
    conda run -n stock_agent python3 run_e2e.py --type noon   --stocks ...(同上)
"""
import os
import sys
import json
import time
import subprocess
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path

# ── 路径 ──
_SCRIPT_DIR = Path(__file__).resolve().parent          # office/test_drive/new_e2e
_OFFICE_DIR = _SCRIPT_DIR.parent.parent                # office/
_REPO_DIR = _OFFICE_DIR.parent.parent.parent           # report_machine/

_WRITER_URL = "http://localhost:8310/api/v1/report"
_REPORTER_PORT = 8312
_WRITER_PORT = 8310

# ── 报告类型 ──
_TYPE_CONFIG = {
    "endday": {
        "query": "生成该股票的日终收盘分析报告",
        "report_type": "endday",
    },
    "noon": {
        "query": "生成该股票的午间收盘分析报告",
        "report_type": "noon",
    },
}


def ensure_dirs(report_type: str):
    """创建三份输出目录(每次测试独立时间戳, 不覆盖历史)"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = _SCRIPT_DIR / f"run_{report_type}_{stamp}"
    dirs = {
        "pre_llm": root / "01_pre_llm",
        "subwriter": root / "02_subwriter",
        "output": root / "03_output",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return root, dirs


def find_pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return [int(x) for x in out.split("\n") if x.strip()]
    except Exception:
        return []


def restart_service_with_env(name: str, cwd: str, cmd: str, port: int,
                             health_url: str, env: dict) -> bool:
    """重启服务并注入 E2E 环境变量"""
    pids = find_pids_on_port(port)
    for pid in pids:
        os.system(f"kill {pid} 2>/dev/null")
    time.sleep(2)
    merged_env = {**os.environ, **env}
    log_dir = Path(cwd) / ".." / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    full_cmd = f"cd {cwd} && nohup {cmd} > {log_dir}/{name}_e2e.log 2>&1 &"
    subprocess.run(["bash", "-c", full_cmd], env=merged_env, timeout=10)
    # 等待健康
    for _ in range(25):
        try:
            r = urllib.request.urlopen(health_url, timeout=2)
            if r.status == 200:
                print(f"  ✅ {name} 已重启并健康")
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"  ❌ {name} 重启后健康检查失败")
    return False


def call_writer(stock_names: list[str], report_type: str) -> dict:
    cfg = _TYPE_CONFIG[report_type]
    body = json.dumps({
        "stock_names": stock_names,
        "query": cfg["query"],
        "report_type": cfg["report_type"],
    }).encode()
    req = urllib.request.Request(
        _WRITER_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=2400) as resp:
        return json.loads(resp.read().decode())


def collect_and_verify(root: Path, dirs: dict, stock_names: list[str]) -> dict:
    """检查三份输出是否齐全, 汇总结果"""
    summary = {
        "root": str(root),
        "pre_llm_files": sorted(p.name for p in dirs["pre_llm"].glob("*.json")),
        "subwriter_files": sorted(p.name for p in dirs["subwriter"].glob("*.json")),
        "report_files": sorted(p.name for p in dirs["output"].glob("*.md")),
    }
    print("\n========== 输出汇总 ==========")
    print(f"  📁 {summary['root']}")
    print(f"  01_pre_llm  : {len(summary['pre_llm_files'])} 份 (期望 >= 每只股票1份)")
    print(f"  02_subwriter: {len(summary['subwriter_files'])} 份 (期望 = {len(stock_names)} 份)")
    print(f"  03_output   : {len(summary['report_files'])} 份 (期望 = {len(stock_names)} 份)")
    for f in summary["report_files"]:
        print(f"    - {f}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="端到端测试(午间/日终)")
    parser.add_argument("--type", required=True, choices=["endday", "noon"])
    parser.add_argument("--stocks", nargs="+", required=True)
    parser.add_argument("--no-restart", action="store_true",
                        help="不重启服务(已手动带环境变量启动)")
    args = parser.parse_args()

    stock_names = list(dict.fromkeys(args.stocks))  # 去重保序
    print(f"报告类型: {args.type} | 股票({len(stock_names)}): {stock_names}")

    # 0. 目录
    root, dirs = ensure_dirs(args.type)

    # 1. 重启 reporter/writer(注入 E2E 环境变量)
    if not args.no_restart:
        e2e_env = {
            "E2E_SAVE_DIR": str(dirs["pre_llm"]),
            "E2E_SUBWRITER_DIR": str(dirs["subwriter"]),
        }
        print("\n[1] 重启 reporter/writer(注入 E2E 环境变量)...")
        ok_r = restart_service_with_env(
            "reporter", f"{_OFFICE_DIR}/reporter",
            "conda run -n stock_agent python3 server.py",
            _REPORTER_PORT, "http://localhost:8312/health", e2e_env)
        ok_w = restart_service_with_env(
            "writer", f"{_OFFICE_DIR}/writer",
            "conda run -n stock_agent python3 server.py",
            _WRITER_PORT, "http://localhost:8310/health", e2e_env)
        if not (ok_r and ok_w):
            print("❌ 服务重启失败, 中止")
            sys.exit(1)

    # 2. 调 Writer API
    print(f"\n[2] 调用 Writer API 生成 {args.type} 报告...")
    t0 = time.time()
    try:
        result = call_writer(stock_names, args.type)
    except Exception as e:
        print(f"❌ Writer API 调用失败: {e}")
        collect_and_verify(root, dirs, stock_names)
        sys.exit(1)
    elapsed = time.time() - t0
    print(f"  响应: {result.get('status')} | total={result.get('total')} "
          f"success={result.get('success')} failed={result.get('failed')} | 耗时 {elapsed:.0f}s")

    # 3. 收集输出
    summary = collect_and_verify(root, dirs, stock_names)

    # 4. 汇总文件保存
    summary["writer_response"] = result
    summary_path = root / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 汇总已保存: {summary_path}")


if __name__ == "__main__":
    main()
