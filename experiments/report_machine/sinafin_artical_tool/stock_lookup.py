"""
Stock code resolution: company name → TS code → Sina URL code.

Uses Tushare stock_basic API to look up A-share stock codes by company name.
Results are cached locally to avoid redundant API calls.

Usage:
    lookup = StockLookup()
    sina_code = lookup.name_to_sina_code("宁德时代")   # → "sz300750"
    sina_code = lookup.code_to_sina_code("300750")     # → "sz300750"
"""
import json, os, re, sys
from pathlib import Path

_STOCK_CACHE_DIR = Path(__file__).parent / "data"
_STOCK_CACHE_FILE = _STOCK_CACHE_DIR / "stock_basic_cache.json"


# ── Exchange prefix mapping (ts_code → sina URL code) ──
_EXCHANGE_MAP = {
    "SH": "sh",
    "SZ": "sz",
    "BJ": "bj",
}


def _ts_code_to_sina(ts_code: str) -> str:
    """Convert TS code like '300750.SZ' to Sina URL format 'sz300750'."""
    m = re.match(r"(\d+)\.(\w+)", ts_code.strip().upper())
    if not m:
        raise ValueError(f"Invalid ts_code format: {ts_code}")
    symbol = m.group(1)
    exchange = m.group(2)
    prefix = _EXCHANGE_MAP.get(exchange)
    if not prefix:
        raise ValueError(f"Unknown exchange suffix: {exchange} (from {ts_code})")
    return f"{prefix}{symbol}"


class StockLookup:
    """Company name ↔ Stock code resolver with local cache."""

    def __init__(self):
        self._cache: dict[str, str] = {}  # company_name → ts_code
        self._all_stocks: list[dict] | None = None
        self._load_cache()

    # ── Public API ──

    def name_to_sina_code(self, name: str) -> str:
        """Company name → Sina URL code (e.g. 宁德时代 → 'sz300750')."""
        ts_code = self._resolve_ts_code(name)
        return _ts_code_to_sina(ts_code)

    def name_to_ts_code(self, name: str) -> str:
        """Company name → TS code (e.g. 宁德时代 → '300750.SZ')."""
        return self._resolve_ts_code(name)

    def code_to_sina_code(self, code: str) -> str:
        """Raw code → Sina URL code. Accepts various formats:
           '300750'     → 'sz300750'
           'sz300750'   → 'sz300750'  (pass-through)
           '300750.SZ'  → 'sz300750'
        """
        code = code.strip()
        # Already a sina code like sz300750?
        if re.match(r"^(sh|sz|bj)\d{6}$", code):
            return code
        # TS code like 300750.SZ?
        if "." in code:
            return _ts_code_to_sina(code)
        # Pure numeric → infer exchange from leading digit
        if code.isdigit():
            prefix = {"6": "sh", "0": "sz", "3": "sz", "4": "bj", "8": "bj"}.get(code[0], "sz")
            return f"{prefix}{code}"
        raise ValueError(f"Cannot convert code: {code}")

    def sina_to_name(self, sina_code: str) -> str:
        """Sina URL code → company name (reverse lookup)."""
        # Extract the numeric symbol
        m = re.match(r"(?:sh|sz|bj)(\d{6})", sina_code)
        if not m:
            raise ValueError(f"Invalid Sina code: {sina_code}")
        symbol = m.group(1)
        stocks = self._get_all_stocks()
        for s in stocks:
            if s["symbol"] == symbol:
                return s["name"]
        return f"UNKNOWN_{sina_code}"

    # ── Internal ──

    def _resolve_ts_code(self, name: str) -> str:
        """Company name → ts_code, using cache first, then Tushare."""
        if name in self._cache:
            return self._cache[name]

        ts_code = self._query_tushare_exact(name)
        if ts_code:
            self._cache[name] = ts_code
            self._save_cache()
            return ts_code

        ts_code = self._query_tushare_fuzzy(name)
        if ts_code:
            self._cache[name] = ts_code
            self._save_cache()
            return ts_code

        raise ValueError(f"Stock not found: '{name}'. "
                         f"Please use a stock code (e.g. 300750) instead.")

    def _query_tushare_exact(self, name: str) -> str | None:
        """Exact name match via Tushare."""
        import tushare as ts
        try:
            pro = ts.pro_api()
            df = pro.stock_basic(name=name, fields="ts_code,symbol,name,list_status")
            if df is not None and not df.empty:
                # Prefer listed (L) stocks
                listed = df[df["list_status"] == "L"]
                if not listed.empty:
                    return listed.iloc[0]["ts_code"]
                return df.iloc[0]["ts_code"]
        except Exception:
            pass
        return None

    def _query_tushare_fuzzy(self, name: str) -> str | None:
        """Fuzzy name match: fetch all then filter by substring."""
        stocks = self._get_all_stocks()
        matches = [s for s in stocks if name in s["name"]]
        if not matches:
            return None
        # Prefer exact match or listed stock
        for s in matches:
            if s["name"] == name:
                return s["ts_code"]
        for s in matches:
            if s.get("list_status") == "L":
                return s["ts_code"]
        return matches[0]["ts_code"]

    def _get_all_stocks(self) -> list[dict]:
        """Fetch all listed A-share stocks (cached)."""
        if self._all_stocks is not None:
            return self._all_stocks

        # Try file cache first
        cache_path = _STOCK_CACHE_FILE
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    self._all_stocks = json.load(f)
                    return self._all_stocks
            except Exception:
                pass

        # Fetch from Tushare
        import tushare as ts
        try:
            pro = ts.pro_api()
            df = pro.stock_basic(list_status="L", fields="ts_code,symbol,name,list_status")
            if df is not None and not df.empty:
                self._all_stocks = df.to_dict("records")
                # Cache to file
                _STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(self._all_stocks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return self._all_stocks or []

    # ── Cache persistence ──

    def _load_cache(self):
        cache_path = _STOCK_CACHE_DIR / "name_to_ts_code.json"
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        _STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _STOCK_CACHE_DIR / "name_to_ts_code.json"
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
