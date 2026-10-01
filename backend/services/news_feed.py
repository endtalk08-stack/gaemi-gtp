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

# First-release coverage: 20 Korean and 20 US names.
# Each entry includes common Korean/English news aliases where useful.
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
        "셀트리온": ["셀트리온", "celltrion"],
        "삼성SDI": ["삼성sdi", "samsung sdi"],
        "현대모비스": ["현대모비스", "hyundai mobis"],
        "신한지주": ["신한지주", "신한금융", "shinhan financial"],
        "POSCO홀딩스": ["posco홀딩스", "포스코홀딩스", "posco holdings"],
        "LG화학": ["lg화학", "lg chem"],
        "HD현대중공업": ["hd현대중공업", "현대중공업", "hd hyundai heavy industries"],
        "삼성물산": ["삼성물산", "samsung c&t"],
        "카카오": ["카카오", "kakao"],
        "한국전력": ["한국전력", "한전", "korea electric power", "kepco"],
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
    "차익실현", "매물 출회", "매도세", "순매도", "외국인 매도", "기관 매도",
    "실적 악화", "실적 부진", "전망 하향", "가이던스 하향", "목표주가 하향",
    "금리 부담", "유가 부담", "환율 부담", "시장 약세", "증시 약세",
    "지정학", "전쟁", "분쟁", "리콜", "소송", "규제 강화",
]

MOVEMENT_SIGNAL_RULES = [
    ("실적상회", "positive", ["실적 상회", "호실적", "어닝 서프라이즈", "실적 개선", "전망 상향", "가이던스 상향"]),
    ("메모리가격", "positive", ["메모리 가격", "d램 가격", "낸드 가격"]),
    ("AI메모리", "positive", ["ai 메모리", "hbm", "고대역폭 메모리"]),
    ("수주·계약", "positive", ["수주", "공급계약", "단일판매", "납품 계약"]),
    ("주주환원", "positive", ["자사주 소각", "자사주 취득", "자사주 매입", "배당 확대", "배당 증가"]),
    ("차익실현", "negative", ["차익실현", "차익 실현", "매물 출회"]),
    ("외국인매도", "negative", ["외국인 매도", "외국인 순매도", "외인 매도"]),
    ("기관매도", "negative", ["기관 매도", "기관 순매도"]),
    ("실적부진", "negative", ["실적 부진", "실적 악화", "어닝 쇼크"]),
    ("전망하향", "negative", ["전망 하향", "가이던스 하향", "목표주가 하향"]),
    ("금리부담", "negative", ["금리 부담", "금리 상승", "국채금리 상승"]),
    ("지정학리스크", "negative", ["지정학", "전쟁", "분쟁", "충돌"]),
    ("리콜·소송", "negative", ["리콜", "소송", "규제 강화"]),
]


