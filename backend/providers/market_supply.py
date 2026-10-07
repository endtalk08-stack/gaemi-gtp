import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


_LOCK_GUARD = threading.Lock()
_LOCKS = {}
_KR_SUPPLY_CACHE = {}
_KR_SUPPLY_CACHE_TTL = 20
_US_OPTIONS_CACHE = {}
_US_OPTIONS_CACHE_TTL = 60


def _get_lock(key):
    with _LOCK_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def fetch_kr_supply_rows(code_six):
    """네이버 수급 원천 행을 그대로 가져온다."""
    code = str(code_six or "").strip()
    now = time.time()
    cached = _KR_SUPPLY_CACHE.get(code)
    if cached and now - cached[0] < _KR_SUPPLY_CACHE_TTL:
        return list(cached[1])

    with _get_lock(("kr-supply", code)):
        now = time.time()
        cached = _KR_SUPPLY_CACHE.get(code)
        if cached and now - cached[0] < _KR_SUPPLY_CACHE_TTL:
            return list(cached[1])
        try:
            url = f"https://m.stock.naver.com/api/stock/{code}/trend?page=1&pageSize=20"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                    "Referer": "https://m.stock.naver.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            rows = data if isinstance(data, list) else []
            _KR_SUPPLY_CACHE[code] = (now, rows)
            return list(rows)
        except Exception as exc:
            print(f"[provider:kr-supply] {code} failed: {type(exc).__name__}: {exc}")
            _KR_SUPPLY_CACHE[code] = (now, [])
            return []


def fetch_us_option_rows(ticker_symbol):
    """CBOE 옵션 원천 행과 조회 오류를 반환한다."""
    key = str(ticker_symbol or "").upper().strip()
    now = time.time()
    cached = _US_OPTIONS_CACHE.get(key)
    if cached and now - cached[0] < _US_OPTIONS_CACHE_TTL:
        return list(cached[1]), cached[2]

    with _get_lock(("us-options", key)):
        now = time.time()
        cached = _US_OPTIONS_CACHE.get(key)
        if cached and now - cached[0] < _US_OPTIONS_CACHE_TTL:
            return list(cached[1]), cached[2]

        error = None
        rows = []
        try:
            url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{urllib.parse.quote(key)}.json"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("data") or []
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list):
                rows = []
        except urllib.error.HTTPError as exc:
            error = exc.code
            print(f"[provider:us-options] {key} HTTP {exc.code}")
        except Exception as exc:
            error = type(exc).__name__
            print(f"[provider:us-options] {key} failed: {type(exc).__name__}: {exc}")

        _US_OPTIONS_CACHE[key] = (now, rows, error)
        return list(rows), error
