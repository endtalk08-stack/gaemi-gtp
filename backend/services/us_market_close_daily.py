"""Scheduled 07:00 KST US-market-close preparation.

Run using an external scheduler at 22:00 UTC Monday-Friday
(07:00 KST Tuesday-Saturday), optionally at 22:20/22:40 for retries.
Never run in Flask startup, /analyze, or central chat.
"""
import datetime
import json
from zoneinfo import ZoneInfo

from .us_market_close_brief import build_us_market_close_brief
from .us_market_close_news import _last_completed_session
from .us_market_close_store import (
    get_us_close_brief_for_session, is_store_configured, save_us_close_brief
)


_KST = ZoneInfo("Asia/Seoul")
_NY = ZoneInfo("America/New_York")
_REQUIRED_INDICES = {"나스닥", "S&P500", "다우"}


def run_once(*, now=None):
    """Collect only on KST Tue-Sat at 07h, skip holidays or incomplete data."""
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must have a timezone")
    local = current.astimezone(_KST)
    if not (1 <= local.weekday() <= 5 and local.hour == 7):
        return {"status": "outside_schedule"}

    if not is_store_configured():
        return {"status": "not_configured"}

    session = _last_completed_session(current)
    session_text = session.isoformat()

    # A cron retry must not collect the same news or overwrite a previous result.
    if get_us_close_brief_for_session(session):
        return {"status": "already_saved", "session_date": session_text}

    brief = build_us_market_close_brief(now=current)
    rows = brief.get("indices") or []
    valid = {
        item.get("name") for item in rows
        if item.get("date") == session_text
    }
    sources = brief.get("article_sources") or []
    if not brief.get("ok") or not _REQUIRED_INDICES.issubset(valid) or not sources:
        return {
            "status": "incomplete",
            "session_date": session_text,
            "indices": len(valid & _REQUIRED_INDICES),
            "articles": len(sources),
        }

    created = save_us_close_brief(brief)
    return {"status": "saved" if created else "already_saved", "session_date": session_text}


if __name__ == "__main__":
    outcome = run_once()
    print("[US close daily] " + json.dumps(outcome, ensure_ascii=False), flush=True)
    if outcome["status"] == "not_configured":
        raise SystemExit(1)