def _clean_text(value):
    text = html.unescape(re.sub(r"<[^>]+>", "", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _parse_datetime(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _source_from_url(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""
    for domain, name in SOURCE_DOMAINS.items():
        if host.endswith(domain):
            return name
    return host or "뉴스"


def _build_item(row, query="", category="전체"):
    title = _clean_text(row.get("title"))
    description = _clean_text(row.get("description"))
    link = row.get("originallink") or row.get("link") or ""
    published = _parse_datetime(row.get("pubDate"))
    return {
        "title": title,
        "description": description,
        "summary": description,
        "link": link,
        "url": link,
        "source": _source_from_url(link),
        "published_at": published.isoformat() if published else "",
        "query": query,
        "category": category,
    }


def _item_age_ok(item):
    dt = _parse_datetime(item.get("published_at"))
    if not dt:
        try:
            dt = datetime.datetime.fromisoformat(str(item.get("published_at", "")).replace("Z", "+00:00"))
        except Exception:
            return True
    now = datetime.datetime.now(datetime.timezone.utc)
    return now - dt <= datetime.timedelta(days=MAX_NEWS_AGE_DAYS)


def _fetch_query(query, display=20, start=1):
    cache_key = (query, int(display), int(start))
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] <= _CACHE_TTL:
            return list(cached[1])
    rows = naver_news.search_news(query, display=display, start=start)
    if not isinstance(rows, list):
        rows = []
    with _CACHE_LOCK:
        _CACHE[cache_key] = (now, list(rows))
    return rows


def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        key = item.get("url") or item.get("link") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _fetch_queries(queries, category="전체", per_query=20):
    queries = [q for q in queries if q]
    if not queries:
        return []
    items = []
    max_workers = min(6, len(queries))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_query, q, per_query, 1): q for q in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                rows = future.result()
            except Exception:
                rows = []
            for row in rows:
                item = _build_item(row, query=query, category=category)
                if item["title"] and _item_age_ok(item):
                    items.append(item)
    items = _dedupe(items)
    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return items


def _search_text(item):
    return f"{item.get('title', '')} {item.get('description', '')}".lower()


def _contains_any(text, words):
    return any(str(word).lower() in text for word in words)


def _is_market_relevant(item):
    text = _search_text(item)
    if _contains_any(text, MARKET_CORE_WORDS):
        return True
    if _contains_any(text, MARKET_CONTEXT_WORDS) and not _contains_any(text, NOISE_WORDS):
        return True
    return False


def _region_for_item(item):
    text = _search_text(item)
    kr = sum(1 for word in MARKET_SIGNALS["국내"] if word.lower() in text)
    us = sum(1 for word in MARKET_SIGNALS["미국"] if word.lower() in text)
    if kr > us and kr > 0:
        return "국내"
    if us > kr and us > 0:
        return "미국"
    return "전체"


def _match_stocks(item):
    text = _search_text(item)
    matches = []
    for region, stocks in STOCK_UNIVERSE.items():
        for name, aliases in stocks.items():
            if any(str(alias).lower() in text for alias in aliases):
                matches.append({"name": name, "region": region})
    return matches


def _match_rules(item, rules):
    text = _search_text(item)
    return [name for name, words in rules.items() if _contains_any(text, words)]


def _match_movement_signals(item):
    text = _search_text(item)
    matches = []
    for name, direction, words in MOVEMENT_SIGNAL_RULES:
        if _contains_any(text, words):
            # 패널은 기존 name/direction을 사용하고,
            # 중앙 채팅/뉴스 근거 연결은 label/tone을 사용한다.
            # 같은 분류 결과를 양쪽에서 공유하도록 두 이름을 함께 보존한다.
            matches.append({
                "name": name,
                "direction": direction,
                "label": name,
                "tone": direction,
            })
    return matches


def _enrich_item(item):
    enriched = dict(item)
    enriched["region"] = _region_for_item(item)
    enriched["stocks"] = _match_stocks(item)
    enriched["themes"] = _match_rules(item, THEME_RULES)
    enriched["issues"] = _match_rules(item, ISSUE_RULES)
    enriched["movement_signals"] = _match_movement_signals(item)
    return enriched


def fetch_general_news(category="전체", limit=30, region="전체"):
    category = category if category in CATEGORY_QUERIES else "전체"
    queries = CATEGORY_QUERIES[category]
    items = [_enrich_item(x) for x in _fetch_queries(queries, category=category, per_query=max(20, limit))]
    items = [x for x in items if _is_market_relevant(x)]
    if region in ("국내", "미국"):
        items = [x for x in items if x.get("region") in (region, "전체")]
    return items[: max(1, int(limit))]


def fetch_stock_news(stock_name, limit=20, market=None):
    stock_name = _clean_text(stock_name)
    if not stock_name:
        return []

    queries = [stock_name]
    for stocks in STOCK_UNIVERSE.values():
        aliases = stocks.get(stock_name)
        if aliases:
            queries = list(dict.fromkeys([stock_name] + aliases[:3]))
            break

    items = [_enrich_item(x) for x in _fetch_queries(queries, category="종목", per_query=max(20, limit))]
    relevant = []
    # 종목 뉴스는 "본문/description에 종목명이 한 번 언급됐다"는 이유만으로
    # 관련 기사로 넣지 않는다. 제목에서 해당 종목이 직접 확인되는 기사만
    # 기본 관련 기사로 인정해, 다른 종목/정책 기사에 회사명이 설명문으로
    # 등장하는 경우가 섞이지 않도록 한다.
    stock_aliases = [stock_name]
    for stocks in STOCK_UNIVERSE.values():
        aliases = stocks.get(stock_name)
        if aliases:
            stock_aliases.extend(aliases)
            break

    for item in items:
        title = str(item.get("title") or "").lower()
        text = _search_text(item)
        title_has_stock = any(str(alias).lower() in title for alias in stock_aliases if alias)
        if not title_has_stock:
            continue
        if not _contains_any(text, STOCK_MATERIAL_SIGNALS):
            continue
        relevant.append(item)

    return relevant[: max(1, int(limit))]


def get_news_coverage():
    return {
        "stocks": STOCK_UNIVERSE,
        "themes": sorted(THEME_RULES.keys()),
        "issues": sorted(ISSUE_RULES.keys()),
        "categories": list(CATEGORY_QUERIES.keys()),
    }
