"""News collection, filtering, scoring, and caching for gaemiGTP.

This module is intentionally independent from the UI. The public functions
keep the same behavior as the original engine implementation.
"""

import datetime
import re
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

NEWS_RESULT_CACHE = {}
NEWS_CACHE_TTL = 120
NEWS_AI_CANDIDATES_CACHE = {}
_NEWS_SINGLEFLIGHT_LOCKS = {}
_NEWS_LOCK_GUARD = threading.Lock()


def _get_news_singleflight_lock(key):
    with _NEWS_LOCK_GUARD:
        lock = _NEWS_SINGLEFLIGHT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _NEWS_SINGLEFLIGHT_LOCKS[key] = lock
        return lock

# 뉴스 품질 우선순위
# - 실제 Google News RSS에서 수집
# - 종목 직접 관련 뉴스와 시장/업종 원인 뉴스를 구분
# - 호재/악재 재료를 모두 살림
# - 단순 시세/수급 기사와 명백한 잡음은 제거
# - 화면에는 핵심 3개, AI용으로는 상위 10개를 보관
NEWS_SOURCE_PRIORITY = {
    "Reuters": 100, "로이터": 100,
    "AP": 98, "Associated Press": 98,
    "Bloomberg": 96, "블룸버그": 96,
    "Financial Times": 95, "파이낸셜타임스": 95,
    "The Wall Street Journal": 94, "월스트리트저널": 94,
    "CNBC": 92,
    "연합뉴스": 90, "한국경제": 88, "매일경제": 87,
    "서울경제": 86, "전자신문": 85, "이데일리": 82,
    "머니투데이": 80, "조선비즈": 75,
}

# 실제 주가에 영향을 줄 가능성이 높은 재료.
NEWS_HARD_EVENT_WORDS = [
    "실적발표", "잠정실적", "실적", "매출", "영업이익", "순이익", "가이던스",
    "수주", "계약", "공급계약", "대형계약", "인수", "합병", "m&a",
    "투자", "증설", "감산", "증산", "출하", "판매", "가격 인상", "가격 하락",
    "공급 중단", "공급 차질", "공급망", "규제", "관세", "제재", "수출 제한",
    "승인", "허가", "소송", "특허", "자사주", "배당", "유상증자", "전환사채",
    "earnings", "revenue", "profit", "guidance", "contract", "deal",
    "acquisition", "merger", "investment", "regulation", "tariff",
    "approval", "lawsuit", "buyback", "dividend", "offering",
]

# 기업/산업의 실질적인 변화로 볼 수 있는 표현. 하드 이벤트와 함께 우선순위를 높인다.
NEWS_MATERIAL_WORDS = [
    "신제품", "제품 출시", "신규 고객", "고객사", "수요 증가", "수요 감소",
    "수요 회복", "수요 둔화", "점유율", "시장 점유율", "공급 확대", "공급 축소",
    "생산 확대", "생산 감소", "생산 중단", "공장", "라인 증설", "라인 가동",
    "가동 중단", "납품", "공급", "출하량", "판매량", "가격 상승", "가격 하락",
    "수익성", "마진", "실적 개선", "실적 악화", "전망 상향", "전망 하향",
    "목표 상향", "목표 하향", "신규 수주", "수주 확대", "백지화", "철회",
    "파기", "지연", "중단", "재개", "협력", "파트너십", "동맹",
    "ai", "hbm", "반도체", "메모리", "파운드리", "gpu", "데이터센터",
]

# 단독 재료가 아니라 전망/의견 중심인 기사는 우선순위를 낮춘다.
NEWS_SOFT_OPINION_WORDS = [
    "전망", "예상", "분석", "목표주가", "증권가", "전문가", "기대감",
    "가능성", "주목", "관심", "수혜주", "관련주", "추천", "진단",
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst",
    "target price", "outlook", "expectation", "potential",
]

