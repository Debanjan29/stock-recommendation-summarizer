"""
Real-time Indian Stock Quotes & Fundamentals Service.
Provides live CMP, 6 core fundamentals (P/E, Market Cap, 52W High/Low, P/B, Div Yield),
and 1-month historical sparkline prices with in-memory TTL caching.
"""

import time
import logging
from typing import Dict, Any, Optional, List
try:
    import yfinance as yf
except ImportError:
    yf = None

from stock_extractor.sectors import get_stock_sector
from stock_extractor.indian_market import indian_market_manager

logger = logging.getLogger(__name__)

# In-memory cache: ticker -> (data_dict, expire_timestamp)
_QUOTE_CACHE: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes cache

# Specific ticker mappings for Yahoo Finance symbol discrepancies
SYMBOL_OVERRIDES: Dict[str, str] = {
    "TATAMOTORS": "TMCV.NS",
    "NIFTY 50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    "M&M": "M&M.NS",
    "BAJAJ-AUTO": "BAJAJ-AUTO.NS"
}


def _resolve_yahoo_symbol(ticker: str) -> str:
    """Normalize Indian ticker to Yahoo Finance symbol."""
    clean = (ticker or "").strip().upper()
    if clean in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[clean]
    if clean.startswith("^"):
        return clean
    if not clean.endswith(".NS") and not clean.endswith(".BO"):
        return f"{clean}.NS"
    return clean


def _fetch_quote_pure_python(clean_ticker: str, company_name: str, sector: str, yahoo_symbol: str) -> Optional[Dict[str, Any]]:
    """
    Lightweight, pure-Python quote fetcher using direct HTTP requests.
    Zero C/Rust/Fortran dependencies: No pandas, no numpy, no lxml, no yfinance required!
    """
    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        urls = [
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d&range=1mo"
        ]
        if yahoo_symbol.endswith(".NS"):
            urls.append(f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol[:-3]}.BO?interval=1d&range=1mo")

        for url in urls:
            try:
                resp = requests.get(url, headers=headers, timeout=4)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                results = data.get("chart", {}).get("result")
                if not results:
                    continue
                meta = results[0].get("meta", {})
                cmp = meta.get("regularMarketPrice")
                if cmp is None:
                    continue

                prev_close = meta.get("previousClose") or meta.get("chartPreviousClose") or cmp
                change = round(float(cmp) - float(prev_close), 2)
                change_pct = round(((float(cmp) - float(prev_close)) / float(prev_close)) * 100, 2) if prev_close else 0.0

                w52_high = meta.get("fiftyTwoWeekHigh")
                w52_low = meta.get("fiftyTwoWeekLow")

                sparkline = []
                quote_indicators = results[0].get("indicators", {}).get("quote", [])
                if quote_indicators and "close" in quote_indicators[0]:
                    closes = quote_indicators[0]["close"] or []
                    sparkline = [round(float(c), 2) for c in closes if c is not None]

                used_sym = meta.get("symbol", yahoo_symbol)
                return {
                    "ticker": clean_ticker,
                    "name": company_name,
                    "sector": sector,
                    "exchange": "BSE" if used_sym.endswith(".BO") else "NSE",
                    "is_listed": True,
                    "cmp": round(float(cmp), 2),
                    "previous_close": round(float(prev_close), 2) if prev_close else None,
                    "change": change,
                    "change_percent": change_pct,
                    "currency": "INR",
                    "market_cap_cr": None,
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "week_52_high": round(float(w52_high), 2) if w52_high else None,
                    "week_52_low": round(float(w52_low), 2) if w52_low else None,
                    "dividend_yield": None,
                    "sparkline": sparkline,
                    "cached_at": time.time()
                }
            except Exception:
                continue
    except Exception:
        pass
    return None


