"""
Session 管理器：创建、轮询、查询、关闭、自动过期清理
"""

import json, os, time, threading, asyncio
from datetime import datetime, timezone

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)
SESSION_TTL = cfg["session"]["ttl_minutes"] * 60  # 秒


class Session:
    """单个会话的数据和状态"""

    def __init__(self, session_id: str, query: str, keyword: str, max_results: int,
                 mode: str = "segments", site: str | None = None, timelimit: str | None = None):
        self.session_id = session_id
        self.query = query
        self.keyword = keyword
        self.max_results = max_results
        self.mode = mode
        self.site = site
        self.timelimit = timelimit
        self.status = "processing"  # processing | done | error | closed
        self.created_at = time.time()
        self.elapsed = 0.0
        self.error = None
        self.articles = {}        # 文章列表（不含原文）
        self.segments = {}        # 要点列表
        self._texts = {}          # 原文（article_id -> segment_id -> text）

    def to_dict(self, include_texts: bool = False) -> dict:
        """序列化（不含原文，除非显式要求）"""
        d = {
            "session_id": self.session_id,
            "status": self.status,
            "mode": self.mode,
            "site": self.site,
            "timelimit": self.timelimit,
            "query": self.query,
            "keyword": self.keyword,
            "max_results": self.max_results,
            "created_at": datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
            "elapsed": round(self.elapsed, 1),
        }
        if self.status == "done":
            d["articles"] = self.articles
            d["segments"] = self.segments
        if self.status == "error":
            d["error"] = self.error
        if include_texts:
            d["_texts"] = self._texts
        return d


class SessionManager:
    """全局会话管理器，线程安全"""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        # 启动后台过期清理
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    # ---- 公开方法 ----

    def create(self, query: str, keyword: str = "", max_results: int = 5,
               mode: str = "segments", site: str | None = None, timelimit: str | None = None) -> str:
        session_id = f"s_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self)}"
        sess = Session(session_id, query, keyword, max_results, mode, site, timelimit)
        with self._lock:
            self._sessions[session_id] = sess
        return session_id

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess and sess.status == "closed":
                return None
            return sess

    def get_status(self, session_id: str) -> dict:
        sess = self.get(session_id)
        if not sess:
            return {"status": "not_found"}
        return sess.to_dict(include_texts=False)

    def set_done(self, session_id: str, articles: dict, segments: dict, texts: dict, elapsed: float):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "done"
            sess.articles = articles
            sess.segments = segments
            sess._texts = texts
            sess.elapsed = elapsed

    def set_error(self, session_id: str, error: str):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "error"
            sess.error = error

    def close(self, session_id: str) -> bool:
        """主动关闭会话"""
        sess = self.get(session_id)
        if not sess:
            return False
        with self._lock:
            sess.status = "closed"
        return True

    def get_segment_text(self, session_id: str, article_id: str, segment_id: str) -> str | None:
        sess = self.get(session_id)
        if not sess or sess.status != "done":
            return None
        return sess._texts.get(article_id, {}).get(segment_id)

    # ---- 后台过期清理 ----

    def _cleanup_loop(self):
        """每分钟检查一次过期会话"""
        while True:
            time.sleep(60)
            now = time.time()
            with self._lock:
                expired = [
                    sid for sid, sess in self._sessions.items()
                    if sess.status != "closed" and (now - sess.created_at) > SESSION_TTL
                ]
                for sid in expired:
                    self._sessions[sid].status = "closed"
                if expired:
                    print(f"[cleanup] 过期关闭 {len(expired)} 个会话", flush=True)
                # 清理已关闭的旧会话（超过 TTL + 10分钟）
                purge = [
                    sid for sid, sess in self._sessions.items()
                    if sess.status == "closed" and (now - sess.created_at) > SESSION_TTL + 600
                ]
                for sid in purge:
                    del self._sessions[sid]
                if purge:
                    print(f"[cleanup] 清理 {len(purge)} 个已关闭会话", flush=True)


# 全局单例
manager = SessionManager()
