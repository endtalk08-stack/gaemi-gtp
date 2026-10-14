"""Shared news feed normalization for the panel and central chat."""

import datetime
import html
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime

from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.providers import naver_news, official_company_news, sec_filings

_CACHE = {}
_CACHE_TTL = 120
_CACHE_LOCK = threading.Lock()
MAX_NEWS_AGE_DAYS = 7

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


def _fetch_query(query, display=20, start=1, *, raise_on_error=False):
    cache_key = (query, int(display), int(start))
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached[0] <= _CACHE_TTL:
            return list(cached[1])
    rows = naver_news.search_news(query, display=display, start=start, raise_on_error=raise_on_error)
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


def _fetch_queries(queries, category="전체", per_query=20, *, raise_on_error=False):
    queries = [q for q in queries if q]
    if not queries:
        return []
    items = []
    failures = 0
    max_workers = min(6, len(queries))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_query, q, per_query, 1, raise_on_error=raise_on_error): q for q in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                rows = future.result()
            except Exception:
                failures += 1
                rows = []
            for row in rows:
                item = _build_item(row, query=query, category=category)
                if item["title"] and _item_age_ok(item):
                    items.append(item)
    if raise_on_error and failures == len(queries):
        raise RuntimeError('all_naver_news_queries_failed')
    items = _dedupe(items)
    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return items


def _search_text(item):
    return f"{item.get('title', '')} {item.get('description', '')}".lower()


def _contains_any(text, words):
    return any(str(word).lower() in text for word in words)


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
    enriched["region"] = item.get("region") or _region_for_item(item)
    enriched["stocks"] = _match_stocks(item)
    enriched["themes"] = _match_rules(item, THEME_RULES)
    enriched["issues"] = _match_rules(item, ISSUE_RULES)
    enriched["movement_signals"] = _match_movement_signals(item)
    return enriched


STOCK_DIRECT_EVENT_WORDS = [
    "실적", "매출", "영업이익", "순이익", "가이던스", "계약", "수주", "공급", "납품",
    "출하", "투자", "증설", "감산", "배당", "자사주", "목표주가", "투자의견",
    "판매", "가격", "출시", "공개", "개발", "양산", "생산", "인수", "매각", "분사",
    "협력", "제휴", "착공", "준공", "리콜", "소송", "규제",
]

STOCK_INDIRECT_IMPACT_WORDS = [
    "경쟁", "경쟁사", "점유율", "공급망", "부품", "수급", "공급 부족", "공급 차질",
    "생산 중단", "생산 차질", "가격 상승", "가격 하락", "수요 증가", "수요 감소",
    "증설", "감산", "재고", "관세", "수출 규제", "규제", "금리", "환율", "유가",
    "지수 편입", "지수편입", "편입", "추종 펀드", "추종펀드",
]

# Stock analysis should start from articles that contain an actual event/change,
# not from articles that merely mention a topic such as HBM/AI/semiconductors.
# Both title and description are treated as one evidence body here.
STOCK_EVENT_ACTION_WORDS = [
    "상승", "하락", "급등", "급락", "반등", "강세", "약세", "최고치", "최저치", "경신",
    "증가", "감소", "확대", "축소", "급증", "급감", "개선", "악화", "상회", "하회",
    "전환", "종료", "재개", "중단", "부족", "품귀", "인상", "인하", "동결",
    "투자", "자금 조달", "조달", "증설", "감산", "생산 확대", "생산 감소",
    "수요 증가", "수요 감소", "공급 확대", "공급 감소", "공급 부족",
    "매입", "매도", "순매수", "순매도", "수주", "계약", "납품", "선정",
    "출시", "진출", "인수", "합병", "협력", "지원", "발행", "소각",
    "소송", "합의", "리콜", "규제", "경고", "발표", "수출", "착공", "건설",
    "어닝 서프라이즈", "어닝 쇼크", "호실적", "실적 부진", "전망 상향", "전망 하향",
]


def _stock_event_strength(item):
    """Measure concrete event/change evidence from title + description."""
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
    title_hits = sum(1 for word in STOCK_EVENT_ACTION_WORDS if word.lower() in title)
    description_hits = sum(1 for word in STOCK_EVENT_ACTION_WORDS if word.lower() in description)
    # Title is useful evidence, but description participates from the start
    # instead of being used only as a fallback.
    return (title_hits * 2) + description_hits


MARKET_STORY_TITLE_MARKERS = [
    "[특징주]", "특징주", "[증시마감]", "증시마감", "장중 시황",
    "개장 전 급등주", "개장전 급등주", "개장 전 급락주", "개장전 급락주",
]

# Generic market roundups are useful for the general feed, but are too broad
# to use as evidence for an individual stock analysis.
STOCK_ROUNDUP_TITLE_MARKERS = [
    "오늘의 증시", "오늘의 증권소식", "오늘 증시", "증시 브리핑",
]


def _is_stock_roundup(item):
    title = str(item.get("title") or "").lower()
    return _contains_any(title, STOCK_ROUNDUP_TITLE_MARKERS)



def _stock_aliases_for_name(stock_name):
    aliases = [str(stock_name or "").strip()]
    for stocks in STOCK_UNIVERSE.values():
        values = stocks.get(stock_name)
        if values:
            aliases.extend(values)
            break
    return list(dict.fromkeys(str(alias).strip().lower() for alias in aliases if str(alias).strip()))


