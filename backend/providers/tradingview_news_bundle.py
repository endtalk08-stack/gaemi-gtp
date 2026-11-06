"""TradingView multi-category news collector for the standalone News App.

Collects the US-scoped overall news feed into one bounded local cache.
No Neon or AI calls happen here.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE_URL = "https://api.tradingviewapi.com/api/news"
CATEGORIES = ("overall",)
FEED_VERSION = "overall-us-ko-v1"
CACHE_PATH = Path("/var/lib/gaemigtp-news/tradingview-news-bundle.json")
CACHE_MAX_AGE_SECONDS = 48 * 60 * 60
MAX_CACHE_ITEMS = 4000

SESSION_INTERVAL_SECONDS = {
    "premarket": 10 * 60,
    "regular": 5 * 60,
    "afterhours": 10 * 60,
    "offhours": 30 * 60,
}
BASIC_COLLECTION_WINDOWS = {
    "premarket": (8 * 60 + 30, 9 * 60),
    "regular": (12 * 60 + 30, 13 * 60),
    "afterhours": (16 * 60 + 30, 17 * 60),
}


def _mode():
    return "pro" if os.environ.get("TRADINGVIEW_NEWS_MODE", "basic_test").strip().lower() == "pro" else "basic_test"


def _session(now):
    ny = dt.datetime.fromtimestamp(now, dt.timezone.utc).astimezone(ZoneInfo("America/New_York"))
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


def _basic_slot(now):
    ny = dt.datetime.fromtimestamp(now, dt.timezone.utc).astimezone(ZoneInfo("America/New_York"))
    minute = ny.hour * 60 + ny.minute
    for name, (start, end) in BASIC_COLLECTION_WINDOWS.items():
        if start <= minute < end:
            return name, ny.strftime("%Y%m%d") + ":" + name
    return None, None


def _write(state):
    path = CACHE_PATH
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("unsafe_tradingview_bundle_cache")
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".tv-news-bundle-", delete=False,
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


def _key(article):
    value = article.get("id") or article.get("newsId")
    if value not in (None, ""):
        return "id:" + str(value)
    path = str(article.get("storyPath") or "").strip()
    if path:
        return "story:" + path
    return "fallback:%s|%s" % (article.get("published") or "", article.get("title") or "")


def _recent(article, now):
    try:
        return float(article.get("published")) >= now - CACHE_MAX_AGE_SECONDS
    except (TypeError, ValueError):
        return True


def _merge(fresh, existing, now):
    merged = []
    index = {}
    for article in list(fresh) + list(existing):
        if not isinstance(article, dict) or not _recent(article, now):
            continue
        row = dict(article)
        cats = row.get("news_categories")
        if not isinstance(cats, list):
            cat = str(row.get("news_category") or "").strip()
            cats = [cat] if cat else []
        row["news_categories"] = [x for x in cats if x in CATEGORIES]
        key = _key(row)
        if key in index:
            current = merged[index[key]]
            for cat in row["news_categories"]:
                if cat not in current["news_categories"]:
                    current["news_categories"].append(cat)
            # Preserve previously checked detail metadata when a fresh headline
            # duplicates the same article during the next list refresh.
            for field in ("shortDescription", "short_description", "detail_checked"):
                if not current.get(field) and row.get(field):
                    current[field] = row[field]
            continue
        index[key] = len(merged)
        merged.append(row)
        if len(merged) >= MAX_CACHE_ITEMS:
            break
    return merged


def _request_news(key, opener):
    params = {"lang": "ko", "market_country": "US"}
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "gaemiGTP-news-worker/1.0",
        },
    )
    with opener(req, timeout=10) as response:
        payload = json.loads(response.read(3_000_000).decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("invalid_tradingview_category_response")
    data = payload.get("data")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("invalid_tradingview_category_items")
    rows = []
    for article in items:
        if not isinstance(article, dict):
            continue
        row = dict(article)
        row["news_category"] = "overall"
        row["news_categories"] = ["overall"]
        rows.append(row)
    return rows


def refresh_news_cache(*, now=None, opener=None, force=False):
    key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
    if not key:
        return []
    now = time.time() if now is None else float(now)
    opener = opener or urllib.request.urlopen
    path = CACHE_PATH
    if not path.parent.is_dir() or path.parent.is_symlink() or path.is_symlink():
        return []
    lock_path = path.with_suffix(".lock")
    if lock_path.is_symlink():
        return []

    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = {}
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return []
        if not isinstance(state, dict):
            return []
        existing = state.get("items", []) if state.get("feed_version") == FEED_VERSION else []
        if not isinstance(existing, list):
            existing = []
        cached = [x for x in existing if isinstance(x, dict) and _recent(x, now)]

        mode = _mode()
        session, interval = _session(now)
        slot_key = None
        if mode == "basic_test":
            session, slot_key = _basic_slot(now)
            if not force and (slot_key is None or state.get("last_slot") == slot_key):
                return cached
        else:
            try:
                last_attempt = float(state.get("last_attempt", 0))
            except (TypeError, ValueError):
                last_attempt = 0
            if not force and now - last_attempt < interval:
                return cached

        state["feed_version"] = FEED_VERSION
        state["last_attempt"] = now
        state["mode"] = mode
        state["session"] = session
        state["interval_seconds"] = interval if mode == "pro" else None
        if slot_key:
            state["last_slot"] = slot_key
        state["items"] = cached
        _write(state)

        fresh = []
        ok_categories = []
        failed_categories = []
        try:
            fresh = _request_news(key, opener)
            ok_categories.append("overall")
            print(
                "[provider:tradingview-bundle] category=overall items=%s"
                % len(fresh),
                flush=True,
            )
        except Exception as exc:
            failed_categories.append("overall")
            print(
                "[provider:tradingview-bundle] category=overall error=%s"
                % type(exc).__name__,
                flush=True,
            )

        state["items"] = _merge(fresh, cached, now)
        state["last_success"] = now if ok_categories else state.get("last_success", 0)
        state["ok_categories"] = ok_categories
        state["failed_categories"] = failed_categories
        state["requests_last_refresh"] = 1
        state["requests_total"] = int(state.get("requests_total", 0) or 0) + 1
        _write(state)
        print(
            "[provider:tradingview-bundle] refreshed mode=%s session=%s items=%s categories=%s"
            % (mode, session, len(state["items"]), ",".join(ok_categories)),
            flush=True,
        )
        return state["items"]
