"""Kiwoom REST US daily close and current quote, read-only.

Only OAuth token issuance and USA quote TRs usa20100/usa20590 are allowed.
No orders, accounts, positions, FX conversions or trading functions.
The module is not imported by existing news/price workers unless explicitly requested.
"""
import datetime as dt
import os
import re
import requests

API_ORIGIN = "https://api.kiwoom.com"
QUOTES_PATH = "/api/us/mrkcond"
SUPPORTED_EXCHANGES = {"NA", "ND", "NY"}
ALLOWED_TR = {"usa20100", "usa20590"}
US_INDEX_SYMBOLS = {"DJI", "IXIC", "INX", "NDX"}


class KiwoomReadOnlyError(RuntimeError):
    pass


def credentials_configured():
    return bool(os.environ.get("GAEMI_KIWOOM_APP_KEY", "").strip()
                and os.environ.get("GAEMI_KIWOOM_APP_SECRET", "").strip())


def _request(path, body, headers=None):
    """Official requests POST(json=...). Never send undocumented market requests."""
    if path == QUOTES_PATH:
        api_id = (headers or {}).get("api-id")
        _validate_stock_request(api_id, body)
    elif path != "/oauth2/token":
        raise KiwoomReadOnlyError("kiwoom_unsupported_api_path")
    try:
        response = requests.post(
            API_ORIGIN + path,
            json=body,
            headers={"Content-Type": "application/json;charset=UTF-8", **(headers or {})},
            timeout=8,
            allow_redirects=False,
        )
    except requests.RequestException:
        # Never include credentials, token, request/response details in logs.
        raise KiwoomReadOnlyError("kiwoom_request_failed") from None

    if response.status_code != 200:
        # Diagnostic metadata only. Never include request credentials, raw
        # HTML, response text, response headers or user-supplied content.
        content_type = str(response.headers.get("Content-Type") or "").lower().split(";", 1)[0].strip()
        kind = content_type if content_type in (
            "application/json", "text/html", "text/plain",
            "application/problem+json",
        ) else "other"
        sample = response.content[:65536]
        stripped = sample.lstrip()[:100]
        if not sample:
            body_type = "empty"
        elif stripped.startswith((b"{", b"[")):
            body_type = "json_like"
        elif stripped.lower().startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
            body_type = "html_like"
        else:
            try:
                sample.decode("utf-8")
                body_type = "text_like"
            except UnicodeError:
                body_type = "binary_like"
        lowercase_html = sample.lower()
        if b"request blocked" in lowercase_html:
            page_code = "request_blocked"
        elif b"request rejected" in lowercase_html:
            page_code = "request_rejected"
        elif b"access denied" in lowercase_html:
            page_code = "access_denied"
        elif b"400 bad request" in lowercase_html:
            page_code = "bad_request_400"
        elif b"403 forbidden" in lowercase_html:
            page_code = "forbidden_403"
        elif b"captcha" in lowercase_html:
            page_code = "captcha"
        else:
            page_code = "unknown"
        raw_server = str(response.headers.get("Server") or "").lower()
        if "openresty" in raw_server:
            server = "openresty"
        elif "nginx" in raw_server:
            server = "nginx"
        elif "cloudflare" in raw_server:
            server = "cloudflare"
        elif "akamai" in raw_server:
            server = "akamai"
        elif "envoy" in raw_server:
            server = "envoy"
        elif raw_server:
            server = "other"
        else:
            server = "none"
        gateway = "yes" if any(response.headers.get(x) for x in (
            "Via", "X-Cache", "CF-Ray", "X-Akamai-Request-ID",
            "X-Served-By", "X-Amz-Cf-Id",
        )) else "no"
        raise KiwoomReadOnlyError(
            "kiwoom_http_" + str(int(response.status_code)) +
            "_content_type_" + kind.replace("/", "_").replace("+", "_") +
            "_body_" + body_type + "_bytes_" + str(min(len(response.content), 65536)) +
            ("_truncated" if len(response.content) > 65536 else "") +
            "_page_" + page_code + "_server_" + server + "_gateway_" + gateway
        )

    try:
        result = response.json()
    except ValueError:
        raise KiwoomReadOnlyError("kiwoom_request_failed") from None
    if not isinstance(result, dict):
        raise KiwoomReadOnlyError("kiwoom_unexpected_response")
    code = str(result.get("return_code", 0))
    if code not in ("0", "0000"):
        # Keep only the numeric server code; never log return_msg or payload.
        safe_code = code if re.fullmatch(r"-?[0-9]{1,6}", code) else "unknown"
        raise KiwoomReadOnlyError("kiwoom_api_rejected_code_" + safe_code)
    return result