def get_stock_quote_and_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Fetch live CMP, 6 core valuation fundamentals, and 30-day sparkline data.
    Cached in-memory for 5 minutes.
    """
    clean_ticker = (ticker or "").strip().upper()
    now = time.time()

    # Check in-memory cache
    if clean_ticker in _QUOTE_CACHE:
        cached_data, expire_time = _QUOTE_CACHE[clean_ticker]
        if now < expire_time:
            return cached_data

    sector = get_stock_sector(clean_ticker)
    company_name = indian_market_manager.stocks_db.get(clean_ticker, clean_ticker)
    yahoo_symbol = _resolve_yahoo_symbol(clean_ticker)

    fallback_payload: Dict[str, Any] = {
        "ticker": clean_ticker,
        "name": company_name,
        "sector": sector,
        "exchange": "NSE",
        "is_listed": False,
        "cmp": None,
        "previous_close": None,
        "change": 0.0,
        "change_percent": 0.0,
        "currency": "INR",
        "market_cap_cr": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "week_52_high": None,
        "week_52_low": None,
        "dividend_yield": None,
        "sparkline": [],
        "cached_at": now
    }

    if yf is None:
        pure_py_result = _fetch_quote_pure_python(clean_ticker, company_name, sector, yahoo_symbol)
        if pure_py_result:
            _QUOTE_CACHE[clean_ticker] = (pure_py_result, now + CACHE_TTL_SECONDS)
            return pure_py_result
        _QUOTE_CACHE[clean_ticker] = (fallback_payload, now + 120)
        return fallback_payload

    try:
        t = yf.Ticker(yahoo_symbol)
        
        # Fast info lookup (ultra-fast price, 52W range, market cap)
        fi = t.fast_info
        cmp = getattr(fi, "last_price", None)
        
        # If .NS failed or returned None, try .BO (BSE) fallback
        if cmp is None and yahoo_symbol.endswith(".NS"):
            bse_symbol = yahoo_symbol[:-3] + ".BO"
            try:
                t_bse = yf.Ticker(bse_symbol)
                fi_bse = t_bse.fast_info
                cmp_bse = getattr(fi_bse, "last_price", None)
                if cmp_bse is not None:
                    t = t_bse
                    fi = fi_bse
                    cmp = cmp_bse
                    yahoo_symbol = bse_symbol
            except Exception:
                pass

        if cmp is None:
            # Stock may be unlisted or delisted
            _QUOTE_CACHE[clean_ticker] = (fallback_payload, now + 120)
            return fallback_payload

        prev_close = getattr(fi, "previous_close", None) or cmp
        change = round(cmp - prev_close, 2)
        change_pct = round(((cmp - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
        
        # Market Cap in Crores (1 Cr = 10,000,000 INR)
        mcap_raw = getattr(fi, "market_cap", None)
        mcap_cr = round(mcap_raw / 10000000, 2) if mcap_raw else None
        
        w52_high = getattr(fi, "year_high", None)
        w52_low = getattr(fi, "year_low", None)

        # Valuation metrics from info (safe dictionary lookup)
        pe_ratio = None
        pb_ratio = None
        div_yield = None
        long_name = company_name

        try:
            info = t.info or {}
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            if pe_ratio:
                pe_ratio = round(float(pe_ratio), 2)
            pb_ratio = info.get("priceToBook")
            if pb_ratio:
                pb_ratio = round(float(pb_ratio), 2)
            div_raw = info.get("dividendYield")
            if div_raw:
                div_yield = round(float(div_raw) * 100 if float(div_raw) < 1.0 else float(div_raw), 2)
            long_name = info.get("longName") or info.get("shortName") or company_name
        except Exception:
            pass

        # 30-day historical prices for mini sparkline chart
        sparkline = []
        try:
            hist = t.history(period="1mo")
            if not hist.empty and "Close" in hist:
                closes = hist["Close"].dropna().tolist()
                sparkline = [round(float(c), 2) for c in closes]
        except Exception:
            pass

        payload: Dict[str, Any] = {
            "ticker": clean_ticker,
            "name": long_name,
            "sector": sector,
            "exchange": "BSE" if yahoo_symbol.endswith(".BO") else "NSE",
            "is_listed": True,
            "cmp": round(float(cmp), 2),
            "previous_close": round(float(prev_close), 2) if prev_close else None,
            "change": change,
            "change_percent": change_pct,
            "currency": "INR",
            "market_cap_cr": mcap_cr,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "week_52_high": round(float(w52_high), 2) if w52_high else None,
            "week_52_low": round(float(w52_low), 2) if w52_low else None,
            "dividend_yield": div_yield,
            "sparkline": sparkline,
            "cached_at": now
        }

        _QUOTE_CACHE[clean_ticker] = (payload, now + CACHE_TTL_SECONDS)
        return payload

    except Exception as e:
        logger.warning(f"Error fetching quote for {clean_ticker}: {e}")
        _QUOTE_CACHE[clean_ticker] = (fallback_payload, now + 120)
        return fallback_payload
