"""
巨潮盘后公告（juchao）搜索后端 — 从巨潮资讯网获取 A 股上市公司盘后公告。

工作流（快慢分离）：
  Phase 0 (search):  只查 akshare 公告列表，秒回标题+日期，不下载 PDF
  Phase 1 (后台线程): 用 announceId/announceTime 异步下载 PDF 并提取正文

依赖:
  pip install akshare requests pypdf

用法:
    from search_engine import search
    results = search("300395", engine="juchao")
    results = search("300395", engine="juchao",
                     start_date="2026-07-20", end_date="2026-07-21")
    results = search("菲利华", engine="juchao",
                     start_date="20260720", end_date="20260721")

返回格式（无正文 — 需后台异步提取）:
    [{title, url, snippet, _known_date, _category,
      _announce_id, _announce_time}, ...]
    _category: "公告"
    _announce_id:  巨潮公告ID（供 PDF 下载）
    _announce_time: 巨潮公告时间戳（供 PDF 下载）
"""
import re
import sys
import os
import random
import time
from datetime import datetime, timedelta

import akshare as ak
from report_machine.Juchao_report_fetch.fetch import _fetch_pdf_text  # noqa: E402

from .base import SearchBackend

# ── 路径：引用 report_machine 下的 fetch 模块（用于后台线程复用 PDF 下载函数） ──
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS_DIR = os.path.join(_THIS_DIR, "..", "..", "..")  # experiments/
if _EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENTS_DIR)

# 只在 search() 中按需导入 akshare（启动时不加载，避免影响导入速度）
# 后台 PDF 提取线程用 fetch 模块的函数

# ── 可选：知识图谱实体解析（股票名称 → 代码） ──
_ENTITY_RESOLVER = None
try:
    from knowledge_graph.query_agent_api.core.entity_resolver import get_resolver
    _ENTITY_RESOLVER = get_resolver()
except ImportError:
    pass


# ============================================================
# 暴露给外部（后台线程）的 PDF 提取函数
# ============================================================

def juchao_fetch_pdf_text(announce_id: str, announce_time: str) -> str | None:
    """下载单条公告的 PDF 并提取文字。

    cninfo 的 bulletin_detail API 和 PDF CDN 偶发连接拒绝（ConnectionResetError），
    自动重试 2 次（2-3s 间隔）可大幅降低失败率。
    """
    for attempt in range(3):
        try:
            result = _fetch_pdf_text(announce_id, announce_time)
            if result is not None:
                return result
            # None 可能是 API 返回空，也可能是提取失败
            if attempt == 2:
                return None
        except Exception as e:
            if attempt == 2:
                print(f"[juchao] PDF 提取全部重试失败: {announce_id}: {e}", flush=True)
                return None
        wait = 2.0 + random.random()
        print(f"[juchao] PDF 提取失败，{wait:.1f}s 后重试: {announce_id}", flush=True)
        time.sleep(wait)
    return None


# ============================================================
# 后端类
# ============================================================

