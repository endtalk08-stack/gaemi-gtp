"""One-shot read-only NVDA premarket verification with Alpaca Market Data.

Makes ONE historical SIP bar request (at least 20 minutes delayed).
Never accesses trading endpoints, orders, portfolios, accounts, or other tickers.
No secret headers or raw errors are printed.
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SYMBOL = "NVDA"
DATA_ORIGIN = "https://data.alpaca.markets"
PRE_START = dt.time(4, 0)
PRE_END = dt.time(9, 30)


def _window(now):
    local = now.astimezone(NY)
    day = local.date()
    latest = min(
        local - dt.timedelta(minutes=20),
        dt.datetime.combine(day, dt.time(9, 29), NY),
    )
    if latest.date() < day or latest.time() <= PRE_START or day.weekday() >= 5:
        day -= dt.timedelta(days=1)
        while day.weekday() >= 5:
            day -= dt.timedelta(days=1)
        latest = dt.datetime.combine(day, dt.time(9, 29), NY)
    return day, dt.datetime.combine(day, PRE_START, NY), latest


def _valid_float(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def main():
    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        print("ALPACA_VERIFY_ERROR=credentials_missing", flush=True)
        return 2
    day, start, end = _window(dt.datetime.now(dt.timezone.utc))
    if start >= end:
        print("ALPACA_VERIFY_ERROR=invalid_window", flush=True)
        return 3
    query = urllib.parse.urlencode({
        "timeframe": "1Min",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "feed": "sip",
        "sort": "desc",
        "limit": 1,
    })
    req = urllib.request.Request(
        DATA_ORIGIN + "/v2/stocks/" + SYMBOL + "/bars?" + query,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
        },
        method="GET",
    )
    print("ALPACA_VERIFY_SCOPE=NVDA_premarket_historical_sip_one_request", flush=True)
    print("ALPACA_VERIFY_SESSION=" + day.isoformat(), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read(131072))
    except urllib.error.HTTPError as error:
        print("ALPACA_VERIFY_ERROR=http_" + str(int(error.code)), flush=True)
        return 4
    except (urllib.error.URLError, ValueError, OSError, TimeoutError):
        print("ALPACA_VERIFY_ERROR=transport_or_json", flush=True)
        return 5
    if not isinstance(data, dict) or data.get("symbol") != SYMBOL:
        print("ALPACA_VERIFY_ERROR=unexpected_response_symbol", flush=True)
        return 6
    bars = data.get("bars")
    if not isinstance(bars, list) or not bars:
        print("ALPACA_VERIFY_NO_PREMARKET_BARS", flush=True)
        return 7
    bar = bars[0]
    if not isinstance(bar, dict):
        print("ALPACA_VERIFY_ERROR=invalid_bar", flush=True)
        return 8
    price = _valid_float(bar.get("c"))
    ts = bar.get("t")
    if not isinstance(ts, str):
        print("ALPACA_VERIFY_ERROR=timestamp_missing", flush=True)
        return 8
    try:
        bar_time = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(NY)
    except ValueError:
        print("ALPACA_VERIFY_ERROR=timestamp_invalid", flush=True)
        return 8
    if (
        price is None or bar_time.date() != day
        or not PRE_START <= bar_time.time() < PRE_END
        or bar_time > end
    ):
        print("ALPACA_VERIFY_ERROR=bar_not_verified_premarket", flush=True)
        return 9
    volume = bar.get("v")
    if not isinstance(volume, int) or volume < 0:
        volume = None
    # Data is delayed SIP, not free full-market real-time.
    print("ALPACA_NVDA_PREMARKET_OK=" + json.dumps({
        "symbol": SYMBOL,
        "date_et": day.isoformat(),
        "bar_time_et": bar_time.strftime("%H:%M"),
        "price_usd": price,
        "volume": volume,
        "feed": "sip",
        "minimum_delay_minutes": 20,
        "is_live": False,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
