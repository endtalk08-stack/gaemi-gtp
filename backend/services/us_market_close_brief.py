"""Verified US close brief for central chat; no AI calls and no UI logic.

Uses the market news result once and existing Yahoo daily-history provider.
Only dated, completed-market quotes and sentences from verified article bodies
can appear. Missing sections stay hidden instead of being invented.
"""
import datetime
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.providers.market_price import fetch_daily_price_history
from .us_market_close_news import build_us_market_close_news_result, _last_completed_session


_INDEXES = (
    ("나스닥", "^IXIC"),
    ("S&P500", "^GSPC"),
    ("다우", "^DJI"),
    ("필라델피아 반도체", "^SOX"),
)
_RISING = ("상승", "강세", "급등", "반등", "올랐", "오름세", "뛰었", "상승세")
_FALLING = ("하락", "약세", "급락", "내렸", "내림세", "떨어졌", "밀렸")
_CORE_SECTORS = (
    "반도체", "기술주", "빅테크", "ai 반도체", "전기차", "배터리",
    "에너지주", "에너지 업종", "금융주", "은행주", "바이오", "제약", "헬스케어",
    "원전", "전력 인프라", "원자력", "소비재", "산업재",
)
_OTHER_SECTORS = ("방산", "우주항공", "가상자산", "암호화폐", "비트코인", "항공", "조선")
_MACRO = ("국채금리", "달러인덱스", "환율", "국제유가", "원유", "wti", "천연가스", "구리", "원자재", "달러화")
_ECONOMY = ("소비자물가", "cpi", "pce", "fomc", "연준", "고용지표", "실업률", "금리 인하", "금리 동결")
_VOLUME = ("거래대금", "거래량", "상승 종목", "하락 종목", "매수세", "매도세")
_EARNINGS = ("실적 발표", "매출액", "어닝", "시간외", "장 마감 후", "장 마감 이후")
_CACHE_LOCK = threading.Lock()
_CACHE = None
_CACHED_AT = 0.0
_TTL = 10 * 60


def _dated_index(symbol, session):
    """Use only closes labelled with a NY exchange date, never an intraday candle."""
    rows = fetch_daily_price_history(symbol)
    dated = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            day = datetime.date.fromisoformat(str(row.get("date") or ""))
            close = float(row.get("close") or 0)
        except (ValueError, TypeError, OverflowError):
            continue
        if day <= session and close > 0 and close < float("inf"):
            dated.append((day, close))
    dated.sort()
    if len(dated) < 2 or dated[-1][0] != session:
        return None
    last_day, last = dated[-1]
    prev = dated[-2][1]
    if prev <= 0:
        return None
    return {"date": last_day.isoformat(), "change_pct": round((last / prev - 1) * 100, 2)}


def _index_changes(session):
    found = {}
    with ThreadPoolExecutor(max_workers=len(_INDEXES)) as pool:
        jobs = {
            pool.submit(_dated_index, symbol, session): name
            for name, symbol in _INDEXES
        }
        for future in as_completed(jobs):
            try:
                item = future.result()
                if item is not None:
                    found[jobs[future]] = item
            except Exception:
                continue
    return [
        {"name": name, **found[name]}
        for name, _ in _INDEXES if name in found
    ]


def _factual_sentences(news_items):
    """Carry short original statements with their article URLs; no invented causes."""
    sentences = []
    seen = set()
    for item in news_items:
        text = str(item.get("article_body") or "")
        for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", text):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if len(sentence) < 30 or len(sentence) > 240:
                continue
            key = re.sub(r"\W+", "", sentence).casefold()
            if key in seen:
                continue
            seen.add(key)
            sentences.append({
                "text": sentence,
                "source": str(item.get("source") or ""),
                "url": str(item.get("url") or item.get("link") or ""),
            })
    return sentences


def _fact_sections(items):
    categories = {
        "주도업종": [],
        "하락업종": [],
        "그 밖에 움직인 업종 · 테마": [],
        "원자재 · 금리 · 환율": [],
        "경제지표 · 통화정책": [],
        "거래대금 · 시장 강도": [],
        "기업 실적 · 시간외 거래": [],
    }
    for item in _factual_sentences(items):
        sentence = item["text"]
        lower = sentence.casefold()
        sector = any(word in lower for word in _CORE_SECTORS)
        rising = any(word in lower for word in _RISING)
        falling = any(word in lower for word in _FALLING)
        # A sentence reporting mixed directions cannot prove which
        # specific sector led or lagged. Keep it out of either ranking.
        if sector and rising and not falling:
            section = "주도업종"
        elif sector and falling and not rising:
            section = "하락업종"
        elif any(word in lower for word in _OTHER_SECTORS):
            section = "그 밖에 움직인 업종 · 테마"
        elif any(word in lower for word in _ECONOMY):
            section = "경제지표 · 통화정책"
        elif any(word in lower for word in _MACRO):
            section = "원자재 · 금리 · 환율"
        elif any(word in lower for word in _VOLUME):
            section = "거래대금 · 시장 강도"
        elif any(word in lower for word in _EARNINGS):
            section = "기업 실적 · 시간외 거래"
        else:
            continue
        if len(categories[section]) < 2:
            categories[section].append(item)
    return categories



