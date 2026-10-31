"""TradingView Data API US stock-news provider.

One shared US news request per eight hours for all TOP20 stocks.
A local, locked cache and hard monthly budget prevent per-ticker API fan-out.
This provider never writes to Neon or invokes AI.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.parse
import urllib.request

API_URL = "https://api.tradingviewapi.com/api/news/stock"
CACHE_PATH = Path("/var/lib/gaemigtp-news/tradingview-us-stock-news.json")
MIN_REQUEST_INTERVAL_SECONDS = 8 * 60 * 60
MONTHLY_REQUEST_LIMIT = 90


def _write_state(path, state):
    if path.is_symlink():
        raise ValueError("unsafe_tradingview_cache")
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".tv-news-", delete=False,
        ) as f:
            name = f.name
            os.fchmod(f.fileno(), 0o600)
            json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _load_news(key, *, now=None, opener=None):
    now = time.time() if now is None else float(now)
    month = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m")
    path = CACHE_PATH
    if not path.parent.is_dir() or path.parent.is_symlink() or path.is_symlink():
        return []
    lock_path = path.with_suffix(".lock")
    if lock_path.is_symlink():
        return []
    opener = opener or urllib.request.urlopen
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    return []
            except (OSError, ValueError, TypeError):
                # Fail closed rather than resetting the API request counter.
                return []
        else:
            state = {"month": month, "requests": 0, "last_attempt": 0, "items": []}
        if state.get("month") != month:
            state = {"month": month, "requests": 0, "last_attempt": 0, "items": []}
        try:
            attempts = int(state.get("requests", 0))
            last_attempt = float(state.get("last_attempt", 0))
            items = state.get("items", [])
            if not isinstance(items, list) or attempts < 0:
                return []
        except (ValueError, TypeError):
            return []
        if now - last_attempt < MIN_REQUEST_INTERVAL_SECONDS or attempts >= MONTHLY_REQUEST_LIMIT:
            return items if now - last_attempt <= 48 * 3600 else []
        # Record usage BEFORE the HTTP request to avoid accidentally paid retries.
        state["requests"] = attempts + 1
        state["last_attempt"] = now
        _write_state(path, state)
        query = urllib.parse.urlencode({"lang": "en", "market_country": "US"})
        req = urllib.request.Request(
            API_URL + "?" + query,
            headers={
                "Authorization": "Bearer " + key,
                "Accept": "application/json",
                "User-Agent": "gaemiGTP-news-worker/1.0",
            },
        )
        try:
            with opener(req, timeout=8) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise ValueError("invalid_tradingview_news_response")
            data = payload.get("data")
            fresh = data.get("items") if isinstance(data, dict) else None
            if not isinstance(fresh, list):
                raise ValueError("invalid_tradingview_news_items")
            state["items"] = [x for x in fresh[:300] if isinstance(x, dict)]
            _write_state(path, state)
            return state["items"]
        except Exception as exc:
            print("[provider:tradingview-news] request_failed=%s" % type(exc).__name__, flush=True)
            return items if now - last_attempt <= 48 * 3600 else []


def fetch_stock_news(ticker):
    """Return normalized, symbol-verified US news; never bill per ticker."""
    ticker = str(ticker or "").upper().strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", ticker):
        return []
    key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
    if not key:
        return []
    try:
        items = _load_news(key)
    except (OSError, ValueError) as exc:
        print("[provider:tradingview-news] cache_failed=%s" % type(exc).__name__, flush=True)
        return []
    results = []
    for article in items:
        related = article.get("relatedSymbols") or []
        if not isinstance(related, list):
            continue
        symbols = {
            str(r.get("symbol") or "").upper().rsplit(":", 1)[-1]
            for r in related if isinstance(r, dict)
        }
        if ticker not in symbols:
            continue
        title = str(article.get("title") or "").strip()
        if not title:
            continue
        link = str(article.get("link") or "")
        if not link.startswith(("https://", "http://")):
            path = str(article.get("storyPath") or "")
            link = "https://www.tradingview.com" + path if path.startswith("/news/") else ""
        if not link:
            continue
        stamp = article.get("published")
        try:
            published = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        provider = article.get("provider")
        source = str(provider.get("name") or "TradingView") if isinstance(provider, dict) else "TradingView"
        results.append({
            "title": title,
            "description": "",  # Respect headline-only news permissions.
            "summary": "",
            "url": link,
            "link": link,
            "published_at": published,
            "source": source,
            "query": ticker,
            "category": "종목",
            "provider": "tradingview",
        })
    return results
