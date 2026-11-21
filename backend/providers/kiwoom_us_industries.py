"""Read-only Kiwoom US industry map and per-industry stock rankings.

Uses only official Kiwoom TRs:
- usa10101: official US industry-code list
- usa23000: period returns by industry
- usa23100: top/bottom stocks within an industry
- usa20540: trading-value ranking within an industry
- usa20550: market-cap ranking within an industry

No Naver/Yahoo classification, no database writes, and no account/order APIs.
"""
import datetime as dt
import math
import re
import threading
import time

import requests

from backend.providers.kiwoom_us_quotes import (
    KiwoomReadOnlyError,
    issue_access_token,
)

API_ORIGIN = "https://api.kiwoom.com"
API_PATHS = {
    "usa10101": "/api/us/stkinfo",
    "usa10104": "/api/us/stkinfo",
    "usa20100": "/api/us/mrkcond",
    "usa23000": "/api/us/sect",
    "usa23100": "/api/us/sect",
    "usa20540": "/api/us/rkinfo",
    "usa20550": "/api/us/rkinfo",
    "usa20551": "/api/us/rkinfo",
}
EXCHANGES = {"NA", "ND", "NY"}
EXCHANGE_CODES = {"1": "NY", "2": "ND", "3": "NA"}
ETF_TICKERS = frozenset({"XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP",
                         "XLE", "XLU", "XLRE", "XLB", "SOXX", "XBI", "IBIT"})
BITCOIN_COMPANIES = ("COIN", "MSTR", "MARA", "RIOT", "CLSK")

# Eleven display groups based on official Kiwoom industry codes. The labels
# match the sidebar heatmap; unmapped official codes remain unclassified.
INDUSTRY_GROUPS = (
    ("utilities", "유틸리티", ("유틸리티", "공익사업", "전기", "가스", "utilities", "electric utilities", "gas utilities", "water utilities")),
    ("real_estate", "부동산", ("부동산", "리츠", "real estate", "reit")),
    ("materials", "소재", ("소재", "화학", "건축자재", "금속", "광업", "materials", "chemicals", "construction materials", "metals", "mining")),
    ("biotech", "바이오", ("바이오", "biotechnology", "biotech")),
    ("energy", "에너지", ("에너지", "energy", "oil & gas", "oil and gas", "renewable energy", "energy equipment", "energy services")),
    ("finance", "금융", ("금융", "financials", "financial", "banks", "banking", "insurance", "capital markets", "consumer finance", "diversified financials", "financial services")),
    ("consumer_staples", "필수소비재", ("필수소비재", "consumer staples", "consumer defensive", "food products", "beverages", "household products", "personal products", "food retail", "food & staples retail", "tobacco")),
    ("industrials", "산업재", ("산업재", "industrials", "industrial", "aerospace defense", "aerospace & defense", "construction", "machinery", "transportation", "commercial services", "electrical equipment", "building products", "professional services", "trading companies")),
    ("internet_platforms", "인터넷플랫폼", ("인터넷플랫폼", "인터넷 플랫폼", "internet platforms", "internet platform", "internet software", "interactive media", "internet retail", "e-commerce", "ecommerce", "online marketplaces", "internet services")),
    ("software", "소프트웨어", ("소프트웨어", "software", "application software", "systems software", "it services", "information technology services")),
    ("communication", "커뮤니케이션", ("커뮤니케이션", "communication services", "telecommunications", "telecommunication services", "wireless telecommunication", "media", "entertainment", "broadcasting", "cable services", "telecom")),
    ("healthcare", "헬스케어", ("헬스케어", "healthcare", "health care", "biotechnology", "biotech", "pharmaceutical", "pharma", "medical devices", "medical equipment", "health care providers", "health care services", "life sciences tools")),
    ("consumer_discretionary", "경기소비재", ("경기소비재", "consumer discretionary", "consumer cyclical", "automobiles", "auto manufacturers", "auto components", "retail", "apparel", "restaurants", "hotels", "leisure", "consumer durables", "specialty retail", "household durables")),
    ("it_hardware", "IT하드웨어", ("it hardware", "technology hardware", "hardware", "storage & peripherals", "computers", "electronic equipment", "communications equipment", "technology equipment", "computer hardware", "electronic components")),
    ("semiconductors", "반도체", ("반도체", "semiconductors", "semiconductor", "semiconductor equipment", "chip equipment", "integrated circuits")),
)

