"""Validated regular-close change for the shared US live quote feed."""
import datetime as dt
import json
import math
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="us-close-baseline")
_CACHE = {}
_OFFICIAL_CACHE = {}


def _target(now):
    local = now.astimezone(_NY)
    day = local.date()
    # After the regular close, do not substitute yesterday's close while
    # today's official record is still being published.
    if local.weekday() < 5 and local.time() >= dt.time(16):
        return day, True
    return day - dt.timedelta(days=1), False


def _lookup(symbol, exchange, target, exact):
    """Read raw (unadjusted) daily close, never Kiwoom's mismatched daily field.

    Yahoo chart is already used by the project for US price history. The
    2026-11-20 QQQ and NVDA closes matched independent historical records.
    """
    yahoo_symbol = {"BRKB": "BRK-B", "BRKA": "BRK-A"}.get(symbol, symbol.replace(".", "-"))
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(yahoo_symbol, safe="") + "?range=10d&interval=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.load(response)
        if payload.get("chart", {}).get("error") is not None:
            return None
        results = payload.get("chart", {}).get("result")
        if not isinstance(results, list) or len(results) != 1:
            return None
        data = results[0]
        meta = data.get("meta", {})
        if (meta.get("symbol") != yahoo_symbol or meta.get("currency") != "USD"
                or meta.get("exchangeTimezoneName") != "America/New_York"):
            return None
        timestamps = data.get("timestamp")
        closes = data.get("indicators", {}).get("quote", [{}])[0].get("close")
        if not isinstance(timestamps, list) or not isinstance(closes, list) or len(timestamps) != len(closes):
            return None
        candidates = []
        for timestamp, close in zip(timestamps, closes):
            if type(timestamp) not in (int, float) or type(close) not in (int, float):
                continue
            day = dt.datetime.fromtimestamp(timestamp, _NY).date()
            if (target - dt.timedelta(days=7) <= day <= target and
                    day.weekday() < 5 and math.isfinite(close) and 0 < close < 10000000):
                candidates.append((day, close))
        if not candidates:
            return None
        day, close = max(candidates)
        if exact and day != target:
            return None
        return float(close), day.isoformat()
    except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError):
        return None


def _verified_baseline(symbol, exchange, target, exact):
    baseline = _lookup(symbol, exchange, target, exact)
    if baseline is not None or not exact:
        return baseline
    # The dated regular-session record can be available before the daily
    # chart updates. Never use usa20100's undated previous-close field.
    from backend.providers.kiwoom_us_quotes import fetch_us_close
    try:
        record = fetch_us_close(symbol, exchange, target)
        price = record.get("close") if record else None
        if (record and record.get("session_date") == target.isoformat()
                and type(price) in (int, float) and math.isfinite(price)
                and 0 < price < 10000000):
            return float(price), target.isoformat()
    except (OSError, RuntimeError, ValueError, TypeError):
        pass
    return None


def validated_change(symbol, exchange, price, *, now=None):
    """Return (percent, close date), or (None, None) until verified.

    One pending read per symbol/session; failures retry after five minutes.
    Prices continue streaming while the read-only baseline is unavailable.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(_NY)
    # Daily candles can still be partial immediately after the closing bell.
    if local.weekday() < 5 and dt.time(16) <= local.time() < dt.time(16, 30):
        return None, None
    target, exact = _target(now)
    key = (symbol, exchange, target, exact)
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            entry = {"future": _POOL.submit(_verified_baseline, symbol, exchange, target, exact), "retry": 0}
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
                entry["retry"] = time.monotonic() + (10 if exact else 300)
                entry["future"] = _POOL.submit(_verified_baseline, symbol, exchange, target, exact)
            return None, None
    close, date = baseline
    return (price / close - 1) * 100, date


def _read_official_close(symbol, exchange, day):
    """Get a dated regular close and independently verified preceding close."""
    from backend.providers.kiwoom_us_quotes import fetch_us_close

    try:
        record = fetch_us_close(symbol, exchange, day)
        if not record or record.get("session_date") != day.isoformat():
            return None
        price = record.get("close")
        if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
            return None
        previous = _lookup(symbol, exchange, day - dt.timedelta(days=1), False)
        if not previous or previous[1] >= day.isoformat():
            return None
        return (float(price), (price / previous[0] - 1) * 100, previous[1])
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        return None


def official_close_quote(symbol, exchange, *, now=None):
    """Return only the confirmed regular close during the 16:00–16:30 ET hold."""
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(_NY)
    if (local.weekday() >= 5 or
            not dt.time(16) <= local.time() < dt.time(16, 30)):
        return None
    day = local.date()
    key = (symbol, exchange, day)
    with _LOCK:
        entry = _OFFICIAL_CACHE.get(key)
        if entry is None:
            entry = {"future": _POOL.submit(_read_official_close, symbol, exchange, day), "retry": 0}
            _OFFICIAL_CACHE[key] = entry
            if len(_OFFICIAL_CACHE) > 250:
                for old in list(_OFFICIAL_CACHE)[:100]:
                    if old != key:
                        _OFFICIAL_CACHE.pop(old, None)
        future = entry["future"]
        if not future.done():
            return None
        result = future.result()
        if result is None:
            if time.monotonic() >= entry["retry"]:
                entry["retry"] = time.monotonic() + 30
                entry["future"] = _POOL.submit(_read_official_close, symbol, exchange, day)
            return None
    price, change, close_date = result
    return {"symbol": symbol, "exchange": exchange, "price": price,
            "change_pct": change, "reference_close_date": close_date,
            "reference_close_session": close_date,
            "received_at_ms": int(now.timestamp() * 1000),
            "stale": False, "source": "kiwoom:regular-close",
            "market_session": "regular_close"}
