"""
fetch_midday_message.py — 午间消息补充（快讯、热门板块、跌停监控、异动检测）

功能:
  3. 今日快讯：财联社重要快讯 + 知识图谱关键词匹配（匹配度 > 0.3 才输出）
  4. 热门板块原因：热门板块上涨逻辑 + 个股关键词匹配板块标题
  5. 跌停监控：东方财富跌停板池中筛选关注的个股
  6. 异动检测：实时盘口异动（火箭发射、大笔买入等）全量循环 + 筛选

输入: 股票名称或代码列表
输出: {股票名: 格式化文本, ...}

使用方式:
  from fetch_midday_message import fetch_all
  data = fetch_all(["光启技术", "贝达药业"])

依赖:
  - levistock (as lk)
  - Neo4j 知识图谱 (keyword matching)
  - DB mid_stock_intraday / stg_tencent_snapshot (stock code 查询)

注意: 适用于交易日 11:30-11:35 调用；所有非今日日期使用 _prev_td 控制。
"""

import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import levistock as lk
from neo4j import GraphDatabase

# ── 路径配置 ──
MIDDAY_DIR = Path(__file__).resolve().parent
ETL_DIR = MIDDAY_DIR.parent.parent / "etl"
KG_DIR = MIDDAY_DIR.parent.parent / "knowledge_graph"
for d in [str(ETL_DIR), str(KG_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

from db_manager import DatabaseManager
from config import DB_PATH
from trade_calendar import prev_trading_day, get_calendar, last_trading_day

# ── 知识图谱配置 ──
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"

# ── 异动类型编码（全量循环用） ──
ALL_CHANGE_TYPES = [
    "8201", "8202", "8203", "8204", "8193", "8194",
    "8205", "8206", "8207", "8208", "64", "128",
    "8209", "8210", "8211", "8212", "8213", "8214",
    "8215", "8216", "8217", "8218",
]

CHANGE_TYPE_LABEL = {
    "8201": "火箭发射", "8202": "快速反弹", "8203": "加速下跌", "8204": "高台跳水",
    "8193": "大笔买入", "8194": "大笔卖出",
    "8205": "封涨停板", "8206": "封跌停板", "8207": "打开跌停板", "8208": "打开涨停板",
    "64": "有大买盘", "128": "有大卖盘",
    "8209": "竞价上涨", "8210": "竞价下跌",
    "8211": "高开5日线", "8212": "低开5日线",
    "8213": "向上缺口", "8214": "向下缺口",
    "8215": "60日新高", "8216": "60日新低",
    "8217": "60日大幅上涨", "8218": "60日大幅下跌",
}

db = DatabaseManager(str(DB_PATH))
_ERROR_LOG_DB = None


# ══════════════════════════════════════════════════════════════
# 通用工具
# ══════════════════════════════════════════════════════════════


def log_error(
    module: str = "fetch_midday_message",
    function: str = "",
    level: str = "ERROR",
    stock_name: str = "",
    ts_code: str = "",
    api_name: str = "",
    error_msg: str = "",
    detail: str = "",
    data_snapshot: str = "",
):
    """将错误记录写入数据库 error_log 表"""
    global _ERROR_LOG_DB
    try:
        if _ERROR_LOG_DB is None:
            _ERROR_LOG_DB = DatabaseManager(str(DB_PATH))
        import uuid
        batch_id_val = uuid.uuid4().hex[:12]
        _ERROR_LOG_DB.execute(
            """INSERT INTO error_log
               (batch_id, timestamp, module, function, level,
                stock_name, ts_code, api_name, error_type, error_msg,
                detail, data_snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batch_id_val,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                module[:64], function[:64], level[:16],
                stock_name[:32] if stock_name else None,
                ts_code[:32] if ts_code else None,
                api_name[:64] if api_name else None,
                error_msg.split(":")[0][:64] if ":" in error_msg else error_msg[:64],
                str(error_msg)[:1024],
                str(detail)[:2048] if detail else "",
                str(data_snapshot)[:2048] if data_snapshot else "",
            ),
        )
    except Exception:
        pass


def _get_stock_codes(stock_names: list[str]) -> dict[str, dict]:
    """获取股票的多格式代码映射

    Returns:
        {name: {ts_code, symbol, market_code}, ...}
    """
    result = {}
    if db.table_exists("mid_stock_intraday"):
        snap_times = db.execute(
            "SELECT DISTINCT fetch_time FROM mid_stock_intraday ORDER BY fetch_time DESC LIMIT 1"
        )
        if snap_times:
            snap_time = snap_times[0][0]
            placeholders = ",".join("?" * len(stock_names))
            rows = db.execute(
                f"SELECT ts_code, name FROM mid_stock_intraday "
                f"WHERE fetch_time=? AND name IN ({placeholders})",
                (snap_time, *stock_names)
            )
            for ts_code, name in rows:
                symbol = ts_code.split(".")[0]
                market_code = f"{'sh' if symbol.startswith('6') else 'sz'}{symbol}"
                cls_code = f"{symbol}.{'sh' if symbol.startswith('6') else 'sz'}"
                result[name] = {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "market_code": market_code,
                    "cls_code": cls_code,  # 财联社快讯中的代码格式: xxxxxx.sh / xxxxxx.sz
                }
    # 回退 Tushare
    for name in stock_names:
        if name in result:
            continue
        try:
            import tushare as ts
            pro = ts.pro_api()
            df = pro.stock_basic(name=name, list_status="L", fields="ts_code,symbol")
            if not df.empty:
                ts_code = df.iloc[0]["ts_code"]
                symbol = df.iloc[0]["symbol"]
                market_code = f"{'sh' if symbol.startswith('6') else 'sz'}{symbol}"
                cls_code = f"{symbol}.{'sh' if symbol.startswith('6') else 'sz'}"
                result[name] = {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "market_code": market_code,
                    "cls_code": cls_code,
                }
        except Exception:
            pass

    # 回退 name_to_code
    for name in stock_names:
        if name in result:
            continue
        try:
            MIDDAY_DIR = Path(__file__).parent
            sys.path.insert(0, str(MIDDAY_DIR))
            from name_to_code import name_info
            info = name_info(name)
            if info:
                ts_code = info["ts_code"]
                symbol = ts_code.split(".")[0]
                market_code = f"{'sh' if symbol.startswith('6') else 'sz'}{symbol}"
                cls_code = f"{symbol}.{'sh' if symbol.startswith('6') else 'sz'}"
                result[name] = {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "market_code": market_code,
                    "cls_code": cls_code,
                }
        except Exception:
            pass

    return result


def _tushare_trade_date() -> str:
    """Tushare 日终数据日期：T-1（上一个交易日）"""
    return prev_trading_day(datetime.now().strftime("%Y%m%d"))


def _list_dates(d1: str, d2: str) -> list[str]:
    """YYYYMMDD 日期列表 [d1, d2]"""
    dates = []
    cur = datetime.strptime(d1, "%Y%m%d")
    end = datetime.strptime(d2, "%Y%m%d")
    while cur <= end:
        dates.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    return dates


# ══════════════════════════════════════════════════════════════
# Neo4j 知识图谱关键词查询
# ══════════════════════════════════════════════════════════════

_NEO4J_DRIVER = None


def _get_neo4j_driver():
    global _NEO4J_DRIVER
    if _NEO4J_DRIVER is None:
        _NEO4J_DRIVER = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS)
        )
    return _NEO4J_DRIVER


def _neo4j_keywords_for_matching(ts_code: str) -> list[dict]:
    """获取个股的行业类 MG 关键词（含权重和 grade），用于财联社快讯匹配

    只使用 match_class='MG' 的行业类关键词（NM 类无匹配意义，已剔除）。
    权重规则（已融合 grade 倍率）:
      - 基础权重：boosted（同时属于概念+行业两类）→ 2.0，其他行业类 → 1.0
      - grade 倍率：MG1 ×0.8, MG2 ×1.0, MG3 ×1.2
      - 最终权重 = 基础权重 × grade 倍率

    Returns:
        [{keyword, weight, match_class, grade}, ...]
    """
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            result = session.run(
                """MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword)
                   WHERE '行业' IN k.categories
                     AND k.match_class = 'MG'
                   RETURN k.keyword AS keyword,
                          k.categories AS categories,
                          k.boosted AS boosted,
                          k.grade AS grade""",
                code=ts_code,
            )
            keywords = []
            for r in result:
                boosted = r.get("boosted", False)
                grade = r.get("grade", 2)  # 默认为 MG2（不变）
                base_weight = 2.0 if boosted else 1.0
                grade_factor = {1: 0.8, 2: 1.0, 3: 1.2}.get(grade, 1.0)
                weight = base_weight * grade_factor
                keywords.append({
                    "keyword": r["keyword"],
                    "weight": weight,
                    "match_class": "MG",
                    "grade": grade,
                })
            return keywords
    except Exception as e:
        log_error(function="_neo4j_keywords_for_matching",
                  ts_code=ts_code, api_name="Neo4j", error_msg=str(e))
        return []


def _neo4j_all_keywords(ts_code: str) -> list[dict]:
    """获取个股所有 match_class='MG' 的关键词（含 grade），用于板块匹配

    NM 类关键词无匹配意义，已过滤。

    Returns:
        [{keyword, grade, match_class}, ...]
    """
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            result = session.run(
                """MATCH (s:Stock {code: $code})-[:HAS_KEY]->(k:Keyword)
                   WHERE k.match_class = 'MG'
                   RETURN DISTINCT k.keyword AS keyword,
                          k.grade AS grade,
                          k.match_class AS match_class""",
                code=ts_code,
            )
            return [
                {
                    "keyword": r["keyword"],
                    "grade": r.get("grade", 2),
                    "match_class": r.get("match_class", "MG"),
                }
                for r in result
            ]
    except Exception as e:
        log_error(function="_neo4j_all_keywords",
                  ts_code=ts_code, api_name="Neo4j", error_msg=str(e))
        return []


def _match_news_score(stock_ts_code: str, article_text: str) -> float:
    """计算单只股票与快讯文本的匹配度

    仅使用 match_class='MG' 的行业类关键词（NM 类已过滤）。
    weight 已融合 grade 倍率：MG1×0.8 / MG2×1.0 / MG3×1.2。
    score = min(1.0, Σweight / 4.0)

    Args:
        stock_ts_code: ts_code 格式（如 "300750.SZ"）
        article_text: 快讯全文

    Returns:
        匹配度 0.0~1.0
    """
    keywords = _neo4j_keywords_for_matching(stock_ts_code)
    if not keywords:
        return 0.0

    effective_m = 0.0
    for kw in keywords:
        if kw["keyword"] in article_text:
            effective_m += kw["weight"]

    if effective_m <= 0:
        return 0.0

    return min(1.0, effective_m / 4.0)


# ══════════════════════════════════════════════════════════════
# 3. 今日快讯 — 财联社重要快讯 + 知识图谱匹配
# ══════════════════════════════════════════════════════════════

def _fetch_telegraph_news(date_from: str, date_to: str) -> list[dict]:
    """获取财联社重要快讯（日期范围），返回 [{title, content, time}, ...]

    Args:
        date_from: YYYYMMDD 起始日期（上一个交易日）
        date_to: YYYYMMDD 截止日期（今日）
    """
    all_news = []
    dates = _list_dates(date_from, date_to)

    for d in dates:
        date_str = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        try:
            items = lk.news_telegraph_cls(date=date_str, category="important")
            if items:
                all_news.extend(items)
        except Exception as e:
            log_error(function="_fetch_telegraph_news",
                      api_name="lk.news_telegraph_cls", error_msg=str(e),
                      detail=f"date={date_str}")

    # 过滤：只保留今日 11:30 之前的消息
    today_str = datetime.now().strftime("%Y-%m-%d")
    cutoff = f"{today_str} 11:30:00"

    filtered = []
    for item in all_news:
        t = item.get("time", "")
        # 非今日消息全部保留（昨日及之前的），今日只保留 11:30 之前的
        if t.startswith(today_str):
            if t <= cutoff:
                filtered.append(item)
        else:
            filtered.append(item)

    return filtered


def _match_news_for_stocks(
    news_items: list[dict],
    stocks: dict[str, dict],  # {name: {ts_code, cls_code, symbol}}
) -> dict[str, list[dict]]:
    """将快讯匹配到关注的股票

    匹配规则（按条目逐条匹配，一条快讯可匹配多只股票）:
      1. 股票中文名在 title/content 中
      2. 股票代码 (xxxxxx.sz/xxxxxx.sh) 在 title/content 中
      3. 知识图谱关键词匹配度 > 0.3

    Returns:
        {stock_name: [{title, content, time, match_type, match_score, keyword_matches}], ...}
    """
    result = {name: [] for name in stocks}

    for item in news_items:
        title = item.get("title", "")
        content = item.get("content", "")
        full_text = f"{title} {content}".lower()
        item_time = item.get("time", "")

        for name, info in stocks.items():
            ts_code = info.get("ts_code", "")
            symbol = info.get("symbol", "")

            # 先计算关键词匹配信息（仅关键词匹配需要）
            raw_score = _match_news_score(ts_code, full_text) if ts_code else 0.0

            # 判定匹配方式及最终分数
            matched = False
            match_type = ""
            match_score = None
            matched_keywords = []

            # 1. 股票中文名匹配
            if name in title or name in content:
                matched = True
                match_type = "名称匹配"
                match_score = 1.0
                matched_keywords = [name]

            # 2. 股票代码匹配（纯数字 xxxxxx）
            elif symbol and symbol in full_text:
                matched = True
                match_type = "代码匹配"
                match_score = 1.0
                matched_keywords = [symbol]

            # 3. 知识图谱关键词匹配（名称/代码均未命中时 *0.75）
            else:
                adjusted = raw_score * 0.75
                if adjusted > 0.3:
                    matched = True
                    match_type = "关键词匹配"
                    match_score = round(adjusted, 4)
                    # 记录匹配到的行业关键词
                    kws = _neo4j_keywords_for_matching(ts_code)
                    matched_keywords = [kw["keyword"] for kw in kws if kw["keyword"] in full_text]

            if matched:
                result[name].append({
                    "title": title,
                    "content": content,
                    "time": item_time,
                    "match_type": match_type,
                    "match_score": match_score,
                    "keyword_matches": matched_keywords,
                })

    return result


def fetch_telegraph_news(
    stock_names: list[str],
    stocks: dict[str, dict],
    date_from: str,
    date_to: str,
) -> dict[str, dict]:
    """统一入口：获取快讯并匹配

    Returns:
        {name: {has_data: bool, news: [...]}}
    """
    news_items = _fetch_telegraph_news(date_from, date_to)
    if not news_items:
        return {name: {"has_data": False, "news": []} for name in stock_names}

    matched = _match_news_for_stocks(news_items, stocks)
    return {
        name: {
            "has_data": bool(matched.get(name)),
            "news": matched.get(name, []),
        }
        for name in stock_names
    }


# ══════════════════════════════════════════════════════════════
# 4. 热门板块原因 — 板块上涨逻辑 + 个股关键词匹配
# ══════════════════════════════════════════════════════════════

def _sector_text(sector: dict) -> str:
    """获取板块的完整文本（用于全文匹配）"""
    parts = [sector.get("secu_name", ""), sector.get("up_reason", "")]
    for stock in sector.get("stock_list", []):
        parts.append(stock.get("secu_name", ""))
        parts.append(stock.get("up_reason", ""))
        for tag in stock.get("up_tags", []):
            parts.append(tag)
    return " ".join(parts)


def fetch_hot_sectors(
    stock_names: list[str],
    stocks: dict[str, dict],
) -> dict[str, dict]:
    """获取热门板块上涨原因并匹配到个股

    匹配规则（由总到分，逐板块→逐股）:
      Step 1: 用个股所有关键词（不分种类）匹配板块标题 secu_name，匹配到则返回该板块
      Step 2: 如标题无匹配，用个股名称匹配板块全文，匹配到则返回

    建议对匹配阶段使用线程池加速（I/O 密集在 Neo4j 关键词查询）

    Returns:
        {name: {has_data: bool, sectors: [...]}}
    """
    try:
        hot_plates = lk.get_sector_hot_plates()
    except Exception as e:
        log_error(function="fetch_hot_sectors",
                  api_name="lk.get_sector_hot_plates", error_msg=str(e))
        return {name: {"has_data": False, "sectors": []} for name in stock_names}

    if not hot_plates:
        return {name: {"has_data": False, "sectors": []} for name in stock_names}

    result = {name: {"has_data": False, "sectors": []} for name in stock_names}

    def _match_one_stock(name: str) -> tuple[str, list]:
        """匹配单只股票 — 用于线程池"""
        info = stocks.get(name)
        if not info:
            return (name, [])

        ts_code = info.get("ts_code", "")
        sectors_matched = []

        # 获取个股所有 match_class='MG' 的关键词（NM 已过滤）
        keywords = _neo4j_all_keywords(ts_code) if ts_code else []
        keywords_lower = [kw["keyword"].lower() for kw in keywords]

        for plate in hot_plates:
            secu_name = plate.get("secu_name", "")
            secu_name_lower = secu_name.lower()

            # Step 1: 用关键词匹配板块标题
            keyword_hit = False
            matched_keywords = []
            for i, kw_lower in enumerate(keywords_lower):
                if kw_lower and kw_lower in secu_name_lower:
                    keyword_hit = True
                    matched_keywords.append(keywords[i]["keyword"])

            if keyword_hit:
                sectors_matched.append({
                    "sector": plate,
                    "match_method": "关键词匹配板块标题",
                    "matched_keywords": matched_keywords,
                })
                continue

            # Step 2: 用个股名称匹配板块全文
            full_text = _sector_text(plate).lower()
            if name.lower() in full_text:
                sectors_matched.append({
                    "sector": plate,
                    "match_method": "股票名称匹配板块全文",
                    "matched_keywords": [],
                })

        return (name, sectors_matched)

    # 使用线程池并行匹配
    with ThreadPoolExecutor(max_workers=min(8, len(stock_names) or 1)) as executor:
        futures = {executor.submit(_match_one_stock, name): name for name in stock_names}
        for future in as_completed(futures):
            name, sectors = future.result()
            result[name] = {
                "has_data": bool(sectors),
                "sectors": sectors,
            }

    return result


# ══════════════════════════════════════════════════════════════
# 5. 跌停监控 — 东方财富跌停板池
# ══════════════════════════════════════════════════════════════

def fetch_limit_down(
    stock_names: list[str],
    stocks: dict[str, dict],
    trade_date: str | None = None,
) -> dict[str, dict]:
    """获取跌停板池，筛选关注的个股

    Args:
        trade_date: YYYYMMDD, None 默认当天

    Returns:
        {name: {has_data: bool, items: [...]}}
    """
    try:
        dt_pool = lk.stock_dt_pool_em(date=trade_date)
    except Exception as e:
        log_error(function="fetch_limit_down",
                  api_name="lk.stock_dt_pool_em", error_msg=str(e))
        return {name: {"has_data": False, "items": []} for name in stock_names}

    if not dt_pool:
        return {name: {"has_data": False, "items": []} for name in stock_names}

    # 建立 symbol 到 stock_name 的快速查找
    symbol_to_name = {info["symbol"]: name for name, info in stocks.items()}
    name_set = set(stock_names)

    result = {name: {"has_data": False, "items": []} for name in stock_names}

    for item in dt_pool:
        stock_code = item.get("stock_code", "")  # 纯数字
        stock_name = item.get("stock_name", "")

        # 按代码匹配（纯数字 xxxxxx）
        if stock_code in symbol_to_name:
            name = symbol_to_name[stock_code]
            result[name]["has_data"] = True
            result[name]["items"].append(item)
        # 按名称匹配
        elif stock_name in name_set:
            result[stock_name]["has_data"] = True
            result[stock_name]["items"].append(item)

    return result


# ══════════════════════════════════════════════════════════════
# 6. 异动检测 — 全量循环异动类型 + 筛选个股
# ══════════════════════════════════════════════════════════════

def _parse_change_pct(change_pct_str: str) -> tuple[float, float]:
    """解析 change_pct 字段 "0.028079,25.63000,0.028079"
    返回 (涨跌幅百分比, 价格)

    对于 "有大买盘"/"有大卖盘" 等类型，change_pct 可能是量/额而非百分比，
    数值极大（如 16090000），此时不解析为涨跌幅，返回 (None, 价格)
    """
    if not change_pct_str or not isinstance(change_pct_str, str):
        return (None, 0.0)
    parts = change_pct_str.split(",")
    try:
        pct_raw = float(parts[0]) if parts[0] else 0.0
    except (ValueError, IndexError):
        pct_raw = 0.0
    try:
        price = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
    except (ValueError, IndexError):
        price = 0.0

    # 异常大的数值（>100 即超过 10000%）说明不是涨跌幅格式
    if abs(pct_raw) > 100:
        return (None, round(price, 2))

    pct = pct_raw * 100
    return (round(pct, 2), round(price, 2))


def fetch_abnormal_movements(
    stock_names: list[str],
    stocks: dict[str, dict],
) -> dict[str, dict]:
    """获取全量盘口异动并筛选关注的个股

    流程:
      1. 循环 ALL_CHANGE_TYPES 获取各类型异动列表
      2. 去重（同一股票同一时间只保留一条）
      3. 用股票名称/代码筛选

    Returns:
        {name: {has_data: bool, changes: [{type, time, change_pct, price, ...}], ...}}
    """
    # Step 1: 全量循环所有异动类型
    all_changes_raw = []
    seen_keys = set()

    for ct in ALL_CHANGE_TYPES:
        try:
            items = lk.stock_changes_em(change_type=ct, filter_st=True)
            for item in items:
                stock_code = item.get("stock_code", "")
                # 去重 key: stock_code + time
                key = f"{stock_code}_{item.get('time', '')}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                item["change_type_code"] = ct
                item["change_type_label"] = CHANGE_TYPE_LABEL.get(ct, ct)
                # 解析 change_pct
                pct_val, price_val = _parse_change_pct(item.get("change_pct", ""))
                item["change_pct_parsed"] = pct_val
                item["price_parsed"] = price_val
                all_changes_raw.append(item)
        except Exception as e:
            log_error(function="fetch_abnormal_movements",
                      api_name=f"lk.stock_changes_em(change_type={ct})",
                      error_msg=str(e))

    if not all_changes_raw:
        return {name: {"has_data": False, "changes": []} for name in stock_names}

    # 建立 symbol 到 name 的映射
    symbol_to_name = {info["symbol"]: name for name, info in stocks.items()}
    name_set = set(stock_names)

    result = {name: {"has_data": False, "changes": []} for name in stock_names}

    for item in all_changes_raw:
        stock_code = item.get("stock_code", "")
        stock_name = item.get("stock_name", "")

        matched_name = None
        if stock_code in symbol_to_name:
            matched_name = symbol_to_name[stock_code]
        elif stock_name in name_set:
            matched_name = stock_name

        if matched_name:
            result[matched_name]["has_data"] = True
            result[matched_name]["changes"].append(item)

    # 按时间排序
    for name in stock_names:
        if result[name]["has_data"]:
            result[name]["changes"].sort(key=lambda x: x.get("time", ""))

    return result


# ══════════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════════

def fetch_all(stock_names: list[str]) -> dict[str, str]:
    """统一消息取数入口: 快讯 + 热门板块 + 跌停 + 异动

    Args:
        stock_names: ['光启技术', '贝达药业']

    Returns:
        {name: formatted_string, "warning": {ts_code: {"non_critical": [section_names]}}}
        warning 为数据完整性检查结果，空 dict 表示全部正常
    """
    # 1. 股票代码映射
    stocks = _get_stock_codes(stock_names)
    if not stocks:
        return {n: f"## {n}\n\n❌ 未找到股票信息" for n in stock_names}

    # 2. 日期计算
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    prev_td = _tushare_trade_date()

    # 3. 并行取数
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_news = pool.submit(
            fetch_telegraph_news, stock_names, stocks, prev_td, today_str
        )
        fut_sectors = pool.submit(fetch_hot_sectors, stock_names, stocks)
        fut_limit = pool.submit(fetch_limit_down, stock_names, stocks)
        fut_changes = pool.submit(fetch_abnormal_movements, stock_names, stocks)

        news_data = fut_news.result()
        sectors_data = fut_sectors.result()
        limit_data = fut_limit.result()
        changes_data = fut_changes.result()

    # 4. 组装输出
    result = {}
    warnings = {}
    for name in stock_names:
        info = stocks.get(name, {})
        ts_code = info.get("ts_code", "")
        lines = []

        # ── 3. 今日快讯 ──
        nd = news_data.get(name, {})
        if nd.get("has_data"):
            lines.append("## 【今日快讯】")
            for i, item in enumerate(nd["news"], 1):
                mt = item.get("match_type", "")
                ms = item.get("match_score")
                score_str = f" | 相关度: {ms:.2f}" if ms else ""
                kw_str = ""
                if item.get("keyword_matches"):
                    kw_str = f" | 相关关键词: {', '.join(item['keyword_matches'][:5])}"
                lines.append(f"  {i}. [{item.get('time', '')}] {item.get('title', '')}")
                lines.append(f"     （相关方式: {mt}{score_str}{kw_str}）")
                content_text = item.get("content", "")
                lines.append(f"     {content_text}")
                lines.append("")

        # ── 4. 热门板块原因 ──
        sd = sectors_data.get(name, {})
        if sd.get("has_data"):
            lines.append("## 【热门板块上涨原因】")
            for si in sd["sectors"]:
                sector = si["sector"]
                secu_name = sector.get("secu_name", "")
                change = sector.get("change", 0)
                change_pct = f"{change * 100:+.2f}%" if isinstance(change, (int, float)) else ""

                lines.append(f"  ### {secu_name} ({change_pct})")

                up_reason = sector.get("up_reason", "")
                if up_reason:
                    lines.append(f"  **上涨原因**: {up_reason}")

                stock_list = sector.get("stock_list", [])
                if stock_list:
                    # 找到本股在板块中的位置（如果有）
                    my_symbol = info.get("symbol", "")
                    my_found = False
                    for s in stock_list:
                        s_code = s.get("secu_code", "")  # "sz000533"
                        s_name = s.get("secu_name", "")
                        if my_symbol and my_symbol in s_code:
                            my_found = True
                            break

                    # 最多展示 10 只
                    for s in stock_list[:10]:
                        s_code = s.get("secu_code", "")
                        s_name = s.get("secu_name", "")
                        s_chg = s.get("change", 0)
                        s_pct = f"{s_chg * 100:+.2f}%" if isinstance(s_chg, (int, float)) else ""
                        s_tags = s.get("up_tags", [])
                        tag_str = f" | 标签:{s_tags}" if s_tags else ""
                        lines.append(f"    - {s_name} | 涨幅:{s_pct}{tag_str}")

                lines.append("")

        # ── 5. 跌停监控 ──
        ld = limit_data.get(name, {})
        if ld.get("has_data"):
            lines.append("## 【跌停监控】")
            lines.append("")
            lines.append("  | 股票名称 | 股票代码 | 板块 |")
            lines.append("  |:---------|:---------|:-----|")
            for item in ld["items"]:
                sname = item.get("stock_name", "")
                scode = item.get("stock_code", "")
                sec = item.get("sector", "")
                lines.append(f"  | {sname} | {scode} | {sec} |")
            lines.append("")

        # ── 6. 异动检测 ──
        cd = changes_data.get(name, {})
        if cd.get("has_data"):
            lines.append("## 【盘中异动监测】")
            # 按异动类型分组展示
            by_type = {}
            for ch in cd["changes"]:
                ct = ch.get("change_type_label", "其他")
                by_type.setdefault(ct, []).append(ch)

            for ctype, chs in by_type.items():
                lines.append(f"  ● {ctype}（{len(chs)} 次）")
                for ch in chs:
                    t = ch.get("time", "")
                    # 格式化时间 HH:MM:SS
                    if len(t) >= 6:
                        t_fmt = f"{t[:2]}:{t[2:4]}:{t[4:6]}"
                    else:
                        t_fmt = t
                    pct = ch.get("change_pct_parsed", 0)
                    price = ch.get("price_parsed", 0)
                    pct_str = f"{pct:+.2f}%" if pct is not None else ""
                    price_str = f" {price:.2f}元" if price else ""
                    lines.append(f"    {t_fmt} 涨跌幅:{pct_str}{price_str}")
                lines.append("")

        # 如果没有任何消息数据，给出提示
        has_any = (
            nd.get("has_data", False)
            or sd.get("has_data", False)
            or ld.get("has_data", False)
            or cd.get("has_data", False)
        )
        if not has_any:
            lines.append("（今日暂无相关消息数据）")
            lines.append("")

        result[name] = "\n".join(lines)

        # ── 数据完整性检查 ──
        # 三个非关键部分全部为空时才记录 warning
        msg_has_data = (
            nd.get("has_data", False)
            or sd.get("has_data", False)
            or cd.get("has_data", False)
        )
        if not msg_has_data:
            warnings[ts_code] = "no data"

    result["warning"] = warnings
    return result


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args or not args:
        print("用法: python fetch_midday_message.py <名称1> [名称2 ...]")
        print("示例: python fetch_midday_message.py 宁德时代 比亚迪")
        sys.exit(0)

    result = fetch_all(args)
    print("\n---\n".join(result.values()))


if __name__ == "__main__":
    main()