LEGACY_INDUSTRY_GROUPS = (
    ("semiconductors", "반도체", ("반도체", "semiconductors", "semiconductor")),
    ("ai_datacenter", "AI 데이터센터", ("ai data center", "data center", "datacenter", "데이터센터")),
    ("software", "소프트웨어", ("소프트웨어", "software")),
    ("internet_platforms", "인터넷플랫폼", ("인터넷플랫폼", "인터넷 플랫폼", "internet platforms", "internet platform", "internet software", "interactive media", "e-commerce")),
    ("finance", "금융", ("금융", "finance", "financial", "financials", "bank", "banks", "capital markets", "insurance")),
    ("biotech_pharma", "바이오·제약", ("바이오", "제약", "biotech", "biotechnology", "pharma", "pharmaceutical", "drug manufacturers")),
    ("healthcare", "헬스케어", ("헬스케어", "healthcare", "health care", "medical devices", "medical equipment", "health care equipment", "health care services", "health care providers")),
    ("ev", "자동차·전기차", ("전기차", "electric vehicle", "electric vehicles", "automobile", "automobiles", "auto components", "auto manufacturers")),
    ("defense", "방산·항공우주", ("방산", "항공우주", "aerospace defense", "aerospace", "defense", "defence")),
)

# Codes observed in Kiwoom's US industry list. Mixed retail, materials, real
# estate and utilities stay outside the requested heatmap groups.
_HEATMAP_OFFICIAL_CODES = {
    "energy": ("10",),
    "finance": ("610", "620", "640"),
    "consumer_staples": ("410", "420", "430"),
    "industrials": ("210", "220", "230", "240", "250", "260", "270", "280", "290"),
    "software": ("720",),
    "communication": ("370", "810", "820"),
    "healthcare": ("510", "520", "530"),
    "consumer_discretionary": ("310", "320", "330", "340", "350", "360"),
    "it_hardware": ("730", "740"),
    "semiconductors": ("710",),
}
_HEATMAP_GROUP_BY_CODE = {
    code: group for group, codes in _HEATMAP_OFFICIAL_CODES.items() for code in codes
}
_OUTSIDE_HEATMAP_CODES = {"380"}



def _normalize_name(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())


def _group_for_official_industry(*names, groups=INDUSTRY_GROUPS):
    normalized_names = [_normalize_name(value) for value in names if value]
    candidates = []
    for key, _label, aliases in groups:
        for alias in aliases:
            normalized_alias = _normalize_name(alias)
            if normalized_alias and any(normalized_alias in value for value in normalized_names):
                candidates.append((len(normalized_alias), key))
    if not candidates:
        return None
    longest = max(length for length, _key in candidates)
    winners = {key for length, key in candidates if length == longest}
    return next(iter(winners)) if len(winners) == 1 else None


_TOKEN_LOCK = threading.Lock()
_ACCESS_TOKEN = None
_ACCESS_TOKEN_EXPIRES_AT = 0.0


def _access_token():
    """Reuse the existing Kiwoom credential file; cache only in process memory."""
    global _ACCESS_TOKEN, _ACCESS_TOKEN_EXPIRES_AT
    now = time.monotonic()
    with _TOKEN_LOCK:
        if _ACCESS_TOKEN and now < _ACCESS_TOKEN_EXPIRES_AT:
            return _ACCESS_TOKEN
        token = issue_access_token()
        _ACCESS_TOKEN = token
        # Kiwoom access tokens are valid for 24 hours; renew conservatively.
        _ACCESS_TOKEN_EXPIRES_AT = now + 23 * 60 * 60
        return token


_API_RATE_LOCK = threading.Lock()
_LAST_API_CALL_AT = 0.0
_MIN_API_CALL_INTERVAL = 0.22  # Stay below Kiwoom's 5 read-TR/sec limit.


_CALL_MAX_ATTEMPTS = 3  # First try + 2 retries; Kiwoom TR rejections are often transient.
_CALL_RETRY_BACKOFF = 0.4  # Seconds added per extra attempt, on top of the rate-limit wait.


def _call(api_id, body, *, token=None, continuation=None):
    last_error = None
    for attempt in range(_CALL_MAX_ATTEMPTS):
        if attempt:
            time.sleep(_CALL_RETRY_BACKOFF * attempt)
        try:
            if continuation is None:
                return _call_once(api_id, body, token=token)
            return _call_once(api_id, body, token=token, continuation=continuation)
        except KiwoomReadOnlyError as exc:
            last_error = exc
    raise last_error


