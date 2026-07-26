"""search_engine — 统一搜索接口

注意：
  - 除 DDG（DuckDuckGo 被墙需走代理）外，所有后端（sinafin/thsfin/baidufin/
    juchao/qnainfo/dcfin）直连国内金融站点，不走代理。
  - DDG 的代理通过 DDGS(proxy=...) 传参，不设环境变量。
  - 这里清除所有 HTTP 代理环境变量，防止其他代码误设。

用法:
    from search_engine import search

    # DDG 基本搜索
    results = search("中国芯片")

    # DDG 站内搜索
    results = search("中国芯片", site="zhihu.com")

    # Sinafin 个股新闻
    results = search("宁德时代", engine="sinafin", max_results=3)
    results = search("300750", engine="sinafin", start_date="2026-07-18")

    # Baidufin 百度股市通资讯
    results = search("300436", engine="baidufin")
    results = search("600519", engine="baidufin", start_date="2026-07-20")

    # Thsfin 同花顺 F10 公司大事
    results = search("300395", engine="thsfin")
    results = search("300395", engine="thsfin", start_date="2026-07-19", end_date="2026-07-22")

    # Dcfin 东方财富股吧（热门/资讯/公告）
    results = search("300395", engine="dcfin")
    results = search("300395", engine="dcfin", start_date="2026-07-19", end_date="2026-07-22")

    # Juchao 巨潮盘后公告
    results = search("300395", engine="juchao")
    results = search("菲利华", engine="juchao", start_date="2026-07-20")

    # QnAinfo 巨潮互动易问答
    results = search("300750", engine="qnainfo")
    results = search("300750", engine="qnainfo",
                     start_date="2026-07-21", end_date="2026-07-24")

返回格式: [{title, url, snippet}, ...]
    engine=sinafin 时额外返回 _known_date 和 _category 字段（资讯/公告）。
    engine=baidufin 时额外返回 _baidu_sentiment / _baidu_provider / _baidu_abstract。
    engine=thsfin 时额外返回 _known_date 字段（事件日期）。
    engine=dcfin 时额外返回 _known_date（精确到分钟）和 _category 字段（热门/资讯/公告）。
    engine=juchao 时额外返回 _known_date、_category（公告）、_announce_id、_announce_time 字段。
    engine=qnainfo 时返回 body_text（回答内容，可直接使用）及问答专属字段：
             _question（问题全文）、_answerer（回答者）、_answer（回答内容）、
             _ask_time（提问时间）、_update_time（更新时间）。
"""
# ── 清除代理环境变量 ──
# 所有非 DDG 后端直连国内金融站点。DDG 的代理通过参数传给 DDGS，
# 不设环境变量。这里清除一切代理 env var，防止被其他代码误设。
import os as _os
for _key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    _os.environ.pop(_key, None)
_os.environ["no_proxy"] = "*"

from .backends.ddgs import DDGSSearchBackend
from .backends.sinafin import SinaFinBackend
from .backends.baidufin import BaidufinBackend
from .backends.thsfin import ThsfinBackend
from .backends.dcfin import DcfinBackend
from .backends.juchao import JuchaoBackend
from .backends.qnainfo import QnAInfoBackend


def search(query: str, max_results: int = 10,
           site: str | None = None, timelimit: str | None = None,
           engine: str = "ddg",
           start_date: str | None = None,
           end_date: str | None = None) -> list[dict]:
    """
    统一搜索接口。支持多后端分发。

    Args:
        query: 搜索关键词（DDG）或股票代码/名称（sinafin/baidufin/thsfin）
        max_results: 返回条数
        site: 站内限制（仅 DDG）
        timelimit: 时间限制（仅 DDG）
        engine: 搜索后端，可选 "ddg"（默认）| "sinafin" | "baidufin" | "thsfin" | "dcfin" | "juchao" | "qnainfo"
        start_date: 起始日期过滤 YYYY-MM-DD
        end_date: 截止日期过滤 YYYY-MM-DD

    Returns:
        [{title, url, snippet}, ...]
        engine=sinafin 时额外含 _known_date 字段。
        engine=dcfin 时额外含 _known_date（精确到分钟）和 _category 字段。
        engine=juchao 时额外含 _known_date、_category、_announce_id、_announce_time 字段（无正文）。
    """
    import os as _os, time as _time
    _t0 = _time.time()
    try:
        import sys as _sys
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "research", "experiments", "mail_tower"))
        from reporting.debug_log import DLog
    except Exception:
        pass
    else:
        DLog.log("backend_search_start", engine=engine, query=query[:40], max_results=max_results)
    if engine == "sinafin":
        backend = SinaFinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    elif engine == "baidufin":
        backend = BaidufinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    elif engine == "thsfin":
        backend = ThsfinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    elif engine == "dcfin":
        backend = DcfinBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit,
                              start_date=start_date, end_date=end_date)
    elif engine == "juchao":
        backend = JuchaoBackend()
        return backend.search(query, max_results=max_results,
                               site=site, timelimit=timelimit,
                               start_date=start_date, end_date=end_date)
    elif engine == "qnainfo":
        backend = QnAInfoBackend()
        return backend.search(query, max_results=max_results,
                               site=site, timelimit=timelimit,
                               start_date=start_date, end_date=end_date)
    else:
        backend = DDGSSearchBackend()
        return backend.search(query, max_results=max_results,
                              site=site, timelimit=timelimit)