# 명백한 잡음/콘텐츠성 기사.
NEWS_NOISE_WORDS = [
    "인터뷰", "화보", "현장", "이모저모", "사설", "칼럼", "오피니언",
    "사용기", "리뷰", "가이드", "주식 초보", "투자전략", "투자 팁",
    "주간전망", "오늘의 운세", "퀴즈", "기부", "봉사", "캠페인",
    "맛집", "여행", "공연", "연예", "채용", "인사", "부고",
]

# 화면 상단의 현재가/수급을 단순 반복하는 기사.
NEWS_MARKET_SUMMARY_WORDS = [
    "보합 마감", "상승 마감", "하락 마감", "급등 마감", "급락 마감",
    "장 마감", "마감 시황", "장 마감 시황", "오늘의 시황", "시황",
    "주가", "수급", "외국인·기관", "외국인 기관", "기관·외국인",
    "기관 외국인", "외국인 순매수", "외국인 순매도", "기관 순매수",
    "기관 순매도", "거래량", "거래대금", "상승률", "하락률",
    "등락", "장중", "증시 마감", "마감",
]

# 시장/업종 전체 움직임의 원인을 설명하는 기사. 종목 단독 뉴스가 없어도 살린다.
NEWS_MARKET_CAUSE_WORDS = [
    "미국", "뉴욕", "나스닥", "s&p", "다우", "반도체", "기술주", "업황",
    "금리", "환율", "유가", "관세", "전쟁", "지정학", "공급", "수요",
    "중국", "대만", "일본", "연준", "fed", "fomc", "물가", "고용",
    "인플레이션", "경기", "침체", "상승세", "하락세", "약세", "강세",
    "호재", "악재", "우려", "기대", "영향", "여파", "때문",
]

# 종목별로 자주 쓰이는 별칭. 제목에 회사의 약칭만 나오는 경우를 보완한다.
NEWS_NAME_ALIASES = {
    "삼성전자": ["삼성전자", "삼성", "samsung electronics"],
    "SK하이닉스": ["sk하이닉스", "하이닉스", "sk hynix"],
    "현대차": ["현대차", "현대자동차", "hyundai motor"],
    "현대자동차": ["현대차", "현대자동차", "hyundai motor"],
    "기아": ["기아", "kia"],
    "네이버": ["네이버", "naver"],
    "NAVER": ["네이버", "naver"],
    "카카오": ["카카오", "kakao"],
    "셀트리온": ["셀트리온", "celltrion"],
    "한미반도체": ["한미반도체", "hanmi semiconductor"],
    "두산에너빌리티": ["두산에너빌리티", "두산중공업", "doosan enerbility"],
    "두산로보틱스": ["두산로보틱스", "doosan robotics"],
    "한화에어로스페이스": ["한화에어로스페이스", "한화에어로", "hanwha aerospace"],
    "엔비디아": ["엔비디아", "nvidia", "nvda"],
    "테슬라": ["테슬라", "tesla", "tsla"],
    "애플": ["애플", "apple", "aapl"],
    "마이크로소프트": ["마이크로소프트", "microsoft", "msft"],
    "아마존": ["아마존", "amazon", "amzn"],
    "구글": ["구글", "알파벳", "google", "alphabet", "googl"],
    "오라클": ["오라클", "oracle", "orcl"],
    "어도비": ["어도비", "adobe", "adbe"],
}


def _news_terms_for_stock(stock_name, ticker=""):
    """검색/관련성 판단에 사용할 종목명·별칭·티커를 만든다."""
    name = str(stock_name or "").strip()
    terms = []
    for term in [name, name.replace(" ", "")]:
        if term and term.lower() not in {x.lower() for x in terms}:
            terms.append(term)

    for alias in NEWS_NAME_ALIASES.get(name, []):
        if alias and alias.lower() not in {x.lower() for x in terms}:
            terms.append(alias)

    ticker_clean = str(ticker or "").replace(".KS", "").replace(".KQ", "").strip()
    if ticker_clean and ticker_clean.lower() not in {x.lower() for x in terms}:
        terms.append(ticker_clean)
    return terms


def _news_contains_any(text, words):
    text_lower = (text or "").lower()
    return any(str(word).lower() in text_lower for word in words)


