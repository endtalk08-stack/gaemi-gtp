"""Simple paired news/storyboard path.

This module intentionally does not collect, score, or invent keywords.
It receives the already-scored news list, reuses the existing article keyword
extractor, and keeps article + timestamp + keyword together as one bundle.
"""

import datetime
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
    """Pick distinct keyword events from the full today-news set for central chat."""
    selected = []
    seen_keywords = set()

    for source in items or []:
        keywords = [str(value).strip() for value in (source.get("storyboard_keywords") or []) if str(value).strip()]
        if not keywords:
            continue

        tones = dict(source.get("storyboard_keyword_tones") or {})
        keyword = next((value for value in keywords if value not in seen_keywords), "")
        if not keyword:
            continue

        seen_keywords.add(keyword)
        article = dict(source)
        article["storyboard_keywords"] = [keyword]
        article["storyboard_keyword"] = keyword
        article["storyboard_keyword_tones"] = {keyword: tones.get(keyword, "neutral")}
        article["storyboard_keyword_tone"] = tones.get(keyword, "neutral")
        selected.append(article)

        if len(selected) >= max(1, int(limit)):
            break

    return selected