def _call_once(api_id, body, *, token=None, continuation=None):
    global _LAST_API_CALL_AT
    path = API_PATHS.get(api_id)
    if not path or not isinstance(body, dict):
        raise KiwoomReadOnlyError("kiwoom_industry_api_not_allowed")
    access_token = token or _access_token()
    with _API_RATE_LOCK:
        now = time.monotonic()
        wait = _MIN_API_CALL_INTERVAL - (now - _LAST_API_CALL_AT)
        if wait > 0:
            time.sleep(wait)
        _LAST_API_CALL_AT = time.monotonic()
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": "Bearer " + access_token,
        "api-id": api_id,
    }
    if continuation is not None:
        headers["cont-yn"] = "Y"
        headers["next-key"] = continuation
    try:
        response = requests.post(
            API_ORIGIN + path,
            json=body,
            headers=headers,
            timeout=8,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise KiwoomReadOnlyError("kiwoom_industry_request_failed") from None
    if response.status_code != 200:
        raise KiwoomReadOnlyError("kiwoom_industry_http_" + str(int(response.status_code)))
    try:
        data = response.json()
    except ValueError:
        raise KiwoomReadOnlyError("kiwoom_industry_response_invalid") from None
    if not isinstance(data, dict):
        raise KiwoomReadOnlyError("kiwoom_industry_response_invalid")
    code = str(data.get("return_code", 0))
    if code not in ("0", "0000"):
        safe_code = code if re.fullmatch(r"-?[0-9]{1,6}", code) else "unknown"
        raise KiwoomReadOnlyError("kiwoom_industry_rejected_code_" + safe_code)
    if api_id == "usa10104":
        data = {**data, "_cont_yn": response.headers.get("cont-yn", ""),
                "_next_key": response.headers.get("next-key", "")}
    return data


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(str(value).strip().replace(",", "").replace("+", "").replace("%", ""))
        return result if math.isfinite(result) and abs(result) < 1e16 else None
    except (TypeError, ValueError):
        return None


def _positive_price(value):
    number = _number(value)
    return abs(number) if number not in (None, 0) else None


def _industry_code(value):
    code = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", code):
        raise ValueError("invalid_industry_code")
    return code


def fetch_us_industry_map(*, token=None):
    """Preserve the existing industry classification for current callers."""
    return fetch_us_industry_maps(token=token)["legacy"]


def fetch_us_industry_maps(*, token=None):
    """Build both classifications from the same pair of Kiwoom responses."""
    access_token = token or _access_token()
    official = _call("usa10101", {"gubun": "1"}, token=access_token).get("list")
    performance = _call(
        "usa23000", {"stex_tp": "0", "inds_cd": "0"}, token=access_token
    ).get("result_list")
    if not isinstance(official, list) or not isinstance(performance, list):
        raise KiwoomReadOnlyError("kiwoom_industry_records_missing")

    return {
        "legacy": _build_us_industry_map(official, performance, LEGACY_INDUSTRY_GROUPS),
        "heatmap": _build_us_industry_map(official, performance, INDUSTRY_GROUPS),
    }


def _build_us_industry_map(official, performance, groups):
    is_heatmap = groups is INDUSTRY_GROUPS
    matched = {key: [] for key, _label, _aliases in groups}
    unmatched = []
    for row in official:
        if not isinstance(row, dict):
            continue
        code = str(row.get("inds_cd") or "").strip()
        name = str(row.get("inds_nm") or "").strip()
        english = str(row.get("inds_enm") or "").strip()
        if not code or not name:
            continue
        if is_heatmap and code in {"110", "120", "130", "140", "630", "910", "920", "930"}:
            # Validate the label from usa10101 instead of guessing from the code.
            expected = ("materials" if code in {"110", "120", "130", "140"}
                        else "real_estate" if code == "630" else "utilities")
            matched_name = _group_for_official_industry(name, english, groups=groups)
            group = expected if matched_name == expected else None
        elif is_heatmap and code in {"510", "520", "530"} and any(
                term in _normalize_name(name + " " + english)
                for term in ("바이오", "biotech", "biotechnology")):
            group = "biotech"
        elif is_heatmap and code in _OUTSIDE_HEATMAP_CODES:
            group = None
        elif is_heatmap and code in _HEATMAP_GROUP_BY_CODE:
            group = _HEATMAP_GROUP_BY_CODE[code]
        else:
            group = _group_for_official_industry(name, english, groups=groups)
        if group:
            matched[group].append({
                "code": code,
                "official_name": name,
                "official_english_name": english,
            })
        else:
            unmatched.append({"code": code, "name": name, "english_name": english})

    perf_by_code = {}
    for row in performance:
        if not isinstance(row, dict):
            continue
        code = str(row.get("inds_cd") or "").strip()
        if code:
            perf_by_code[code] = row

    items = []
    for key, label, _aliases in groups:
        matches = matched[key]
        codes = list(dict.fromkeys(match["code"] for match in matches))
        perf_rows = [perf_by_code[code] for code in codes if code in perf_by_code]
        def average(field):
            values = [_number(row.get(field)) for row in perf_rows]
            values = [value for value in values if value is not None]
            return sum(values) / len(values) if values else None
        items.append({
            "key": key,
            "name": label,
            "code": codes[0] if len(codes) == 1 else None,
            "codes": codes,
            "official_name": " · ".join(match["official_name"] for match in matches) or None,
            "official_english_name": " · ".join(match["official_english_name"] for match in matches if match["official_english_name"]) or None,
            "change_pct": average("perf_1d"),
            "perf_5d": average("perf_5d"),
            "perf_1m": average("perf_1m"),
            "change_method": (
                "official_industry_return" if len(codes) == 1 else
                "equal_weighted_official_industry_returns" if len(codes) > 1 else None
            ),
            "mapping_status": (
                "matched" if codes and len(perf_rows) == len(codes)
                and (not is_heatmap or all(_number(row.get("perf_1d")) is not None for row in perf_rows)) else
                "performance_missing" if codes else
                "unmatched"
            ),
        })

    items = rank_us_industry_rows(items)

    complete = all(item["mapping_status"] == "matched" for item in items)
    return {
        "ok": True,
        "source": "kiwoom:usa10101+usa23000",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mapping_complete": complete,
        "mapping_ambiguous": [],
        "unmatched_official_industries": unmatched[:60],
        "items": items,
    }


def rank_us_industry_rows(items):
    ranked = sorted(
        items,
        key=lambda item: (
            item["change_pct"] is not None,
            item["change_pct"] if item["change_pct"] is not None else float("-inf"),
        ),
        reverse=True,
    )
    return [{**item, "rank": rank} for rank, item in enumerate(ranked, 1)]


def _industry_codes(value):
    values = value if isinstance(value, (list, tuple)) else [value]
    codes = list(dict.fromkeys(_industry_code(item) for item in values if str(item or "").strip()))
    if not codes or len(codes) > 20:
        raise ValueError("invalid_industry_codes")
    return codes


def _rank_number(value):
    number = _number(value)
    return int(number) if number is not None and number >= 0 else None


def fetch_us_industry_stocks(industry_codes, sort="marketcap", *, token=None, limit=36, symbols=None):
    """Fetch official industry stocks, optionally filtering bare tickers before ranking."""
    codes = _industry_codes(industry_codes)
    if sort not in ("change", "value", "marketcap"):
        raise ValueError("invalid_industry_sort")
    if type(limit) is not int or not 1 <= limit <= 36:
        raise ValueError("invalid_industry_limit")
    access_token = token or _access_token()

    api_id = {
        "change": "usa23100",
        "value": "usa20540",
        "marketcap": "usa20550",
    }[sort]
    rows_by_symbol = {}
    for code in codes:
        if sort == "change":
            body = {"stex_tp": "0", "sort_tp": "1", "inds_cd": code}
        else:
            body = {
                "stex_tp": "0",
                "inds_cd": code,
                "stk_tp": "1",
                "trde_qty_tp": "0",
                "stk_cnd": "0",
                "pric_cnd": "0",
                "trde_prica_cnd": "0",
            }
        records = _call(api_id, body, token=access_token).get("result_list")
        if not isinstance(records, list):
            raise KiwoomReadOnlyError("kiwoom_industry_stock_records_missing")

        for record in records:
            if not isinstance(record, dict):
                continue
            symbol = str(record.get("stk_cd") or "").strip().upper()
            if not re.fullmatch(r"[A-Z0-9.-]{1,20}", symbol):
                continue
            if symbols is not None and symbol.removesuffix(".O") not in symbols:
                continue
            exchange_raw = str(record.get("stex_tp") or "").strip().upper()
            exchange = EXCHANGE_CODES.get(exchange_raw, exchange_raw)
            if exchange not in EXCHANGES:
                continue
            korean_name = str(record.get("stk_nm") or "").strip()
            name = korean_name or (str(record.get("stk_enm") or "").strip() if sort != "marketcap" else "")
            if not name or len(name) > 100:
                continue

            price = _positive_price(record.get("cur_prc"))
            change_pct = _number(record.get("flu_rt"))
            volume = _number(record.get("acc_trde_qty"))
            raw_value = _number(record.get("trde_prica"))
            trading_value = raw_value * 1000 if raw_value is not None and raw_value >= 0 else None
            raw_market_cap = _number(record.get("mac"))
            market_cap_usd = raw_market_cap * 1000 if raw_market_cap is not None and raw_market_cap >= 0 else None
            if sort == "marketcap" and (market_cap_usd is None or market_cap_usd <= 0):
                continue
            source_rank = _rank_number(record.get("rank"))
            row = {
                "symbol": symbol,
                "name": name,
                "english_name": str(record.get("stk_enm") or "").strip()[:100],
                "exchange": exchange,
                "price": price,
                "change_pct": change_pct,
                "volume": volume if volume is not None and volume >= 0 else None,
                "trading_value": trading_value,
                "market_cap_usd": market_cap_usd,
                "source_rank": source_rank,
            }
            current = rows_by_symbol.get(symbol)
            if current is None:
                rows_by_symbol[symbol] = row
            elif market_cap_usd is not None and (
                current.get("market_cap_usd") is None or market_cap_usd > current["market_cap_usd"]
            ):
                rows_by_symbol[symbol] = row

    rows = list(rows_by_symbol.values())
    if sort == "change":
        rows.sort(key=lambda row: row["change_pct"] if row["change_pct"] is not None else float("-inf"), reverse=True)
    elif sort == "value":
        rows.sort(key=lambda row: row["trading_value"] if row["trading_value"] is not None else float("-inf"), reverse=True)
    else:
        rows.sort(
            key=lambda row: (
                row["market_cap_usd"] is not None,
                row["market_cap_usd"] if row["market_cap_usd"] is not None else float("-inf"),
                -(row["source_rank"] or 10**9),
            ),
            reverse=True,
        )
    rows = rows[:limit]
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank

    return {
        "ok": True,
        "source": "kiwoom:" + api_id,
        "industry_code": codes[0] if len(codes) == 1 else None,
        "industry_codes": codes,
        "sort": sort,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": rows,
    }


def fetch_us_internet_platform_group():
    """Average the three approved issuers using Kiwoom market-cap ranking data."""
    # In Kiwoom's catalog 370 is Media. Only the approved issuers count
    # toward this representative group, and Alphabet counts once.
    aliases_by_issuer = (("GOOG", "GOOGL"), ("META",), ("NFLX",))
    allowed_symbols = {symbol for aliases in aliases_by_issuer for symbol in aliases}
    ranking = fetch_us_industry_stocks("370", "marketcap", symbols=allowed_symbols)
    by_symbol = {}
    for row in ranking["items"]:
        symbol = row["symbol"].removesuffix(".O")
        if row["exchange"] == "ND" and row["change_pct"] is not None:
            by_symbol.setdefault(symbol, {**row, "symbol": symbol})

    members = []
    for aliases in aliases_by_issuer:
        representative = next((by_symbol[symbol] for symbol in aliases if symbol in by_symbol), None)
        if representative is None:
            return None
        members.append(representative)

    leaders = sorted(members, key=lambda item: item["market_cap_usd"], reverse=True)
    return {
        "display_name": "인터넷플랫폼 대표 종목군",
        "description": "알파벳·메타·넷플릭스 3개 기업의 등락률 평균",
        "change_pct": math.fsum(member["change_pct"] for member in members) / len(members),
        "change_method": "equal_weighted_representative_company_returns",
        "mapping_status": "matched",
        "source": ranking["source"],
        "fetched_at": ranking["fetched_at"],
        "member_symbols": [member["symbol"] for member in members],
        "stocks": [{**row, "rank": rank} for rank, row in enumerate(leaders, 1)],
    }


def fetch_us_etf_marketcap(*, token=None, limit=20):
    """Fetch the US ETF market-cap ranking from Kiwoom's official ETF ranking TR."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("invalid_etf_limit")
    access_token = token or _access_token()
    body = {
        "stex_tp": "0",
        "etf_cat1": "",
        "etf_cat2": "",
        "trde_qty_tp": "0",
        "stk_cnd": "0",
        "pric_cnd": "0",
        "trde_prica_cnd": "0",
    }
    records = _call("usa20551", body, token=access_token).get("result_list")
    if not isinstance(records, list):
        raise KiwoomReadOnlyError("kiwoom_etf_records_missing")

    rows = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        symbol = str(record.get("stk_cd") or "").strip().upper()
        name = str(record.get("stk_nm") or "").strip()
        exchange_raw = str(record.get("stex_tp") or "").strip().upper()
        exchange = EXCHANGE_CODES.get(exchange_raw, exchange_raw)
        if not re.fullmatch(r"[A-Z0-9.-]{1,20}", symbol) or symbol in seen:
            continue
        if exchange not in EXCHANGES or not name or len(name) > 100:
            continue
        raw_market_cap = _number(record.get("mac"))
        market_cap_usd = raw_market_cap * 1000 if raw_market_cap is not None and raw_market_cap >= 0 else None
        price = _positive_price(record.get("cur_prc"))
        change_pct = _number(record.get("flu_rt"))
        rows.append({
            "symbol": symbol,
            "name": name,
            "english_name": str(record.get("stk_enm") or "").strip()[:100],
            "exchange": exchange,
            "price": price,
            "change_pct": change_pct,
            "market_cap_usd": market_cap_usd,
            "source_rank": _rank_number(record.get("rank")),
        })
        seen.add(symbol)

    rows.sort(
        key=lambda row: (
            row["market_cap_usd"] is not None,
            row["market_cap_usd"] if row["market_cap_usd"] is not None else float("-inf"),
            -(row["source_rank"] or 10**9),
        ),
        reverse=True,
    )
    rows = rows[:limit]
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return {
        "ok": True,
        "source": "kiwoom:usa20551",
        "sort": "marketcap",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": rows,
    }


def fetch_us_etf_exchanges(*, token=None):
    """Verify the agreed ETF ticker/exchange pairs against Kiwoom usa10104."""
    symbols = {}
    continuation = None
    for _ in range(40):
        kwargs = {"token": token}
        if continuation is not None:
            kwargs["continuation"] = continuation
        data = _call("usa10104", {"stex_tp": "%"}, **kwargs)
        records = data.get("list")
        if not isinstance(records, list):
            raise KiwoomReadOnlyError("kiwoom_etf_list_missing")
        for row in records:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("code") or "").strip().upper()
            exchange = EXCHANGE_CODES.get(str(row.get("stex_tp") or "").strip().upper(),
                                          str(row.get("stex_tp") or "").strip().upper())
            if symbol in ETF_TICKERS and exchange in EXCHANGES and str(row.get("etn") or "").strip() not in ("Y", "1"):
                symbols[symbol] = exchange
        if symbols.keys() >= ETF_TICKERS or data.get("_cont_yn") != "Y":
            break
        next_key = str(data.get("_next_key") or "")
        if not next_key or next_key == continuation:
            break
        continuation = next_key
    return symbols


def fetch_us_bitcoin_related_stocks(*, token=None):
    """Rank a bounded, explicit universe of related listed companies by cap."""
    access_token = token or _access_token()
    rows = []
    for symbol in BITCOIN_COMPANIES:
        try:
            record = _call("usa20100", {"stex_tp": "ND", "stk_cd": symbol}, token=access_token)
        except KiwoomReadOnlyError:
            continue
        exchange = str(record.get("stex_tp") or "").strip().upper()
        market_cap = _number(record.get("mac"))
        name = str(record.get("stk_nm") or record.get("stk_enm") or "").strip()
        if (str(record.get("stk_cd") or "").strip().upper() != symbol
                or exchange != "ND" or not name or market_cap is None or market_cap <= 0):
            continue
        rows.append({"symbol": symbol, "exchange": exchange, "name": name,
                     "market_cap_usd": market_cap * 1000,
                     "change_pct": _number(record.get("flu_rt")),
                     "price": _positive_price(record.get("cur_prc"))})
    rows.sort(key=lambda row: row["market_cap_usd"], reverse=True)
    return [{**row, "rank": index} for index, row in enumerate(rows[:3], 1)]