def _is_market_summary_news(title):
    """단순 주가/수급 기사만 제외하고, 실제 원인이 있는 기사는 보존한다."""
    title_lower = (title or "").lower()
    if not title_lower:
        return False

    summary_hits = sum(1 for word in NEWS_MARKET_SUMMARY_WORDS if word.lower() in title_lower)
    if summary_hits == 0:
        return False

    # 실적/계약/투자/규제 등 재료가 있으면 유지한다.
    if _news_contains_any(title_lower, NEWS_HARD_EVENT_WORDS + NEWS_MATERIAL_WORDS):
        return False

    # 미국/금리/반도체 등 시장 원인이 있으면 유지한다.
    market_cause = [
        "미국", "뉴욕", "나스닥", "s&p", "다우", "반도체", "기술주", "업황",
        "금리", "환율", "유가", "관세", "전쟁", "지정학", "공급", "수요",
        "중국", "대만", "연준", "fed", "fomc", "물가", "고용", "경기",
        "침체", "인플레이션", "때문", "영향", "여파", "우려",
    ]
    if _news_contains_any(title_lower, market_cause):
        return False

    # 단순 상승/하락/마감/수급만 설명하는 기사는 제외한다.
    return summary_hits >= 1


# 화면 표시용 뉴스와 AI 분석용 후보를 분리한다.
NEWS_AI_CANDIDATES_CACHE = {}


def _news_source_score(source_name):
    source = (source_name or "").strip()
    for key, score in NEWS_SOURCE_PRIORITY.items():
        if key.lower() == source.lower():
            return score
    return 60


def _news_freshness_score(pub_date):
    """RSS 발행 시각 기준 최신 기사일수록 높은 점수."""
    if not pub_date:
        return 0
    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        age_hours = max(0.0, (now - dt.astimezone(datetime.timezone.utc)).total_seconds() / 3600.0)
        if age_hours <= 6:
            return 40
        if age_hours <= 24:
            return 32
        if age_hours <= 48:
            return 24
        if age_hours <= 72:
            return 14
        if age_hours <= 168:
            return 4
        if age_hours <= 336:
            return 2
        if age_hours <= 720:
            return 1
    except Exception:
        pass
    return 0


def _news_relevance_score(title, stock_name, ticker):
    """종목 직접 관련성 + 재료성 + 시장 영향 가능성을 평가한다."""
    title_lower = (title or "").lower()
    score = 0
    terms = _news_terms_for_stock(stock_name, ticker)

    direct_hits = sum(1 for term in terms if term and term.lower() in title_lower)
    direct = direct_hits > 0
    if direct:
        score += 45
        if direct_hits >= 2:
            score += 10

    hard_hits = sum(1 for word in NEWS_HARD_EVENT_WORDS if word.lower() in title_lower)
    material_hits = sum(1 for word in NEWS_MATERIAL_WORDS if word.lower() in title_lower)
    cause_hits = sum(1 for word in NEWS_MARKET_CAUSE_WORDS if word.lower() in title_lower)

    score += min(hard_hits, 5) * 8
    score += min(material_hits, 5) * 5
    if cause_hits:
        score += min(cause_hits, 4) * 4

    # 의견/전망만 있는 기사는 낮추되, 확정 재료와 함께 있으면 너무 세게 감점하지 않는다.
    hard_or_material = hard_hits > 0 or material_hits > 0
    soft_hits = sum(1 for word in NEWS_SOFT_OPINION_WORDS if word.lower() in title_lower)
    score += soft_hits * (2 if hard_or_material else -6)

    noise_hits = sum(1 for word in NEWS_NOISE_WORDS if word.lower() in title_lower)
    score -= noise_hits * 18

    # 단순 시세/수급 기사는 별도 필터와 함께 추가 감점한다.
    if _is_market_summary_news(title):
        score -= 45

    return score


