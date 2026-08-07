#!/usr/bin/env python3
"""探测 ms.10jqka.com.cn gateway 接口族里可能的研报原文/PDF 下载接口。

候选路径基于:
- SkillHub 下载接口: /gateway/market/api/v1/skills/square/download（同族）
- 搜索结果的 extra.seq=6260545、uid、news ID 58153563
"""

import json
import urllib.error
import urllib.request

SEQS = ["6260545"]           # extra.seq
DUIDS = ["ead63780908e6131"]  # 搜索接口 uid
NEWS_IDS = ["58153563"]      # news 页面 ID

PATHS = [
    "/gateway/market/api/v1/research/report/download",
    "/gateway/market/api/v1/research/download",
    "/gateway/market/api/v1/report/download",
    "/gateway/market/api/v1/reports/{}/pdf",
    "/gateway/market/api/v1/research/{}/pdf",
    "/gateway/unified-wap/v1/information/notice-detail",
    "/gateway/market/api/v1/information/notice-detail",
]


def try_get(url, params=None):
    if params:
        url = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read()[:200]
            ctype = r.headers.get("Content-Type", "?")
            return f"{r.status} [{ctype}] {body!r}"
    except Exception as e:
        code = getattr(e, "code", None)
        return f"{type(e).__name__} code={code}"


def main():
    for p in PATHS:
        for v in SEQS + DUIDS + NEWS_IDS:
            path = p.format(v) if "{}" in p else p
            url = "https://ms.10jqka.com.cn" + path
            print(f"{url} -> {try_get(url)}")
    # 带参数变体
    for p in ["/gateway/market/api/v1/research/report/download"]:
        for params in (
            {"seq": "6260545"},
            {"id": "6260545"},
            {"duid": "ead63780908e6131"},
            {"article_id": "58153563"},
        ):
            url = "https://ms.10jqka.com.cn" + p
            print(f"{url} {params} -> {try_get(url, params)}")


if __name__ == "__main__":
    main()
