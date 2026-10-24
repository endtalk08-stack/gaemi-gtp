"""QQQ's last completed daily closes for the existing compact widget.

This only reuses the website's current Yahoo daily-history provider. It does NOT
claim to be Kiwoom real-time data, create a collector, or write to the database.
"""
import datetime
import math
import threading
import time
from zoneinfo import ZoneInfo

from backend.providers.market_price import fetch_daily_price_history

_LOCK = threading.Lock()
_CACHED_UNTIL = 0.0
_CACHED_RESULT = None


def read_qqq_daily_history():
    """Return (snapshot|None); one shared fetch per TTL, even on busy weekends."""
    global _CACHED_UNTIL, _CACHED_RESULT
    now_monotonic = time.monotonic()
    if now_monotonic < _CACHED_UNTIL:
        return _CACHED_RESULT
    with _LOCK:
        now_monotonic = time.monotonic()
        if now_monotonic < _CACHED_UNTIL:
            return _CACHED_RESULT

        us_now = datetime.datetime.now(ZoneInfo("America/New_York"))
        today = us_now.date()
        # Before the regular close has settled, exclude today's incomplete bar.
        include_today = us_now.weekday() < 5 and (us_now.hour, us_now.minute) >= (16, 30)
        by_date = {}
        try:
            raw = fetch_daily_price_history("QQQ")
        except Exception:
            raw = []
        for item in raw or ():
            if not isinstance(item, dict):
                continue
            try:
                date = datetime.date.fromisoformat(str(item.get("date") or ""))
                close = float(item.get("close"))
            except (ValueError, TypeError, OverflowError):
                continue
            if (date > today or (date == today and not include_today)
                    or not math.isfinite(close) or close <= 0):
                continue
            by_date[date] = close

        entries = sorted(by_date.items())[-60:]
        if len(entries) >= 2:
            previous, latest = entries[-2][1], entries[-1][1]
            _CACHED_RESULT = {
                "ok": True,
                "symbol": "QQQ",
                "source": "yahoo-daily",
                "last_trading_date": entries[-1][0].isoformat(),
                "close": round(latest, 4),
                "change_pct": round((latest / previous - 1) * 100, 2),
                "points": [{"date": d.isoformat(), "close": round(v, 4)}
                           for d, v in entries],
            }
            _CACHED_UNTIL = now_monotonic + (21600 if us_now.weekday() >= 5 else 900)
        else:
            # Cache a failure for one minute to avoid a thundering herd.
            _CACHED_RESULT = None
            _CACHED_UNTIL = now_monotonic + 60
        return _CACHED_RESULT
