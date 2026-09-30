"""Explainable scoring for stock-news flow analysis.

This module does not collect news. It scores the normalized records produced by
news_feed so the central "왜?" flow can rank evidence without changing the
existing news panel. For the central keyword view, broad movement labels are
refined back to concrete phrases that are actually present in title+description.
"""

import datetime
from collections import Counter
from email.utils import parsedate_to_datetime


STRONG_EVIDENCE_WORDS = (
    "공시", "실적", "매출", "영업이익", "순이익", "eps", "가이던스",
    "계약", "수주", "공급계약", "납품", "배당", "자사주", "목표주가",
)

# Central chat should show concrete evidence keywords, not replace them with a
# broader interpretation. The panel/news classifier itself remains untouched.
CONCRETE_SIGNAL_RULES = {
    "실적상회": [
        ("어닝서프라이즈", ["어닝 서프라이즈"]),
        ("가이던스상향", ["가이던스 상향"]),
        ("전망상향", ["전망 상향"]),
        ("실적개선", ["실적 개선"]),
        ("호실적", ["호실적"]),
        ("실적상회", ["실적 상회"]),
    ],
    "메모리가격": [
        ("D램가격", ["d램 가격", "dram 가격"]),
        ("낸드가격", ["낸드 가격"]),
        ("메모리가격", ["메모리 가격"]),
    ],
    "AI메모리": [
        ("HBM", ["hbm", "고대역폭 메모리"]),
        ("AI메모리", ["ai 메모리"]),
    ],
    "수주·계약": [
        ("공급계약", ["공급계약", "공급 계약"]),
        ("납품계약", ["납품 계약"]),
        ("단일판매", ["단일판매"]),
        ("수주", ["수주"]),
    ],
    "주주환원": [
        ("자사주소각", ["자사주 소각"]),
        ("자사주매입", ["자사주 매입"]),
        ("자사주취득", ["자사주 취득"]),
        ("배당확대", ["배당 확대"]),
        ("배당증가", ["배당 증가"]),
    ],
    "차익실현": [("차익실현", ["차익실현", "차익 실현"]), ("매물출회", ["매물 출회"])],
    "외국인매도": [("외국인순매도", ["외국인 순매도"]), ("외국인매도", ["외국인 매도", "외인 매도"])],
    "기관매도": [("기관순매도", ["기관 순매도"]), ("기관매도", ["기관 매도"])],
    "실적악화": [
        ("어닝쇼크", ["어닝 쇼크"]),
        ("가이던스하향", ["가이던스 하향"]),
        ("전망하향", ["전망 하향"]),
        ("실적부진", ["실적 부진"]),
        ("실적악화", ["실적 악화"]),
    ],
    "금리부담": [("고금리", ["고금리"]), ("금리상승", ["금리 상승"]), ("금리부담", ["금리 부담"])],
    "유가부담": [("원유가격상승", ["원유 가격 상승"]), ("유가상승", ["유가 상승"]), ("유가부담", ["유가 부담"])],
    "환율부담": [("달러강세", ["달러 강세"]), ("원달러상승", ["원달러 상승"]), ("환율부담", ["환율 부담"])],
    "시장약세": [("코스피약세", ["코스피 약세"]), ("코스닥약세", ["코스닥 약세"]), ("증시약세", ["증시 약세"]), ("시장약세", ["시장 약세"])],
    "지정학적리스크": [("중동긴장", ["중동 긴장"]), ("전쟁", ["전쟁"]), ("분쟁", ["분쟁"]), ("지정학", ["지정학"])],
    "규제·소송": [("규제강화", ["규제 강화"]), ("제재", ["제재"]), ("소송", ["소송"]), ("리콜", ["리콜"])],
}


def _parse_date(value):
    try:
        date = parsedate_to_datetime(str(value or "").strip())
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)
        return date.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _freshness_score(item):
    date = _parse_date(item.get("pub_date"))
    if not date:
        return 0
    hours = max(0.0, (datetime.datetime.now(datetime.timezone.utc) - date).total_seconds() / 3600)
    if hours <= 12:
        return 15
    if hours <= 24:
        return 12
    if hours <= 72:
        return 8
    if hours <= 120:
        return 4
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
    refined = []
    seen = set()
    for raw in item.get("movement_signals") or []:
        signal = dict(raw)
        label = _concrete_signal_label(item, signal.get("label"))
        if not label or label in seen:
            continue
        signal["label"] = label
        refined.append(signal)
        seen.add(label)
    return refined


