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


ISSUE_MODES = frozenset(("auto", "ai", "code", "both"))


def normalize_issue_mode(mode):
    """Safe per-request preference; unsupported values keep existing behavior."""
    value = str(mode or "").strip().lower()
    return value if value in ISSUE_MODES else "auto"


def issue_mode_for_question(question, *, explicit=None):
    """Route article-fact questions to code, movement reasons to existing AI."""
    requested = normalize_issue_mode(explicit)
    if requested != "auto":
        return requested
    content = str(question or "").replace(" ", "").lower()
    if any(word in content for word in ("왜올랐", "왜떨어", "왜하락", "왜상승", "상승이유", "하락이유", "주가원인", "주가이유")):
        return "ai"
    if any(word in content for word in ("이슈는", "이슈있", "최근이슈", "오늘이슈", "뉴스있", "뉴스는", "핵심재료", "관련기사", "새소식")):
        return "code"
    return "auto"


def clean_us_snapshot(payload, *, now=None, issue_mode="auto"):
    """Read cited, 24-hour code and preserved AI channels without changing either.

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
    # Both news channels are retained. UI preferences never invoke an AI
    # model, rerun article selection or write to Neon.
    v3 = (
        str(result.get("_title_only_revision") or "") == "3"
        and str(result.get("_code_fact_extraction_version") or "") == "3"
    )

    def fresh_source_briefs(briefs):
        if not isinstance(briefs, list):
            return []
        fresh = []
        for brief in briefs:
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
        return fresh[:3]

    channels = {
        "code": fresh_source_briefs(result.get("_code_issue_briefs")) if v3 else [],
        "ai": fresh_source_briefs(result.get("_ai_issue_briefs")),
    }
    mode = normalize_issue_mode(issue_mode)
    if mode == "code":
        selected, channel = channels["code"], "code"
    elif mode == "ai":
        selected, channel = channels["ai"], "ai"
    elif mode == "both":
        selected = channels["code"] + channels["ai"]
        channel = "both"
    else:
        # Visible news flow is always CODE in automatic mode.
        # Preserve previous AI issues in Neon without displaying them as
        # substitute "article facts" when verified articles are unavailable.
        selected = channels["code"]
        channel = "code" if selected else "unavailable"
    result["issue_channels"] = channels
    result["issue_mode"] = mode
    result["_issue_display_channel"] = channel
    result["issue_briefs"] = selected[:6] if mode == "both" else selected[:3]

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