def _news_impact_type(title, stock_name, ticker):
    """뉴스가 호재/악재/시장요인/중립 중 어디에 가까운지 내부용으로 분류한다."""
    t = (title or "").lower()
    positive = [
        "호재", "실적 개선", "실적 증가", "매출 증가", "영업이익 증가", "수주",
        "계약", "공급 확대", "수요 회복", "수요 증가", "증설", "투자 확대",
        "가격 인상", "점유율 상승", "목표 상향", "전망 상향", "승인", "허가",
        "자사주", "배당 확대", "신규 고객", "신제품", "강세", "상승",
    ]
    negative = [
        "악재", "실적 악화", "실적 감소", "매출 감소", "영업이익 감소", "수주 취소",
        "계약 해지", "공급 차질", "공급 중단", "수요 감소", "수요 둔화", "감산",
        "투자 축소", "가격 하락", "점유율 하락", "목표 하향", "전망 하향", "규제",
        "관세", "제재", "소송", "리콜", "생산 중단", "약세", "하락",
    ]
    p = sum(1 for w in positive if w.lower() in t)
    n = sum(1 for w in negative if w.lower() in t)
    if p > n and p > 0:
        return "positive"
    if n > p and n > 0:
        return "negative"
    if _news_contains_any(t, NEWS_MARKET_CAUSE_WORDS):
        return "market"
    return "neutral"


def _news_duplicate_key(title):
    """표현만 조금 다른 동일/유사 기사 중복을 줄이기 위한 키."""
    key = re.sub(r"[^0-9a-zA-Z가-힣]", "", (title or "").lower())
    for token in ("속보", "단독", "종합", "오늘", "긴급"):
        key = key.replace(token, "")
    return key


def _clean_news_title(title):
    title = title or ""
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'<[^>]+>', '', title)
    # Google News RSS 제목 뒤의 언론사 표기를 제거한다.
    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
    title = re.sub(r'[\.…]+\s*$', '', title)
    title = re.sub(r'\.{2,}|…', ' · ', title)
    return title.strip().strip('"\'“”')


