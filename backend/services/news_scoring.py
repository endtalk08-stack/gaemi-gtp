"""Explainable scoring for stock-news flow analysis.

This module does not collect news. It scores the normalized records produced by
news_feed so the central "왜?" flow can rank evidence without changing the
existing news panel. For the central keyword view, broad movement labels are
refined back to concrete phrases that are actually present in title+description.
"""

import datetime
from collections import Counter
from zoneinfo import ZoneInfo

from .news_feed import STOCK_UNIVERSE
from email.utils import parsedate_to_datetime


STRONG_EVIDENCE_WORDS = (
    "공시", "실적", "매출", "영업이익", "순이익", "eps", "가이던스",
    "계약", "수주", "공급계약", "납품", "배당", "자사주", "목표주가",
)

# Central chat should show concrete evidence keywords, not replace them with a
# broader interpretation. The panel/news classifier itself remains untouched.
CONCRETE_SIGNAL_RULES = {
    "실적상회": [
        ("매출상회", ["매출 상회"]),
        ("어닝서프라이즈", ["어닝 서프라이즈"]),
        ("가이던스상향", ["가이던스 상향"]),
        ("전망상향", ["전망 상향"]),
        ("실적개선", ["실적 개선"]),
        ("호실적", ["호실적"]),
        ("실적상회", ["실적 상회"]),
    ],
    "메모리가격": [("D램가격", ["d램 가격", "dram 가격"]), ("낸드가격", ["낸드 가격"]), ("메모리가격", ["메모리 가격"])],
    "AI메모리": [("HBM수요", ["hbm 수요"]), ("HBM", ["hbm", "고대역폭 메모리"]), ("AI메모리", ["ai 메모리"])],
    "수주·계약": [("대형수주", ["대형 수주"]), ("BESS공급계약", ["bess 공급계약", "bess 공급 계약"]), ("방산계약", ["방산 계약"]), ("공급계약", ["공급계약", "공급 계약"]), ("납품계약", ["납품 계약"]), ("단일판매", ["단일판매"]), ("수주", ["수주"])],
    "주주환원": [("자사주소각", ["자사주 소각"]), ("자사주매입", ["자사주 매입"]), ("자사주취득", ["자사주 취득"]), ("배당확대", ["배당 확대"]), ("배당증가", ["배당 증가"])],
    "차익실현": [("차익실현", ["차익실현", "차익 실현"]), ("매물출회", ["매물 출회"])],
    "외국인매도": [("외국인순매도", ["외국인 순매도"]), ("외국인매도", ["외국인 매도", "외인 매도"])],
    "기관매도": [("기관순매도", ["기관 순매도"]), ("기관매도", ["기관 매도"])],
    "실적악화": [("어닝쇼크", ["어닝 쇼크"]), ("가이던스하향", ["가이던스 하향"]), ("전망하향", ["전망 하향"]), ("실적부진", ["실적 부진"]), ("실적악화", ["실적 악화"])],
    "금리부담": [("고금리", ["고금리"]), ("금리상승", ["금리 상승"]), ("금리부담", ["금리 부담"])],
    "유가부담": [("원유가격상승", ["원유 가격 상승"]), ("유가상승", ["유가 상승"]), ("유가부담", ["유가 부담"])],
    "환율부담": [("달러강세", ["달러 강세"]), ("원달러상승", ["원달러 상승"]), ("환율부담", ["환율 부담"])],
    "시장약세": [("코스피약세", ["코스피 약세"]), ("코스닥약세", ["코스닥 약세"]), ("증시약세", ["증시 약세"]), ("시장약세", ["시장 약세"])],
    "지정학적리스크": [("중동긴장", ["중동 긴장"]), ("전쟁", ["전쟁"]), ("분쟁", ["분쟁"])],
    "규제·소송": [("규제강화", ["규제 강화"]), ("제재", ["제재"]), ("소송", ["소송"]), ("리콜", ["리콜"])],
}

