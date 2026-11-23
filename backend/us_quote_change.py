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
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="us-close-baseline")
_CACHE = {}


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
    yahoo_symbol = symbol.replace(".", "-")
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
