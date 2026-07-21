"""
Session 管理器（v3.0）— 支持引擎分发 + list 模式下逐篇存储正文

状态流转:
  - processing:     运行中（Phase 0 刚完成）
  - preview:        Phase 1 完成（预览可见），Phase 2 进行中（仅 preview 模式）
  - list_ready:     list 模式下，文章列表已返回，Phase 1 正文提取进行中
  - done:           全部完成
  - error:          出错
  - closed:         已关闭
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
    """单个会话的数据和状态（v3.0）"""

    def __init__(self, session_id: str, query: str, keyword: str, max_results: int,
                 mode: str = "full", site: str | None = None, timelimit: str | None = None,
                 filter_days: int | None = None, filter_title: str | None = None,
                 include_snippet: bool = False, llm_mode: str = "segments",
                 engine: str = "ddg",
                 start_date: str | None = None,
                 end_date: str | None = None):
        self.session_id = session_id
        self.query = query
        self.keyword = keyword
        self.max_results = max_results
        self.mode = mode
        self.engine = engine
        self.start_date = start_date
        self.end_date = end_date
        self.site = site
        self.timelimit = timelimit
        self.filter_days = filter_days
        self.filter_title = filter_title
        self.include_snippet = include_snippet
        self.llm_mode = llm_mode
        self.status = "processing"  # processing | preview | list_ready | done | error | closed
        self.created_at = time.time()
        self.elapsed = 0.0
        self.error = None
        # Phase 1 预览（文章列表，无正文）
        self.preview = None
        # Phase 2 完整分析
        self.articles = {}
        self.segments = {}
        self._texts = {}
        self._phase1_raw = []
        # list 模式：逐篇存储正文（article_id → {body_text, truncated, fetch_error, fetched_at}）
        self.article_bodies: dict[str, dict] = {}

    def to_dict(self, include_texts: bool = False) -> dict:
        d = {
            "session_id": self.session_id,
            "status": self.status,
            "mode": self.mode,
            "llm_mode": self.llm_mode,
            "engine": self.engine,
            "start_date": self.start_date,
            "end_date": self.end_date,
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
        if self.mode == "list":
            if self.status == "list_ready":
                # Phase 1 进行中：返回预览列表 + body_status
                arts = list(self.preview.get("articles", [])) if self.preview else []
                for a in arts:
                    body = self.article_bodies.get(a.get("id", ""))
                    a["body_status"] = "ready" if body else "processing"
                d["_list_articles"] = arts  # list 用内部字段
            elif self.status == "done" and not self.articles:
                # list + none：所有正文已提取完成
                arts = list(self.preview.get("articles", [])) if self.preview else []
                for a in arts:
                    a["body_status"] = "ready" if a.get("id", "") in self.article_bodies else "error"
                d["_list_articles"] = arts
            else:
                # list + segments/summary：LLM 结果已就绪
                d["articles"] = self.articles
                d["segments"] = self.segments
        elif self.status in ("done", "error"):
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
               include_snippet: bool = False, llm_mode: str = "segments",
               engine: str = "ddg",
               start_date: str | None = None,
               end_date: str | None = None) -> str:
        session_id = f"s_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self)}"
        sess = Session(session_id, query, keyword, max_results, mode, site, timelimit,
                       filter_days, filter_title, include_snippet, llm_mode,
                       engine, start_date, end_date)
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
            sess.status = "list_ready" if sess.mode == "list" else "preview"
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
            sess._phase1_raw = []

    def set_list_done(self, session_id: str, elapsed: float):
        """list 模式：全部文章正文提取完毕"""
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "done"
            sess.elapsed = elapsed
            sess._phase1_raw = []

    def set_article_body(self, session_id: str, article_id: str,
                         body_text: str, truncated: bool = False,
                         fetch_error: str = ""):
        """list 模式：存储单篇提取结果"""
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.article_bodies[article_id] = {
                "body_text": body_text,
                "truncated": truncated,
                "fetch_error": fetch_error,
                "fetched_at": time.time(),
            }

    def get_article_body(self, session_id: str, article_id: str) -> dict | None:
        """获取单篇正文，None 表示尚未提取完成"""
        sess = self.get(session_id)
        if not sess:
            return None
        with self._lock:
            return sess.article_bodies.get(article_id)

    def set_error(self, session_id: str, error: str):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "error"
            sess.error = error
            sess._phase1_raw = []

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
