"""External stock identifier lookup provider."""

import json
import threading
import time
import urllib.parse
import urllib.request


KR_SEARCH_CACHE = {}
KR_SEARCH_CACHE_TTL = 3600
_KR_SEARCH_LOCKS = {}
_KR_SEARCH_LOCK_GUARD = threading.Lock()


def _get_singleflight_lock(key):
    with _KR_SEARCH_LOCK_GUARD:
        lock = _KR_SEARCH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _KR_SEARCH_LOCKS[key] = lock
        return lock


def search_krx_code(stock_name):
    key = str(stock_name or "").strip()
    if not key:
        return None, None

    now = time.time()
    cached = KR_SEARCH_CACHE.get(key)
    if cached and now - cached[0] < KR_SEARCH_CACHE_TTL:
        return cached[1], cached[2]

    lock = _get_singleflight_lock(("kr-search", key))
    with lock:
        now = time.time()
        cached = KR_SEARCH_CACHE.get(key)
        if cached and now - cached[0] < KR_SEARCH_CACHE_TTL:
            return cached[1], cached[2]
        try:
            url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(key)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                items = res_json.get("items", [])
                if items and len(items[0]) > 0:
                    first = items[0][0]
                    code = first[0]
                    market = first[3].upper()
                    suffix = ".KS" if "KOSPI" in market else ".KQ"
                    value = (f"{code}{suffix}", code)
                    KR_SEARCH_CACHE[key] = (now, value[0], value[1])
                    return value
        except Exception:
            pass

    # 실패 결과는 장시간 캐시하지 않는다. 외부 자동검색이 잠깐 실패해도 다음 조회에서 재시도한다.
    return None, None
