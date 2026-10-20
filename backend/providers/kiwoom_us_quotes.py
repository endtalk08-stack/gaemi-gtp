"""Kiwoom REST US daily close and current quote, read-only.

Only OAuth token issuance and USA quote TRs usa20100/usa20590 are allowed.
No orders, accounts, positions, FX conversions or trading functions.
The module is not imported by existing news/price workers unless explicitly requested.
"""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request

API_ORIGIN = "https://api.kiwoom.com"
QUOTES_PATH = "/api/us/mrkcond"
SUPPORTED_EXCHANGES = {"NA", "ND", "NY"}
ALLOWED_TR = {"usa20100", "usa20590"}


class KiwoomReadOnlyError(RuntimeError):
    pass


def credentials_configured():
    return bool(os.environ.get("GAEMI_KIWOOM_APP_KEY", "").strip()
                and os.environ.get("GAEMI_KIWOOM_APP_SECRET", "").strip())


def _request(path, body, headers=None):
    req = urllib.request.Request(
        API_ORIGIN + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json;charset=UTF-8", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Diagnostic metadata only. Never include request credentials, headers,
        # response body, server-provided message text, or tokens in the error.
        content_type = str(exc.headers.get("Content-Type") or "").lower().split(";", 1)[0].strip()
        kind = content_type if content_type in (
            "application/json", "text/html", "text/plain",
            "application/problem+json"
        ) else "other"
        try:
            sample = exc.read(65537)
        except OSError:
            sample = b""
        length = min(len(sample), 65536)
        truncated = len(sample) > 65536
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
        # Fixed-character, bounded output: safe to emit into CI logs.
        suffix = "_truncated" if truncated else ""
        # Fixed, allowlisted WAF/proxy signatures only. No free-form title,
        # raw HTML, response header value, or URL ever reaches a log.
        lowercase_html = sample[:65536].lower()
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
        raw_server = str(exc.headers.get("Server") or "").lower()
        if "nginx" in raw_server:
            server = "nginx"
        elif "openresty" in raw_server:
            server = "openresty"
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
        gateway = "yes" if any(exc.headers.get(x) for x in (
            "Via", "X-Cache", "CF-Ray", "X-Akamai-Request-ID",
            "X-Served-By", "X-Amz-Cf-Id"
        )) else "no"
        raise KiwoomReadOnlyError(
            "kiwoom_http_" + str(int(exc.code)) +
            "_content_type_" + kind.replace("/", "_").replace("+", "_") +
            "_body_" + body_type + "_bytes_" + str(length) + suffix +
            "_page_" + page_code + "_server_" + server + "_gateway_" + gateway
        ) from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise KiwoomReadOnlyError("kiwoom_request_failed") from None
    if not isinstance(result, dict):
        raise KiwoomReadOnlyError("kiwoom_unexpected_response")
    if str(result.get("return_code", 0)) != "0":
        raise KiwoomReadOnlyError("kiwoom_api_rejected") from None
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
    return symbol, exchange


def _market_request(api_id, body, token):
    if api_id not in ALLOWED_TR:
        raise KiwoomReadOnlyError("kiwoom_non_readonly_api_disallowed")
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
