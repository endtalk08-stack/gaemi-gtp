"""Validated regular-close change for the shared US live quote feed."""
import datetime as dt
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_quotes import fetch_us_close

_NY = ZoneInfo("America/New_York")
_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="us-close-baseline")
_CACHE = {}
# Dated Kiwoom QQQ close disagreed with independently verified regular close.
REGULAR_CLOSE_VERIFIED = False


def _target(now):
    local = now.astimezone(_NY)
    day = local.date()
    # After the regular close, do not substitute yesterday's close while
    # today's official record is still being published.
    if local.weekday() < 5 and local.time() >= dt.time(16):
        return day, True
    return day - dt.timedelta(days=1), False


def _lookup(symbol, exchange, target, exact):
    for offset in range(8):
        day = target - dt.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        try:
            result = fetch_us_close(symbol, exchange, day)
        except Exception:
            return None
        if result and result.get("session_date") == day.isoformat():
            close = result.get("close")
            if exact and day != target:
                return None
            return (float(close), day.isoformat()) if type(close) in (int, float) and close > 0 else None
        if exact:
            return None
    return None


def validated_change(symbol, exchange, price, *, now=None):
    """Return (percent, close date), or (None, None) until verified.

    One pending read per symbol/session; failures retry after five minutes.
    Prices continue streaming while the read-only baseline is unavailable.
    """
    # Suppress rates until the close source is reconciled and checked in live data.
    if not REGULAR_CLOSE_VERIFIED:
        return None, None
    now = now or dt.datetime.now(dt.timezone.utc)
    target, exact = _target(now)
    key = (symbol, exchange, target, exact)
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            entry = {"future": _POOL.submit(_lookup, symbol, exchange, target, exact), "retry": 0}
            _CACHE[key] = entry
            if len(_CACHE) > 250:
                for old in list(_CACHE)[:100]:
                    if old != key:
                        _CACHE.pop(old, None)
        future = entry["future"]
        if not future.done():
            return None, None
        baseline = future.result()
        if baseline is None:
            if time.monotonic() >= entry["retry"]:
                entry["retry"] = time.monotonic() + 300
                entry["future"] = _POOL.submit(_lookup, symbol, exchange, target, exact)
            return None, None
    close, date = baseline
    return (price / close - 1) * 100, date
