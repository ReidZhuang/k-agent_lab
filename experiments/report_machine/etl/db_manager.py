"""
SQLite 数据库管理模块
"""
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from config import DB_PATH


class DatabaseManager:
    """SQLite 数据库管理器"""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DB_PATH)
        self._conn = None

    def connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def get_conn(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql, params=None):
        with self.get_conn() as conn:
            cur = conn.execute(sql, params or [])
            if cur.description:
                return cur.fetchall()
            return []

    def executemany(self, sql, params_list):
        with self.get_conn() as conn:
            conn.executemany(sql, params_list)

    def insert_batch(self, table, columns, rows):
        """批量插入（带事务）"""
        if not rows:
            return 0
        cols = ",".join(columns)
        placeholders = ",".join(["?"] * len(columns))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        with self.get_conn() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def table_exists(self, table_name):
        r = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return len(r) > 0

    def count_rows(self, table_name, where=None):
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        r = self.execute(sql)
        return r[0][0] if r else 0

    def init_schema(self, sql_path=None):
        if sql_path is None:
            sql_path = Path(__file__).parent / "init_schema.sql"
        sql = Path(sql_path).read_text("utf-8")
        with self.get_conn() as conn:
            conn.executescript(sql)
        print(f"✅ Schema initialized from {sql_path}")

    def log_update(self, batch_id, api_name, table_name, trade_date,
                   start_time, end_time, status, rows_fetched=0,
                   rows_written=0, error_msg=""):
        self.execute("""
            INSERT INTO meta_update_log
            (batch_id, api_name, table_name, trade_date,
             start_time, end_time, status, rows_fetched,
             rows_written, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (batch_id, api_name, table_name, trade_date,
              start_time, end_time, status, rows_fetched,
              rows_written, error_msg))
