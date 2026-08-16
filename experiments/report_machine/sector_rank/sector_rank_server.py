"""
THS 板块内个股涨幅排名服务 (on-demand, 端口 8324)

用户输入 THS 板块 → 输出板块内涨幅排名前 20 股票。

排序规则(用户确认):
  1. 涨幅降序
  2. 涨幅并列时: 涨停股按"谁先涨停"(触板时间) 先后排前; 非涨停股排后
  3. 仍并列: 成交额(amount_wan) 降序

统计字段: 涨幅(chg_pct)、主力增量(当日资金净额, pysnowball capital_flow)、
         主力金额(净占比 = 净额/成交额, 自算)。

数据源:
  板块/成分/快照 → 本地 report_market.db (stg_ths_index/stg_ths_member/stg_tencent_snapshot)
  触板时间 → 腾讯分时接口(web.ifzq.gtimg.cn/appstock/app/minute/query, 分钟级)
  主力资金 → pysnowball capital_flow(雪球, 复用 office fetcher 的 token 基建与刷新机制)

按需取数: 板块成分+快照全本地; 分时只拉"并列组内已涨停"的股票; 资金流只拉前 N 名。
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

# ── 路径与复用(与 ETL 脚本同款: sys.path insert) ──────────────────────
# 注意: 只 insert etl 目录; midday 目录有同名 config.py 会冲突, 仅用绝对路径引用
_HERE = Path(__file__).resolve().parent
_ETL_DIR = _HERE.parent / "etl"
_MIDDAY_DIR = _HERE.parent / "data_fetch" / "midday"
sys.path.insert(0, str(_ETL_DIR))
from config import DB_PATH  # noqa: E402
from db_manager import DatabaseManager  # noqa: E402

TOKEN_FILE = _MIDDAY_DIR / "config" / "snowball_token.json"
TOKEN_REFRESH_SCRIPT = _HERE.parent / "snowball_token" / "refresh_token.py"

PORT = 8324
app = FastAPI(title="THS Sector Rank", docs_url="/docs")
db = DatabaseManager(db_path=DB_PATH)

_log_lock = threading.Lock()


def _log(msg: str):
    with _log_lock:
        print(f"{datetime.now().isoformat(timespec='seconds')} {msg}", flush=True)


# ── 雪球 token(复制 fetch_midday_data.py 的 _init_snowball 模式) ────────
_SNOWBALL_INITED = False


def _refresh_token_file() -> bool:
    """调用 refresh_token.py --force 刷新, 写回 TOKEN_FILE; 成功返回 True"""
    import subprocess
    if not TOKEN_REFRESH_SCRIPT.exists():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(TOKEN_REFRESH_SCRIPT), "--force"],
            capture_output=True, text=True, timeout=180,
        )
        if result.stdout:
            _log("[snowball] 刷新输出: " + result.stdout.strip()[-200:])
    except Exception as e:
        _log(f"[snowball] 刷新进程异常: {e}")
        return False
    return TOKEN_FILE.exists()


def _init_snowball():
    """取数前初始化雪球 token: 文件缺失或失效(400016)时自动刷新"""
    global _SNOWBALL_INITED
    if _SNOWBALL_INITED:
        return
    import pysnowball as ball
    try:
        xq, u = "", ""
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE) as f:
                cfg = json.load(f)
            xq, u = cfg.get("xq_a_token", ""), cfg.get("u", "")
        if xq and u:
            ball.set_token(f"xq_a_token={xq}; u={u}")
            if _token_valid():
                _SNOWBALL_INITED = True
                return
            _log("[snowball] Token 已过期, 尝试自动刷新...")
        else:
            _log("[snowball] 未找到有效 Token, 尝试自动刷新...")
        if _refresh_token_file():
            with open(TOKEN_FILE) as f:
                cfg = json.load(f)
            ball.set_token(f"xq_a_token={cfg['xq_a_token']}; u={cfg['u']}")
            _SNOWBALL_INITED = True
            _log("[snowball] Token 自动刷新成功")
            return
        _log("[snowball] Token 自动刷新失败(资金流字段将为空, 不阻塞)")
        _SNOWBALL_INITED = True
    except Exception as e:
        _log(f"[snowball] init failed: {e}")
        _SNOWBALL_INITED = True


def _token_valid() -> bool:
    """capital_flow 校验严格(失效返回 error_code 400016), 用它实测"""
    try:
        from pysnowball.capital import capital_flow
        d = capital_flow("SZ000001")  # 平安银行, 稳定存在
        return bool(d and d.get("error_code") == 0)
    except Exception:
        return False


def fetch_capital_flow(codes: list[str]) -> dict[str, dict]:
    """并发拉 pysnowball capital_flow → {xq_code: {"net_yuan": float} | {"error": str}}

    codes: 雪球格式代码(SZ000568 / SH600519), 与 etl 快照 ts_code 后缀同源
    net_yuan = items 末条累计净额(当日资金净额, 主力口径)
    """
    _init_snowball()
    import pysnowball as ball

    def one(code: str):
        try:
            d = ball.capital_flow(code)
            if d is None or d.get("error_code") != 0:
                msg = (d or {}).get("error_description", "无数据") if d else "无数据"
                return code, {"error": msg}
            items = d.get("data", {}).get("items", [])
            if not items:
                return code, {"error": "无数据"}
            return code, {"net_yuan": items[-1].get("amount")}
        except Exception as e:
            return code, {"error": str(e)}

    with ThreadPoolExecutor(max_workers=5) as ex:
        return dict(ex.map(one, codes))


# ── 腾讯分时: 触板时间 ────────────────────────────────────────────────
def fetch_limit_up_time(ts_code: str, limit_up: float) -> str | None:
    """分时数据首次 price >= limit_up 的时间(HHMM); 失败/未触板返回 None"""
    suffix = ts_code.split(".")[-1].upper()
    pref = {"SZ": "sz", "SH": "sh", "BJ": "bj"}.get(suffix)
    if not pref:
        return None
    sym = f"{pref}{ts_code[:6]}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={sym}"
    try:
        r = requests.get(url, timeout=8)
        rows = r.json()["data"][sym]["data"]["data"]
        for line in rows:
            parts = line.split()
            if len(parts) >= 2 and float(parts[1]) >= limit_up - 0.005:
                return parts[0]  # "HHMM"
    except Exception:
        pass
    return None


# ── 本地查询 ──────────────────────────────────────────────────────────
def search_sectors(name: str, limit: int = 20) -> list[dict]:
    rows = db.execute(
        "SELECT ts_code, name, count FROM stg_ths_index WHERE name LIKE ? "
        "ORDER BY name LIMIT ?",
        (f"%{name}%", limit),
    )
    return [{"ts_code": r[0], "name": r[1], "member_count": r[2]} for r in rows]


def get_sector_by_ts_code(ts_code: str) -> dict | None:
    rows = db.execute(
        "SELECT ts_code, name, count FROM stg_ths_index WHERE ts_code=?", (ts_code,))
    if not rows:
        return None
    return {"ts_code": rows[0][0], "name": rows[0][1], "member_count": rows[0][2]}


def get_sectors_by_name(name: str) -> list[dict]:
    rows = db.execute(
        "SELECT ts_code, name, count FROM stg_ths_index WHERE name=?", (name,))
    return [{"ts_code": r[0], "name": r[1], "member_count": r[2]} for r in rows]


def get_members_with_snapshot(sector_ts_code: str) -> tuple[list[dict], str, str]:
    """成分 × 最新快照批次 → (股票列表, fetch_time, trade_date)

    股票: {ts_code, name, price, chg_pct, amount_wan, turnover_rate, limit_up}
    快照缺失的股票跳过。
    """
    rows = db.execute(
        """SELECT m.con_code, m.con_name,
                  s.price, s.chg_pct, s.amount_wan, s.turnover_rate, s.limit_up,
                  s.fetch_time, s.time_stamp
           FROM stg_ths_member m
           JOIN stg_tencent_snapshot s ON m.con_code = s.ts_code
           WHERE m.ts_code = ?
             AND s.fetch_time = (SELECT MAX(fetch_time) FROM stg_tencent_snapshot)""",
        (sector_ts_code,),
    )
    stocks = [{
        "ts_code": r[0], "name": r[1], "price": r[2], "chg_pct": r[3],
        "amount_wan": r[4] or 0.0, "turnover_rate": r[5], "limit_up": r[6],
    } for r in rows]
    fetch_time = rows[0][7] if rows else ""
    trade_date = rows[0][8][:8] if rows else ""
    return stocks, fetch_time, trade_date


# ── 排序(三级规则) ────────────────────────────────────────────────────
def sort_key(st: dict):
    # 1 涨幅降序; 2 涨停股触板时间升序(无触板时间=非涨停, 排后); 3 成交额降序
    t = st.get("limit_up_time") or "9999"
    return (-st["chg_pct"], t, -st["amount_wan"])


def build_ranked(stocks: list[dict], top: int) -> tuple[list[dict], int]:
    """三级排序 → 前 top; 返回 (排名结果, 处理的并列组数)"""
    # 仅对"并列组内且已涨停"的股票拉分时(成本最小化)
    by_chg: dict[float, list[dict]] = {}
    for st in stocks:
        by_chg.setdefault(round(st["chg_pct"], 4), []).append(st)

    def _is_limit_up(st: dict) -> bool:
        # limit_up>0 排除退市股(数据源涨停价占位 -1.0 的假涨停)
        return bool(st["limit_up"] and st["limit_up"] > 0 and st["price"] > 0
                    and st["price"] >= st["limit_up"] - 0.005)

    tie_groups = 0
    for chg, group in by_chg.items():
        if len(group) <= 1:
            continue
        tie_groups += 1
        need = [st for st in group if _is_limit_up(st)]
        if not need:
            continue
        with ThreadPoolExecutor(max_workers=5) as ex:
            results = ex.map(
                lambda st: (st["ts_code"], fetch_limit_up_time(st["ts_code"], st["limit_up"])),
                need,
            )
        times = dict(results)
        for st in need:
            st["limit_up_time"] = times.get(st["ts_code"])
        for st in group:
            st.setdefault("limit_up_time", None)

    ranked = sorted(stocks, key=sort_key)[:top]
    for i, st in enumerate(ranked, 1):
        st["rank"] = i
        st["is_limit_up"] = bool(st.get("limit_up_time")) or _is_limit_up(st)
        st.pop("price", None)
        st.pop("limit_up", None)
    return ranked, tie_groups


# ── 主力资金并入 ──────────────────────────────────────────────────────
def attach_main_flow(ranked: list[dict]):
    """并发拉前 N 名资金流, 填入 main_inflow_wan / main_inflow_pct"""
    def xq_code(ts: str) -> str:
        return ("SZ" if ts.endswith(".SZ") else "SH" if ts.endswith(".SH") else "BJ") + ts[:6]
    flows = fetch_capital_flow([xq_code(st["ts_code"]) for st in ranked])
    for st in ranked:
        f = flows.get(xq_code(st["ts_code"])) or {}
        if "error" in f:
            st["main_inflow_wan"] = None
            st["main_inflow_pct"] = None
            continue
        net_wan = f["net_yuan"] / 10000.0 if f.get("net_yuan") is not None else None
        st["main_inflow_wan"] = round(net_wan, 2) if net_wan is not None else None
        st["main_inflow_pct"] = round(net_wan / st["amount_wan"] * 100, 2) if (
            net_wan is not None and st["amount_wan"]) else None


# ── API ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "port": PORT, "db": str(DB_PATH)}


@app.get("/api/sector/search")
def sector_search(name: str = Query(..., description="板块名称(模糊)"), limit: int = 20):
    cands = search_sectors(name, limit)
    if not cands:
        return JSONResponse({"error": f"未找到包含 '{name}' 的板块"}, status_code=404)
    return {"total": len(cands), "items": cands}


@app.get("/api/sector/rank")
def sector_rank(
    ts_code: str | None = Query(None, description="板块代码, 如 885525.TI"),
    name: str | None = Query(None, description="板块名称(精确, 重名返回 300)"),
    top: int = Query(20, ge=1, le=50),
):
    if not ts_code and not name:
        return JSONResponse({"error": "必须提供 ts_code 或 name"}, status_code=400)
    if ts_code:
        sector = get_sector_by_ts_code(ts_code)
        if not sector:
            return JSONResponse({"error": f"未找到板块 {ts_code}"}, status_code=404)
    else:
        matches = get_sectors_by_name(name)
        if not matches:
            return JSONResponse(
                {"error": f"未找到板块 '{name}'", "suggest": search_sectors(name, 10)},
                status_code=404)
        if len(matches) > 1:
            return JSONResponse(
                {"error": f"板块名 '{name}' 有 {len(matches)} 个, 请用 ts_code 指定", "items": matches},
                status_code=300)
        sector = matches[0]

    stocks, fetch_time, trade_date = get_members_with_snapshot(sector["ts_code"])
    if not stocks:
        return JSONResponse({"error": "该板块无成分股快照数据(可能快照缺失)"}, status_code=404)

    ranked, tie_groups = build_ranked(stocks, top)
    attach_main_flow(ranked)

    return {
        "trade_date": trade_date,
        "sector": sector,
        "data_time": fetch_time,
        "member_with_snapshot": len(stocks),
        "tie_handled": tie_groups,
        "stocks": ranked,
    }


if __name__ == "__main__":
    _log(f"sector_rank_server 启动, 端口 {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
