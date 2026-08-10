#!/usr/bin/env python3
"""
端到端测试产物同步 — worktree → 主 checkout

规则(2026-08-05 用户约定): worktree 上测试的结果必须能合并进主 checkout,
用户在主 checkout 阅览产物。本脚本同步两类产物:

  1. test_drive/new_e2e/run_*/          → 主 checkout 同名位置(测试上下文/完整输入文档)
  2. office/output/<股票>/*.md          → 主 checkout 对应股票目录(报告, 按股票名分目录)

幂等: 目标已存在同名文件时跳过, 不覆盖历史产物。

用法:
    conda run -n stock_agent python3 sync_e2e_to_main.py [--dry-run]
"""
import os
import shutil
import sys
import argparse
from pathlib import Path

# ── 路径推断 ──
_SCRIPT = Path(__file__).resolve()
# .../report_machine/office/test_drive/new_e2e/sync_e2e_to_main.py
_NEW_E2E_DIR = _SCRIPT.parent
_WORKTREE_REPO = _NEW_E2E_DIR.parent.parent.parent.parent.parent  # report_machine 上溯到 repo 根
# worktree 路径形如 <repo>/.claude/worktrees/<name>/, 主 checkout 为 <repo>(上溯 3 层)
if _WORKTREE_REPO.parent.name == "worktrees" and _WORKTREE_REPO.parent.parent.name == ".claude":
    _MAIN_REPO = _WORKTREE_REPO.parent.parent.parent
else:
    _MAIN_REPO = _WORKTREE_REPO


def sync_dir(src: Path, dst: Path, dry: bool, only_prefix: str = "") -> int:
    """同步 src 目录内容到 dst(同名文件跳过), 返回复制文件数;
    only_prefix 非空时只同步名称以该前缀开头的项(如 run_*)"""
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in src.iterdir():
        if only_prefix and not item.name.startswith(only_prefix):
            continue
        target = dst / item.name
        if target.exists():
            continue
        if dry:
            print(f"  [dry] {item.name}")
        else:
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser(description="同步 worktree 端到端测试产物到主 checkout")
    parser.add_argument("--dry-run", action="store_true", help="只列出将同步的内容")
    args = parser.parse_args()
    dry = args.dry_run

    if _MAIN_REPO == _WORKTREE_REPO:
        print("⚠️ 当前不在 worktree 中, 无需同步")
        return

    print(f"worktree : {_WORKTREE_REPO}")
    print(f"主checkout: {_MAIN_REPO}")
    total = 0

    # 1. run_* 测试目录(工具脚本本身不入产物)
    src_runs = _NEW_E2E_DIR
    dst_runs = _MAIN_REPO / _NEW_E2E_DIR.relative_to(_WORKTREE_REPO)
    n = sync_dir(src_runs, dst_runs, dry, only_prefix="run_")
    print(f"[1] run_* 测试目录: 同步 {n} 项")
    total += n

    # 2. office/output 报告(按股票目录)
    src_out = _WORKTREE_REPO / "experiments/report_machine/office/output"
    dst_out = _MAIN_REPO / "experiments/report_machine/office/output"
    for stock_dir in sorted(p for p in src_out.iterdir() if p.is_dir() and p.name not in ("__pycache__",)):
        n = sync_dir(stock_dir, dst_out / stock_dir.name, dry)
        if n:
            print(f"[2] 报告 {stock_dir.name}/: 同步 {n} 份")
        total += n

    print(f"\n{'[dry-run] ' if dry else ''}合计待同步/已同步: {total} 项")
    if dry:
        print("加 --dry-run 确认后, 去掉该参数执行实际同步")


if __name__ == "__main__":
    main()
