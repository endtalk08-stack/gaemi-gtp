"""Evidence-bounded, price-triggered stock signals from the existing analysis result.

This is not causal attribution. Only source-verified central articles are exposed.
No additional collection, model calls, storage or screen-specific analysis.
"""
from datetime import datetime, timedelta, timezone
from math import isfinite


def _number(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _date(value):
    try:
        date = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return date if date.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def build_stock_signals(stock, price_snapshot, news_result, *, now=None):
    """One observed movement signal per stock; cite at most three verified articles.

    A price move is a trigger, not proof the accompanying news caused it.
    """
    price = price_snapshot if isinstance(price_snapshot, dict) else {}
    move = _number(price.get("change_pct"))
    current = _number(price.get("current"))
    if current is None or current <= 0 or move is None or abs(move) < 1.0:
        return []

    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("now must be timezone aware")

    result = news_result if isinstance(news_result, dict) else {}
    candidates = result.get("storyboard_news_items") or []
    briefs = result.get("issue_briefs") or []
    brief_by_time = {
        str(brief.get("reaction_at")): brief
        for brief in briefs if isinstance(brief, dict) and brief.get("reaction_at")
    }
    evidence = []
    seen = set()
    for item in sorted(
        (item for item in candidates if isinstance(item, dict)),
        key=lambda entry: _number(entry.get("storyboard_selection_score")) or 0,
        reverse=True,
    ):
        if item.get("detail_read") is not True or str(item.get("relation_type") or "") != "direct":
            continue
        published = _date(item.get("published_at"))
        if published is None or not timedelta(0) <= at - published <= timedelta(hours=24):
            continue
        url = str(item.get("url") or item.get("link") or "").strip()
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        seen.add(url)
        brief = brief_by_time.get(str(item.get("published_at"))) or {}
        summary = str(brief.get("summary") or "").strip()[:480]
        evidence.append({
            "title": title[:240],
            "headline": str(brief.get("headline") or title).strip()[:160],
            "summary": summary,
            "source": str(item.get("source") or "").strip()[:90],
            "published_at": published.isoformat(),
            "url": url,
        })
        if len(evidence) == 3:
            break

    direction = "상승" if move > 0 else "하락"
    return [{
        "stock": str(stock or "").strip(),
        "title": f"{str(stock or '').strip()} {abs(move):.2f}% {direction}",
        "change_pct": round(move, 2),
        "currency": str(price.get("currency") or ""),
        "current": current,
        "status": "related_news_found" if evidence else "cause_unverified",
        "evidence": evidence,
        "reason_confirmed": False,
    }]