def _signal_score(item):
    signals = item.get("movement_signals") or []
    return min(20, len(signals) * 5)


def _classification_score(item):
    # Existing panel classification is reused as supporting context, not rebuilt here.
    issue_count = len(item.get("issues") or [])
    theme_count = len(item.get("themes") or [])
    stock_count = len(item.get("related_stocks") or [])
    return min(10, issue_count * 2 + theme_count * 2 + min(stock_count, 2))


def score_stock_news(items, stock_name):
    """Attach transparent score components and rank normalized stock news."""
    scored = []
    for raw in items or []:
        item = dict(raw)
        item["movement_signals"] = _refine_movement_signals(item)
        breakdown = {
            "direct_stock": _direct_score(item, stock_name),
            "material_strength": _material_score(item),
            "movement_signal": _signal_score(item),
            "freshness": _freshness_score(item),
            "classification_context": _classification_score(item),
        }
        # Keep the existing relevance score visible but cap its influence.
        relevance = max(0, min(int(item.get("relevance_score") or 0), 10))
        breakdown["investment_relevance"] = relevance
        item["flow_score_breakdown"] = breakdown
        item["flow_score"] = sum(breakdown.values())
        scored.append(item)

    scored.sort(key=lambda item: (item.get("flow_score", 0), item.get("pub_date", "")), reverse=True)
    return scored


def summarize_stock_flow(items):
    """Aggregate scored articles into an explainable positive/negative/mixed flow.

    Counts remain available, but direction is decided from weighted evidence so
    one weak repeated keyword does not automatically beat a newer, stronger
    stock-specific material article.
    """
    signal_counts = Counter()
    signal_scores = Counter()
    signal_tones = {}
    issue_counts = Counter()
    theme_counts = Counter()
    positive_count = 0
    negative_count = 0
    positive_score = 0.0
    negative_score = 0.0

    for item in items or []:
        article_score = max(1, int(item.get("flow_score") or 0))
        signals = item.get("movement_signals") or []
        # An article with several labels should not multiply its full article
        # score for every label. Split the evidence weight across its signals.
        per_signal_score = article_score / max(1, len(signals))
        for signal in signals:
            label = str(signal.get("label") or "").strip()
            tone = str(signal.get("tone") or "").strip()
            if label:
                signal_counts[label] += 1
                signal_scores[label] += per_signal_score
                if tone in ("positive", "negative"):
                    signal_tones[label] = tone
            if tone == "positive":
                positive_count += 1
                positive_score += per_signal_score
            elif tone == "negative":
                negative_count += 1
                negative_score += per_signal_score
        issue_counts.update(item.get("issues") or [])
        theme_counts.update(item.get("themes") or [])

    directional_total = positive_score + negative_score
    balance = (positive_score - negative_score) / directional_total if directional_total else 0.0
    if directional_total == 0:
        direction = "neutral"
    elif balance >= 0.18:
        direction = "positive"
    elif balance <= -0.18:
        direction = "negative"
    else:
        direction = "mixed"

    ranked_signals = sorted(
        signal_counts,
        key=lambda label: (signal_scores[label], signal_counts[label], label),
        reverse=True,
    )
    top_signals = [
        {
            "label": label,
            "tone": signal_tones.get(label, "neutral"),
            "count": signal_counts[label],
            "evidence_score": round(signal_scores[label], 1),
        }
        for label in ranked_signals[:5]
    ]

    positive_signals = [signal for signal in top_signals if signal["tone"] == "positive"]
    negative_signals = [signal for signal in top_signals if signal["tone"] == "negative"]

    return {
        "article_count": len(items or []),
        "direction": direction,
        "direction_balance": round(balance, 3),
        "positive_signal_count": positive_count,
        "negative_signal_count": negative_count,
        "positive_evidence_score": round(positive_score, 1),
        "negative_evidence_score": round(negative_score, 1),
        "top_signals": top_signals,
        "top_positive_signals": positive_signals[:3],
        "top_negative_signals": negative_signals[:3],
        "top_issues": [{"label": label, "count": count} for label, count in issue_counts.most_common(5)],
        "top_themes": [{"label": label, "count": count} for label, count in theme_counts.most_common(5)],
    }
