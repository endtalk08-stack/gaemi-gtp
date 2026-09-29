"""Shared NAVER news feed normalization for the panel and central chat."""

import datetime
import html
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime

from backend.providers import naver_news

_CACHE = {}
_CACHE_TTL = 120
_CACHE_LOCK = threading.Lock()

CATEGORY_QUERIES = {
    "전체": ["증시", "경제"], "증시": ["코스피 코스닥 나스닥"], "종목": ["상장사 주식"],
    "경제지표": ["CPI GDP 고용 물가"], "에너지": ["유가 원유 에너지"], "연준": ["연준 FOMC 금리"],
    "일정": ["경제 일정 FOMC 일정"], "투자의견": ["목표주가 투자의견"],
    "실적발표": ["실적 발표 매출 영업이익"],
}

# First-release coverage is intentionally limited to 10 Korean and 10 US names.
# It is configurable coverage, not a live market-cap ranking claim.
STOCK_UNIVERSE = {
    "국내": {
        "삼성전자": ["삼성전자", "samsung electronics"],
        "SK하이닉스": ["sk하이닉스", "하이닉스", "sk hynix"],
        "LG에너지솔루션": ["lg에너지솔루션", "lg energy solution"],
        "삼성바이오로직스": ["삼성바이오로직스", "samsung biologics"],
        "현대차": ["현대차", "현대자동차", "hyundai motor"],
        "기아": ["기아", "kia"],
        "한화에어로스페이스": ["한화에어로스페이스", "hanwha aerospace"],
        "KB금융": ["kb금융", "kb financial"],
        "NAVER": ["naver", "네이버"],
        "두산에너빌리티": ["두산에너빌리티", "doosan enerbility"],
    },
    "미국": {
        "엔비디아": ["엔비디아", "nvidia"], "애플": ["애플", "apple"],
        "마이크로소프트": ["마이크로소프트", "microsoft"], "아마존": ["아마존", "amazon"],
        "알파벳": ["알파벳", "google", "alphabet"], "메타": ["메타", "meta platforms"],
        "브로드컴": ["브로드컴", "broadcom"], "테슬라": ["테슬라", "tesla"],
        "버크셔 해서웨이": ["버크셔", "berkshire"], "일라이 릴리": ["일라이 릴리", "eli lilly"],
    },
}

THEME_RULES = {
    "반도체": ["반도체", "hbm", "dram", "낸드", "파운드리", "메모리", "칩"],
    "AI·소프트웨어": ["ai", "인공지능", "소프트웨어", "클라우드", "데이터센터"],
    "2차전지": ["2차전지", "배터리", "양극재", "음극재"],
    "자동차·모빌리티": ["자동차", "전기차", "자율주행", "모빌리티"],
    "바이오·헬스케어": ["바이오", "제약", "헬스케어", "신약", "의료"],
    "에너지": ["유가", "원유", "천연가스", "에너지", "정유", "전력"],
    "조선": ["조선", "선박", "lng선", "수주"], "방산": ["방산", "국방", "무기", "미사일"],
    "금융": ["은행", "금융", "증권", "보험", "채권"],
    "인터넷·플랫폼": ["플랫폼", "인터넷", "이커머스", "광고"],
    "로봇·자동화": ["로봇", "자동화", "휴머노이드"],
}

ISSUE_RULES = {
    "금리·통화정책": ["금리", "연준", "fomc", "fed", "파월", "한국은행"],
    "물가·경제지표": ["cpi", "pce", "gdp", "고용", "실업률", "물가", "소비자물가"],
    "실적발표": ["실적", "매출", "영업이익", "순이익", "eps", "earnings"],
    "반도체 업황": ["반도체", "hbm", "dram", "메모리", "파운드리"],
    "AI 투자": ["ai", "인공지능", "데이터센터"],
    "유가·에너지": ["유가", "원유", "천연가스", "opec", "정유"],
    "환율": ["환율", "원달러", "달러", "엔화", "위안"],
    "정책·규제": ["정부", "정책", "규제", "법안", "관세"],
    "공급망": ["공급망", "수급", "공급", "재고", "운임"],
}

