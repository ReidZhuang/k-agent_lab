#!/usr/bin/env python3
"""探查研报 PDF 文件路径 download_tmp/<hash>.pdf 在哪些 10jqka 域名下可访问。"""

import json
import urllib.request

PDF_PATH = None


def main():
    wd = json.load(open("report_detail.json"))["data"]["wordData"]
    pdf_path = wd.get("path", "")
    print("PDF path:", pdf_path)
    domains = [
        "basic.10jqka.com.cn",
        "page.10jqka.com.cn",
        "d.10jqka.com.cn",
        "img.10jqka.com.cn",
        "ms.10jqka.com.cn",
        "www.10jqka.com.cn",
        "pdf.10jqka.com.cn",
        "static.10jqka.com.cn",
        "data.10jqka.com.cn",
    ]
    for dom in domains:
        url = f"https://{dom}/{pdf_path}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                ctype = r.headers.get("Content-Type", "?")
                clen = r.headers.get("Content-Length", "?")
                print(f"{dom} -> {r.status} [{ctype}] len={clen}")
        except Exception as e:
            print(f"{dom} -> {type(e).__name__}: {getattr(e, 'code', e)}")


if __name__ == "__main__":
    main()
