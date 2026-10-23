"""Read a fresh Kiwoom US quote for DigitalOcean's existing Groq news AI.

This reuses the Render relay fed by DigitalOcean; it does NOT call Kiwoom
again, save quotes, add workers, or replace the news/event pipeline.
Unavailable or stale quotes remain unavailable (never a Yahoo daily close).
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request

# Exact verified names from the worker's approved US universe / observed tickers.
# Unknown aliases are deliberately not guessed or matched fuzzily.
US_AI_TICKERS = {
    "TSMC ADR": "TSM",
    "네비우스 그룹": "NBIS",
    "마이크로소프트": "MSFT",
    "마이크론 테크놀로지": "MU",
    "메타": "META",
    "모더나": "MRNA",
    "브로드컴": "AVGO",
    "샌디스크": "SNDK",
    "스페이스X": "SPCX",
    "아마존닷컴": "AMZN",
    "아이렌": "IREN",
    "아이온큐": "IONQ",
    "알파벳 Class A": "GOOGL",
    "애플": "AAPL",
    "엔비디아": "NVDA",
    "오라클": "ORCL",
    "인텔": "INTC",
    "일라이 릴리": "LLY",
    "코어위브": "CRWV",
    "테슬라": "TSLA",
    "팔란티어 테크놀로지스": "PLTR",
}

DEFAULT_FEED_URL = "https://gaemi-gtp.onrender.com/market/us-live-quotes"
MAX_QUOTE_AGE_MS = 25000


def verified_price_context(stock_name, payload, *, now_ms=None):
    """Return a fresh price only for this exact US listing and its verified symbol."""
    expected = US_AI_TICKERS.get(str(stock_name or "").strip())
    if not expected or not isinstance(payload, dict):
        return None
    if payload.get("ok") is not True or payload.get("market") != "us":
        return None
    if payload.get("source") != "kiwoom-direct":
        return None
    items = payload.get("items")
    if not isinstance(items, list) or len(items) > 30:
        return None
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != expected:
            continue
        if item.get("stale") is not False:
            return None
        received_at_ms = item.get("received_at_ms")
        price = item.get("price")
        change_pct = item.get("change_pct")
        if type(received_at_ms) is not int or type(price) not in (int, float):
            return None
        age_ms = now_ms - received_at_ms
        if not (-3000 <= age_ms <= MAX_QUOTE_AGE_MS):
            return None
        if not (math.isfinite(price) and 0 < price < 10000000):
            return None
        if change_pct is not None and (type(change_pct) not in (int, float)
                                      or not math.isfinite(change_pct)
                                      or not (-100 < change_pct < 100)):
            return None
        return {
            "symbol": expected,
            "current_price": float(price),
            "change_pct": float(change_pct) if change_pct is not None else None,
            "currency": "USD",
            "quote_source": "kiwoom-direct",
            "quote_received_at_ms": received_at_ms,
            "status": "fresh",
        }
    return None


def fetch_verified_us_price_context(stock_name, *, opener=None, now_ms=None):
    """Read only the signed-feed receiver's cached result; fail closed in 3s."""
    if str(stock_name or "").strip() not in US_AI_TICKERS:
        return None
    url = os.getenv("GAEMI_US_QUOTE_FEED_URL", DEFAULT_FEED_URL).strip()
    parsed = urllib.parse.urlsplit(url)
    # The currently deployed endpoint is public but price is never accepted
    # from an arbitrary page, and no credentials are sent.
    if (parsed.scheme != "https" or parsed.hostname != "gaemi-gtp.onrender.com"
            or parsed.path != "/market/us-live-quotes" or parsed.query
            or parsed.fragment or parsed.username or parsed.password):
        print("[news-ai-price] unavailable reason=invalid_endpoint", flush=True)
        return None
    opener = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "gaemiGTP-news-ai-quote/1.0",
        })
        with opener(req, timeout=3) as response:
            body = response.read(8193)
        if len(body) > 8192:
            raise ValueError("oversized_quote_payload")
        payload = json.loads(body)
        return verified_price_context(stock_name, payload, now_ms=now_ms)
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        print("[news-ai-price] unavailable reason=feed_read_failed", flush=True)
        return None
