"""
THS Member 数据修复脚本 — 补齐因 ETL 限流缺失的板块成分

问题: etl_runner.py 中 sleep(0.05) 导致 ths_member 调用
速率 ≈438次/分钟，超出 Tushare 500次/分钟 限流阈值，
循环在 885/886 段被中断，303+101 个板块数据缺失。

修复:
  1. 扫描 stg_ths_index 中缺失成员的板块
  2. 逐个调用 ths_member，间隔 0.2s + 限流重试
  3. 写入 stg_ths_member
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH
from db_manager import DatabaseManager

import tushare as ts

pro = ts.pro_api()
db = DatabaseManager(DB_PATH)

logger = print  # 简单打印


def _get_missing_sectors():
    """获取 stg_ths_index 中存在但 stg_ths_member 中无数据的板块"""
    all_ = db.execute("SELECT ts_code FROM stg_ths_index ORDER BY ts_code")
    existing = set()
    for (r,) in db.execute("SELECT DISTINCT ts_code FROM stg_ths_member"):
        existing.add(r)

    missing = [c for (c,) in all_ if c not in existing]
    logger(f"[扫描] 共 {len(all_)} 个板块, 已有 {len(existing)} 个, 缺失 {len(missing)} 个")
    return missing


def _safe_ths_member(ts_code: str, max_retries=10) -> list:
    """带限流重试的 ths_member 调用"""
    for attempt in range(max_retries):
        try:
            df = pro.ths_member(ts_code=ts_code)
            return [(ts_code, r["con_code"], r.get("con_name", ""))
                    for _, r in df.iterrows()] if df is not None and not df.empty else None
        except Exception as e:
            if "频率超限" in str(e):
                wait = min(60 * (attempt + 1), 120)
                logger(f"  ⚠ 频率超限(code={ts_code}), 等待 {wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                logger(f"  ❌ {ts_code} 调用失败: {e}")
                return None
    logger(f"  ❌ {ts_code} 重试耗尽, 跳过")
    return None


def fix_ths_member():
    """主修复流程"""
    missing = _get_missing_sectors()
    if not missing:
        logger("\n✅ 没有缺失数据")
        return

    logger(f"\n开始补齐 {len(missing)} 个板块...")
    total_rows = 0
    success = 0
    empty = 0
    fail = 0
    t0 = time.time()

    for i, code in enumerate(missing, 1):
        rows = _safe_ths_member(code)
        if rows is None:
            fail += 1
        elif len(rows) == 0:
            empty += 1
        else:
            db.insert_batch("stg_ths_member",
                            ["ts_code", "con_code", "con_name"], rows)
            total_rows += len(rows)
            success += 1

        if i % 100 == 0:
            elapsed = time.time() - t0
            logger(f"  进度: {i}/{len(missing)}, "
                   f"成功={success}, 空={empty}, 失败={fail}, "
                   f"累计{total_rows}行, 耗时{elapsed:.0f}s")

        time.sleep(0.2)  # 间隔 0.2s，确保不超限流

    elapsed = time.time() - t0
    logger(f"\n{'='*50}")
    logger(f"修复完成！耗时 {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger(f"成功={success}, 空数据={empty}, 失败={fail}")
    logger(f"新增行数: {total_rows}")

    # 最终校验
    still_missing = _get_missing_sectors()
    if still_missing:
        logger(f"⚠ 仍有 {len(still_missing)} 个板块缺失: {still_missing[:10]}...")
    else:
        logger("✅ 所有板块均已补齐！")


if __name__ == "__main__":
    fix_ths_member()