SOURCE_DOMAINS = {
    "hankyung.com": "한국경제", "yna.co.kr": "연합뉴스", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "edaily.co.kr": "이데일리", "mt.co.kr": "머니투데이", "biz.chosun.com": "조선비즈", "chosun.com": "조선일보",
    "fnnews.com": "파이낸셜뉴스", "hankookilbo.com": "한국일보", "heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문", "newsis.com": "뉴시스", "donga.com": "동아일보", "joongang.co.kr": "중앙일보",
    "khan.co.kr": "경향신문", "zdnet.co.kr": "ZDNet Korea",
}
MARKET_CORE_WORDS = [
    "증시", "주식", "주가", "코스피", "코스닥", "나스닥", "다우", "s&p", "상장", "ipo", "시가총액",
    "외국인", "기관", "매수", "매도", "거래량", "거래대금", "실적", "매출", "영업이익", "순이익",
    "배당", "공시", "목표주가", "투자의견", "금리", "연준", "fomc", "환율", "cpi", "pce", "gdp",
    "고용", "물가", "유가", "원유", "반도체", "배터리", "2차전지", "자동차", "조선", "방산", "바이오",
    "ai", "인공지능", "수출", "관세", "무역", "공급망", "투자", "인수", "합병",
]
MARKET_CONTEXT_WORDS = ["기업", "상장사", "산업", "업종", "시장", "경제", "금융", "증권", "펀드", "etf", "생산", "판매", "수주", "계약", "공급", "투자자", "성장률", "경기", "정부", "규제", "정책"]
NOISE_WORDS = ["연예", "배우", "가수", "아이돌", "드라마", "예능", "영화", "스포츠", "축구", "야구", "날씨", "맛집", "여행", "축제", "공연", "육아", "결혼", "범죄", "교통사고"]
MARKET_SIGNALS = {
    "국내": ["국내 증시", "한국 증시", "코스피", "코스닥", "국내 주식", "한국 경제", "원화", "한국은행"],
    "미국": ["미국 증시", "미국 주식", "미국 경제", "미국 시장", "뉴욕증시", "나스닥", "s&p", "다우", "월가", "미 연준"],
}


def _strip_html(value):
    value = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def _source_from_url(url):
    try:
        host = urllib.parse.urlparse(url or "").netloc.lower().removeprefix("www.")
        for domain, label in SOURCE_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return label
        return host or "출처 확인"
    except Exception:
        return "출처 확인"


def _parse_date(value):
    try:
        date = parsedate_to_datetime(str(value or "").strip())
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)
        return date.astimezone(datetime.timezone.utc)
    except Exception:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def _display_age(value):
    date = _parse_date(value)
    if date.year <= 1:
        return ""
    seconds = max(0, int((datetime.datetime.now(datetime.timezone.utc) - date).total_seconds()))
    if seconds < 60:
        return "방금 전"
    if seconds < 3600:
        return f"{seconds // 60}분 전"
    if seconds < 86400:
        return f"{seconds // 3600}시간 전"
    if seconds < 604800:
        return f"{seconds // 86400}일 전"
    return date.astimezone().strftime("%m/%d")


def _matches(text, words):
    text = str(text or "").lower()
    return any(word.lower() in text for word in words)


def _labels(text, rules):
    return [label for label, words in rules.items() if _matches(text, words)]


def _related_stocks(text):
    return [name for stocks in STOCK_UNIVERSE.values() for name, aliases in stocks.items() if _matches(text, aliases)]


def _investment_relevance(item, explicit_query=False):
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
    title_core = sum(word in title for word in MARKET_CORE_WORDS)
    desc_core = sum(word in description for word in MARKET_CORE_WORDS)
    title_context = sum(word in title for word in MARKET_CONTEXT_WORDS)
    desc_context = sum(word in description for word in MARKET_CONTEXT_WORDS)
    if _matches(title, NOISE_WORDS) and not title_core:
        return -1
    # General terms such as "산업" or "경제" alone are not investment news.
    # A category feed must include at least one finance/market signal.
    if not explicit_query and title_core + desc_core == 0:
        return -1
    score = title_core * 3 + min(desc_core, 3) + title_context + min(desc_context, 2)
    return score if score >= (1 if explicit_query else 2) else -1