def _fetch_one_news_rss(search_term, days=7):
    """Google News RSS 한 검색어를 조회한다. 기본 7일, 부족할 때만 보충 기간을 넓힌다."""
    rows = []
    try:
        days = max(1, int(days))
        search_query = f'"{search_term}" when:{days}d' if search_term else ""
        query = urllib.parse.quote(search_query)
        url = (
            f"https://news.google.com/rss/search?q={query}"
            f"&hl=ko&gl=KR&ceid=KR:ko"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title_el = item.find('title')
            source_el = item.find('source')
            pub_el = item.find('pubDate')
            link_el = item.find('link')
            title = _clean_news_title(title_el.text if title_el is not None else "")
            source = (source_el.text or "").strip() if source_el is not None else ""
            pub_date = (pub_el.text or "").strip() if pub_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if title:
                rows.append({"title": title, "source": source, "pub_date": pub_date, "link": link})
    except Exception as e:
        print(f"[뉴스] RSS 조회 예외 search={search_term}: {type(e).__name__}: {e}")
    return rows


def _fetch_realtime_news_uncached(stock_name, ticker_map=None):
    """종목 관련 최신 호재/악재/시장원인 뉴스를 수집한다. 기본 7일, 부족할 때 14일 보충."""
    clean_stock_name = str(stock_name or "").strip()
    ticker_map = ticker_map or {}
    ticker_guess = ticker_map.get(clean_stock_name)
    if ticker_guess:
        ticker_guess = str(ticker_guess).replace(".KS", "").replace(".KQ", "")
    elif re.match(r"^[A-Za-z\-]+$", clean_stock_name):
        ticker_guess = clean_stock_name.upper()

    terms = _news_terms_for_stock(clean_stock_name, ticker_guess)
    primary = terms[0] if terms else clean_stock_name

    queries = [
        primary,
        f"{primary} 실적 계약 수주 투자 공급",
        f"{primary} 악재 우려 규제 관세 소송",
        f"{primary} 호재 기대 전망 수요 고객",
        f"{primary} 반도체 시장 미국 금리 수요",
    ]
    if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
        queries[0] = f"{primary} {ticker_guess}"

    def collect_queries(query_items, days):
        rows = []
        executor = ThreadPoolExecutor(max_workers=min(5, len(query_items)))
        try:
            futures = [executor.submit(_fetch_one_news_rss, q, days) for q in query_items]
            for future in futures:
                try:
                    rows.extend(future.result())
                except Exception as e:
                    print(f"[뉴스] 검색 작업 예외: {type(e).__name__}: {e}")
        finally:
            executor.shutdown(wait=True)
        return rows

    raw_rows = collect_queries(queries, 7)

    def build_candidates(rows):
        candidates = []
        seen_titles = set()
        seen_duplicate_keys = set()
        all_terms_lower = [x.lower() for x in terms if x]

        for row in rows:
            title = row["title"]
            title_lower = title.lower()
            title_key = re.sub(r"\s+", " ", title_lower).strip()
            duplicate_key = _news_duplicate_key(title)
            if title_key in seen_titles or duplicate_key in seen_duplicate_keys:
                continue
            seen_titles.add(title_key)
            seen_duplicate_keys.add(duplicate_key)

            freshness_score = _news_freshness_score(row["pub_date"])
            if freshness_score == 0:
                continue

            direct = any(term in title_lower for term in all_terms_lower)
            material_hit = _news_contains_any(title_lower, NEWS_HARD_EVENT_WORDS + NEWS_MATERIAL_WORDS)
            market_cause_hit = _news_contains_any(title_lower, NEWS_MARKET_CAUSE_WORDS)
            noise_hit = _news_contains_any(title_lower, NEWS_NOISE_WORDS)
            market_summary = _is_market_summary_news(title)

            if not direct and not market_cause_hit:
                continue
            if market_summary:
                continue
            if direct and noise_hit and not material_hit and not market_cause_hit:
                continue

            source_score = _news_source_score(row["source"])
            relevance_score = _news_relevance_score(title, clean_stock_name, ticker_guess or "")
            impact_type = _news_impact_type(title, clean_stock_name, ticker_guess or "")

            score = (
                source_score
                + freshness_score
                + relevance_score
                + (28 if direct else 0)
                + (24 if material_hit else 0)
                + (12 if market_cause_hit else 0)
                - (25 if noise_hit else 0)
            )
            candidates.append({
                "title": title, "source": row["source"], "pub_date": row["pub_date"],
                "link": row.get("link", ""),
                "source_score": source_score, "freshness_score": freshness_score,
                "relevance_score": relevance_score, "direct": direct,
                "material": material_hit, "market_cause": market_cause_hit,
                "impact_type": impact_type, "score": score,
            })
        return candidates

    candidates = build_candidates(raw_rows)

    # 1차(최근 7일)에서 3개가 안 나오면 14일 → 30일 순으로 보충한다.
    # 관련성 필터는 그대로 유지하므로 오래된 기사라도 종목과 직접 관련된 경우만 추가된다.
    if len(candidates) < 3:
        fallback_queries = [
            f"{primary} 호재", f"{primary} 악재",
            f"{primary} 실적 계약 수주", f"{primary} 규제 관세 소송 공급차질",
            f"{primary} 투자 공급 고객 수요 전망",
        ]
        if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
            fallback_queries.append(f"{ticker_guess} earnings news")
        fallback_rows = collect_queries(fallback_queries, 14)
        candidates = build_candidates(raw_rows + fallback_rows)

    if len(candidates) < 3:
        # 14일 내에도 부족한 경우에만 최근 30일까지 확장한다.
        # 단순 주가/시장요약 기사는 기존 필터에서 계속 제외한다.
        extended_queries = [
            primary,
            f"{primary} 실적",
            f"{primary} 계약 수주",
            f"{primary} 투자 공급 고객",
            f"{primary} 규제 관세 소송",
        ]
        if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
            extended_queries.append(f"{ticker_guess} stock company news")
        extended_rows = collect_queries(extended_queries, 30)
        candidates = build_candidates(raw_rows + fallback_rows + extended_rows)

    candidates.sort(
        key=lambda x: (x["score"], x["direct"], x["material"], x["freshness_score"]),
        reverse=True,
    )

    internal_candidates = [dict(item) for item in candidates[:10]]
    NEWS_AI_CANDIDATES_CACHE[clean_stock_name] = internal_candidates

    selected = []
    selected_keys = set()
    pools = [
        [x for x in candidates if x["direct"] and x["material"]],
        [x for x in candidates if x["direct"] and not x["material"]],
        [x for x in candidates if x["market_cause"] and not x["direct"]],
    ]
    for pool in pools:
        for item in pool:
            key = item["title"].lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= 3:
                break
        if len(selected) >= 3:
            break

    if len(selected) < 3:
        for item in candidates:
            key = item["title"].lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= 3:
                break

    # 화면에 표시할 3개는 실제 RSS 발행시각 기준 최신순으로 정렬한다.
    # 점수 계산은 관련성/재료성 선별용으로만 사용하고, 화면 순서는 시간 우선이다.
    def _news_datetime_for_sort(item):
        try:
            raw = str(item.get("pub_date", "")).strip()
            if not raw:
                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    selected.sort(key=_news_datetime_for_sort, reverse=True)

    print(f"[뉴스 품질] {clean_stock_name} 후보={len(candidates)} / 내부AI={len(internal_candidates)} / 화면={len(selected)}")
    for i, item in enumerate(selected[:3], 1):
        print(f"[뉴스 품질] {clean_stock_name} 화면#{i} score={item['score']} type={item['impact_type']} direct={item['direct']} material={item['material']} source={item['source']}")

    def _news_display_age(pub_date):
        """RSS 발행시각을 화면용 상대시간으로 표시한다."""
        if not pub_date:
            return ""
        try:
            dt = parsedate_to_datetime(pub_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            seconds = max(0, int((now - dt.astimezone(datetime.timezone.utc)).total_seconds()))
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
        except Exception:
            return ""

    display_items = []
    company_names = set(terms)
    for item in selected[:3]:
        original_title = item["title"]
        # 기존 화면의 뉴스 제목은 그대로 유지한다.
        # 구조화 데이터만 추가하고 제목 자체는 손대지 않는다.
        display_title = re.sub(r"\s+", " ", str(original_title)).strip() or "관련 뉴스"
        source = str(item.get("source", "")).strip() or "출처 확인 필요"
        pub_date = str(item.get("pub_date", "")).strip()
        display_items.append({
            "title": display_title or original_title,
            "original_title": original_title,
            "source": source,
            "pub_date": pub_date,
            "display_datetime": _news_display_age(pub_date),
            "link": str(item.get("link", "")).strip(),
            "original_link": str(item.get("link", "")).strip(),
        })
    return display_items


def fetch_realtime_news(stock_name, ticker_map=None):
    """뉴스 결과를 120초 캐시하고 동일 종목 동시 요청은 한 번만 외부 검색한다."""
    key = str(stock_name).strip()
    now = datetime.datetime.now().timestamp()
    cached = NEWS_RESULT_CACHE.get(key)
    if cached and now - cached[0] < NEWS_CACHE_TTL:
        return list(cached[1])

    lock = _get_news_singleflight_lock(key)
    with lock:
        now = datetime.datetime.now().timestamp()
        cached = NEWS_RESULT_CACHE.get(key)
        if cached and now - cached[0] < NEWS_CACHE_TTL:
            return list(cached[1])

        try:
            result = _fetch_realtime_news_uncached(stock_name, ticker_map)
        except Exception as exc:
            print(f"[뉴스] 수집 실패: {type(exc).__name__}: {exc}")
            result = []
        NEWS_RESULT_CACHE[key] = (now, list(result))
        return result


def get_news_ai_candidates(stock_name, limit=10):
    """AI 원인 분석에서 사용할 내부 뉴스 후보를 반환한다."""
    items = NEWS_AI_CANDIDATES_CACHE.get(str(stock_name).strip(), [])
    return [dict(item) for item in items[:max(1, int(limit))]]

