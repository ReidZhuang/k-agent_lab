"""
FastAPI application for Sina Finance stock news extraction.

Endpoints:
    GET /news?code=300750         — Fetch news by stock code (3 pages → CSV)
    GET /news?code=sz300750       — Fetch news by Sina-style code
    GET /news?name=宁德时代        — Fetch news by company name
    GET /health                   — Health check

Usage:
    conda run -n stock_agent uvicorn api:app --host 0.0.0.0 --port 8000
    # or directly:
    conda run -n stock_agent python3 api.py
"""
import sys, os, json
from pathlib import Path
from typing import Optional

# ── Ensure conda env has the packages ──
#   conda activate stock_agent
#   pip install fastapi uvicorn

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse

from stock_lookup import StockLookup
from sina_scraper import SinaNewsScraper

app = FastAPI(
    title="Sina Finance Stock News Tool",
    description="Scrape stock news article listings from Sina Finance, output as CSV.",
    version="1.0",
)

# Shared instances
_lookup: StockLookup | None = None
_scraper: SinaNewsScraper | None = None


def _get_lookup() -> StockLookup:
    global _lookup
    if _lookup is None:
        _lookup = StockLookup()
    return _lookup


def _get_scraper() -> SinaNewsScraper:
    global _scraper
    if _scraper is None:
        _scraper = SinaNewsScraper()
    return _scraper


# ── API endpoints ──


@app.get("/health")
def health():
    return {"status": "ok", "service": "sinafin-artical-tool"}


@app.get("/news", responses={
    200: {
        "content": {"text/csv": {}},
        "description": "Returns a CSV file with columns: 标题, URL, 日期, 时间",
    }
})
def get_news(
    code: Optional[str] = Query(None, description="Stock code (e.g. 300750, sz300750, 300750.SZ)"),
    name: Optional[str] = Query(None, description="Company name (e.g. 宁德时代)"),
    pages: int = Query(3, description="Number of pages to scrape (default 3)"),
    format: str = Query("csv", description="Output format: csv or json"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD, inclusive)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD, inclusive)"),
):
    """
    抓取新浪财经个股新闻列表，返回 CSV 或 JSON。

    **用法示例:**
    - `/news?code=300750` — 用股票代码查询
    - `/news?code=sz300750` — 用新浪格式代码查询
    - `/news?name=宁德时代` — 用公司名称查询（自动通过 Tushare 转码）
    - `/news?name=宁德时代&format=json` — JSON 格式输出
    - `/news?code=300750&start_date=2026-07-18&end_date=2026-07-21` — 按日期范围过滤
    """
    # ── Resolve stock code ──
    sina_code = _resolve_code(code, name)
    if not sina_code:
        raise HTTPException(
            status_code=400,
            detail="请提供股票代码 (code) 或公司名称 (name)。例如: ?code=300750 或 ?name=宁德时代"
        )

    # ── Company name for display ──
    try:
        display_name = _get_lookup().sina_to_name(sina_code)
    except Exception:
        display_name = sina_code

    # ── Scrape ──
    scraper = _get_scraper()
    try:
        news = scraper.fetch_news(sina_code, pages=pages, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"抓取失败: {e}")

    if not news:
        raise HTTPException(status_code=404, detail=f"未找到 {display_name} ({sina_code}) 的新闻")

    # ── Response ──
    if format == "json":
        return {
            "stock": {"code": sina_code, "name": display_name},
            "total": len(news),
            "pages_scraped": pages,
            "news": news,
        }

    csv_str = scraper.to_csv(news)
    filename = f"{sina_code}_news_{len(news)}items.csv"
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
    <head><meta charset="utf-8"><title>Sina Finance Stock News Tool</title></head>
    <body>
        <h2>📰 新浪财经个股新闻抓取工具</h2>
        <p><b>用法:</b></p>
        <ul>
            <li><a href="/news?code=300750">/news?code=300750</a> — 按股票代码（自动检测 sz/sh）</li>
            <li><a href="/news?code=sz300750">/news?code=sz300750</a> — 按新浪格式代码</li>
            <li><a href="/news?name=宁德时代">/news?name=宁德时代</a> — 按公司名称</li>
            <li><a href="/news?name=宁德时代&format=json">/news?name=宁德时代&format=json</a> — JSON 格式</li>
            <li><a href="/news?code=600519&pages=5">/news?code=600519&pages=5</a> — 抓取 5 页</li>
        </ul>
        <p><b>输出:</b> CSV 文件（标题, URL, 日期, 时间），默认按时间倒序排列</p>
    </body>
    </html>
    """


# ── Helper ──


def _resolve_code(code: Optional[str], name: Optional[str]) -> str | None:
    """Resolve the Sina-format stock code from either a code or company name."""
    lookup = _get_lookup()

    if code:
        code = code.strip()
        try:
            return lookup.code_to_sina_code(code)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if name:
        name = name.strip()
        try:
            return lookup.name_to_sina_code(name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return None


# ── Standalone runner ──


if __name__ == "__main__":
    import uvicorn
    print("Starting Sina Finance Stock News API server...")
    print("  Test:  curl http://localhost:8000/news?name=宁德时代")
    print("  Docs:  http://localhost:8000/docs")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