# First-pass shared material dictionary built from real KR/US news examples.
# Company/product/project proper nouns are intentionally excluded; this list is
# for reusable investment meaning. Tone is only assigned where the phrase itself
# has a clear direction. Neutral entries are kept as evidence, not forced bullish/bearish.
DETAIL_KEYWORD_RULES = [
    ("거래량호조", "positive", ["거래량 호조"]),
    ("목표가상향", "positive", ["목표가 상향", "목표주가 상향"]),
    ("목표가하향", "negative", ["목표가 하향", "목표주가 하향"]),
    ("비중확대", "positive", ["비중 확대"]),
    ("매수의견", "positive", ["매수 의견", "매수의견"]),
    ("의견상향", "positive", ["의견 상향", "투자의견 상향"]),
    ("의견하향", "negative", ["의견 하향", "투자의견 하향"]),
    ("밸류매력", "neutral", ["밸류 매력", "밸류에이션 매력"]),
    ("실적기대", "positive", ["실적 기대"]),
    ("실적전망", "neutral", ["실적 전망"]),
    ("매출발표", "neutral", ["매출 발표", "실적 발표", "분기 매출", "분기 실적"]),
    ("매출증가", "positive", ["매출 증가", "매출 상승"]),
    ("매출급증", "positive", ["매출 급증", "매출 폭증"]),
    ("수요급증", "positive", ["수요 급증", "수요 급등", "수요 폭증"]),
    ("설비투자재개", "positive", ["설비투자 재개", "설비 투자 재개"]),
    ("설비투자확대", "positive", ["설비투자 확대", "설비 투자 확대"]),
    ("설비투자축소", "negative", ["설비투자 축소", "설비 투자 축소"]),
    ("공급부족", "positive", ["공급 부족"]),
    ("판매증가", "positive", ["판매 증가"]),
    ("판매감소", "negative", ["판매 감소"]),
    ("유럽판매감소", "negative", ["유럽 판매 감소"]),
    ("반발매수세", "positive", ["반발 매수세", "반발매수"]),
    ("코스닥강세", "positive", ["코스닥 강세"]),
    ("반도체주약세", "negative", ["반도체주 약세", "반도체주가 약세"]),
    ("반도체강세", "positive", ["반도체 강세"]),
    ("AI주반등", "positive", ["ai주 반등", "ai 주 반등"]),
    ("수요증가", "positive", ["수요 증가", "수요 확대"]),
    ("수요둔화", "negative", ["수요 둔화", "수요 감소"]),
    ("초기수요", "neutral", ["초기 수요"]),
    ("방공수요", "positive", ["방공 수요"]),
    ("강관수요", "positive", ["강관 수요"]),
    ("메모리투자", "positive", ["메모리 투자"]),
    ("매출인식", "positive", ["매출 인식"]),
    ("소각기대", "positive", ["소각 기대"]),
    ("지분율상승", "positive", ["지분율 상승"]),
    ("금융지원", "positive", ["금융 지원"]),
    ("정부지원", "positive", ["정부 지원"]),
    ("원전협력", "positive", ["원전 협력"]),
    ("AI공동개발", "positive", ["ai 공동개발", "ai 공동 개발"]),
    ("기술협력", "positive", ["기술 협력"]),
    ("전략적협력", "positive", ["전략적 협력"]),
    ("잠수함수출", "positive", ["잠수함 수출"]),
    ("해군수주", "positive", ["해군 수주"]),
    ("수주경쟁", "neutral", ["수주 경쟁"]),
    ("사업자선정", "positive", ["사업자 선정"]),
    ("CEO이탈", "negative", ["ceo 이탈", "ceo 사임"]),
    ("임시CEO", "neutral", ["임시 ceo"]),
    ("지분희석", "negative", ["지분 희석"]),
    ("주식발행", "neutral", ["주식 발행"]),
    ("ATM증자", "negative", ["atm 증자", "at-the-market"]),
    ("보고서제출지연", "negative", ["보고서 제출 지연", "보고서 지연"]),
    ("나스닥경고", "negative", ["나스닥 경고"]),
    ("상장규정", "neutral", ["상장 규정"]),
    ("국채금리상승", "negative", ["국채금리 상승", "국채 금리 상승"]),
    ("국채금리하락", "positive", ["국채금리 하락", "국채 금리 하락"]),
    ("국채금리", "neutral", ["국채금리", "국채 금리"]),
    ("물가둔화", "positive", ["물가 둔화", "물가가 둔화", "물가 둔화세", "인플레이션 둔화"]),
    ("물가상승", "negative", ["물가 상승", "물가가 상승", "물가 상승세", "인플레이션 상승"]),
    ("인플레이션", "neutral", ["인플레이션"]),
    ("디플레이션", "negative", ["디플레이션"]),
    ("금리인하 기대", "positive", ["금리 인하 기대", "금리인하 기대", "금리 인하 가능성", "금리인하 가능성"]),
    ("구인건수", "neutral", ["구인 건수", "구인건수"]),
    ("중동대화", "positive", ["중동 대화"]),
    ("긴장완화", "positive", ["긴장 완화"]),
    # Industry/technology/context tags: useful for later KR-US linkage, but neutral by themselves.
    ("AI반도체", "neutral", ["ai 반도체"]),
    ("AI인프라", "neutral", ["ai 인프라"]),
    ("AI생태계", "neutral", ["ai 생태계"]),
    ("ALD", "neutral", ["ald"]),
    ("LMR배터리", "neutral", ["lmr 배터리"]),
    ("전공정장비", "neutral", ["전공정 장비"]),
    ("BESS", "neutral", ["bess"]),
    ("LNG운반선", "neutral", ["lng 운반선", "lng선"]),
    ("고선가선박", "neutral", ["고선가 선박"]),
    ("맞춤형칩", "neutral", ["맞춤형 칩", "커스텀 칩", "custom chip"]),
    ("가스관건설", "neutral", ["가스관 건설"]),
    ("연료전지", "neutral", ["연료전지"]),
    ("우라늄채굴", "neutral", ["우라늄 채굴"]),
    ("기업보안", "neutral", ["기업 보안"]),
    ("클라우드", "neutral", ["클라우드"]),
    ("전투기사업", "neutral", ["전투기 사업"]),
    ("피지컬AI", "neutral", ["피지컬 ai", "physical ai"]),
    ("자율주행AI", "neutral", ["자율주행 ai", "자율 주행 ai"]),
    ("자율주행데이터셋", "neutral", ["자율주행 데이터셋", "자율 주행 데이터셋", "주행 데이터셋", "주행 데이터 세트"]),
    ("AI에이전트", "neutral", ["ai 에이전트", "ai agent", "ai 비서"]),
    ("AI검색", "neutral", ["ai 검색", "ai 기반 검색"]),
    ("AI추론", "neutral", ["ai 추론", "추론 ai", "추론 모델"]),
    ("AI학습", "neutral", ["ai 학습", "ai 훈련", "학습 데이터"]),
    ("AI데이터센터", "neutral", ["ai 데이터센터", "ai 데이터 센터"]),
    ("AI로봇", "neutral", ["ai 로봇", "로봇 ai"]),
    ("휴머노이드", "neutral", ["휴머노이드"]),
    ("AI모델", "neutral", ["ai 모델", "인공지능 모델"]),
    ("주행데이터", "neutral", ["주행 데이터"]),
    ("자체알고리즘", "neutral", ["자체 알고리즘"]),
    ("AI판매상담", "neutral", ["ai 판매 상담", "ai 판매상담", "ai 판매 상담원", "ai 상담원"]),
    ("AI쇼핑", "neutral", ["ai 쇼핑", "ai 기반 쇼핑"]),
    ("쇼핑개편", "neutral", ["쇼핑 개편", "쇼핑 경험 개편", "쇼핑 검색 개편"]),
    ("상품정보개편", "neutral", ["상품정보 개편", "상품 정보 개편", "상품정보 바꾼", "상품 정보 바꾼"]),
    ("기술경쟁", "neutral", ["기술 경쟁", "기술력 경쟁"]),
    ("알고리즘경쟁", "neutral", ["알고리즘 경쟁"]),
    ("기술공개", "neutral", ["기술 공개", "기술을 공개", "공개한 기술"]),
    ("데이터공개", "neutral", ["데이터 공개", "데이터를 공개", "공개한 주행 데이터"]),
    ("서비스출시", "neutral", ["서비스 출시", "서비스를 출시", "서비스 공개"]),
    ("신규도입", "neutral", ["신규 도입", "새로 도입", "도입한다", "도입했다"]),
    ("사업확대", "positive", ["사업 확대", "사업을 확대", "사업 확장"]),
    ("시장진출", "neutral", ["시장 진출", "시장에 진출"]),
    ("투자확대", "positive", ["투자 확대", "투자를 확대", "투자 늘려", "투자를 늘려"]),
]


