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
MAX_NEWS_AGE_DAYS = 7

CATEGORY_QUERIES = {
    "전체": ["증시", "경제"], "증시": ["코스피 코스닥 나스닥"], "종목": ["상장사 주식"],
    "경제지표": ["CPI GDP 고용 물가"], "에너지": ["유가 원유 에너지"], "연준": ["연준 FOMC 금리"],
    "일정": ["경제 일정 FOMC 일정"], "투자의견": ["목표주가 투자의견"],
    "실적발표": ["실적 발표 매출 영업이익"],
}

# First-release coverage: 10 Korean and 20 US names.
# Each US entry includes its ticker and common Korean/English news aliases.
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
        "엔비디아": ["NVDA", "엔비디아", "nvidia"],
        "애플": ["AAPL", "애플", "apple"],
        "마이크로소프트": ["MSFT", "마이크로소프트", "microsoft"],
        "아마존": ["AMZN", "아마존", "amazon"],
        "알파벳": ["GOOGL", "GOOG", "알파벳", "구글", "google", "alphabet"],
        "메타": ["META", "메타", "메타 플랫폼스", "meta platforms"],
        "브로드컴": ["AVGO", "브로드컴", "broadcom"],
        "테슬라": ["TSLA", "테슬라", "tesla"],
        "버크셔 해서웨이": ["BRK.B", "BRK.A", "버크셔 해서웨이", "버크셔", "berkshire hathaway", "berkshire"],
        "일라이 릴리": ["LLY", "일라이 릴리", "릴리", "eli lilly"],
        "AMD": ["AMD", "에이엠디", "어드밴스드 마이크로 디바이시스", "advanced micro devices"],
        "마이크론 테크놀로지": ["MU", "마이크론", "마이크론 테크놀로지", "micron", "micron technology"],
        "퀄컴": ["QCOM", "퀄컴", "qualcomm"],
        "TSMC": ["TSM", "TSMC", "대만 TSMC", "타이완 반도체", "taiwan semiconductor"],
        "ASML": ["ASML", "에이에스엠엘", "asml holding"],
        "팔란티어": ["PLTR", "팔란티어", "palantir", "palantir technologies"],
        "로빈후드": ["HOOD", "로빈후드", "robinhood", "robinhood markets"],
        "오라클": ["ORCL", "오라클", "oracle"],
        "록히드마틴": ["LMT", "록히드마틴", "록히드 마틴", "lockheed martin"],
        "엑슨모빌": ["XOM", "엑슨모빌", "엑슨 모빌", "exxonmobil", "exxon mobil"],
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
STOCK_MATERIAL_SIGNALS = [
    "실적", "매출", "영업이익", "순이익", "eps", "earnings", "revenue", "guidance",
    "공시", "계약", "수주", "공급", "납품", "출하", "투자", "증설", "감산",
    "배당", "자사주", "목표주가", "투자의견", "판매", "가격", "규제", "관세",
    "hbm", "반도체", "메모리", "ai", "인공지능", "데이터센터", "신제품",
    # A daily move can be explained by negative news as well as positive news.
    # Keep these concrete so a bare "주가 하락" headline is not treated as a cause.
    "차익실현", "매물 출회", "매도세", "순매도", "외국인 매도", "기관 매도",
    "실적 악화", "실적 부진", "전망 하향", "가이던스 하향", "목표주가 하향",
    "금리 부담", "유가 부담", "환율 부담", "시장 약세", "증시 약세",
    "지정학", "전쟁", "분쟁", "리콜", "소송", "규제 강화",
]

# Labels returned with each article are evidence tags, not a claim that the
# article alone caused the move.  The central "왜?" view can later show them
# as the confirmed signals behind its explanation.
MOVEMENT_SIGNAL_RULES = [
    ("실적상회", "positive", ["실적 상회", "호실적", "어닝 서프라이즈", "실적 개선", "전망 상향", "가이던스 상향"]),
    ("메모리가격", "positive", ["메모리 가격", "d램 가격", "낸드 가격"]),
    ("AI메모리", "positive", ["ai 메모리", "hbm", "고대역폭 메모리"]),
    ("수주·계약", "positive", ["수주", "공급계약", "단일판매", "납품 계약"]),
    ("주주환원", "positive", ["자사주 소각", "자사주 취득", "자사주 매입", "배당 확대", "배당 증가"]),
    ("차익실현", "negative", ["차익실현", "차익 실현", "매물 출회"]),
    ("외국인매도", "negative", ["외국인 매도", "외국인 순매도", "외인 매도"]),
    ("기관매도", "negative", ["기관 매도", "기관 순매도"]),
    ("실적악화", "negative", ["실적 악화", "실적 부진", "어닝 쇼크", "전망 하향", "가이던스 하향"]),
    ("금리부담", "negative", ["금리 부담", "금리 상승", "고금리"]),
    ("유가부담", "negative", ["유가 부담", "유가 상승", "원유 가격 상승"]),
    ("환율부담", "negative", ["환율 부담", "원달러 상승", "달러 강세"]),
    ("시장약세", "negative", ["코스피 약세", "코스닥 약세", "증시 약세", "시장 약세"]),
    ("지정학적리스크", "negative", ["지정학", "전쟁", "분쟁", "중동 긴장"]),
    ("규제·소송", "negative", ["규제 강화", "제재", "소송", "리콜"]),
]


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


