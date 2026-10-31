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
        query = urllib.parse.urlencode({"lang": "ko", "market_country": "US"})
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
        # Use the TradingView news page path as the article destination.
        # Publisher/original URLs are intentionally not used.
        story_path = str(article.get("storyPath") or "").strip()
        link = "https://www.tradingview.com" + story_path if story_path.startswith("/news/") else ""
        stamp = article.get("published")
        try:
            published = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        provider = article.get("provider")
        source = str(provider.get("name") or "TradingView") if isinstance(provider, dict) else "TradingView"
        # Preserve TradingView's supplied content and rights metadata.
        # The list response may omit story-detail fields; keep them empty rather
        # than substituting publisher text or generating a summary.
        short_description = str(
            article.get("shortDescription")
            or article.get("short_description")
            or ""
        ).strip()
        ast_description = (
            article.get("astDescription")
            if article.get("astDescription") is not None
            else article.get("ast_description")
        )
        results.append({
            "title": title,
            "description": short_description,
            "summary": short_description,
            "short_description": short_description,
            "ast_description": ast_description if isinstance(ast_description, (dict, list, str)) else None,
            "news_id": article.get("id") or article.get("newsId"),
            "permission": article.get("permission"),
            "paywall": article.get("paywall"),
            "copyright": article.get("copyright"),
            "related_symbols": related,
            "url": link,
            "link": link,
            "published_at": published,
            "source": source,
            "query": ticker,
            "category": "종목",
            "provider": "tradingview",
        })
    return results