# Keep news assertions and their subjects intact; only adjust sentence endings.
_SPOKEN_ENDINGS = (
    ("전망된다.", "전망돼."),
    ("것으로 보인다.", "것으로 보여."),
    ("예상된다.", "예상돼."),
    ("밝혔다.", "밝혔어."),
    ("전했다.", "전했어."),
    ("꼽았다.", "꼽았어."),
    ("이어졌다.", "이어졌어."),
    ("보였다.", "보였어."),
    ("기록했다.", "기록했어."),
    ("나타났다.", "나타났어."),
    ("내려갔다.", "내려갔어."),
    ("올라갔다.", "올라갔어."),
    ("어졌다.", "어졌어."),
    ("했다.", "했어."),
    ("됐다.", "됐어."),
    ("졌다.", "졌어."),
    ("났다.", "났어."),
    ("였다.", "였어."),
    ("었다.", "었어."),
    ("았다.", "았어."),
    ("있다.", "있어."),
    ("없다.", "없어."),
    ("이다.", "이야."),
)


def _naturalize_fact(text):
    """Change only known factual endings, never subjects, quantities or causality."""
    original = str(text or "").strip()
    for ending, spoken in _SPOKEN_ENDINGS:
        if original.endswith(ending):
            return original[:-len(ending)] + spoken
    return original


def _joined_first_fact(text):
    """Use a plain additive connector only for facts from one verified article."""
    for ending, linked in (
        ("했어.", "했고,"),
        ("보였어.", "보였고,"),
        ("됐어.", "됐고,"),
        ("졌어.", "졌고,"),
        ("났어.", "났고,"),
        ("였어.", "였고,"),
        ("었어.", "었고,"),
        ("았어.", "았고,"),
    ):
        if text.endswith(ending):
            return text[:-len(ending)] + linked
    return ""


def _render_market_facts(facts):
    """Up to two supported statements, with no synthetic 'because' or inference."""
    visible = [_naturalize_fact(item["text"]) for item in facts]
    if len(visible) == 2:
        first_url = str(facts[0].get("url") or "")
        second_url = str(facts[1].get("url") or "")
        if first_url and first_url == second_url:
            linked = _joined_first_fact(visible[0])
            if linked:
                return linked + " " + visible[1]
    return "\n\n".join(visible)


def build_us_market_close_brief(*, now=None):
    """One cached market-scoped result reused by any future renderer."""
    global _CACHE, _CACHED_AT
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    session = _last_completed_session(current)
    with _CACHE_LOCK:
        if _CACHE and _CACHE.get("session_date") == session.isoformat() and time.monotonic() - _CACHED_AT < _TTL:
            return {**_CACHE, "sections": [dict(x) for x in _CACHE["sections"]]}

        indices = _index_changes(session)
        news = build_us_market_close_news_result(limit=4, now=current, include_body=True)
        articles = news.get("items") or []
        categories = _fact_sections(articles)
        sections = []
        if indices:
            overview = ", ".join(
                f'{item["name"]} {item["change_pct"]:+.2f}%'
                for item in indices if item["name"] in {"나스닥", "S&P500", "다우"}
            )
            if overview:
                sections.append({"title": "미국장은 어땠어? 🇺🇸", "content": f"{session:%m월 %d일} 미국장은 {overview}로 마감했어."})
            sections.append({
                "title": "주요 지수",
                "content": "\n".join(f'{item["name"]}  {item["change_pct"]:+.2f}%' for item in indices),
            })
        else:
            sections.append({
                "title": "미국장은 어땠어? 🇺🇸",
                "content": f"{session.isoformat()} 미국장 지수 종가를 아직 확인하지 못했어.",
            })

        for title, facts in categories.items():
            if not facts:
                continue
            sections.append({
                "title": title,
                "content": _render_market_facts(facts),
            })

        if not articles:
            sections.append({
                "title": "마감시황 기사",
                "content": "해당 거래일의 원문이 확인된 마감시황 기사를 아직 확보하지 못했어. 확인되지 않은 상승·하락 이유는 표시하지 않을게.",
            })
        result = {
            "ok": bool(indices or articles),
            "market": "us",
            "kind": "close_brief",
            "session_date": session.isoformat(),
            "indices": indices,
            "sections": sections,
            "article_sources": [
                {"title": item.get("title", ""), "source": item.get("source", ""), "url": item.get("url", "")}
                for item in articles
            ],
        }
        _CACHE = result
        _CACHED_AT = time.monotonic()
        return {**result, "sections": [dict(x) for x in sections]}