def issue_access_token():
    appkey = os.environ.get("GAEMI_KIWOOM_APP_KEY", "").strip()
    secret = os.environ.get("GAEMI_KIWOOM_APP_SECRET", "").strip()
    if not appkey or not secret:
        raise KiwoomReadOnlyError("kiwoom_credentials_missing")
    result = _request("/oauth2/token", {
        "grant_type": "client_credentials",
        "appkey": appkey, "secretkey": secret,
    })
    token = result.get("token")
    if not isinstance(token, str) or not token:
        raise KiwoomReadOnlyError("kiwoom_token_missing")
    return token


def _clean_symbol(symbol, exchange):
    symbol = str(symbol or "").upper()
    exchange = str(exchange or "").upper()
    if (not re.fullmatch(r"[A-Z0-9.\-]{1,20}", symbol)
            or exchange not in SUPPORTED_EXCHANGES):
        raise ValueError("invalid_us_symbol_or_exchange")
    if symbol in US_INDEX_SYMBOLS:
        raise KiwoomReadOnlyError("kiwoom_index_not_stock")
    return symbol, exchange

def _validate_stock_request(api_id, body):
    """Reject index-list codes and non-stock exchange values BEFORE HTTP.

    usa10102's NW/NQ/NS identify US indices and MUST NOT be sent to
    stock-only usa20100/usa20590, which accept NA/ND/NY.
    """
    if api_id not in ALLOWED_TR:
        raise KiwoomReadOnlyError("kiwoom_non_readonly_api_disallowed")
    if not isinstance(body, dict):
        raise KiwoomReadOnlyError("kiwoom_stock_request_invalid")
    exchange = body.get("stex_tp")
    symbol = body.get("stk_cd")
    if exchange not in SUPPORTED_EXCHANGES:
        raise KiwoomReadOnlyError("kiwoom_invalid_stock_exchange")
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9.\-]{1,20}", symbol):
        raise KiwoomReadOnlyError("kiwoom_stock_symbol_invalid")
    if symbol in US_INDEX_SYMBOLS:
        raise KiwoomReadOnlyError("kiwoom_index_not_stock")
    if api_id == "usa20590" and not (
        isinstance(body.get("base_dt"), str)
        and re.fullmatch(r"[0-9]{8}", body["base_dt"])
    ):
        raise KiwoomReadOnlyError("kiwoom_stock_session_invalid")


def _market_request(api_id, body, token):
    _validate_stock_request(api_id, body)
    if not token:
        raise KiwoomReadOnlyError("kiwoom_token_missing")
    return _request(QUOTES_PATH, body, {
        "authorization": "Bearer " + token, "api-id": api_id,
    })


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(str(value).strip().replace(",", "").replace("+", ""))
        return n if -1e15 < n < 1e15 else None
    except (TypeError, ValueError):
        return None


def fetch_us_close(symbol, exchange, session_date, *, token=None):
    """Use usa20590 exact dated daily quote, never an extended-hours snapshot.

    If the requested NY trading date is missing, return None rather than
    silently substituting an earlier or later price.
    """
    symbol, exchange = _clean_symbol(symbol, exchange)
    if type(session_date) is not dt.date:
        raise ValueError("invalid_session_date")
    daycode = session_date.strftime("%Y%m%d")
    data = _market_request("usa20590", {
        "stex_tp": exchange, "stk_cd": symbol, "base_dt": daycode,
    }, token or issue_access_token())
    items = data.get("result_list")
    if not isinstance(items, list):
        raise KiwoomReadOnlyError("kiwoom_daily_records_missing")
    for item in items:
        if not isinstance(item, dict) or str(item.get("dt", "")).replace("-", "") != daycode:
            continue
        close = _num(item.get("cur_prc"))
        change = _num(item.get("flu_rt"))
        if close is None or close <= 0 or change is None:
            raise KiwoomReadOnlyError("kiwoom_daily_record_invalid")
        return {
            "ticker": symbol, "exchange": exchange,
            "session_date": session_date.isoformat(),
            "close": close, "change_pct": change,
            "volume": _num(item.get("acc_trde_qty")),
            "source": "kiwoom:usa20590",
        }
    return None


def fetch_us_quote(symbol, exchange, *, token=None):
    """Current trading quote only; not necessarily the official session close."""
    symbol, exchange = _clean_symbol(symbol, exchange)
    data = _market_request("usa20100", {
        "stex_tp": exchange, "stk_cd": symbol,
    }, token or issue_access_token())
    return {
        "ticker": symbol, "exchange": exchange,
        "current": _num(data.get("cur_prc")),
        "change_pct": _num(data.get("flu_rt")),
        "previous_close": _num(data.get("base_close_pric")),
        "source": "kiwoom:usa20100",
        "official_close": False,
    }
