"""
SQLite 数据库管理模块 — 线程安全版

每个线程独立持有自己的 SQLite 连接（threading.local），
避免多线程共享同一连接导致的 check_same_thread 和事务冲突问题。
"""
import sqlite3
import time
import threading
from pathlib import Path
from contextlib import contextmanager
from config import DB_PATH


class DatabaseManager:
    """SQLite 数据库管理器（线程安全）"""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DB_PATH)
        self._local = threading.local()

    def _get_conn(self):
        """获取当前线程的 SQLite 连接（按需创建）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def close(self):
        """关闭当前线程的连接"""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    def close_all(self):
        """谨慎使用：遍历所有线程的连接并关闭（仅兜底时调用）"""
        pass  # threading.local 不支持跨线程遍历

    @contextmanager
    def get_conn(self):
        conn = self._get_conn()
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

    def insert_batch(self, table, columns, rows, ignore=False):
        """批量插入（带事务）

        Args:
            ignore: True 时用 INSERT OR IGNORE（依赖表 UNIQUE 约束幂等）
        """
        if not rows:
            return 0
        cols = ",".join(columns)
        placeholders = ",".join(["?"] * len(columns))
        verb = "INSERT OR IGNORE" if ignore else "INSERT"
        sql = f"{verb} INTO {table} ({cols}) VALUES ({placeholders})"
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
