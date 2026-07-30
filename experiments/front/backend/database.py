"""
数据库操作模块
"""
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH


class Database:
    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def get_conn(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params=None):
        with self.get_conn() as conn:
            cur = conn.execute(sql, params or [])
            if cur.description:
                return [dict(r) for r in cur.fetchall()]
            return []

    def execute_one(self, sql: str, params=None):
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    # ── 建表 ──

    def _init_tables(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT NOT NULL UNIQUE,
                    password    TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS stock_pool (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    ts_code     TEXT NOT NULL,
                    stock_name  TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(user_id, ts_code)
                );

                CREATE TABLE IF NOT EXISTS user_favorite (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    file_path   TEXT NOT NULL,
                    file_name   TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(user_id, file_path)
                );

                CREATE TABLE IF NOT EXISTS stg_stock_basic (
                    ts_code     TEXT PRIMARY KEY,
                    symbol      TEXT,
                    name        TEXT,
                    area        TEXT,
                    industry    TEXT,
                    market      TEXT,
                    list_date   TEXT,
                    update_date TEXT
                );
            """)

    # ── 用户 ──

    def create_user(self, username: str, password_hash: str):
        self.execute(
            "INSERT OR IGNORE INTO user (username, password) VALUES (?, ?)",
            (username, password_hash),
        )

    def get_user_by_username(self, username: str):
        return self.execute_one(
            "SELECT id, username, password FROM user WHERE username=?", (username,)
        )

    def get_user_by_id(self, user_id: int):
        return self.execute_one(
            "SELECT id, username FROM user WHERE id=?", (user_id,)
        )

    # ── 股票池 ──

    def add_stock_to_pool(self, user_id: int, ts_code: str, stock_name: str):
        self.execute(
            "INSERT OR IGNORE INTO stock_pool (user_id, ts_code, stock_name) VALUES (?, ?, ?)",
            (user_id, ts_code, stock_name),
        )

    def remove_stock_from_pool(self, user_id: int, ts_code: str):
        self.execute(
            "DELETE FROM stock_pool WHERE user_id=? AND ts_code=?",
            (user_id, ts_code),
        )

    def get_stock_pool(self, user_id: int):
        return self.execute(
            "SELECT ts_code, stock_name, created_at FROM stock_pool WHERE user_id=? ORDER BY created_at",
            (user_id,),
        )

    # ── 股票基础信息 ──

    def refresh_stock_basic(self, df_rows: list[tuple]):
        """全量替换 stg_stock_basic"""
        with self.get_conn() as conn:
            conn.execute("DELETE FROM stg_stock_basic")
            conn.executemany(
                "INSERT INTO stg_stock_basic (ts_code, symbol, name, area, industry, market, list_date, update_date) VALUES (?,?,?,?,?,?,?,?)",
                df_rows,
            )

    def search_stock(self, keyword: str):
        """按名称或代码模糊搜索"""
        kw = f"%{keyword}%"
        return self.execute(
            "SELECT ts_code, symbol, name, industry FROM stg_stock_basic WHERE name LIKE ? OR symbol LIKE ? OR ts_code LIKE ? LIMIT 20",
            (kw, kw, kw),
        )

    def get_stock_by_names(self, names: list[str]):
        """按名称或代码匹配股票（先精确名称，再精确代码，再模糊名称）"""
        placeholders = ",".join("?" * len(names))
        # 1. 按名称精确匹配
        rows = self.execute(
            f"SELECT ts_code, symbol, name, industry FROM stg_stock_basic WHERE name IN ({placeholders})",
            names,
        )
        matched = set(r["name"] for r in rows)
        unmatched = [n for n in names if n not in matched]
        if not unmatched:
            return rows

        # 2. 按代码精确匹配
        code_params = [f"%{n}%" for n in unmatched]
        code_conditions = " OR ".join(["symbol LIKE ?" for _ in unmatched])
        code_rows = self.execute(
            f"SELECT ts_code, symbol, name, industry FROM stg_stock_basic WHERE {code_conditions}",
            code_params,
        )
        matched_symbols = set(r["symbol"] for r in code_rows)
        rows.extend(code_rows)

        # 3. 仍未匹配的 → 按名称模糊匹配
        still_unmatched = [n for n in unmatched if n not in matched_symbols and
                          not any(n in r["name"] for r in rows)]
        if still_unmatched:
            fuzzy_conditions = " OR ".join(["name LIKE ?" for _ in still_unmatched])
            fuzzy_params = [f"%{n}%" for n in still_unmatched]
            fuzzy_rows = self.execute(
                f"SELECT ts_code, symbol, name, industry FROM stg_stock_basic WHERE {fuzzy_conditions}",
                fuzzy_params,
            )
            rows.extend(fuzzy_rows)

        return rows

    # ── 收藏夹 ──

    def add_favorite(self, user_id: int, file_path: str, file_name: str):
        self.execute(
            "INSERT OR IGNORE INTO user_favorite (user_id, file_path, file_name) VALUES (?, ?, ?)",
            (user_id, file_path, file_name),
        )

    def remove_favorite(self, user_id: int, file_path: str):
        self.execute(
            "DELETE FROM user_favorite WHERE user_id=? AND file_path=?",
            (user_id, file_path),
        )

    def get_favorites(self, user_id: int):
        return self.execute(
            "SELECT file_path, file_name, created_at FROM user_favorite WHERE user_id=? ORDER BY created_at",
            (user_id,),
        )

    def is_favorite(self, user_id: int, file_path: str):
        r = self.execute_one(
            "SELECT 1 FROM user_favorite WHERE user_id=? AND file_path=?",
            (user_id, file_path),
        )
        return r is not None


db = Database()