def _parse_date(value):
    """Parse RSS/ISO timestamps consistently for scoring and storyboard output."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        date = parsedate_to_datetime(raw)
    except Exception:
        try:
            date = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return date.astimezone(datetime.timezone.utc)


def _freshness_score(item):
    date = _parse_date(item.get("pub_date") or item.get("published_at"))
    if not date:
        return 0
    hours = max(0.0, (datetime.datetime.now(datetime.timezone.utc) - date).total_seconds() / 3600)
    if hours <= 12: return 15
    if hours <= 24: return 12
    if hours <= 72: return 8
    if hours <= 120: return 4
    return 2


def _stock_aliases(stock_name):
    stock = str(stock_name or "").strip().lower()
    aliases = [stock]
    for stocks in STOCK_UNIVERSE.values():
        for name, values in stocks.items():
            if str(name).strip().lower() == stock:
                aliases.extend(str(value).strip().lower() for value in values)
                break
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _direct_score(item, stock_name):
    title = str(item.get("title") or "").lower()
    return 35 if any(alias in title for alias in _stock_aliases(stock_name)) else 0


def _context_relevance_score(item, stock_name):
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
    aliases = _stock_aliases(stock_name)
    if not aliases:
        return 0

    title_hits = sum(title.count(alias) for alias in aliases)
    body_hits = sum(description.count(alias) for alias in aliases)

    # 제목 직접 언급은 중앙 핵심기사의 강한 신호로 사용한다.
    # 본문에만 등장한 기사는 점수를 낮게 주되 더보기에서는 보존한다.
    if title_hits:
        return 25 + min(10, max(0, title_hits - 1) * 5)
    if body_hits:
        return min(12, body_hits * 4)
    return 0


def _material_score(item):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    matches = sum(word.lower() in text for word in STRONG_EVIDENCE_WORDS)
    return min(20, matches * 5)


def _concrete_signal_label(item, label):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    for concrete_label, phrases in CONCRETE_SIGNAL_RULES.get(str(label or ""), []):
        if any(phrase.lower() in text for phrase in phrases):
            return concrete_label
    return str(label or "").strip()


def _refine_movement_signals(item):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    refined, seen = [], set()
    for raw in item.get("movement_signals") or []:
        signal = dict(raw)
        label = _concrete_signal_label(item, signal.get("label"))
        if label and label not in seen:
            signal["label"] = label
            refined.append(signal)
            seen.add(label)

    # Title + description are the article's evidence boundary. If a concrete
    # signal is explicitly present there, keep it even when feed-level
    # movement_signals did not carry that label through.
    for group_rules in CONCRETE_SIGNAL_RULES.values():
        for label, phrases in group_rules:
            if label not in seen and any(phrase.lower() in text for phrase in phrases):
                tone = "negative" if label in {"금리부담", "유가부담", "환율부담", "시장약세", "반도체주약세", "외국인매도", "기관매도", "실적악화", "전망하향"} else "positive"
                refined.append({"label": label, "tone": tone})
                seen.add(label)

    for label, tone, phrases in DETAIL_KEYWORD_RULES:
        if label not in seen and any(phrase.lower() in text for phrase in phrases):
            refined.append({"label": label, "tone": tone})
            seen.add(label)
    return refined


def _signal_score(item):
    return min(20, len(item.get("movement_signals") or []) * 5)


def _classification_score(item):
    issue_count = len(item.get("issues") or [])
    theme_count = len(item.get("themes") or [])
    stock_count = len(item.get("related_stocks") or [])
    return min(10, issue_count * 2 + theme_count * 2 + min(stock_count, 2))


def build_keyword_storyboard(items, merge_minutes=30, display_timezone="Asia/Seoul"):
    """Build a compact time-ordered keyword flow without changing article display.

    News timestamps are stored in UTC. Convert them only for presentation so the
    storyboard uses the market's local clock instead of silently showing UTC.
    """
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    events = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    for item in items or []:
        dt = _parse_date(item.get("pub_date") or item.get("published_at"))
        if not dt or dt < cutoff:
            continue
        article_keywords = item.get("article_keywords") or []
        article_keyword_details = item.get("article_keyword_details") or []
        keywords = []
        keyword_tones = {}
        if len(article_keywords) == 3:
            detail_tones = {
                str(detail.get("label") or "").strip(): str(detail.get("tone") or "neutral").strip()
                for detail in article_keyword_details
            }
            for label in article_keywords:
                label = str(label or "").strip()
                if label and label not in keywords:
                    keywords.append(label)
                    tone = detail_tones.get(label, "neutral")
                    keyword_tones[label] = tone if tone in ("positive", "negative", "neutral") else "neutral"
        else:
            signals = item.get("movement_signals") or []
            for signal in signals:
                label = str(signal.get("label") or "").strip()
                tone = str(signal.get("tone") or "neutral").strip()
                if label and label not in keywords:
                    keywords.append(label)
                    keyword_tones[label] = tone if tone in ("positive", "negative", "neutral") else "neutral"
        if not dt or not keywords:
            continue
        local_dt = dt.astimezone(tz)
        events.append({
            "time": local_dt.strftime("%H:%M"),
            "timestamp": local_dt.isoformat(),
            "keywords": keywords,
            "keyword_tones": keyword_tones,
        })

    events.sort(key=lambda event: event["timestamp"])
    merged = []
    for event in events:
        if not merged:
            merged.append(event)
            continue

        previous = merged[-1]
        prev_dt = _parse_date(previous["timestamp"])
        cur_dt = _parse_date(event["timestamp"])
        def related(a, b):
            a = str(a or "").replace("#", "").replace(" ", "")
            b = str(b or "").replace("#", "").replace(" ", "")
            if not a or not b:
                return False
            if a == b:
                return True
            # 같은 핵심어를 포함한 세부 표현도 같은 흐름으로 묶는다.
            if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
                return True
            return False

        related_topic = any(
            related(left, right)
            for left in previous["keywords"]
            for right in event["keywords"]
        )
        within_window = prev_dt and cur_dt and (cur_dt - prev_dt).total_seconds() <= merge_minutes * 60

        if within_window and related_topic:
            for keyword in event["keywords"]:
                if keyword not in previous["keywords"]:
                    previous["keywords"].append(keyword)
                    previous.setdefault("keyword_tones", {})[keyword] = event.get("keyword_tones", {}).get(keyword, "neutral")
            previous["timestamp"] = event["timestamp"]
            previous["time"] = event["time"]
        else:
            merged.append(event)

    compact = []
    seen_keywords = set()
    for event in reversed(merged):
        fresh = [k for k in event["keywords"] if k not in seen_keywords]
        if not fresh:
            continue
        event["keywords"] = fresh
        event["keyword_tones"] = {k: event.get("keyword_tones", {}).get(k, "neutral") for k in fresh}
        compact.append(event)
        seen_keywords.update(fresh)
        if len(compact) >= 3:
            break
    compact.reverse()
    return compact


def score_stock_news(items, stock_name):
    scored = []
    for raw in items or []:
        item = dict(raw)
        item["movement_signals"] = _refine_movement_signals(item)
        breakdown = {
            "direct_stock": _direct_score(item, stock_name), "context_relevance": _context_relevance_score(item, stock_name),
            "material_strength": _material_score(item),
            "movement_signal": _signal_score(item), "freshness": _freshness_score(item),
            "classification_context": _classification_score(item),
        }
        relevance = max(0, min(int(item.get("relevance_score") or 0), 10))
        breakdown["investment_relevance"] = relevance
        item["flow_score_breakdown"] = breakdown
        item["flow_score"] = sum(breakdown.values())
        scored.append(item)
    scored.sort(key=lambda item: (item.get("flow_score", 0), item.get("pub_date", "")), reverse=True)

    # Stock-news analysis/display uses Korean-language articles only.
    # Collection and the existing relevance/material scoring stay unchanged.
    def has_korean_text(item):
        text = f"{item.get('title') or ''} {item.get('description') or ''}"
        return any("\uac00" <= char <= "\ud7a3" for char in text)

    return [item for item in scored if has_korean_text(item)]


def summarize_stock_flow(items):
    signal_counts, signal_scores, signal_tones = Counter(), Counter(), {}
    issue_counts, theme_counts = Counter(), Counter()
    positive_count = negative_count = 0
    positive_score = negative_score = 0.0
    for item in items or []:
        article_score = max(1, int(item.get("flow_score") or 0))
        signals = item.get("movement_signals") or []
        per_signal_score = article_score / max(1, len(signals))
        for signal in signals:
            label = str(signal.get("label") or "").strip()
            tone = str(signal.get("tone") or "").strip()
            if label:
                signal_counts[label] += 1
                signal_scores[label] += per_signal_score
                if tone in ("positive", "negative", "neutral"): signal_tones[label] = tone
            if tone == "positive": positive_count += 1; positive_score += per_signal_score
            elif tone == "negative": negative_count += 1; negative_score += per_signal_score
        issue_counts.update(item.get("issues") or [])
        theme_counts.update(item.get("themes") or [])
    directional_total = positive_score + negative_score
    balance = (positive_score - negative_score) / directional_total if directional_total else 0.0
    direction = "neutral" if directional_total == 0 else "positive" if balance >= 0.18 else "negative" if balance <= -0.18 else "mixed"
    ranked_signals = sorted(signal_counts, key=lambda label: (signal_scores[label], signal_counts[label], label), reverse=True)
    top_signals = [{"label": label, "tone": signal_tones.get(label, "neutral"), "count": signal_counts[label], "evidence_score": round(signal_scores[label], 1)} for label in ranked_signals[:5]]
    return {
        "article_count": len(items or []), "direction": direction, "direction_balance": round(balance, 3),
        "positive_signal_count": positive_count, "negative_signal_count": negative_count,
        "positive_evidence_score": round(positive_score, 1), "negative_evidence_score": round(negative_score, 1),
        "top_signals": top_signals,
        "top_positive_signals": [s for s in top_signals if s["tone"] == "positive"][:3],
        "top_negative_signals": [s for s in top_signals if s["tone"] == "negative"][:3],
        "top_issues": [{"label": label, "count": count} for label, count in issue_counts.most_common(5)],
        "top_themes": [{"label": label, "count": count} for label, count in theme_counts.most_common(5)],
    }

def build_connected_keyword_test(items, stock_name, max_keywords=3):
    """Test-only: build article-summary keyword candidates, then keep three."""
    import re

    # Reusable expressions are helpers only. They must not decide the whole
    # article by themselves; title evidence stays the strongest signal.
    summary_rules = [
        ("목표가상향", ["목표가 상향", "목표주가 상향"]),
        ("목표가하향", ["목표가 하향", "목표주가 하향"]),
        ("매수의견", ["매수 의견", "매수의견", "'매수' 상향", '"매수" 상향']),
        ("투자의견상향", ["투자의견 상향", "의견 상향"]),
        ("투자의견하향", ["투자의견 하향", "의견 하향"]),
        ("가격상승", ["가격 상승", "가격 급등", "가격이 상승", "가격이 급등"]),
        ("가격하락", ["가격 하락", "가격 급락", "가격이 하락", "가격이 급락"]),
        ("물량증가", ["물량 증가", "출하량 증가", "판매량 증가"]),
        ("물량감소", ["물량 감소", "출하량 감소", "판매량 감소"]),
        ("수요증가", ["수요 증가", "수요 확대", "수요 급증"]),
        ("수요둔화", ["수요 둔화", "수요 감소"]),
        ("성장가속", ["성장 가속", "성장세 가속"]),
        ("투자확대", ["투자 확대", "투자를 확대"]),
        ("현금유입", ["현금 유입"]),
        ("안전성확인", ["안전성 확인", "안전성을 확인"]),
        ("실적프리뷰", ["실적 프리뷰"]),
        ("투자심리악화", ["투자심리 악화", "투자 심리 악화", "투자심리가 부정적"]),
        ("내부자매수", ["내부자 매수", "내부 임원", "임원 매입", "이사 매입"]),
        ("매입종료", ["매입 종료", "매입 마무리", "매입을 마무리", "매입 완료", "매입을 완료"]),
        ("사업매각", ["사업 매각"]),
        ("사업분사", ["사업 분사", "분사"]),
        ("발사계약", ["발사 계약"]),
        ("3상데이터", ["3상 데이터", "3상 임상", "3상 임상시험"]),
    ]

    # Broad words are useful classification context but weak final summary
    # keywords when a more concrete article phrase exists.
    broad_labels = {"AI", "반도체", "메모리", "시장", "기업", "주식", "증시"}
    aliases = _stock_aliases(stock_name)
    results = []

    for item in items or []:
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title:
            continue

        title_lower = title.lower()
        desc_lower = description.lower()
        full_lower = f"{title_lower} {desc_lower}".strip()
        candidates = []
        seen = set()

        def add(label, source, evidence, priority):
            clean = re.sub(r"\s+", "", str(label or "").strip())
            if not clean or clean in seen or clean.lower() in aliases:
                return
            seen.add(clean)
            candidates.append({
                "label": clean,
                "source": source,
                "evidence": str(evidence or "").strip(),
                "priority": priority,
            })

        # 1) Title-first: reusable meaning phrases found in the headline.
        for label, phrases in summary_rules:
            matched = next((p for p in phrases if p.lower() in title_lower), "")
            if matched:
                add(label, "title", matched, 100)

        # Existing signal dictionaries remain useful as supporting vocabulary,
        # but title matches outrank description-only matches.
        for signal in _refine_movement_signals(item):
            label = str(signal.get("label") or "").strip()
            if not label or label in broad_labels:
                continue
            compact = label.replace(" ", "")
            if compact.lower() in title_lower.replace(" ", ""):
                add(label, "title-signal", label, 90)
            elif compact.lower() in desc_lower.replace(" ", ""):
                add(label, "description-signal", label, 45)

        # 2) Description supplements the headline; it never replaces the
        # headline as the article's center.
        for label, phrases in summary_rules:
            if label in seen:
                continue
            matched = next((p for p in phrases if p.lower() in desc_lower), "")
            if matched:
                add(label, "description", matched, 55)

        # 3) Keep concrete headline nouns/names that make this article
        # distinguishable. Quoted names, English product/project names and
        # phase labels are candidates, not automatic winners.
        for quoted in re.findall(r"['\"“”‘’]([^'\"“”‘’]{2,24})['\"“”‘’]", title):
            if not any(word in quoted for word in ("상승", "하락", "급등", "급락")):
                add(quoted, "title-entity", quoted, 82)

        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9.\-]{2,20}\b", title):
            if token.lower() not in {"the", "and", "for", "with", "from"}:
                add(token, "title-entity", token, 78)

        for phase in re.findall(r"(?<!\d)([123])상(?:\s*임상(?:시험)?)?", title):
            add(f"{phase}상데이터", "title-entity", f"{phase}상", 80)

        # Test-only: keep concrete Korean event phrases from the headline.
        # This supplements reusable rules without adding stock-specific terms.
        korean_event_patterns = [
            r"([가-힣A-Za-z0-9]+(?:팹|공장))\s*(착공|준공|증설)",
            r"([가-힣A-Za-z0-9]+(?:메모리|제품|기술))\s*(공개|출시|개발)",
            r"([A-Za-z0-9가-힣]+)\s*(양산|생산)",
        ]
        for pattern in korean_event_patterns:
            for match in re.finditer(pattern, title):
                subject, event = match.groups()
                add(f"{subject}{event}", "title-event", match.group(0), 84)

        # Keep headline scale only when it belongs to a concrete corporate event.
        event_scale_words = ("매입", "인수", "계약", "수주", "투자", "매각", "증자")
        if any(word in title for word in event_scale_words):
            for amount in re.findall(r"(?<![\d.])(?:\d+(?:[.,]\d+)*)\s*(?:조원|억원|만원|달러)", title):
                add(amount, "title-scale", amount, 76)

        # A final keyword should explain article content, not merely repeat the
        # searched stock or its own price move.
        candidates = [
            row for row in candidates
            if row["label"] not in broad_labels
            and row["label"] not in {"주가상승", "주가하락", "급등", "급락"}
        ]
        candidates.sort(key=lambda row: (-row["priority"], row["source"], row["label"]))

        selected = []
        for row in candidates:
            label = row["label"]
            overlap_index = next(
                (
                    index for index, old in enumerate(selected)
                    if label in old["label"] or old["label"] in label
                ),
                None,
            )
            if overlap_index is not None:
                old = selected[overlap_index]
                if old["label"] in label and len(label) > len(old["label"]):
                    selected[overlap_index] = row
                continue
            selected.append(row)
            if len(selected) >= max_keywords:
                break

        enough = len(selected) == max_keywords
        results.append({
            "title": title,
            "description": description,
            "candidate_keywords": [row["label"] for row in candidates],
            "keywords": [row["label"] for row in selected] if enough else [],
            "keyword_details": selected if enough else [],
            "enough_evidence": enough,
            "status": "PASS" if enough else "SKIP",
        })

    return {"stock": stock_name, "articles": results}
