"""研报服务并发压测 — 模拟用户场景(几秒内 10~20 次调用)

用法:
    python test_concurrency.py                # 默认: 同股10并发 + 不同股10并发
    python test_concurrency.py --same 20      # 同股票 20 并发
    python test_concurrency.py --mix 20       # 混合 20 并发
"""
import argparse
import asyncio
import json
import random
import time

import httpx

BASE = "http://127.0.0.1:8700"
# 不同股票池(深沪混合)
STOCKS = ["002821", "600519", "300750", "688166", "000001",
          "300395", "002594", "600036", "601318", "002714"]


async def one(client: httpx.AsyncClient, code: str, edition: int, idx: int) -> dict:
    t0 = time.time()
    try:
        r = await client.post(f"{BASE}/reports", json={"code": code, "edition": edition})
        el = time.time() - t0
        try:
            d = r.json()
        except Exception:
            d = {"_raw": r.text[:100]}
        return {"idx": idx, "code": code, "edition": edition, "ms": round(el * 1000),
                "status": r.status_code,
                "list_n": len(d.get("list") or []),
                "bodies_n": len(d.get("bodies") or []),
                "error": (d.get("error") or {}).get("type")}
    except Exception as e:
        return {"idx": idx, "code": code, "edition": edition,
                "ms": round((time.time() - t0) * 1000), "status": -1, "error": str(e)[:60]}


async def run_batch(label: str, tasks: list[dict]):
    async with httpx.AsyncClient(timeout=180) as client:
        t0 = time.time()
        results = await asyncio.gather(*[one(client, t["code"], t["edition"], i)
                                         for i, t in enumerate(tasks)])
        total = time.time() - t0
    ok = [r for r in results if r["status"] == 200]
    fail = [r for r in results if r["status"] != 200]
    times = sorted(r["ms"] for r in results)
    print(f"\n=== {label} ({len(tasks)} 请求) ===")
    print(f"总耗时: {total:.1f}s | 成功: {len(ok)}/{len(tasks)} | 失败: {len(fail)}")
    if times:
        print(f"耗时: 中位 {times[len(times)//2]}ms | 最小 {times[0]}ms | 最大 {times[-1]}ms")
    for r in results[:8]:
        err = f" err={r['error']}" if r["error"] else ""
        print(f"  [{r['idx']}] {r['code']} e{r['edition']} {r['ms']}ms "
              f"list={r['list_n']} bodies={r['bodies_n']} http={r['status']}{err}")
    return results


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", type=int, default=10, help="同股票并发数")
    ap.add_argument("--mix", type=int, default=10, help="混合并发数")
    args = ap.parse_args()

    # 场景1: 同股票并发(验证 in-flight 合并 + 缓存) — 冷缓存
    print("[预热] 清空服务缓存后测试...")
    same_tasks = [{"code": "002821", "edition": 0}] * args.same
    await run_batch(f"同股票 002821 edition=0 x{args.same}(冷缓存)", same_tasks)

    # 场景2: 同股票 edition=1(正文已在缓存)
    ed1_tasks = [{"code": "002821", "edition": 1}] * args.same
    await run_batch(f"同股票 002821 edition=1 x{args.same}(缓存命中)", ed1_tasks)

    # 场景3: 不同股票混合(验证并行抓取能力)
    mix_tasks = [{"code": random.choice(STOCKS), "edition": random.choice([0, 1])}
                 for _ in range(args.mix)]
    await run_batch(f"混合股票 x{args.mix}", mix_tasks)


if __name__ == "__main__":
    asyncio.run(main())
