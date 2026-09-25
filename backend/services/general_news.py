"""General news feed for the gaemiGTP right-side news workspace.

Display-only feed:
- title / source / published time / original link
- Naver Search API is used when NAVER_CLIENT_ID and NAVER_CLIENT_SECRET exist
- Google News RSS is a fallback when Naver credentials are unavailable or fail
"""

import datetime
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime


_CACHE = {}
_CACHE_TTL = 120
_CACHE_LOCK = threading.Lock()

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "").strip().strip("'\"")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip().strip("'\"")

CATEGORY_QUERIES = {
    "전체": ["증시", "주식", "경제", "반도체", "연준"],
    "증시": ["증시", "코스피", "코스닥", "나스닥"],
    "종목": ["기업 주식", "상장사", "반도체 기업"],
    "경제지표": ["CPI", "GDP", "고용 물가"],
    "에너지": ["유가", "원유", "에너지"],
    "연준": ["연준", "FOMC"],
    "일정": ["경제 일정", "FOMC 일정", "실적 발표 일정"],
    "투자의견": ["목표주가", "투자의견"],
    "실적발표": ["실적 발표", "매출 영업이익"],
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
        host = urllib.parse.urlparse(url or "").netloc.lower()
        host = host.removeprefix("www.")
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


def _naver_search(query, display=20):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    url = (
        "https://openapi.naver.com/v1/search/news.json?"
        + urllib.parse.urlencode({
            "query": query,
            "display": max(1, min(int(display), 100)),
            "start": 1,
            "sort": "date",
        })
    )
    req = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            "User-Agent": "gaemiGTP/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[general-news] Naver search failed query={query}: {type(exc).__name__}: {exc}")
        return []

    rows = []
    for item in payload.get("items", []):
        title = _strip_html(item.get("title"))
        original_link = str(item.get("originallink") or item.get("link") or "").strip()
        pub_date = str(item.get("pubDate") or "").strip()
        if not title or not original_link:
            continue
        rows.append({
            "title": title,
            "source": _source_from_url(original_link),
            "pub_date": pub_date,
            "link": original_link,
            "provider": "naver",
        })
    return rows


def _google_rss_search(query, days=2):
    search_query = f"{query} when:{max(1, int(days))}d"
    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({
            "q": search_query,
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko",
        })
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            root = ET.fromstring(resp.read())
    except Exception as exc:
        print(f"[general-news] Google RSS failed query={query}: {type(exc).__name__}: {exc}")
        return []

    rows = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        source_el = item.find("source")
        pub_el = item.find("pubDate")
        link_el = item.find("link")

        title = _strip_html(title_el.text if title_el is not None else "")
        # Google News 제목 뒤에 붙는 "- 언론사"를 제거.
        title = re.sub(r"\s*[-–—―|]\s*[^-–—―|]+$", "", title).strip()
        source = _strip_html(source_el.text if source_el is not None else "")
        pub_date = _strip_html(pub_el.text if pub_el is not None else "")
        link = _strip_html(link_el.text if link_el is not None else "")
        if not title or not link:
            continue
        rows.append({
            "title": title,
            "source": source or "Google News",
            "pub_date": pub_date,
            "link": link,
            "provider": "google",
        })
    return rows


def _collect_queries(queries):
    queries = [q for q in queries if str(q or "").strip()]
    if not queries:
        return []

    def worker(q):
        rows = _naver_search(q, 20)
        if rows:
            return rows
        return _google_rss_search(q, 2)

    output = []
    executor = ThreadPoolExecutor(max_workers=min(5, len(queries)))
    try:
        futures = [executor.submit(worker, q) for q in queries]
        for future in futures:
            try:
                output.extend(future.result())
            except Exception:
                pass
    finally:
        executor.shutdown(wait=True)
    return output


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

    queries = [query] if query else CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["전체"])
    raw = _collect_queries(queries)

    seen = set()
    items = []
    for row in raw:
        title = _strip_html(row.get("title"))
        key = re.sub(r"[^0-9a-zA-Z가-힣]", "", title.lower())
        if not title or not key or key in seen:
            continue
        seen.add(key)

        item_category = category if category != "전체" and not query else _classify(title)
        pub_date = str(row.get("pub_date") or "").strip()
        items.append({
            "id": key[:40],
            "category": item_category,
            "title": title,
            "source": str(row.get("source") or "출처 확인").strip(),
            "pub_date": pub_date,
            "display_datetime": _display_age(pub_date),
            "link": str(row.get("link") or "").strip(),
            "original_link": str(row.get("link") or "").strip(),
        })

    items.sort(key=lambda x: _parse_date(x.get("pub_date")), reverse=True)
    result = items[:limit]

    with _CACHE_LOCK:
        _CACHE[cache_key] = (time.time(), [dict(item) for item in result])

    return result
