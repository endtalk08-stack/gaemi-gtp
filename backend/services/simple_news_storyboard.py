"""Simple paired news/storyboard path.

This module intentionally does not collect, score, or invent keywords.
It receives the already-scored news list, reuses the existing article keyword
extractor, and keeps article + timestamp + keyword together as one bundle.
"""

import datetime
import re
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo


def _parse_article_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
    except Exception:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def build_simple_today_news(items, stock_name, limit=3, display_timezone="Asia/Seoul"):
    """Return today's article bundles; each article keeps its own keyword and time."""
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    source_items = [dict(item) for item in (items or [])]

    today = datetime.datetime.now(tz).date()
    bundles = []

    for article in source_items:
        dt = _parse_article_datetime(article.get("pub_date") or article.get("published_at"))
        if not dt:
            continue
        local_dt = dt.astimezone(tz)
        if local_dt.date() != today:
            continue

        keywords = list(article.get("article_keywords") or [])
        details = list(article.get("article_keyword_details") or [])
        detail_by_label = {
            str(detail.get("label") or "").strip(): detail
            for detail in details
            if str(detail.get("label") or "").strip()
        }
        storyboard_keywords = [str(keyword).strip() for keyword in keywords[:3] if str(keyword).strip()]
        storyboard_keyword_tones = {}
        for keyword in storyboard_keywords:
            detail = detail_by_label.get(keyword, {})
            tone = str(detail.get("tone") or "neutral").strip()
            if tone not in ("positive", "negative", "neutral"):
                tone = "neutral"
            storyboard_keyword_tones[keyword] = tone

        representative = storyboard_keywords[0] if storyboard_keywords else ""
        tone = storyboard_keyword_tones.get(representative, "neutral") if representative else "neutral"

        article["article_keywords"] = keywords
        article["article_keyword_details"] = details
        article["storyboard_keywords"] = storyboard_keywords
        article["storyboard_keyword_tones"] = storyboard_keyword_tones
        article["storyboard_keyword"] = representative
        article["storyboard_keyword_tone"] = tone
        article["storyboard_time"] = local_dt.strftime("%H:%M")
        article["storyboard_date"] = local_dt.strftime("%Y-%m-%d")
        bundles.append((local_dt, article))

    bundles.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [article for _, article in bundles]
    if limit is None:
        return ordered
    return ordered[:max(1, int(limit))]


def select_keyword_storyboard_news(items, limit=3):
    """Pick at most ``limit`` notable, distinct events for the central flow.

    The source list is already restricted to today's stock-relevant articles.
    This final step must not simply show the three newest articles: a direct,
    concrete event is more useful than a newer but weak mention.  It also keeps
    the selection deliberately sparse; if no article has a grounded event
    keyword, the caller receives an empty list rather than filler.
    """
    selected = []
    seen_keywords = set()
    selected_headlines = []

    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _selection_score(source):
        """Rank evidence without inventing a market interpretation.

        ``analysis_relevance_tier`` and ``analysis_event_strength`` come from
        the collector, while ``flow_score_breakdown`` comes from the existing
        explainable scorer.  The weights intentionally favor a company named
        in the headline and an explicit event over recency.
        """
        tier = max(0, int(_number(source.get("analysis_relevance_tier"))))
        event_strength = max(0.0, _number(source.get("analysis_event_strength")))
        breakdown = source.get("flow_score_breakdown") or {}
        direct = max(0.0, _number(breakdown.get("direct_stock")))
        material = max(0.0, _number(breakdown.get("material_strength")))
        signal = max(0.0, _number(breakdown.get("movement_signal")))

        return (
            (tier * 100)
            + min(event_strength, 8.0) * 8.0
            + min(direct, 35.0)
            + min(material, 20.0)
            + min(signal, 20.0)
            + min(_number(source.get("flow_score")), 100.0) / 10.0
        )

    def _keyword_key(value):
        return "".join(str(value or "").split()).lower()

    def _overlaps_existing(value):
        key = _keyword_key(value)
        if not key:
            return True
        for seen in seen_keywords:
            if key == seen:
                return True
            # Treat containment as the same event, but only for meaningful
            # multi-token labels. This keeps e.g. AI요금개편 and
            # 제미나이AI요금개편 from occupying two central slots.
            if min(len(key), len(seen)) >= 5 and (key in seen or seen in key):
                return True
        return False

    def _headline_key(value):
        """Build a comparison key without changing the original headline."""
        return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())

    def _is_same_event_as_selected(source):
        """Keep syndicated rewrites of the same event out of the 3-item flow.

        The full article list remains untouched.  This guard applies only to
        the concise central storyboard, where showing three rewrites of one
        event is less useful than showing three distinct events.
        """
        headline = _headline_key(source.get("title"))
        if len(headline) < 12:
            return False
        return any(
            SequenceMatcher(None, headline, previous).ratio() >= 0.75
            for previous in selected_headlines
        )

    candidates = []
    for source in items or []:
        keywords = [str(value).strip() for value in (source.get("storyboard_keywords") or []) if str(value).strip()]
        if not keywords:
            continue

        # Keep only articles that passed the existing grounded-keyword path.
        # This prevents a bare company mention from occupying a daily slot.
        candidates.append((source, keywords))

    candidates.sort(
        key=lambda pair: (
            _selection_score(pair[0]),
            str(pair[0].get("published_at") or pair[0].get("pub_date") or ""),
        ),
        reverse=True,
    )

    for source, keywords in candidates:

        tones = dict(source.get("storyboard_keyword_tones") or {})

        keyword = next((value for value in keywords if not _overlaps_existing(value)), "")
        if not keyword:
            continue
        if _is_same_event_as_selected(source):
            continue

        seen_keywords.add(_keyword_key(keyword))
        headline = _headline_key(source.get("title"))
        if headline:
            selected_headlines.append(headline)
        article = dict(source)
        article["storyboard_keywords"] = [keyword]
        article["storyboard_keyword"] = keyword
        article["storyboard_keyword_tones"] = {keyword: tones.get(keyword, "neutral")}
        article["storyboard_keyword_tone"] = tones.get(keyword, "neutral")
        article["storyboard_selection_score"] = round(_selection_score(source), 1)
        selected.append(article)

        if len(selected) >= max(1, int(limit)):
            break

    # Selection is based on importance, but the chat is a timeline.  Present
    # the chosen events in newest-first order without changing their members.
    selected.sort(
        key=lambda item: str(item.get("published_at") or item.get("pub_date") or ""),
        reverse=True,
    )
    return selected