def _is_recent_news(value):
    """Only accept provider items published during the current seven-day window."""
    date = _parse_date(value)
    if date.year <= 1:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - date
    return datetime.timedelta(0) <= age <= datetime.timedelta(days=MAX_NEWS_AGE_DAYS)


def _dedupe(items):
    seen = set()
    output = []
    for item in items:
        key = item.get("originallink") or item.get("link") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _text(item):
    return f"{item.get('title', '')} {item.get('description', '')}".lower()


def _matched_labels(text, rules):
    labels = []
    for label, keywords in rules.items():
        if any(keyword.lower() in text for keyword in keywords):
            labels.append(label)
    return labels


def _related_stocks(text):
    related = []
    for market, stocks in STOCK_UNIVERSE.items():
        for name, aliases in stocks.items():
            if any(alias.lower() in text for alias in aliases):
                related.append({"market": market, "name": name})
    return related


def _movement_signals(text):
    signals = []
    for label, tone, keywords in MOVEMENT_SIGNAL_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            signals.append({"label": label, "tone": tone})
    return signals


def _is_market_relevant(text):
    if any(word in text for word in NOISE_WORDS):
        return False
    core_hits = sum(word in text for word in MARKET_CORE_WORDS)
    context_hits = sum(word in text for word in MARKET_CONTEXT_WORDS)
    return core_hits >= 1 and (core_hits >= 2 or context_hits >= 1)


def _normalize(raw, market_hint=None, relevance_score=0):
    title = _strip_html(raw.get("title"))
    description = _strip_html(raw.get("description"))
    text = f"{title} {description}".lower()
    originallink = raw.get("originallink") or raw.get("link") or ""
    related_stocks = _related_stocks(text)
    markets = []
    for market, words in MARKET_SIGNALS.items():
        if any(word in text for word in words):
            markets.append(market)
    for stock in related_stocks:
        if stock["market"] not in markets:
            markets.append(stock["market"])
    if market_hint and market_hint not in markets:
        markets.append(market_hint)
    return {
        "title": title,
        "description": description,
        "link": raw.get("link") or originallink,
        "originallink": originallink,
        "source": _source_from_url(originallink),
        "pub_date": raw.get("pubDate") or "",
        "age": _display_age(raw.get("pubDate")),
        "markets": markets,
        "themes": _matched_labels(text, THEME_RULES),
        "issues": _matched_labels(text, ISSUE_RULES),
        "related_stocks": related_stocks,
        "movement_signals": _movement_signals(text),
        "relevance_score": relevance_score,
    }


def _query_news(query, display=100, sort="date"):
    try:
        result = naver_news.search_news(query=query, display=display, sort=sort)
        return result.get("items", []) if isinstance(result, dict) else []
    except Exception:
        return []


def _query_many(queries, display=100, sort="date"):
    unique_queries = list(dict.fromkeys(query.strip() for query in queries if query and query.strip()))
    if not unique_queries:
        return []
    workers = min(8, len(unique_queries))
    items = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_query_news, query, display, sort): query for query in unique_queries}
        for future in as_completed(futures):
            try:
                items.extend(future.result())
            except Exception:
                pass
    return _dedupe(items)


def _cache_get(key):
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]
    return None


def _cache_set(key, value):
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)
    return value


def get_market_news(category="전체", market="전체", limit=30):
    key = ("market", category, market, limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    queries = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["전체"])
    if market == "국내":
        queries = [f"{query} 한국" for query in queries]
    elif market == "미국":
        queries = [f"{query} 미국" for query in queries]

    items = _query_many(queries, display=100, sort="date")
    normalized = []
    for raw in items:
        if not _is_recent_news(raw.get("pubDate")):
            continue
        item = _normalize(raw, market_hint=market if market in ("국내", "미국") else None)
        text = _text(item)
        if not _is_market_relevant(text):
            continue
        if market in ("국내", "미국") and market not in item["markets"]:
            continue
        normalized.append(item)
        if len(normalized) >= limit:
            break
    return _cache_set(key, normalized)


def get_stock_news(stock_name, limit=20):
    stock_name = str(stock_name or "").strip()
    if not stock_name:
        return []
    market = None
    aliases = [stock_name]
    for market_name, stocks in STOCK_UNIVERSE.items():
        if stock_name in stocks:
            market = market_name
            aliases = stocks[stock_name]
            break
        for name, stock_aliases in stocks.items():
            if stock_name.lower() in [alias.lower() for alias in stock_aliases]:
                stock_name = name
                market = market_name
                aliases = stock_aliases
                break
        if market:
            break

    # Search every known alias because Korean providers frequently mix Korean,
    # English company names and tickers in otherwise identical stock coverage.
    raw_items = _query_many(aliases, display=100, sort="date")
    scored = []
    for raw in raw_items:
        if not _is_recent_news(raw.get("pubDate")):
            continue
        item = _normalize(raw, market_hint=market)
        text = _text(item)
        if not any(alias.lower() in text for alias in aliases):
            continue
        material_hits = sum(keyword in text for keyword in STOCK_MATERIAL_SIGNALS)
        direct_title = any(alias.lower() in item["title"].lower() for alias in aliases)
        score = (5 if direct_title else 0) + min(material_hits, 5)
        if score <= 0:
            continue
        item["relevance_score"] = score
        scored.append(item)

    scored = _dedupe(sorted(scored, key=lambda item: (item["relevance_score"], _parse_date(item["pub_date"])), reverse=True))
    return _cache_set(("stock", stock_name, limit), scored[:limit])