def _stock_analysis_relevance(item, stock_name):
    """Return analysis relevance tier without changing the raw collected item."""
    aliases = _stock_aliases_for_name(stock_name)
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()

    provider_stock = str(item.get("provider_stock") or "").strip().lower()
    trusted_source = str(item.get("source_type") or "") in {"official_company", "sec_filing"}
    if trusted_source and provider_stock == str(stock_name or "").strip().lower():
        return 3

    if any(alias in title for alias in aliases):
        return 3

    # Description-only mentions can still be useful when the article explains
    # either a concrete company event or a clear transmission path to the stock.
    # This keeps competitor/supply-chain/market-impact stories without reopening
    # broad columns that merely mention the company.
    for alias in aliases:
        start = 0
        while True:
            index = description.find(alias, start)
            if index < 0:
                break
            left = max(0, index - 120)
            right = min(len(description), index + len(alias) + 120)
            nearby = description[left:right]
            if _contains_any(nearby, STOCK_DIRECT_EVENT_WORDS):
                return 2
            if _contains_any(nearby, STOCK_INDIRECT_IMPACT_WORDS):
                return 2
            start = index + len(alias)

    # [특징주]/[증시마감] are useful market-story test material only when the
    # searched stock is actually named in the article and material signals exist.
    if _contains_any(title, MARKET_STORY_TITLE_MARKERS):
        full_text = f"{title} {description}"
        if any(alias in full_text for alias in aliases) and _contains_any(full_text, STOCK_MATERIAL_SIGNALS):
            return 1

    return 0


def _primary_us_ticker(stock_name):
    aliases = STOCK_UNIVERSE.get("미국", {}).get(stock_name) or []
    for value in aliases:
        token = str(value or "").strip().upper()
        if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", token):
            return token
    return ""


def _select_stock_news_with_source_reserve(relevant, limit):
    """Preserve trusted US source rows before filling the remaining ranked slots."""
    max_count = max(1, int(limit))
    source_limits = {
        "official_company": min(10, max_count),
        "sec_filing": min(5, max_count),
    }

    selected = []
    selected_ids = set()

    def item_key(item):
        return (
            str(item.get("url") or item.get("link") or "").strip()
            or str(item.get("title") or "").strip()
        )

    for source_type, reserve in source_limits.items():
        kept = 0
        for item in relevant:
            if kept >= reserve or len(selected) >= max_count:
                break
            if str(item.get("source_type") or "") != source_type:
                continue
            key = item_key(item)
            if not key or key in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(key)
            kept += 1

    for item in relevant:
        if len(selected) >= max_count:
            break
        key = item_key(item)
        if not key or key in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(key)

    return selected


def fetch_stock_news(stock_name, limit=20, market=None, *, raise_on_error=False):
    stock_name = _clean_text(stock_name)
    if not stock_name:
        return []

    queries = [stock_name]
    stock_region = ""
    for region, stocks in STOCK_UNIVERSE.items():
        aliases = stocks.get(stock_name)
        if aliases:
            stock_region = region
            # Keep the existing three-alias cap for domestic stocks, but do not
            # cut off US company-name aliases behind ticker symbols.  Names such
            # as 구글/google/alphabet are important NAVER search terms for 알파벳.
            search_aliases = aliases if region == "미국" else aliases[:3]
            queries = list(dict.fromkeys([stock_name] + search_aliases))
            break

    is_us_stock = stock_region == "미국" or market == "미국"
    ticker = _primary_us_ticker(stock_name) if is_us_stock else ""

    # Keep independent providers concurrent so adding official/SEC sources does
    # not serialize extra network latency onto the existing NAVER hot path.
    jobs = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs["stock"] = pool.submit(
            _fetch_queries,
            queries,
            category="종목",
            per_query=max(20, limit),
            raise_on_error=raise_on_error,
        )
        if is_us_stock:
            jobs["official"] = pool.submit(
                official_company_news.fetch_company_news,
                stock_name,
                min(max(6, int(limit)), 15),
            )
            jobs["sec"] = pool.submit(
                sec_filings.fetch_recent_filings,
                stock_name,
                ticker,
                min(max(4, int(limit)), 10),
                MAX_NEWS_AGE_DAYS,
            )

        provider_rows = {}
        provider_failures = set()
        for name, future in jobs.items():
            try:
                provider_rows[name] = future.result()
            except Exception:
                provider_failures.add(name)
                provider_rows[name] = []

    if raise_on_error and 'stock' in provider_failures and not any(provider_rows.values()):
        raise RuntimeError('stock_news_providers_failed')
    stock_items = provider_rows.get("stock") or []
    official_items = provider_rows.get("official") or []
    sec_items = provider_rows.get("sec") or []

    items = [
        _enrich_item(x)
        for x in _dedupe(stock_items + official_items + sec_items)
        if _item_age_ok(x)
    ]
    relevant = []
    for item in items:
        if _is_stock_roundup(item):
            continue
        text = _search_text(item)
        relevance_tier = _stock_analysis_relevance(item, stock_name)
        if relevance_tier <= 0:
            continue

        # Keep articles that name the stock directly in the title even when our
        # material/action dictionaries do not know the article's wording yet.
        # Indirect mentions still require the existing material + event checks
        # so broad market stories do not flood stock analysis.
        material_signal = _contains_any(text, STOCK_MATERIAL_SIGNALS)
        event_strength = _stock_event_strength(item)
        if relevance_tier < 3:
            if not material_signal:
                continue
            if event_strength <= 0:
                continue

        selected = dict(item)
        selected["analysis_relevance_tier"] = relevance_tier
        selected["analysis_event_strength"] = event_strength
        selected["analysis_material_signal"] = material_signal
        relevant.append(selected)

    # Choose eventful articles first. Stock relevance still breaks ties, and
    # recency is the final tie-breaker.
    relevant.sort(
        key=lambda item: (
            int(item.get("analysis_event_strength") or 0),
            int(item.get("analysis_relevance_tier") or 0),
            item.get("published_at") or "",
        ),
        reverse=True,
    )
    return _select_stock_news_with_source_reserve(relevant, limit)

