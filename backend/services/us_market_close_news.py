"""New York closing-session news, using the existing shared NAVER news fetcher.

This is a market-scoped result, not stock-news selection. It is fetched only
when explicitly requested; /analyze and the central chat are not changed.
"""
import datetime
import threading
import time
from zoneinfo import ZoneInfo

from backend.providers import naver_news
from .news_feed import _fetch_queries


_NY_TZ = ZoneInfo("America/New_York")
_QUERIES = ("뉴욕증시 마감", "미국 증시 마감", "뉴욕증시 다우 나스닥")
_MARKET_WORDS = ("뉴욕증시", "미국증시", "미국 증시", "미 증시", "나스닥", "다우", "s&p", "월가")
_CLOSE_WORDS = ("마감", "거래 마쳐", "거래를 마쳐", "장을 마쳐", "종가", "폐장")
_NOT_CLOSED = ("개장", "장중", "선물", "마감 앞두", "마감 전", "마감 전망", "마감 예상")
_DOMESTIC_HEADLINES = ("코스피", "코스닥", "국내증시", "한국증시", "한국 증시")
_CACHE_LOCK = threading.Lock()
_CACHE = None
_CACHED_AT = 0.0
_SUCCESS_TTL = 10 * 60
_EMPTY_TTL = 45


def _last_completed_session(now):
    """Identify the latest completed NY weekday close, not the KST date."""
    local = now.astimezone(_NY_TZ)
    session = local.date()
    if local.weekday() >= 5 or local.time() < datetime.time(16):
        session -= datetime.timedelta(days=1)
    while session.weekday() >= 5:
        session -= datetime.timedelta(days=1)
    return session


def _matches_market_close(item, session, now):
    title = str(item.get("title") or "").casefold()
    description = str(item.get("description") or "").casefold()
    if not any(word in title for word in _MARKET_WORDS):
        return False
    if any(word in title for word in _DOMESTIC_HEADLINES):
        return False
    if any(word in title for word in _NOT_CLOSED):
        return False
    if not any(word in (title + " " + description) for word in _CLOSE_WORDS):
        return False
    try:
        published = datetime.datetime.fromisoformat(
            str(item.get("published_at") or "").replace("Z", "+00:00")
        )
        if published.tzinfo is None:
            return False
    except (ValueError, TypeError):
        return False

    # Reports published from 16:00 ET through 10:00 ET the following day.
    # Never include upcoming/pre-close articles or a different US session.
    start = datetime.datetime.combine(session, datetime.time(16), tzinfo=_NY_TZ)
    end = start + datetime.timedelta(hours=18)
    local_time = published.astimezone(_NY_TZ)
    return start <= local_time <= end and published <= now


def build_us_market_close_news_result(limit=12, *, now=None):
    """Return one bounded, cached market-news result for future consumers.

    Reuses the shared NAVER query cache and normalization. A lock coalesces
    simultaneous calls to this result within one worker. No background fetch.
    """
    global _CACHE, _CACHED_AT
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    session = _last_completed_session(current).isoformat()
    size = max(1, min(int(limit), 20))
    base = {"market": "us", "kind": "close_news", "session_date": session, "source": "naver"}

    if not naver_news.is_configured():
        return {**base, "ok": False, "error": "source_not_configured", "items": []}

    with _CACHE_LOCK:
        stamp = time.monotonic()
        ttl = _SUCCESS_TTL if _CACHE and _CACHE["items"] else _EMPTY_TTL
        if (
            _CACHE is None
            or _CACHE["session_date"] != session
            or stamp - _CACHED_AT >= ttl
        ):
            items = _fetch_queries(_QUERIES, category="미국장 마감", per_query=15)
            selected = [
                {**item, "market": "us", "news_scope": "market_close", "session_date": session}
                for item in items
                if _matches_market_close(item, datetime.date.fromisoformat(session), current)
            ][:20]
            _CACHE = {
                **base,
                "ok": True,
                "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "items": selected,
            }
            _CACHED_AT = time.monotonic()

        return {**_CACHE, "items": [dict(item) for item in _CACHE["items"][:size]]}
