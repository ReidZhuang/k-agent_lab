"""
kg_loader.py — 关键词文件解析 → SQLite meta_sector_keywords

解析 keyword_tree_final_v2.md，提取每个板块的 (source, ts_code, name, category, keywords)，
去重后写入 meta_sector_keywords 表。
"""

import re
import sqlite3
from config import DB_PATH, KEYWORD_FILE

# 类别映射：章节标题 → 分类
CATEGORY_MAP = {
    "概念指数": "概念",
    "行业指数": "行业",
    "地域指数": "地区",
    "概念板块": "概念",
    "行业板块": "行业",
    "地域板块": "地区",
    "地区板块": "地区",
}

# 数据源映射
SOURCE_MAP = {
    "同花顺": "THS",
    "东方财富": "DC",
    "通达信": "TDX",
}


def _detect_category(header: str) -> str | None:
    """从节标题判断分类"""
    for kw, cat in CATEGORY_MAP.items():
        if kw in header:
            return cat
    return None


def _detect_source(section: str) -> str | None:
    """从章标题判断数据源"""
    for kw, src in SOURCE_MAP.items():
        if kw in section:
            return src
    return None


def parse_keyword_file() -> list[dict]:
    """解析关键词 md 文件

    Returns:
        [{source, ts_code, name, category, keywords}]
        其中 keywords 是去重后的列表
    """
    text = KEYWORD_FILE.read_text(encoding="utf-8")
    lines = text.split("\n")

    entries = []
    source = None
    category = None

    for line in lines:
        stripped = line.strip()

        # 检测章标题：## 一、同花顺...
        m = re.match(r"^##\s+(.+)", stripped)
        if m:
            source = _detect_source(m.group(1))
            continue

        # 检测节标题：### 1. N — 概念指数...
        m = re.match(r"^###\s+(.+)", stripped)
        if m:
            category = _detect_category(m.group(1))
            continue

        # 检测条目：- `CODE` keywords
        m = re.match(r"^- `([^`]+)`\s*(.*)", stripped)
        if not m or not source or not category:
            continue

        ts_code = m.group(1)
        kw_str = m.group(2).strip()

        # 解析关键词：第一个是板块名称，后面是关键词
        parts = [p.strip() for p in kw_str.split(";") if p.strip()]
        if not parts:
            continue

        name = parts[0]  # 板块名

        if len(parts) > 1:
            # 有关键词列表（概念/行业类）
            raw_keywords = parts[1:]
            # 板块内去重，同时排除与板块名重复的词
            seen = {name}
            deduped = []
            for kw in raw_keywords:
                if kw not in seen:
                    seen.add(kw)
                    deduped.append(kw)
        else:
            # 无额外关键词（地区类：整行只有"福建"之类的板块名）
            # 把板块名本身作为关键词
            deduped = [name]

        entries.append({
            "source": source,
            "ts_code": ts_code,
            "name": name,
            "category": category,
            "keywords": deduped,
        })

    return entries


def init_schema(conn):
    """创建 meta_sector_keywords 表"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta_sector_keywords (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            source   TEXT NOT NULL,
            ts_code  TEXT NOT NULL,
            name     TEXT,
            category TEXT NOT NULL,
            keywords TEXT NOT NULL,
            UNIQUE(source, ts_code)
        );
        CREATE INDEX IF NOT EXISTS idx_msk_code ON meta_sector_keywords(ts_code);
        CREATE INDEX IF NOT EXISTS idx_msk_source ON meta_sector_keywords(source);
        CREATE INDEX IF NOT EXISTS idx_msk_cat ON meta_sector_keywords(category);
    """)


def load_to_db(entries, conn):
    """将解析结果写入 meta_sector_keywords"""
    cur = conn.cursor()
    cur.execute("DELETE FROM meta_sector_keywords")
    conn.commit()

    inserted = 0
    for e in entries:
        kw_str = ";".join(e["keywords"])
        cur.execute(
            """INSERT OR IGNORE INTO meta_sector_keywords
               (source, ts_code, name, category, keywords)
               VALUES (?, ?, ?, ?, ?)""",
            (e["source"], e["ts_code"], e["name"], e["category"], kw_str),
        )
        if cur.rowcount:
            inserted += 1

    conn.commit()
    return inserted


def main():
    print(f"[loader] 解析 {KEYWORD_FILE.name} ...")
    entries = parse_keyword_file()
    print(f"[loader] 共解析 {len(entries)} 个板块")

    # 统计去重
    total_kw = sum(len(e["keywords"]) for e in entries)
    print(f"[loader] 关键词总数（去重后）: {total_kw}")

    # 按数据源统计
    from collections import Counter
    src_count = Counter(e["source"] for e in entries)
    cat_count = Counter(e["category"] for e in entries)
    for src, n in sorted(src_count.items()):
        print(f"  {src}: {n}")
    for cat, n in sorted(cat_count.items()):
        print(f"  {cat}: {n}")

    conn = sqlite3.connect(str(DB_PATH))
    init_schema(conn)
    n = load_to_db(entries, conn)
    conn.close()
    print(f"[loader] 写入 SQLite: {n} 条")
    print("[loader] ✅ 完成")


if __name__ == "__main__":
    main()
