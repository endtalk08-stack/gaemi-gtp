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
KR_DAILY_HISTORY_CACHE_TTL = 600
US_DAILY_HISTORY_CACHE_TTL = 15


def _get_lock(key):
    with _CACHE_LOCK_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _CACHE_LOCKS[key] = lock
        return lock


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
    """가격 지표가 공통으로 재사용하는 Yahoo 일봉 원천."""
    key = str(ticker or "").strip().upper()
    if not key:
        return []

    ttl = KR_DAILY_HISTORY_CACHE_TTL if key.endswith((".KS", ".KQ")) else US_DAILY_HISTORY_CACHE_TTL
    now = time.time()
    cached = DAILY_HISTORY_CACHE.get(key)
    if cached and now - cached[0] < ttl:
        return list(cached[1])

    with _get_lock(("daily-history", key)):
        now = time.time()
        cached = DAILY_HISTORY_CACHE.get(key)
        if cached and now - cached[0] < ttl:
            return list(cached[1])

        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(key)}?range=6mo&interval=1d"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            chart_rows = data.get("chart", {}).get("result", [])
            if not chart_rows:
                DAILY_HISTORY_CACHE[key] = (now, [])
                return []

            quote = chart_rows[0].get("indicators", {}).get("quote", [{}])[0]
            closes = quote.get("close", []) or []
            highs = quote.get("high", []) or []
            lows = quote.get("low", []) or []
            volumes = quote.get("volume", []) or []

            rows = []
            for index, close in enumerate(closes):
                if close is None:
                    continue
                try:
                    close_value = float(close)
                    if close_value <= 0:
                        continue
                    high_value = float(highs[index]) if index < len(highs) and highs[index] is not None else 0.0
                    low_value = float(lows[index]) if index < len(lows) and lows[index] is not None else 0.0
                    volume_value = float(volumes[index]) if index < len(volumes) and volumes[index] is not None else 0.0
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "close": close_value,
                    "high": high_value,
                    "low": low_value,
                    "volume": volume_value,
                })

            DAILY_HISTORY_CACHE[key] = (now, rows)
            return list(rows)
        except Exception as exc:
            print(f"야후 일봉 조회 예외 {key}: {type(exc).__name__}: {exc}")
            DAILY_HISTORY_CACHE[key] = (now, [])
            return []


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
            current = rows[-1]
            previous = rows[-2]
            result = (
                current.get("close"),
                previous.get("close"),
                current.get("high"),
                current.get("low"),
            )
        else:
            result = (None, None, None, None)

        US_QUOTE_CACHE[key] = (now, result)
        return result
