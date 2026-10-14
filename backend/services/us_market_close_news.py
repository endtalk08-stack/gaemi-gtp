"""New York closing-session news, using the existing shared NAVER news fetcher.

This is a market-scoped result, not stock-news selection. It is fetched only
when explicitly requested; /analyze and the central chat are not changed.
"""
import datetime
import re
import threading
import time
from zoneinfo import ZoneInfo

from backend.providers import naver_news
from .news_feed import _fetch_queries


_NY_TZ = ZoneInfo("America/New_York")
_QUERIES = ("뉴욕증시 마감", "미국 증시 마감")
_MARKET_WORDS = ("뉴욕증시", "미국증시", "미국 증시", "미 증시", "나스닥", "다우", "s&p", "월가")
_CLOSE_WORDS = ("마감", "거래 마쳐", "거래를 마쳐", "장을 마쳐", "종가", "폐장")
_NOT_CLOSED = ("개장", "장중", "선물", "마감 앞두", "마감 전", "마감 전망", "마감 예상")
_DOMESTIC_HEADLINES = ("코스피", "코스닥", "국내증시", "한국증시", "한국 증시")
_CACHE_LOCK = threading.Lock()
_CACHE = None
_CACHED_AT = 0.0
_SUCCESS_TTL = 10 * 60
_EMPTY_TTL = 45
# Bound external work: at most 20 metadata hits and 6 body reads.
_PER_QUERY = 10
_MAX_BODY_READS = 6
_MAX_ARTICLES = 4
_SECTOR_WORDS = (
    "반도체", "기술주", "빅테크", "전기차", "에너지", "금융주", "은행주",
    "바이오", "헬스케어", "소비재", "산업재", "자동차주", "항공주",
    "유틸리티", "원전", "전력", "방산",
)
_RISING_WORDS = ("상승", "강세", "급등", "반등", "올랐", "오름세")
_FALLING_WORDS = ("하락", "약세", "급락", "내렸", "내림세")
_FACTOR_WORDS = (
    "국채금리", "기준금리", "금리", "연준", "fomc", "cpi", "pce",
    "물가", "고용", "실업률", "기업 실적", "실적 발표", "유가",
    "관세", "달러", "원유", "경제지표", "인플레이션",
)


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


def _information_coverage(text):
    """Detect *mentions* of needed information; do not infer actual price moves."""
    content = str(text or "").casefold()
    coverage = set()
    index_hits = sum(
        marker in content
        for marker in ("나스닥", "다우", "s&p", "스탠더드앤드푸어스")
    )
    if index_hits >= 2 or "3대 지수" in content or "3대지수" in content:
        coverage.add("indices")

    # Require sector and direction words in the same sentence. A keyword
    # anywhere in an article is not enough to count as an industry move.
    for sentence in re.split(r"(?<=[.!?])\\s+|[\\n\\r]+", content):
        if not any(word in sentence for word in _SECTOR_WORDS):
            continue
        if any(word in sentence for word in _RISING_WORDS):
            coverage.add("rising_sectors")
        if any(word in sentence for word in _FALLING_WORDS):
            coverage.add("falling_sectors")
    if any(word in content for word in _FACTOR_WORDS):
        coverage.add("market_factors")
    return coverage


def _select_informative_articles(candidates, size):
    """Read a few candidate originals, keep only verified, complementary bodies."""
    from .news_detail import read_selected_article_details

    ranked = sorted(
        candidates,
        key=lambda item: (
            len(_information_coverage(
                str(item.get("title") or "") + " " + str(item.get("description") or "")
            )),
            str(item.get("published_at") or ""),
        ),
        reverse=True,
    )[:_MAX_BODY_READS]
    if not ranked:
        return []

    details = read_selected_article_details(ranked, limit=len(ranked), with_sources=True)
    verified = []
    for article, detail in zip(ranked, details):
        if detail.get("source") not in {"jsonld_article_body", "article_or_main_paragraphs"}:
            continue
        body = str(detail.get("text") or "").strip()
        if len(body) < 160:
            continue
        coverage = _information_coverage(body)
        if len(coverage) < 2:
            continue
        verified.append({
            **article, "article_body": body, "detail_source": detail["source"],
            "information_coverage": sorted(coverage),
        })

    verified.sort(
        key=lambda article: (
            len(article["information_coverage"]),
            len(article["article_body"]),
            article.get("published_at") or "",
        ),
        reverse=True,
    )
    chosen = []
    covered = set()
    for article in verified:
        new_information = set(article["information_coverage"]) - covered
        if not new_information:
            continue
        chosen.append(article)
        covered.update(new_information)
        if len(chosen) >= size or len(covered) == 4:
            break
    return chosen


def build_us_market_close_news_result(limit=3, *, now=None, include_body=False):
    """Select a few fact-bearing NY close articles from the existing Naver feed.

    A per-worker lock coalesces concurrent calls. Raw article text remains in
    the internal result cache; the inspection API never returns full bodies.
    No background work, /analyze changes, or AI calls.
    """
    global _CACHE, _CACHED_AT
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    session = _last_completed_session(current).isoformat()
    size = max(1, min(int(limit), _MAX_ARTICLES))
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
            items = _fetch_queries(_QUERIES, category="미국장 마감", per_query=_PER_QUERY)
            candidates = [
                {**item, "market": "us", "news_scope": "market_close", "session_date": session}
                for item in items
                if _matches_market_close(item, datetime.date.fromisoformat(session), current)
            ]
            selected = _select_informative_articles(candidates, _MAX_ARTICLES)
            _CACHE = {
                **base, "ok": True,
                "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "items": selected,
            }
            _CACHED_AT = time.monotonic()

        result_items = []
        for article in _CACHE["items"][:size]:
            copy = dict(article)
            if not include_body:
                copy.pop("article_body", None)
            result_items.append(copy)
        return {**_CACHE, "items": result_items}