class JuchaoBackend(SearchBackend):
    """巨潮盘后公告搜索后端（仅查列表，不下载 PDF）。"""

    DEFAULT_DAYS_BACK = 7

    def search(self, query: str, max_results: int = 10,
               site: str | None = None, timelimit: str | None = None,
               start_date: str | None = None,
               end_date: str | None = None) -> list[dict]:
        """
        执行盘后公告搜索（仅列表，不下载 PDF）。

        Args:
            query: 股票代码（6位纯数字）或股票名称（如 "菲利华"）
            start_date: 起始日期 YYYYMMDD 或 YYYY-MM-DD
            end_date: 截止日期（同上）
            max_results: 最大返回条数

        Returns:
            [{title, url, snippet, _known_date, _category,
              _announce_id, _announce_time}, ...]
        """
        # 1. 解析股票代码
        code = self._resolve_code(query.strip())
        if not code:
            raise ValueError(
                f"无法从 '{query}' 解析出股票代码。请提供6位数字代码或A股股票名称。"
            )

        # 2. 确定日期范围
        start, end = self._resolve_dates(start_date, end_date)

        # 3. 查询公告列表（仅 akshare，不下载 PDF）
        articles = self._fetch_list(code, start, end)

        # 4. 按日期倒序排列，截断
        articles.sort(key=lambda a: a.get("_known_date", ""), reverse=True)
        return articles[:max_results]

    # ── 内部方法 ──

    def _fetch_list(self, code: str, start_date: str, end_date: str) -> list[dict]:
        """仅查询公告列表（akshare），返回结构化结果，不含 PDF 正文。"""
        import akshare as ak
        from report_machine.Juchao_report_fetch.fetch import _extract_param

        last_exc = None
        for attempt in range(2):
            try:
                df = ak.stock_zh_a_disclosure_report_cninfo(
                    symbol=code,
                    start_date=start_date,
                    end_date=end_date,
                )
                break  # 成功
            except Exception as e:
                last_exc = e
                err_msg = str(e)
                if "None of [Index" in err_msg or "Expecting value" in err_msg:
                    return []  # 无公告
                if attempt == 0:
                    wait = 1 + random.random()
                    print(f"[juchao] akshare 失败（{type(e).__name__}），{wait:.1f}s 后重试: {code}", flush=True)
                    time.sleep(wait)
                else:
                    raise  # 重试耗尽
        else:
            # 2 次都异常
            raise last_exc

        if df is None or df.empty:
            return []

        articles = []
        for _, row in df.iterrows():
            title = str(row.get("公告标题", ""))
            link = str(row.get("公告链接", ""))
            date = str(row.get("公告时间", ""))

            ann_id = _extract_param(link, "announcementId")
            ann_time = _extract_param(link, "announcementTime")

            # 统一日期格式
            date_clean = re.sub(r"\D", "", date)
            known_date = ""
            if len(date_clean) == 8:
                known_date = f"{date_clean[:4]}-{date_clean[4:6]}-{date_clean[6:8]}"

            articles.append({
                "title": title,
                "url": "",
                "snippet": title,  # 列表模式下先显示标题
                "_known_date": known_date,
                "_category": "公告",
                "_announce_id": ann_id or "",
                "_announce_time": ann_time or "",
            })

        return articles

    @staticmethod
    def _resolve_code(query: str) -> str | None:
        """解析 股票名称/代码 → 6位纯数字代码"""
        q = query.strip()

        # 1) 已经是6位纯数字
        if re.match(r'^\d{6}$', q):
            return q

        # 2) 含后缀格式 300395.SZ / SH600519
        m = re.match(r'^(\d{6})\.(SH|SZ|BJ|HK)$', q.upper())
        if m:
            return m.group(1)
        m = re.match(r'^(SH|SZ|BJ|HK)(\d{6})$', q.upper())
        if m:
            return m.group(2)

        # 3) 通过知识图谱解析（股票名称 → TS代码）
        if _ENTITY_RESOLVER is not None:
            try:
                value, etype = _ENTITY_RESOLVER.resolve(q)
                if etype == "stock_code":
                    code = value.split(".")[0]
                    if re.match(r'^\d{6}$', code):
                        return code
            except Exception:
                pass

        return None

    @staticmethod
    def _resolve_dates(start_date: str | None, end_date: str | None) -> tuple[str, str]:
        """确定日期范围。默认向前 DEFAULT_DAYS_BACK 天。"""
        today = datetime.now()

        if not end_date:
            end = today.strftime("%Y%m%d")
        else:
            end = re.sub(r"\D", "", end_date)
            if len(end) != 8:
                end = today.strftime("%Y%m%d")

        if not start_date:
            start_dt = today - timedelta(days=JuchaoBackend.DEFAULT_DAYS_BACK)
            start = start_dt.strftime("%Y%m%d")
        else:
            start = re.sub(r"\D", "", start_date)
            if len(start) != 8:
                start_dt = today - timedelta(days=JuchaoBackend.DEFAULT_DAYS_BACK)
                start = start_dt.strftime("%Y%m%d")

        return start, end
