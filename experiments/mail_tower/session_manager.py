"""
Session 管理器（v3.0）— 支持引擎分发 + list 模式下逐篇存储正文

支持多 worker：每次变更同步写文件，get() 读文件兜底，
              不同 worker 进程可共享 session 数据。

状态流转:
  - processing:     运行中（Phase 0 刚完成）
  - preview:        Phase 1 完成（预览可见），Phase 2 进行中（仅 preview 模式）
  - list_ready:     list 模式下，文章列表已返回，Phase 1 正文提取进行中
  - done:           全部完成
  - error:          出错
  - closed:         已关闭
"""
import json, os, time, threading, secrets
from datetime import datetime, timezone

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)
SESSION_TTL = cfg["session"]["ttl_minutes"] * 60
LIST_TTL = cfg.get("session", {}).get("list", {}).get("ttl_minutes", 15) * 60


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
        self.status = "processing"
        self.list_status: str = "processing"     # processing | ready | empty | error
        self.article_status: str = "free"        # free | waiting | processing | ready | error
        self.created_at = time.time()
        self._loaded_at = time.time()
        self.elapsed = 0.0
        self.error = None
        self.call_count = 0
        self.list_ready_at = 0.0
        self.preview = None
        self.articles = {}
        self.segments = {}
        self._texts = {}
        self._phase1_raw = []
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
                arts = list(self.preview.get("articles", [])) if self.preview else []
                for a in arts:
                    body = self.article_bodies.get(a.get("id", ""))
                    a["body_status"] = "ready" if body else "processing"
                d["_list_articles"] = arts
            elif self.status == "done" and not self.articles:
                arts = list(self.preview.get("articles", [])) if self.preview else []
                for a in arts:
                    a["body_status"] = "ready" if a.get("id", "") in self.article_bodies else "error"
                d["_list_articles"] = arts
            else:
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

    def to_file_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "keyword": self.keyword,
            "max_results": self.max_results,
            "mode": self.mode,
            "engine": self.engine,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "site": self.site,
            "timelimit": self.timelimit,
            "filter_days": self.filter_days,
            "filter_title": self.filter_title,
            "include_snippet": self.include_snippet,
            "llm_mode": self.llm_mode,
            "status": self.status,
            "list_status": self.list_status,
            "article_status": self.article_status,
            "created_at": self.created_at,
            "elapsed": self.elapsed,
            "error": self.error,
            "call_count": self.call_count,
            "list_ready_at": self.list_ready_at,
            "preview": self.preview,
            "article_bodies": self.article_bodies,
            "_phase1_raw": self._phase1_raw,
        }

    @classmethod
    def from_file_dict(cls, data: dict) -> "Session":
        sess = cls(
            session_id=data["session_id"],
            query=data.get("query", ""),
            keyword=data.get("keyword", ""),
            max_results=data.get("max_results", 5),
            mode=data.get("mode", "full"),
            site=data.get("site"),
            timelimit=data.get("timelimit"),
            filter_days=data.get("filter_days"),
            filter_title=data.get("filter_title"),
            include_snippet=data.get("include_snippet", False),
            llm_mode=data.get("llm_mode", "segments"),
            engine=data.get("engine", "ddg"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )
        for key in ("status", "list_status", "article_status",
                    "created_at", "elapsed", "error",
                    "call_count", "list_ready_at",
                    "preview", "article_bodies", "_phase1_raw"):
            if key in data:
                setattr(sess, key, data[key])
        sess._loaded_at = time.time()
        return sess


class SessionManager:
    """全局会话管理器，线程安全 + 文件持久化（支持多 worker）"""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _file_path(self, session_id: str) -> str:
        return os.path.join(SESSIONS_DIR, f"{session_id}.json")

    def _save_to_file(self, session_id: str):
        sess = self._sessions.get(session_id)
        if not sess:
            return
        path = self._file_path(session_id)
        tmp = path + ".tmp"
        data = sess.to_file_dict()
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)  # 原子替换，读取方不会看到截断中的文件
        except Exception as e:
            print(f"[session] 保存文件失败 {session_id}: {e}", flush=True)

    def _load_from_file(self, session_id: str) -> Session | None:
        path = self._file_path(session_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sess = Session.from_file_dict(data)
            with self._lock:
                self._sessions[session_id] = sess
            return sess
        except Exception as e:
            print(f"[session] 加载文件失败 {session_id}: {e}", flush=True)
            return None

    def _remove_file(self, session_id: str):
        path = self._file_path(session_id)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[session] 删除文件失败 {session_id}: {e}", flush=True)

    def create(self, query: str, keyword: str = "", max_results: int = 5,
               mode: str = "full", site: str | None = None, timelimit: str | None = None,
               filter_days: int | None = None, filter_title: str | None = None,
               include_snippet: bool = False, llm_mode: str = "segments",
               engine: str = "ddg",
               start_date: str | None = None,
               end_date: str | None = None) -> str:
        with self._lock:
            _now = datetime.now()
            session_id = f"s_{_now.strftime('%Y%m%d_%H%M%S')}_{_now.strftime('%f')}_{secrets.randbelow(10**10)}"
            sess = Session(session_id, query, keyword, max_results, mode, site, timelimit,
                           filter_days, filter_title, include_snippet, llm_mode,
                           engine, start_date, end_date)
            self._sessions[session_id] = sess
        self._save_to_file(session_id)
        return session_id

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess and sess.status == "closed":
                return None
            if sess:
                return sess
        sess = self._load_from_file(session_id)
        if sess and sess.status == "closed":
            return None
        return sess

    def get_status(self, session_id: str) -> dict:
        sess = self.get(session_id)
        if not sess:
            return {"status": "not_found"}
        return sess.to_dict(include_texts=False)

    def set_preview(self, session_id: str, preview: dict, phase1_raw: list, elapsed: float,
                    engine: str = ""):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "list_ready" if sess.mode == "list" else "preview"
            sess.list_status = "ready"
            if engine in ("qnainfo",):
                sess.article_status = "free"
            elif sess.mode == "list":
                # 正文提取由后台线程或 /article 内联处理
                sess.article_status = "waiting"
            sess.preview = preview
            sess._phase1_raw = phase1_raw
            sess.elapsed = elapsed
            if sess.mode == "list" and sess.list_ready_at == 0:
                sess.list_ready_at = time.time()
                sess.call_count += 1
        self._save_to_file(session_id)

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
        self._save_to_file(session_id)

    def set_list_done(self, session_id: str, elapsed: float):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "done"
            sess.elapsed = elapsed
            sess._phase1_raw = []
        self._save_to_file(session_id)

    def set_article_processing(self, session_id: str):
        """标记正文提取开始（article_status → processing）"""
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            if sess.article_status != "error":
                sess.article_status = "processing"
        self._save_to_file(session_id)

    def set_article_ready(self, session_id: str, has_ready: bool = True):
        """标记正文提取完成（article_status → ready 或 error）

        Args:
            has_ready: True=至少一篇就绪, False=全部失败
        """
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.article_status = "ready" if has_ready else "error"
        self._save_to_file(session_id)

    def set_article_body(self, session_id: str, article_id: str,
                         body_text: str, truncated: bool = False,
                         fetch_error: str = ""):
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return
            sess.article_bodies[article_id] = {
                "body_text": body_text,
                "truncated": truncated,
                "fetch_error": fetch_error,
                "fetched_at": time.time(),
            }
        self._save_to_file(session_id)

    def set_error(self, session_id: str, error: str):
        sess = self.get(session_id)
        if not sess:
            return
        with self._lock:
            sess.status = "error"
            sess.list_status = "error"
            sess.article_status = "error"
            sess.error = error
            sess._phase1_raw = []
        self._save_to_file(session_id)

    def close(self, session_id: str) -> bool:
        sess = self.get(session_id)
        if not sess:
            return False
        with self._lock:
            sess.status = "closed"
            sess._phase1_raw = []
        self._save_to_file(session_id)
        return True

    def increment_call_count(self, session_id: str) -> int:
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess and sess.mode == "list" and sess.status != "closed":
                sess.call_count += 1
                self._save_to_file(session_id)
                return sess.call_count
            return 0

    def close_after_article(self, session_id: str, close_signal: bool) -> bool:
        if close_signal:
            self.close(session_id)
            return True
        with self._lock:
            sess = self._sessions.get(session_id)
            if sess and sess.mode == "list" and sess.status == "closed":
                return True
            return False

    def sync_body_avail(self, session_id: str) -> int:
        sess = self._sessions.get(session_id)
        if not sess or not sess.preview:
            return 0
        preview_arts = sess.preview.get("articles", [])
        updated = 0
        for a in preview_arts:
            if a.get("body_avail") != "有":
                continue
            body = sess.article_bodies.get(a["id"], {})
            bt = body.get("body_text", "")
            if not bt and body.get("fetch_error"):
                a["body_avail"] = "无"
                updated += 1
        if updated:
            self._save_to_file(session_id)
        return updated

    def get_article_body(self, session_id: str, article_id: str) -> dict | None:
        sess = self.get(session_id)
        if not sess:
            return None
        body = sess.article_bodies.get(article_id)
        if body is not None:
            return body
        # 内存未命中 → 从文件兜底（跨 worker 场景：另一 worker 刚写入正文到文件）
        file_sess = self._load_from_file(session_id)
        if not file_sess:
            return None
        body = file_sess.article_bodies.get(article_id)
        if body is not None:
            with self._lock:
                self._sessions[session_id] = file_sess
        return body

    def get_phase1_raw(self, session_id: str) -> list:
        sess = self.get(session_id)
        if not sess:
            return []
        return sess._phase1_raw

    def get_article_info(self, session_id: str, article_id: str) -> dict | None:
        """从 session 的 _phase1_raw 中获取文章 URL 等信息。

        article_id 格式 "a_01" → _phase1_raw[0] 的 url。

        Returns:
            {"url": "...", "title": "..."} 或 None
        """
        sess = self.get(session_id)
        if not sess or not sess._phase1_raw:
            return None
        try:
            idx = int(article_id.split("_")[1]) - 1
            raw = sess._phase1_raw[idx]
            return {
                "url": raw.get("url", ""),
                "title": raw.get("title", ""),
                "snippet": raw.get("snippet", ""),
            }
        except (IndexError, ValueError, AttributeError):
            return None

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
                expired = []
                for sid, sess in self._sessions.items():
                    if sess.status in ("closed",):
                        continue
                    if sess.mode == "list" and sess.list_ready_at > 0:
                        ttl = LIST_TTL
                        ref_time = sess.list_ready_at
                    else:
                        ttl = SESSION_TTL
                        ref_time = sess.created_at
                    if (now - ref_time) > ttl:
                        expired.append(sid)
                for sid in expired:
                    self._sessions[sid].status = "closed"
                    self._sessions[sid]._phase1_raw = []
                    self._remove_file(sid)
                if expired:
                    print(f"[cleanup] 过期关闭 {len(expired)} 个会话", flush=True)
                purge = [
                    sid for sid, sess in self._sessions.items()
                    if sess.status == "closed" and (now - sess.created_at) > SESSION_TTL + 600
                ]
                for sid in purge:
                    del self._sessions[sid]
                    self._remove_file(sid)
                if purge:
                    print(f"[cleanup] 清理 {len(purge)} 个已关闭会话", flush=True)


manager = SessionManager()
