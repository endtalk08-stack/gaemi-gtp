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
        if not keywords:
            continue

        detail_by_label = {
            str(detail.get("label") or "").strip(): detail
            for detail in details
            if str(detail.get("label") or "").strip()
        }
        representative = str(keywords[0]).strip()
        detail = detail_by_label.get(representative, {})
        tone = str(detail.get("tone") or "neutral").strip()
        if tone not in ("positive", "negative", "neutral"):
            tone = "neutral"

        article["article_keywords"] = keywords
        article["article_keyword_details"] = details
        article["storyboard_keyword"] = representative
        article["storyboard_keyword_tone"] = tone
        article["storyboard_time"] = local_dt.strftime("%H:%M")
        article["storyboard_date"] = local_dt.strftime("%Y-%m-%d")
        bundles.append((local_dt, article))

    bundles.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [article for _, article in bundles]\n    if limit is None:\n        return ordered\n    return ordered[:max(1, int(limit))]
