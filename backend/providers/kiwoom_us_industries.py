"""Read-only Kiwoom US industry map and per-industry stock rankings.

Uses only official Kiwoom TRs:
- usa10101: official US industry-code list
- usa23000: period returns by industry
- usa23100: top/bottom stocks within an industry
- usa20540: trading-value ranking within an industry

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
    "usa23000": "/api/us/sect",
    "usa23100": "/api/us/sect",
    "usa20540": "/api/us/rkinfo",
}
EXCHANGES = {"NA", "ND", "NY"}
EXCHANGE_CODES = {"1": "NY", "2": "ND", "3": "NA"}

# These 11 display groups are the agreed gaemiGTP heatmap labels.
# They are matched only against Kiwoom's own inds_nm / inds_enm response.
INDUSTRY_GROUPS = (
    ("energy", "에너지", ("에너지", "energy")),
    ("finance", "금융", ("금융", "finance", "financial", "financials")),
    ("consumer_staples", "필수소비재", ("필수소비재", "consumer staples", "consumer staple")),
    ("industrials", "산업재", ("산업재", "industrials", "industrial")),
    ("internet_platforms", "인터넷플랫폼", ("인터넷플랫폼", "인터넷 플랫폼", "internet platforms", "internet platform")),
    ("software", "소프트웨어", ("소프트웨어", "software")),
    ("communication", "커뮤니케이션", ("커뮤니케이션", "communication", "communications", "communication services")),
    ("healthcare", "헬스케어", ("헬스케어", "healthcare", "health care")),
    ("consumer_discretionary", "경기소비재", ("경기소비재", "consumer discretionary", "consumer cyclical")),
    ("it_hardware", "IT하드웨어", ("IT하드웨어", "IT 하드웨어", "it hardware", "technology hardware")),
    ("semiconductors", "반도체", ("반도체", "semiconductors", "semiconductor")),
)

def _normalize_name(value):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())

_ALIAS_TO_GROUP = {
    _normalize_name(alias): key
    for key, _label, aliases in INDUSTRY_GROUPS
    for alias in aliases
}

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


def _call(api_id, body, *, token=None):
    path = API_PATHS.get(api_id)
    if not path or not isinstance(body, dict):
        raise KiwoomReadOnlyError("kiwoom_industry_api_not_allowed")
    access_token = token or _access_token()
    try:
        response = requests.post(
            API_ORIGIN + path,
            json=body,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + access_token,
                "api-id": api_id,
            },
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
    """Return the 11 agreed display groups, matched to Kiwoom's official codes."""
    access_token = token or _access_token()
    official = _call("usa10101", {"gubun": "1"}, token=access_token).get("list")
    performance = _call(
        "usa23000", {"stex_tp": "0", "inds_cd": "0"}, token=access_token
    ).get("result_list")
    if not isinstance(official, list) or not isinstance(performance, list):
        raise KiwoomReadOnlyError("kiwoom_industry_records_missing")

    matched = {}
    ambiguous = set()
    unmatched = []
    for row in official:
        if not isinstance(row, dict):
            continue
        code = str(row.get("inds_cd") or "").strip()
        name = str(row.get("inds_nm") or "").strip()
        english = str(row.get("inds_enm") or "").strip()
        if not code or not name:
            continue
        group = (
            _ALIAS_TO_GROUP.get(_normalize_name(name))
            or _ALIAS_TO_GROUP.get(_normalize_name(english))
        )
        if not group:
            unmatched.append({"code": code, "name": name, "english_name": english})
            continue
        if group in matched:
            ambiguous.add(group)
        else:
            matched[group] = {
                "code": code,
                "official_name": name,
                "official_english_name": english,
            }

    perf_by_code = {}
    for row in performance:
        if not isinstance(row, dict):
            continue
        code = str(row.get("inds_cd") or "").strip()
        if code:
            perf_by_code[code] = row

    items = []
    for key, label, _aliases in INDUSTRY_GROUPS:
        match = matched.get(key) if key not in ambiguous else None
        code = match["code"] if match else None
        perf = perf_by_code.get(code) if code else None
        items.append({
            "key": key,
            "name": label,
            "code": code,
            "official_name": match["official_name"] if match else None,
            "official_english_name": match["official_english_name"] if match else None,
            "change_pct": _number(perf.get("perf_1d")) if perf else None,
            "perf_5d": _number(perf.get("perf_5d")) if perf else None,
            "perf_1m": _number(perf.get("perf_1m")) if perf else None,
            "mapping_status": (
                "ambiguous" if key in ambiguous else
                "matched" if match and perf else
                "performance_missing" if match else
                "unmatched"
            ),
        })

    items.sort(
        key=lambda item: (
            item["change_pct"] is not None,
            item["change_pct"] if item["change_pct"] is not None else float("-inf"),
        ),
        reverse=True,
    )
    for rank, item in enumerate(items, 1):
        item["rank"] = rank

    complete = all(item["mapping_status"] == "matched" for item in items)
    return {
        "ok": True,
        "source": "kiwoom:usa10101+usa23000",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mapping_complete": complete,
        "mapping_ambiguous": sorted(ambiguous),
        "unmatched_official_industries": unmatched[:40],
        "items": items,
    }


def fetch_us_industry_stocks(industry_code, sort="change", *, token=None, limit=36):
    """Fetch only the selected industry's source-ranked stock page."""
    code = _industry_code(industry_code)
    if sort not in ("change", "value"):
        raise ValueError("invalid_industry_sort")
    if type(limit) is not int or not 1 <= limit <= 36:
        raise ValueError("invalid_industry_limit")
    access_token = token or _access_token()

    if sort == "change":
        api_id = "usa23100"
        body = {"stex_tp": "0", "sort_tp": "1", "inds_cd": code}
    else:
        api_id = "usa20540"
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

    rows = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        symbol = str(record.get("stk_cd") or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\\-]{1,20}", symbol) or symbol in seen:
            continue
        exchange_raw = str(record.get("stex_tp") or "").strip().upper()
        exchange = EXCHANGE_CODES.get(exchange_raw, exchange_raw)
        if exchange not in EXCHANGES:
            continue
        name = str(record.get("stk_nm") or record.get("stk_enm") or "").strip()
        if not name or len(name) > 100:
            continue
        price = _positive_price(record.get("cur_prc"))
        change_pct = _number(record.get("flu_rt"))
        volume = _number(record.get("acc_trde_qty"))
        raw_value = _number(record.get("trde_prica"))
        trading_value = raw_value * 1000 if raw_value is not None and raw_value >= 0 else None
        rows.append({
            "symbol": symbol,
            "name": name,
            "english_name": str(record.get("stk_enm") or "").strip()[:100],
            "exchange": exchange,
            "price": price,
            "change_pct": change_pct,
            "volume": volume if volume is not None and volume >= 0 else None,
            "trading_value": trading_value,
            "source_rank": str(record.get("rank") or "").strip() or None,
        })
        seen.add(symbol)

    if sort == "change":
        rows.sort(key=lambda row: row["change_pct"] if row["change_pct"] is not None else float("-inf"), reverse=True)
    else:
        rows.sort(key=lambda row: row["trading_value"] if row["trading_value"] is not None else float("-inf"), reverse=True)
    rows = rows[:limit]
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank

    return {
        "ok": True,
        "source": "kiwoom:" + api_id,
        "industry_code": code,
        "sort": sort,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "items": rows,
    }
