"""Read-only freshness guard shared by Render chat and market sidebar.

DigitalOcean owns news collection and original article-body verification. Render only filters Neon snapshots
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
    """Return only source-dated verified-title v3 briefs and news for US screens.

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
    # Render is presentation-only: use the worker's original verified-article
    # briefs with title-only revision v3, never a pasted title/description or AI.
    code_briefs = result.get("_code_issue_briefs")
    if (
        str(result.get("_title_only_revision") or "") != "3"
        or str(result.get("_code_fact_extraction_version") or "") != "3"
        or not isinstance(code_briefs, list)
    ):
        code_briefs = []
    fresh = []
    for brief in code_briefs:
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

    # Price reason shares the same strict 24-hour cited-article freshness rule.
    reason = result.get("price_reason")
    if isinstance(reason, dict):
        sources = []
        for source in reason.get("source_articles") or []:
            if not isinstance(source, dict):
                continue
            pub = _article_date(source.get("published_at"))
            url = str(source.get("url") or "").strip()
            if pub is None or not cutoff <= pub <= upper or not url.startswith(("https://", "http://")):
                continue
            publisher = str(source.get("source") or "").strip() or (urlparse(url).hostname or "")
            if publisher:
                sources.append(source)
        result["price_reason"] = {**reason, "source_articles": sources} if sources else None

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
