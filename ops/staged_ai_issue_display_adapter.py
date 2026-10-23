"""Preserve original article publication times separately from AI analysis time."""
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from staged_daily_groq_issues import parse_issues

SEOUL = ZoneInfo("Asia/Seoul")


def _published_kst(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (ValueError, TypeError, IndexError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(SEOUL)


def to_issue_briefs(issues, display_time, stock_names, sources_by_issue=None):
    validated = parse_issues(json.dumps({"issues": issues}, ensure_ascii=False))
    if not isinstance(display_time, str):
        raise ValueError("Invalid display time")
    if not isinstance(stock_names, list) or any(
        not isinstance(name, str) or not name.strip() for name in stock_names
    ):
        raise ValueError("Invalid stock names")

    result = []
    for index, issue in enumerate(validated):
        inputs = (
            sources_by_issue[index]
            if isinstance(sources_by_issue, list) and index < len(sources_by_issue)
            and isinstance(sources_by_issue[index], list) else []
        )
        sources, representative = [], None
        for item in inputs[:3]:
            if not isinstance(item, dict):
                continue
            link = str(item.get("url") or "").strip()
            source = {
                "title": str(item.get("title") or ""),
                "published_at": str(item.get("published_at") or ""),
                "source": str(item.get("source") or ""),
                "url": link if link.startswith(("https://", "http://")) else "",
            }
            sources.append(source)
            if representative is None:
                published = _published_kst(source["published_at"])
                if published is not None:
                    representative = (published, source["source"])
        if representative:
            published, publisher = representative
            # Only the original short time belongs in the existing issue UI.
            # Source publication/AI-run metadata stays in its original fields.
            time_text = published.strftime("%H:%M")
            # Publisher names and citation links are stored for future UI,
            # but must not be displayed until explicitly enabled.
        else:
            time_text = ""  # Never substitute AI execution time for article time.
        result.append({
            "time": time_text,
            "reaction_at": "",
            "headline": issue["headline"],
            "summary": issue["summary"],
            "tags": [str(tag).lstrip("#") for tag in issue["tags"]],
            "stock_names": stock_names[:4],
            "source_articles": sources,
        })
    return result
