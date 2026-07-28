#!/usr/bin/env python3
"""
手动重试脚本 — 读取 fallback/ 目录下的失败 context，重新提交 reporter

用法:
  # 重试所有失败的 context
  conda run -n stock_agent python retry_fallback.py

  # 只重试指定股票的 context
  conda run -n stock_agent python retry_fallback.py --stock 宁德时代

  # 查看有哪些失败的 context
  conda run -n stock_agent python retry_fallback.py --list
"""
import os
import sys
import json
import glob
import argparse

_OFFICE_DIR = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
if _OFFICE_DIR not in sys.path:
    sys.path.insert(0, _OFFICE_DIR)

from models import ReportContext
from cfg import load_config

_cfg = load_config()
_reporter_cfg = _cfg.get("reporter", {})
_REPORTER_URL = (
    f"http://{_reporter_cfg.get('host', 'localhost')}"
    f":{_reporter_cfg.get('port', 8312)}"
)
_FALLBACK_DIR = os.path.join(_OFFICE_DIR, "fallback")


def list_fallbacks(stock_name: str | None = None) -> list[str]:
    """列出所有 fallback 文件"""
    if stock_name:
        pattern = os.path.join(_FALLBACK_DIR, f"{stock_name}_*.json")
    else:
        pattern = os.path.join(_FALLBACK_DIR, "*.json")
    return sorted(glob.glob(pattern))


def retry(filepath: str) -> bool:
    """重试一个 fallback 文件"""
    print(f"正在重试: {os.path.basename(filepath)}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False

    context = ReportContext(**data)
    import requests
    try:
        resp = requests.post(
            f"{_REPORTER_URL}/api/v1/generate",
            json=context.model_dump(),
            timeout=120,
        )
        if resp.ok:
            result = resp.json()
            if result.get("status") == "ok":
                print(f"  ✅ 成功: {result.get('output_path')}")
                # 重试成功后可选择删除 fallback 文件
                # os.remove(filepath)
                return True
            else:
                print(f"  ⚠️  返回异常: {result.get('error', '未知')}")
                return False
        else:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="手动重试失败的 reporter 请求")
    parser.add_argument("--stock", help="只重试指定股票的 fallback")
    parser.add_argument("--list", action="store_true", help="列出所有 fallback 文件")
    parser.add_argument("--retry-all", action="store_true", help="重试所有 fallback")
    args = parser.parse_args()

    if not os.path.isdir(_FALLBACK_DIR):
        print(f"fallback 目录不存在: {_FALLBACK_DIR}")
        return

    files = list_fallbacks(args.stock)

    if args.list or not (args.retry_all or args.stock):
        print(f"找到 {len(files)} 个 fallback 文件:")
        for f in files:
            stat = os.stat(f)
            size = stat.st_size
            mtime = os.path.getmtime(f)
            import time
            print(f"  {os.path.basename(f)} ({size} bytes, "
                  f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(mtime))})")
        if not args.retry_all and not args.stock:
            print("\n使用 --retry-all 重试所有，或 --stock <名称> 重试指定股票")
        return

    if args.retry_all:
        files = list_fallbacks()

    success = 0
    fail = 0
    for f in files:
        if retry(f):
            success += 1
        else:
            fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败")


if __name__ == "__main__":
    main()
