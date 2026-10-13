"""Shared, stock-code keyed Naver industry labels for market ranking results.

The industry source is independent of which ranking tab happens to need it.
Only the industry's verified Naver fields are used; no ticker-name inference.
"""
import concurrent.futures
import json
import re
import threading
import time
import urllib.parse
import urllib.request

INDUSTRY_CACHE = {}
_REGION_LOCKS = {"kr": threading.Lock(), "us": threading.Lock()}
_PRESENT_TTL = 12 * 60 * 60
_ABSENT_TTL = 5 * 60
_FAILURE_TTL = 30
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://stock.naver.com/",
    "Accept": "application/json",
}


def _valid_code(market, code):
    pattern = r"[A-Z0-9]{6}" if market == "kr" else r"[A-Z0-9._^-]{1,32}"
    return bool(re.fullmatch(pattern, code))


def _label(payload):
    if not isinstance(payload, dict):
        return None
    for field in ("industryName", "sectorName"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _naver_json(path, params=None):
    url = "https://stock.naver.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=4) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("unexpected Naver industry payload")
    return payload


def _kr_industry(code):
    # Verified 2026-10-13: Samsung Electronics profile returns industryName.
    try:
        data = _naver_json(f"/api/stockSecurity/items/v2/domestic/{code}/profile")
        if data.get("itemCode") not in (None, code):
            raise ValueError("industry profile code mismatch")
        return _label(data), False
    except Exception as exc:
        print(f"[네이버 업종] 국내 {code} 조회 실패: {type(exc).__name__}", flush=True)
        return None, True


def _us_industries(codes):
    # Verified 2026-10-13: repeated itemCodes return a code-keyed object;
    # each item's sectorName is the industry label.
    try:
        data = _naver_json(
            "/api/stockSecurity/items/v1/foreign/prices",
            [("itemCodes", code) for code in codes],
        )
        return {code: (_label(data.get(code)), False) for code in codes}
    except Exception as exc:
        print(f"[네이버 업종] 미국 묶음 조회 실패: {type(exc).__name__}", flush=True)
        return {code: (None, True) for code in codes}


def get_stock_industries(market, codes, known=None):
    """Return one cached industry map shared by popular and trading-value menus.

    Known labels from a ranking payload seed the same map. For unknown KR
    symbols, look up one profile per stock code, with a bounded worker pool.
    For US symbols, make one Naver batch request per uncached set. Missing
    labels never become fabricated industry names.
    """
    if market not in _REGION_LOCKS:
        return {}
    ordered = []
    for value in codes:
        code = str(value or "").strip().upper()
        if _valid_code(market, code) and code not in ordered:
            ordered.append(code)
    if not ordered:
        return {}

    # Lock per country guarantees one-flight industry collection, even when
    # different ranking menus are opened concurrently.
    with _REGION_LOCKS[market]:
        now = time.monotonic()
        for symbol, label in (known or {}).items():
            code = str(symbol or "").strip().upper()
            if _valid_code(market, code) and isinstance(label, str) and label.strip():
                INDUSTRY_CACHE[(market, code)] = (now, label.strip(), _PRESENT_TTL)

        result = {}
        missing = []
        for code in ordered:
            cached = INDUSTRY_CACHE.get((market, code))
            if cached and now - cached[0] < cached[2]:
                if cached[1]:
                    result[code] = cached[1]
            else:
                missing.append(code)
        if not missing:
            return result

        if market == "kr":
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(missing))) as pool:
                fetched = dict(zip(missing, pool.map(_kr_industry, missing)))
        else:
            fetched = _us_industries(missing)

        timestamp = time.monotonic()
        for code in missing:
            label, failed = fetched.get(code, (None, True))
            ttl = _FAILURE_TTL if failed else _PRESENT_TTL if label else _ABSENT_TTL
            INDUSTRY_CACHE[(market, code)] = (timestamp, label, ttl)
            if label:
                result[code] = label
        return result
