"""Explainable scoring for stock-news flow analysis.

This module does not collect or reclassify news. It scores the normalized
records produced by news_feed so the central "왜?" flow can rank evidence
without changing the existing news panel.
"""

import datetime
from collections import Counter
from email.utils import parsedate_to_datetime


STRONG_EVIDENCE_WORDS = (
    "공시", "실적", "매출", "영업이익", "순이익", "eps", "가이던스",
    "계약", "수주", "공급계약", "납품", "배당", "자사주", "목표주가",
)


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
    # A narrow gap is deliberately treated as mixed. This is the news-side
    # basis for a later "왜 보합일까?" explanation instead of forcing a side.
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
