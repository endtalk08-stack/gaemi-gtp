"""Test-only Marketaux news normalization and broad category classification."""

import datetime
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.providers.marketaux_news import (
    MarketauxConfigurationError,
    MarketauxRequestError,
    fetch_news,
)


CATEGORIES = ("전체", "증시", "종목", "경제지표", "에너지", "연준", "일정", "투자의견", "실적발표")
_CACHE_TTL_SECONDS = 300
_cache = {}
_cache_lock = threading.Lock()
_feed_cache = None
_FEED_CACHE_TTL_SECONDS = 1800

_CATEGORY_SEARCH = {
    "전체": "stock market",
    "증시": "stock market",
    "종목": "company shares",
    "경제지표": "inflation GDP employment CPI",
    "에너지": "energy oil gas",
    "연준": "Federal Reserve FOMC interest rates",
    "일정": "economic calendar upcoming meeting",
    "투자의견": "analyst rating price target",
    "실적발표": "earnings revenue guidance",
}

_CATEGORY_TERMS = (
    ("실적발표", ("earnings", "revenue", "guidance", "quarterly results", "profit")),
    ("경제지표", ("cpi", "gdp", "inflation", "employment", "jobs report", "pce")),
    ("연준", ("federal reserve", "fomc", "fed ", "powell", "interest rate")),
    ("에너지", ("energy", "oil", "crude", "gas", "opec")),
    ("투자의견", ("analyst", "rating", "price target", "upgrade", "downgrade")),
    ("일정", ("calendar", "scheduled", "upcoming", "meeting", "conference")),
)

# Test feed: each group is one Marketaux request and returns up to three items.
# Country filters refer to the exchange country identified for an article entity.
TEST_FEEDS = (
    ("한국시장", {"countries": "kr", "search": "stock market"}),
    ("미국시장", {"countries": "us", "search": "stock market"}),
    ("글로벌 증시", {"search": "global stock market"}),
    ("주요 산업", {"search": "(semiconductor | \"artificial intelligence\")", "industries": "Technology"}),
    ("거시경제", {"search": "(inflation | \"interest rate\" | employment)"}),
    ("실적발표", {"search": "(earnings | revenue | guidance)"}),
)


def _display_age(value):
    try:
        published_at = datetime.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=datetime.timezone.utc)
        seconds = max(0, int((datetime.datetime.now(datetime.timezone.utc) - published_at).total_seconds()))
    except (TypeError, ValueError):
        return ""

    if seconds < 60:
        return "방금 전"
    if seconds < 3600:
        return f"{seconds // 60}분 전"
    if seconds < 86400:
        return f"{seconds // 3600}시간 전"
    return f"{seconds // 86400}일 전"


def _classify(item):
    text = " ".join(
        str(item.get(field) or "")
        for field in ("title", "description", "snippet")
    ).lower()
    for category, terms in _CATEGORY_TERMS:
        if any(term in text for term in terms):
            return category

    entities = item.get("entities") or []
    if any(isinstance(entity, dict) and entity.get("symbol") for entity in entities):
        return "종목"
    return "증시"


def _normalize(item, category=None):
    title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
    url = str(item.get("url") or "").strip()
    if not title or not url:
        return None

    source = item.get("source") or {}
    if not isinstance(source, dict):
        source = {}
    entities = item.get("entities") or []
    symbols = [
        str(entity.get("symbol"))
        for entity in entities
        if isinstance(entity, dict) and entity.get("symbol")
    ]
    return {
        "id": str(item.get("uuid") or url),
        "category": category or _classify(item),
        "title": title,
        "description": re.sub(r"\s+", " ", str(item.get("description") or item.get("snippet") or "")).strip(),
        "source": str(source.get("name") or source.get("domain") or "Marketaux"),
        "published_at": str(item.get("published_at") or ""),
        "display_datetime": _display_age(item.get("published_at")),
        "url": url,
        "language": str(item.get("language") or "en"),
        "symbols": symbols,
    }


def fetch_marketaux_news(category="전체", limit=3):
    """Return a small, normalized Marketaux news result for the test panel."""
    category = str(category or "전체").strip()
    if category not in CATEGORIES:
        category = "전체"
    limit = max(1, min(int(limit or 3), 3))
    cache_key = (category, limit)

    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
            return [dict(item) for item in cached[1]]

    payload = fetch_news(search=_CATEGORY_SEARCH[category], limit=limit)
    items = [normalized for raw in payload["data"] if (normalized := _normalize(raw))]
    if category != "전체":
        matching = [item for item in items if item["category"] == category]
        items = matching or items
    result = items[:limit]

    with _cache_lock:
        _cache[cache_key] = (time.time(), [dict(item) for item in result])
    return result


def fetch_marketaux_test_feed():
    """Return six broad test feeds from one cached, parallel Marketaux refresh."""
    global _feed_cache
    with _cache_lock:
        if _feed_cache and time.time() - _feed_cache[0] < _FEED_CACHE_TTL_SECONDS:
            return {category: [dict(item) for item in items] for category, items in _feed_cache[1].items()}

    def fetch_one(category, params):
        payload = fetch_news(**params, limit=3)
        return category, [
            normalized
            for raw in payload["data"]
            if (normalized := _normalize(raw, category=category))
        ][:3]

    feeds = {}
    with ThreadPoolExecutor(max_workers=len(TEST_FEEDS)) as executor:
        futures = [executor.submit(fetch_one, category, params) for category, params in TEST_FEEDS]
        for future in as_completed(futures):
            category, items = future.result()
            feeds[category] = items

    ordered_feeds = {category: feeds.get(category, []) for category, _ in TEST_FEEDS}
    with _cache_lock:
        _feed_cache = (time.time(), ordered_feeds)
    return {category: [dict(item) for item in items] for category, items in ordered_feeds.items()}


__all__ = [
    "CATEGORIES",
    "MarketauxConfigurationError",
    "MarketauxRequestError",
    "fetch_marketaux_news",
    "fetch_marketaux_test_feed",
]
