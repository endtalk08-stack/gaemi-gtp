"""TradingView Data API US stock-news provider.

One shared US stock-news request is reused by every ticker. Collection cadence
follows the US market session and a local rolling cache prevents per-ticker API
fan-out. This provider never writes to Neon and never invokes AI.
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
from zoneinfo import ZoneInfo

API_URL = "https://api.tradingviewapi.com/api/news/stock"
CACHE_PATH = Path("/var/lib/gaemigtp-news/tradingview-us-stock-news.json")

# Initial news-first collection policy. America/New_York handles DST
# automatically, so the Korea-time windows move with the US market.
SESSION_INTERVAL_SECONDS = {
    "premarket": 10 * 60,
    "regular": 5 * 60,
    "afterhours": 10 * 60,
    "offhours": 30 * 60,
}
# Basic test mode spends at most three HTTP requests per US trading day.
# Windows are New York local time and therefore follow DST automatically.
BASIC_COLLECTION_WINDOWS = {
    "premarket": (8 * 60 + 30, 9 * 60),
    "regular": (12 * 60 + 30, 13 * 60),
    "afterhours": (16 * 60 + 30, 17 * 60),
}
DEFAULT_MONTHLY_REQUEST_LIMIT = 200
CACHE_MAX_AGE_SECONDS = 48 * 60 * 60
MAX_CACHE_ITEMS = 3000


def _monthly_request_limit():
    value = os.environ.get("TRADINGVIEW_NEWS_MONTHLY_LIMIT", "").strip()
    if not value:
        return DEFAULT_MONTHLY_REQUEST_LIMIT
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_MONTHLY_REQUEST_LIMIT
    return max(1, min(parsed, 100_000))


def collection_session(now=None):
    """Return the current US-news session and production interval."""
    stamp = time.time() if now is None else float(now)
    ny = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).astimezone(
        ZoneInfo("America/New_York")
    )
    if ny.weekday() >= 5:
        return "offhours", SESSION_INTERVAL_SECONDS["offhours"]

    minute = ny.hour * 60 + ny.minute
    if 4 * 60 <= minute < 9 * 60 + 30:
        return "premarket", SESSION_INTERVAL_SECONDS["premarket"]
    if 9 * 60 + 30 <= minute < 16 * 60:
        return "regular", SESSION_INTERVAL_SECONDS["regular"]
    if 16 * 60 <= minute < 20 * 60:
        return "afterhours", SESSION_INTERVAL_SECONDS["afterhours"]
    return "offhours", SESSION_INTERVAL_SECONDS["offhours"]


def _collection_mode():
    value = os.environ.get("TRADINGVIEW_NEWS_MODE", "basic_test").strip().lower()
    return "pro" if value == "pro" else "basic_test"


def _basic_collection_slot(now):
    """Return one of the three Basic test slots every day, including weekends."""
    stamp = time.time() if now is None else float(now)
    ny = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).astimezone(
        ZoneInfo("America/New_York")
    )
    minute = ny.hour * 60 + ny.minute
    for name, (start, end) in BASIC_COLLECTION_WINDOWS.items():
        if start <= minute < end:
            return name, ny.strftime("%Y%m%d") + ":" + name
    return None, None


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


def _article_key(article):
    article_id = article.get("id") or article.get("newsId")
    if article_id not in (None, ""):
        return "id:" + str(article_id)
    story_path = str(article.get("storyPath") or "").strip()
    if story_path:
        return "story:" + story_path
    return "fallback:%s|%s" % (
        str(article.get("published") or ""),
        str(article.get("title") or "").strip(),
    )


def _article_is_recent(article, now):
    try:
        published = float(article.get("published"))
    except (TypeError, ValueError):
        return True
    return published >= now - CACHE_MAX_AGE_SECONDS


def _merge_items(fresh, existing, now):
    """Merge newest API rows into a bounded 48-hour local cache."""
    merged = []
    seen = set()
    for article in list(fresh) + list(existing):
        if not isinstance(article, dict) or not _article_is_recent(article, now):
            continue
        key = _article_key(article)
        if key in seen:
            continue
        seen.add(key)
        merged.append(article)
        if len(merged) >= MAX_CACHE_ITEMS:
            break
    return merged


def _load_news(key, *, now=None, opener=None):
    now = time.time() if now is None else float(now)
    month = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m")
    session, interval_seconds = collection_session(now)
    mode = _collection_mode()
    monthly_limit = _monthly_request_limit()
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
            state = {
                "month": month,
                "requests": 0,
                "last_attempt": 0,
                "last_success": 0,
                "items": [],
            }

        if state.get("month") != month:
            state = {
                "month": month,
                "requests": 0,
                "last_attempt": 0,
                "last_success": 0,
                "items": state.get("items", []) if isinstance(state.get("items"), list) else [],
            }

        try:
            attempts = int(state.get("requests", 0))
            last_attempt = float(state.get("last_attempt", 0))
            items = state.get("items", [])
            if not isinstance(items, list) or attempts < 0:
                return []
        except (ValueError, TypeError):
            return []

        # Keep useful recent cache data even after a monthly budget is reached.
        cached = [x for x in items if isinstance(x, dict) and _article_is_recent(x, now)]
        slot_key = None
        if mode == "basic_test":
            session, slot_key = _basic_collection_slot(now)
            if slot_key is None or state.get("last_slot") == slot_key:
                return cached
        elif now - last_attempt < interval_seconds:
            return cached
        if attempts >= monthly_limit:
            return cached

        # Record usage BEFORE the HTTP request to avoid accidental retry storms.
        state["requests"] = attempts + 1
        state["last_attempt"] = now
        state["session"] = session
        state["mode"] = mode
        state["interval_seconds"] = interval_seconds if mode == "pro" else None
        state["monthly_limit"] = monthly_limit
        if slot_key is not None:
            state["last_slot"] = slot_key
        state["items"] = cached
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
            state["items"] = _merge_items(
                [x for x in fresh if isinstance(x, dict)],
                cached,
                now,
            )
            state["last_success"] = now
            state.pop("last_error", None)
            _write_state(path, state)
            print(
                "[provider:tradingview-news] refreshed mode=%s session=%s items=%s requests=%s/%s"
                % (mode, session, len(state["items"]), state["requests"], monthly_limit),
                flush=True,
            )
            return state["items"]
        except Exception as exc:
            state["last_error"] = type(exc).__name__
            state["items"] = cached
            _write_state(path, state)
            print(
                "[provider:tradingview-news] request_failed=%s"
                % type(exc).__name__,
                flush=True,
            )
            return cached


def refresh_news_cache(*, now=None, opener=None):
    """Read the already collected overall-news cache; do not make a second API call.

    The dedicated TradingView news worker owns new API collection. Keep the
    older stock-only cache as a read-only fallback while the system is paused
    or before the first overall-news batch is available.
    """
    from backend.providers import tradingview_news_bundle

    stamp = time.time() if now is None else float(now)
    for path, expected_version in (
        (tradingview_news_bundle.CACHE_PATH, tradingview_news_bundle.FEED_VERSION),
        (CACHE_PATH, None),
    ):
        if path.is_symlink() or not path.is_file() or path.parent.is_symlink():
            continue
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(state, dict):
            continue
        if expected_version is not None and state.get("feed_version") != expected_version:
            continue
        rows = state.get("items", [])
        if isinstance(rows, list):
            fresh = [row for row in rows if isinstance(row, dict) and
                     _article_is_recent(row, stamp)]
            if fresh:
                return fresh
    return []

def fetch_stock_news(ticker):
    """Return normalized, symbol-verified US news; never bill per ticker."""
    ticker = str(ticker or "").upper().strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", ticker):
        return []

    items = refresh_news_cache()
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

        story_path = str(article.get("storyPath") or "").strip()
        link = (
            "https://www.tradingview.com" + story_path
            if story_path.startswith("/news/")
            else ""
        )
        stamp = article.get("published")
        try:
            published = dt.datetime.fromtimestamp(
                int(stamp), dt.timezone.utc
            ).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            continue

        provider = article.get("provider")
        source = (
            str(provider.get("name") or "TradingView")
            if isinstance(provider, dict)
            else "TradingView"
        )
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
            "ast_description": (
                ast_description
                if isinstance(ast_description, (dict, list, str))
                else None
            ),
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
