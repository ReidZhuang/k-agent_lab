"""
Configuration for Sina Finance Article Tool.
"""
import os

# ── Tushare ──
# Token is auto-detected from tushare's config (~/.tushare/tushare.json or env var TUSHARE_TOKEN)
# If you need to set it manually:
#   import tushare as ts; ts.set_token('your_token')
#   or export TUSHARE_TOKEN=your_token

# ── Sina URLs ──
# Page 1 uses a different URL pattern than subsequent pages.
SINA_LIST_URL_PAGE1 = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{sina_code}.phtml"
SINA_LIST_URL_PAGEN = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php?symbol={sina_code}&Page={page}"

# ── Defaults ──
DEFAULT_PAGES = 3           # number of pages to scrape
REQUEST_TIMEOUT = 15        # seconds
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
