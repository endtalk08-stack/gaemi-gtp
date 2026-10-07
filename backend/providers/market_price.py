import json
import threading
import time
import urllib.parse
import urllib.request


_CACHE_LOCK_GUARD = threading.Lock()
_CACHE_LOCKS = {}
KR_QUOTE_CACHE = {}
KR_QUOTE_CACHE_TTL = 5
US_QUOTE_CACHE = {}
US_QUOTE_CACHE_TTL = 15
DAILY_HISTORY_CACHE = {}


def _get_lock(key):
    with _CACHE_LOCK_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _CACHE_LOCKS[key] = lock
        return lock


def _history_ttl(ticker):
    symbol = str(ticker or "").upper()
    return 600 if symbol.endswith((".KS", ".KQ")) else 15


def fetch_kr_stock_quote(code_six):
    code_six = str(code_six or "").strip()
    now = time.time()
    cached = KR_QUOTE_CACHE.get(code_six)
    if cached and now - cached[0] < KR_QUOTE_CACHE_TTL:
        return cached[1]

    with _get_lock(("kr-quote", code_six)):
        now = time.time()
        cached = KR_QUOTE_CACHE.get(code_six)
        if cached and now - cached[0] < KR_QUOTE_CACHE_TTL:
            return cached[1]
        try:
            url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                    "Referer": "https://m.stock.naver.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("datas", [])
            if rows:
                item = rows[0]
                result = (
                    float(str(item.get("closePrice", 0)).replace(",", "")),
                    float(str(item.get("compareToPreviousClosePrice", 0)).replace(",", "")),
                    float(str(item.get("fluctuationsRatio", 0)).replace(",", "")),
                    float(str(item.get("highPrice", 0)).replace(",", "")),
                    float(str(item.get("lowPrice", 0)).replace(",", "")),
                )
                KR_QUOTE_CACHE[code_six] = (now, result)
                return result
        except Exception as exc:
            print("네이버 실시간 시세 조회 예외:", exc)

    result = (None, None, None, None, None)
    KR_QUOTE_CACHE[code_six] = (now, result)
    return result


def fetch_daily_price_history(ticker):
    """Yahoo 2년 일봉 원천을 공통으로 제공한다."""
    key = str(ticker or "").strip().upper()
    if not key:
        return []

    now = time.time()
    ttl = _history_ttl(key)
    cached = DAILY_HISTORY_CACHE.get(key)
    if cached and now - cached[0] < ttl:
        return cached[1]

    with _get_lock(("daily-history", key)):
        now = time.time()
        cached = DAILY_HISTORY_CACHE.get(key)
        if cached and now - cached[0] < ttl:
            return cached[1]

        rows = []
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(key)}?range=2y&interval=1d"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            chart_rows = data.get("chart", {}).get("result", [])
            if chart_rows:
                quote = chart_rows[0].get("indicators", {}).get("quote", [{}])[0]
                closes = quote.get("close", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                volumes = quote.get("volume", [])

                for close, high, low, volume in zip(closes, highs, lows, volumes):
                    if close is None or high is None or low is None:
                        continue
                    try:
                        close_value = float(close)
                        high_value = float(high)
                        low_value = float(low)
                        volume_value = float(volume or 0)
                    except (TypeError, ValueError):
                        continue
                    if close_value <= 0 or high_value <= 0 or low_value <= 0:
                        continue
                    rows.append({
                        "close": close_value,
                        "high": high_value,
                        "low": low_value,
                        "volume": volume_value,
                    })
        except Exception as exc:
            print("야후 일봉 조회 예외:", exc)

        DAILY_HISTORY_CACHE[key] = (now, rows)
        return rows


def fetch_us_stock_quote(ticker):
    key = str(ticker or "").strip().upper()
    now = time.time()
    cached = US_QUOTE_CACHE.get(key)
    if cached and now - cached[0] < US_QUOTE_CACHE_TTL:
        return cached[1]

    with _get_lock(("us-quote", key)):
        now = time.time()
        cached = US_QUOTE_CACHE.get(key)
        if cached and now - cached[0] < US_QUOTE_CACHE_TTL:
            return cached[1]

        rows = fetch_daily_price_history(key)
        if len(rows) >= 2:
            latest = rows[-1]
            previous = rows[-2]
            result = (
                latest["close"],
                previous["close"],
                latest["high"],
                latest["low"],
            )
        else:
            result = (None, None, None, None)

        US_QUOTE_CACHE[key] = (now, result)
        return result
