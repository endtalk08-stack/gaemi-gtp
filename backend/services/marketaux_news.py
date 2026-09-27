"""Test-only Marketaux news normalization and verified category classification."""

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
_FEED_CACHE_TTL_SECONDS = 21600

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

_EARNINGS_PATTERN = re.compile(r"\b(earnings|eps|revenue|profit|guidance|quarterly results|financial results|net income)\b", re.IGNORECASE)
_FED_PATTERN = re.compile(r"\b(federal reserve|fomc|jerome powell|powell|fed)\b", re.IGNORECASE)
_ENERGY_PATTERN = re.compile(r"\b(oil|crude|opec|lng|natural gas|liquefied natural gas|brent|wti|refinery|gasoline|diesel)\b", re.IGNORECASE)
_OPINION_PATTERN = re.compile(r"\b(analyst|rating|price target|upgrade|downgrade|overweight|underweight|buy rating|sell rating|initiated coverage)\b", re.IGNORECASE)
_ECONOMIC_INDICATOR_PATTERN = re.compile(r"\b(cpi|pce|gdp|inflation|employment|unemployment|nonfarm payroll|jobs report|jobless claims|consumer price index|producer price index|retail sales|pmi)\b", re.IGNORECASE)
_SCHEDULE_PATTERN = re.compile(r"\b(economic calendar|fomc meeting|earnings (?:release|report|announcement|calendar|date|season|call)|investor day|results call|conference call|(?:cpi|pce|gdp|employment|payroll|pmi|inflation) (?:release|report|data|due|scheduled))\b", re.IGNORECASE)
_MARKET_PATTERN = re.compile(r"\b(stock market|equity market|share market|market close|market open|trading session|nasdaq|nyse|s&p|dow jones|sensex|nifty|stock(?:s)? (?:rise|rises|rose|fall|falls|fell|rally|rallies|rallied|slide|slides|slid|gain|gains|gained|drop|drops|dropped))\b", re.IGNORECASE)

TEST_FEEDS = (
    ("증시", {"search": "stock market"}),
    ("종목", {"search": "(company shares | stock performance)", "countries": "us,kr"}),
    ("경제지표", {"search": "(inflation | GDP | employment | CPI)"}),
    ("에너지", {"search": "(energy | oil | crude | gas | OPEC)"}),
    ("연준", {"search": "(Federal Reserve | FOMC | Powell | \"interest rate\")"}),
    ("일정", {"search": "(economic calendar | scheduled | upcoming meeting)"}),
    ("투자의견", {"search": "(analyst rating | \"price target\" | upgrade | downgrade)"}),
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
    if seconds < 60: return "방금 전"
    if seconds < 3600: return f"{seconds // 60}분 전"
    if seconds < 86400: return f"{seconds // 3600}시간 전"
    return f"{seconds // 86400}일 전"


def _article_text(item):
    return " ".join(str(item.get(field) or "") for field in ("title", "description", "snippet"))


def _classify(item):
    text = _article_text(item)
    entities = item.get("entities") or []
    has_ticker = any(isinstance(entity, dict) and str(entity.get("symbol") or "").strip() for entity in entities)
    if _SCHEDULE_PATTERN.search(text): return "일정"
    if _EARNINGS_PATTERN.search(text): return "실적발표"
    if _FED_PATTERN.search(text): return "연준"
    if _ECONOMIC_INDICATOR_PATTERN.search(text): return "경제지표"
    if _ENERGY_PATTERN.search(text): return "에너지"
    if _OPINION_PATTERN.search(text): return "투자의견"
    if has_ticker: return "종목"
    if _MARKET_PATTERN.search(text): return "증시"
    return None


def _normalize(item, category=None):
    title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
    url = str(item.get("url") or "").strip()
    if not title or not url: return None
    source = item.get("source") or {}
    if not isinstance(source, dict): source = {}
    entities = item.get("entities") or []
    symbols = [str(entity.get("symbol")) for entity in entities if isinstance(entity, dict) and entity.get("symbol")]
    return {
        "id": str(item.get("uuid") or url), "category": category, "title": title,
        "description": re.sub(r"\s+", " ", str(item.get("description") or item.get("snippet") or "")).strip(),
        "source": str(source.get("name") or source.get("domain") or "Marketaux"),
        "published_at": str(item.get("published_at") or ""), "display_datetime": _display_age(item.get("published_at")),
        "url": url, "language": str(item.get("language") or "en"), "symbols": symbols,
    }


def fetch_marketaux_news(category="전체", limit=3):
    category = str(category or "전체").strip()
    if category not in CATEGORIES: category = "전체"
    limit = max(1, min(int(limit or 3), 3))
    cache_key = (category, limit)
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
            return [dict(item) for item in cached[1]]
    payload = fetch_news(search=_CATEGORY_SEARCH[category], limit=limit)
    items, seen = [], set()
    for raw in payload["data"]:
        normalized = _normalize(raw)
        if not normalized: continue
        assigned_category = _classify(raw)
        if not assigned_category or (category != "전체" and assigned_category != category): continue
        identity = normalized["id"]
        if identity in seen: continue
        seen.add(identity); normalized["category"] = assigned_category; items.append(normalized)
    result = items[:limit]
    with _cache_lock: _cache[cache_key] = (time.time(), [dict(item) for item in result])
    return result


def fetch_marketaux_test_feed():
    """Build the right-panel feed without letting one failed upstream request kill all news."""
    global _feed_cache
    with _cache_lock:
        if _feed_cache and time.time() - _feed_cache[0] < _FEED_CACHE_TTL_SECONDS:
            return {category: [dict(item) for item in items] for category, items in _feed_cache[1].items()}

    def fetch_one(category, params):
        try:
            payload = fetch_news(**params, limit=3)
            return category, payload.get("data") or [], None
        except (MarketauxConfigurationError, MarketauxRequestError) as exc:
            return category, [], exc
        except Exception as exc:
            print(f"[Marketaux feed] {category} failed: {type(exc).__name__}: {exc}")
            return category, [], exc

    raw_items = []
    failures = 0
    with ThreadPoolExecutor(max_workers=min(4, len(TEST_FEEDS))) as executor:
        futures = [executor.submit(fetch_one, category, params) for category, params in TEST_FEEDS]
        for future in as_completed(futures):
            category, items, error = future.result()
            if error:
                failures += 1
                print(f"[Marketaux feed] skipped failed category: {category}")
                continue
            raw_items.extend(items)

    feeds = {category: [] for category, _ in TEST_FEEDS}
    seen = set()
    for raw in raw_items:
        normalized = _normalize(raw)
        if not normalized: continue
        identity = normalized["id"]
        if identity in seen: continue
        seen.add(identity)
        category = _classify(raw)
        if category not in feeds: continue
        normalized["category"] = category
        if len(feeds[category]) < 3: feeds[category].append(normalized)

    ordered_feeds = {category: feeds.get(category, []) for category, _ in TEST_FEEDS}
    # Cache partial successes too. If every upstream call failed, return empty feeds
    # instead of turning the whole right panel into an error state.
    if raw_items:
        with _cache_lock: _feed_cache = (time.time(), ordered_feeds)
    if failures:
        print(f"[Marketaux feed] completed with {failures}/{len(TEST_FEEDS)} failed requests")
    return {category: [dict(item) for item in items] for category, items in ordered_feeds.items()}


__all__ = ["CATEGORIES", "MarketauxConfigurationError", "MarketauxRequestError", "fetch_marketaux_news", "fetch_marketaux_test_feed"]
