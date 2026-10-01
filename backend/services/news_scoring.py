"""Explainable scoring for stock-news flow analysis.

This module does not collect news. It scores the normalized records produced by
news_feed so the central "왜?" flow can rank evidence without changing the
existing news panel. For the central keyword view, broad movement labels are
refined back to concrete phrases that are actually present in title+description.
"""

import datetime
from collections import Counter
from zoneinfo import ZoneInfo
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
    "지정학적리스크": [("중동긴장", ["중동 긴장"]), ("전쟁", ["전쟁"]), ("분쟁", ["분쟁"]), ("지정학", ["지정학"])],
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


def _direct_score(item, stock_name):
    title = str(item.get("title") or "").lower()
    stock = str(stock_name or "").strip().lower()
    return 25 if stock and stock in title else 0


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
        signals = item.get("movement_signals") or []
        keywords = []
        keyword_tones = {}
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
        shared = set(previous["keywords"]) & set(event["keywords"])
        within_window = prev_dt and cur_dt and (cur_dt - prev_dt).total_seconds() <= merge_minutes * 60

        if within_window and shared:
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
            "direct_stock": _direct_score(item, stock_name), "material_strength": _material_score(item),
            "movement_signal": _signal_score(item), "freshness": _freshness_score(item),
            "classification_context": _classification_score(item),
        }
        relevance = max(0, min(int(item.get("relevance_score") or 0), 10))
        breakdown["investment_relevance"] = relevance
        item["flow_score_breakdown"] = breakdown
        item["flow_score"] = sum(breakdown.values())
        scored.append(item)
    scored.sort(key=lambda item: (item.get("flow_score", 0), item.get("pub_date", "")), reverse=True)
    return scored


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
