"""Read-only Nasdaq chart data and 24-hour verified market-close marker.

Render only. Yahoo historical prices remain a market-data API lookup; the
existing DigitalOcean worker owns news generation, Neon owns saved tags.
No persistence, AI calls, or background collectors.
"""
import datetime as dt
import math

from backend.providers.market_price import fetch_daily_price_history
from backend.services.us_market_close import read_brief


def build_nasdaq_chart():
    """Show validated dated Nasdaq closes; attach a tag only to its matching session."""
    source_rows = fetch_daily_price_history("^IXIC")
    unique = {}
    for row in source_rows or []:
        if not isinstance(row, dict):
            continue
        date_text = row.get("date")
        try:
            day = dt.date.fromisoformat(date_text) if isinstance(date_text, str) else None
            close = float(row.get("close"))
        except (TypeError, ValueError, OverflowError):
            continue
        if day is None or not math.isfinite(close) or not 0 < close < 1000000:
            continue
        unique[day.isoformat()] = round(close, 2)
    points = [{"date": day, "close": unique[day]} for day in sorted(unique)[-60:]]
    if len(points) < 2:
        return None

    # An unavailable or expired issue should not hide verified price history.
    annotation = None
    try:
        brief = read_brief()
        candidate = (brief or {}).get("nasdaq_chart_annotation") or {}
        tags = candidate.get("tags")
        session_date = candidate.get("session_date_et")
        confirmed_close = float(candidate.get("close"))
        match = next((row for row in points if row["date"] == session_date), None)
        if (
            candidate.get("symbol") == ".IXIC" and match is not None
            and math.isfinite(confirmed_close) and confirmed_close > 0
            and abs(match["close"] - confirmed_close) / confirmed_close <= 0.005
            and isinstance(tags, list) and len(tags) == 3
            and all(isinstance(tag, str) and tag.startswith("#") and 1 < len(tag) <= 48 for tag in tags)
        ):
            annotation = {
                "session_date_et": session_date,
                "close": confirmed_close,
                "tags": tags[:],
            }
    except (TypeError, ValueError, OverflowError):
        pass
    except Exception as exc:
        print("[nasdaq chart] read-only brief unavailable: " + type(exc).__name__, flush=True)

    return {
        "symbol": ".IXIC",
        "name": "나스닥 종합",
        "source": "yahoo_daily",
        "timezone": "America/New_York",
        "points": points,
        "annotation": annotation,
    }
