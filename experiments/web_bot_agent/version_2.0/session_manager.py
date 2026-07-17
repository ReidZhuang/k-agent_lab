"""
Session 管理器（v2.0）— 支持双阶段状态:
  - processing: Phase 1 运行中
  - preview:    Phase 1 完成（预览可见），Phase 2 进行中
  - done:       Phase 2 完成
  - error:      出错
  - closed:     已关闭
"""
import json, os, time, threading
from datetime import datetime, timezone

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)
SESSION_TTL = cfg["session"]["ttl_minutes"] * 60


class Session:
    """单个会话的数据和状态（v2.0）"""

    def __init__(self, session_id: str, query: str, keyword: str, max_results: int,
                 mode: str = "full", site: str | None = None, timelimit: str | None = None,
                 filter_days: int | None = None, filter_title: str | None = None,
                 include_snippet: bool = False, llm_mode: str = "segments"):
        self.session_id = session_id
        self.query = query
        self.keyword = keyword
        self.max_results = max_results
        self.mode = mode
        self.site = site
        self.timelimit = timelimit
        self.filter_days = filter_days
        self.filter_title = filter_title
        self.include_snippet = include_snippet
        self.llm_mode = llm_mode
        self.status = "processing"  # processing | preview | done | error | closed
        self.created_at = time.time()
        self.elapsed = 0.0
        self.error = None
        # Phase 1 预览
        self.preview = None
        # Phase 2 完整分析
        self.articles = {}
        self.segments = {}
        self._texts = {}
        self._phase1_raw = []

    def to_dict(self, include_texts: bool = False) -> dict:
        d = {
            "session_id": self.session_id,
            "status": self.status,
            "mode": self.mode,
            "llm_mode": self.llm_mode,
            "site": self.site,
            "timelimit": self.timelimit,
            "filter_days": self.filter_days,
            "filter_title": self.filter_title,
            "query": self.query,
            "keyword": self.keyword,
            "max_results": self.max_results,
            "created_at": datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
            "elapsed": round(self.elapsed, 1),
        }
        if self.preview:
            d["preview"] = self.preview
        if self.status in ("done", "error"):
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
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def create(self, query: str, keyword: str = "", max_results: int = 5,
               mode: str = "full", site: str | None = None, timelimit: str | None = None,
               filter_days: int | None = None, filter_title: str | None = None,
               include_snippet: bool = False, llm_mode: str = "segments") -> str:
        session_id = f"s_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self)}"
        sess = Session(session_id, query, keyword, max_results, mode, site, timelimit,
                       filter_days, filter_title, include_snippet, llm_mode)
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

    def set_preview(self, session_id: str, preview: dict, phase1_raw: list, elapsed: float):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "preview"
            sess.preview = preview
            sess._phase1_raw = phase1_raw
            sess.elapsed = elapsed

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
            sess._phase1_raw = []  # 释放内存

    def set_error(self, session_id: str, error: str):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "error"
            sess.error = error
            sess._phase1_raw = []  # 释放内存

    def close(self, session_id: str) -> bool:
        sess = self.get(session_id)
        if not sess:
            return False
        with self._lock:
            sess.status = "closed"
            sess._phase1_raw = []
        return True

    def get_phase1_raw(self, session_id: str) -> list:
        sess = self.get(session_id)
        if not sess:
            return []
        return sess._phase1_raw

    def get_segment_text(self, session_id: str, article_id: str, segment_id: str) -> str | None:
        sess = self.get(session_id)
        if not sess or sess.status != "done":
            return None
        return sess._texts.get(article_id, {}).get(segment_id)

    def _cleanup_loop(self):
        while True:
            time.sleep(60)
            now = time.time()
            with self._lock:
                expired = [
                    sid for sid, sess in self._sessions.items()
                    if sess.status not in ("closed",) and (now - sess.created_at) > SESSION_TTL
                ]
                for sid in expired:
                    self._sessions[sid].status = "closed"
                    self._sessions[sid]._phase1_raw = []
                if expired:
                    print(f"[cleanup] 过期关闭 {len(expired)} 个会话", flush=True)
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
