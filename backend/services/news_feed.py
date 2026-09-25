"""General news feed processing.

Boundary:
providers/*  -> external source retrieval only
news_feed.py -> normalize / dedupe / classify / sort / cache
app.py       -> HTTP transport only
frontend     -> rendering only
"""

import datetime
import html
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime

from backend.providers import google_news, naver_news


_CACHE = {}
_CACHE_TTL = 120
_CACHE_LOCK = threading.Lock()

# Keep requests small. "전체" uses only two broad searches instead of five separate searches.
CATEGORY_QUERIES = {
    "전체": ["증시", "경제"],
    "증시": ["코스피 코스닥 나스닥"],
    "종목": ["상장사 주식"],
    "경제지표": ["CPI GDP 고용 물가"],
    "에너지": ["유가 원유 에너지"],
    "연준": ["연준 FOMC 금리"],
    "일정": ["경제 일정 FOMC 일정"],
    "투자의견": ["목표주가 투자의견"],
    "실적발표": ["실적 발표 매출 영업이익"],
}

SOURCE_DOMAINS = {
    "hankyung.com": "한국경제",
    "yna.co.kr": "연합뉴스",
    "mk.co.kr": "매일경제",
    "sedaily.com": "서울경제",
    "edaily.co.kr": "이데일리",
    "mt.co.kr": "머니투데이",
    "biz.chosun.com": "조선비즈",
    "chosun.com": "조선일보",
    "fnnews.com": "파이낸셜뉴스",
    "hankookilbo.com": "한국일보",
    "heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문",
    "newsis.com": "뉴시스",
    "donga.com": "동아일보",
    "joongang.co.kr": "중앙일보",
    "khan.co.kr": "경향신문",
    "zdnet.co.kr": "ZDNet Korea",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
}


def _strip_html(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _source_from_url(url):
    try:
        host = urllib.parse.urlparse(url or "").netloc.lower().removeprefix("www.")
        for domain, label in SOURCE_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return label
        if host:
            return host
    except Exception:
        pass
    return "출처 확인"


def _parse_date(value):
    try:
        dt = parsedate_to_datetime(str(value or "").strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def _display_age(value):
    dt = _parse_date(value)
    if dt.year <= 1:
        return ""
    now = datetime.datetime.now(datetime.timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return "방금 전"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    days = hours // 24
    if days < 7:
        return f"{days}일 전"
    return dt.astimezone().strftime("%m/%d")


def _classify(title):
    t = str(title or "").lower()
    rules = [
        ("실적발표", ["실적", "매출", "영업이익", "순이익", "earnings"]),
        ("경제지표", ["cpi", "gdp", "pce", "고용", "실업률", "물가", "소비자물가"]),
        ("연준", ["연준", "fomc", "fed", "파월", "금리"]),
        ("에너지", ["유가", "원유", "석유", "정유", "천연가스", "에너지"]),
        ("투자의견", ["목표주가", "투자의견", "상향", "하향", "증권사"]),
        ("일정", ["예정", "일정", "회의", "컨퍼런스", "개최"]),
        ("종목", ["삼성전자", "sk하이닉스", "엔비디아", "테슬라", "애플", "현대차", "naver"]),
    ]
    for category, words in rules:
        if any(word in t for word in words):
            return category
    return "증시"


def _normalize_provider_row(row, requested_category):
    provider = str(row.get("provider") or "").strip()
    title = _strip_html(row.get("raw_title"))
    raw_source = _strip_html(row.get("raw_source"))
    pub_date = _strip_html(row.get("raw_pub_date"))
    raw_link = str(row.get("raw_link") or "").strip()
    original_link = str(row.get("raw_original_link") or "").strip()

    if provider == "google":
        # Google RSS title commonly ends with the publisher name.
        title = re.sub(r"\s*[-–—―|]\s*[^-–—―|]+$", "", title).strip()
        source = raw_source or "Google News"
        final_link = raw_link
    else:
        final_link = original_link or raw_link
        source = raw_source or _source_from_url(final_link)

    if not title or not final_link:
        return None

    category = requested_category if requested_category != "전체" else _classify(title)
    return {
        "provider": provider,
        "category": category,
        "title": title,
        "source": source,
        "pub_date": pub_date,
        "display_datetime": _display_age(pub_date),
        "link": final_link,
        "original_link": final_link,
    }


def _fetch_provider(provider_name, query):
    if provider_name == "naver":
        return naver_news.fetch_news(query, display=20)
    return google_news.fetch_news(query, days=2)


def _collect_raw_rows(queries):
    queries = [q for q in queries if str(q or "").strip()]
    if not queries:
        return []

    jobs = [(provider, query) for query in queries for provider in ("naver", "google")]
    rows = []

    # Naver and Google run in parallel. One slow provider no longer blocks the other first.
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as executor:
        futures = [executor.submit(_fetch_provider, provider, query) for provider, query in jobs]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception:
                pass
    return rows


def fetch_general_news(category="전체", query="", limit=10):
    category = str(category or "전체").strip()
    if category not in CATEGORY_QUERIES:
        category = "전체"

    query = str(query or "").strip()
    limit = max(1, min(int(limit or 10), 20))

    cache_key = (category, query.lower(), limit)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            return [dict(item) for item in cached[1]]

    queries = [query] if query else CATEGORY_QUERIES[category]
    raw_rows = _collect_raw_rows(queries)

    items = []
    seen = set()

    for raw in raw_rows:
        item = _normalize_provider_row(raw, category)
        if not item:
            continue

        duplicate_key = re.sub(r"[^0-9a-zA-Z가-힣]", "", item["title"].lower())
        if not duplicate_key or duplicate_key in seen:
            continue
        seen.add(duplicate_key)

        item["id"] = duplicate_key[:40]
        items.append(item)

    items.sort(key=lambda x: _parse_date(x.get("pub_date")), reverse=True)
    result = items[:limit]

    with _CACHE_LOCK:
        _CACHE[cache_key] = (time.time(), [dict(item) for item in result])

    return result