def _infer_market(text, requested_market):
    if requested_market in STOCK_UNIVERSE:
        return requested_market
    us_stocks = set(STOCK_UNIVERSE["미국"])
    if us_stocks.intersection(_related_stocks(text)) or _matches(text, ["미국 증시", "뉴욕증시", "나스닥", "s&p", "다우", "월가", "연준"]):
        return "미국"
    return "국내"


def _matches_requested_market(text, requested_market):
    if requested_market == "전체":
        return True
    matching_stocks = set(_related_stocks(text))
    if matching_stocks.intersection(STOCK_UNIVERSE[requested_market]):
        return True
    return _matches(text, MARKET_SIGNALS[requested_market])


def _normalize_provider_row(row, category, market):
    title = _strip_html(row.get("raw_title"))
    description = _strip_html(row.get("raw_description"))
    pub_date = _strip_html(row.get("raw_pub_date"))
    link = str(row.get("raw_original_link") or row.get("raw_link") or "").strip()
    if not title or not link:
        return None
    text = f"{title} {description}"
    issues = _labels(text, ISSUE_RULES)
    stocks = _related_stocks(text)
    return {
        "provider": "naver", "content_type": "뉴스", "market": _infer_market(text, market),
        "category": category if category != "전체" else ("이슈" if issues else "종목" if stocks else "증시"),
        "title": title, "description": description, "source": _source_from_url(link), "pub_date": pub_date,
        "display_datetime": _display_age(pub_date), "link": link, "original_link": link,
        "related_stocks": stocks, "issues": issues, "themes": _labels(text, THEME_RULES),
    }


def _queries_for(category, market, query):
    if query:
        return [query]
    base = CATEGORY_QUERIES[category]
    if market == "국내":
        return [f"국내 {item}" for item in base]
    if market == "미국":
        return [f"미국 {item}" for item in base]
    return base


def _collect_raw_rows(queries):
    queries = [query for query in queries if str(query or "").strip()]
    if not queries:
        return []
    rows = []
    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as executor:
        futures = [executor.submit(naver_news.fetch_news, query, 20) for query in queries]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception:
                pass
    return rows


def fetch_general_news(category="전체", query="", limit=10, market="전체"):
    category = str(category or "전체").strip()
    category = category if category in CATEGORY_QUERIES else "전체"
    market = str(market or "전체").strip()
    market = market if market in ("전체", "국내", "미국") else "전체"
    query = str(query or "").strip()
    limit = max(1, min(int(limit or 10), 20))
    cache_key = (category, market, query.lower(), limit, "naver-shared-feed-v1")
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return [dict(item) for item in cached[1]]

    items, seen = [], set()
    for raw in _collect_raw_rows(_queries_for(category, market, query)):
        item = _normalize_provider_row(raw, category, market)
        if not item:
            continue
        relevance = _investment_relevance(item, explicit_query=bool(query))
        text = f"{item['title']} {item['description']}"
        if relevance < 0 or not _matches_requested_market(text, market):
            continue
        duplicate_key = re.sub(r"[^0-9a-zA-Z가-힣]", "", item["title"].lower())
        if not duplicate_key or duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        item["id"] = duplicate_key[:40]
        item["relevance_score"] = relevance
        items.append(item)

    items.sort(key=lambda item: (_parse_date(item.get("pub_date")), item["relevance_score"]), reverse=True)
    result = items[:limit]
    with _CACHE_LOCK:
        _CACHE[cache_key] = (time.time(), [dict(item) for item in result])
    return result


def get_news_coverage():
    return {
        "markets": list(STOCK_UNIVERSE),
        "stocks": {market: list(stocks) for market, stocks in STOCK_UNIVERSE.items()},
        "themes": list(THEME_RULES),
        "content_types": ["뉴스", "공시"],
    }
