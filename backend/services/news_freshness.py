"""Read-only freshness guard shared by Render chat and market sidebar.

DigitalOcean owns collection and AI work. Render only filters Neon snapshots
using the original published_at of cited articles, never the AI/DB write time.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def _article_date(value):
    stamp = str(value or "").strip()
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            parsed = parsedate_to_datetime(stamp)
        except (ValueError, TypeError, IndexError, OverflowError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def clean_us_snapshot(payload, *, now=None):
    """Return only 24h source-dated AI briefs and news articles for US screens.

    Both consumers use this function. Reject old source timestamps even when
    a snapshot was saved minutes ago. Unknown dates are not fabricated.
    """
    if not isinstance(payload, dict):
        return {}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=24)
    upper = now.astimezone(timezone.utc)
    result = deepcopy(payload)
    # Accept only the AI channel. Legacy code-generated issue_briefs are not
    # substituted when today's AI call failed or produced no issues.
    ai_briefs = result.get("_ai_issue_briefs")
    if not isinstance(ai_briefs, list):
        ai_briefs = []
    fresh = []
    for brief in ai_briefs:
        if not isinstance(brief, dict):
            continue
        valid_sources = []
        for source in brief.get("source_articles") or []:
            if not isinstance(source, dict):
                continue
            pub = _article_date(source.get("published_at"))
            url = str(source.get("url") or "").strip()
            if pub is None or not cutoff <= pub <= upper or not url.startswith(("https://", "http://")):
                continue
            publisher = str(source.get("source") or "").strip() or (urlparse(url).hostname or "")
            if not publisher:
                continue
            valid_sources.append((pub, {**source, "source": publisher}))
        if not valid_sources:
            continue
        latest = max(pub for pub, _ in valid_sources)
        fresh.append({
            **brief,
            "time": latest.astimezone(SEOUL).strftime("%H:%M"),
            "reaction_at": "",
            "source_articles": [source for _, source in valid_sources],
        })
    result["issue_briefs"] = fresh[:3]

    # Do not let an old article become today's news merely because DigitalOcean
    # refreshed the snapshot or a cached panel reloaded.
    for key in ("paired_news_items", "panel_news_items", "storyboard_news_items"):
        items = result.get(key)
        if not isinstance(items, list):
            continue
        result[key] = [
            item for item in items
            if isinstance(item, dict)
            and (pub := _article_date(item.get("published_at") or item.get("pubDate"))) is not None
            and cutoff <= pub <= upper
        ]
    return result
