"""Single-shot Kiwoom official-style US quote connectivity verification.

Use the same requests POST(json=...), header and API IDs as Kiwoom's published
2026 REST Python examples. Never print keys, tokens, raw response or cookies.
One OAuth attempt only, followed by NVDA current/daily reads if authorized.
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import requests

API_ORIGIN = "https://api.kiwoom.com"
JSON_CONTENT_TYPE = "application/json;charset=UTF-8"
NY = ZoneInfo("America/New_York")


class ProbeError(Exception):
    pass


def _diagnostic(response):
    raw = response.content[:65536]
    short = raw.lstrip().lower()
    content_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
    kind = "json" if content_type == "application/json" else "html" if content_type == "text/html" else "other"
    body = "html" if short.startswith((b"<!doctype html", b"<html", b"<head", b"<body")) else "json" if short.startswith((b"{", b"[")) else "other"
    page = "request_blocked" if b"request blocked" in short else "request_rejected" if b"request rejected" in short else "access_denied" if b"access denied" in short else "unknown"
    server = response.headers.get("Server", "").lower()
    server_kind = next((x for x in ("nginx", "openresty", "cloudflare", "akamai", "envoy") if x in server), "other" if server else "none")
    gateway = "yes" if any(response.headers.get(x) for x in ("Via", "X-Cache", "CF-Ray", "X-Akamai-Request-ID", "X-Served-By", "X-Amz-Cf-Id")) else "no"
    return ("http" + str(response.status_code) + "_type_" + kind + "_body_" + body +
            "_bytes_" + str(len(response.content)) + "_page_" + page +
            "_server_" + server_kind + "_gateway_" + gateway)


def _call(session, path, body, *, api_id=None, token=None):
    headers = {"Content-Type": JSON_CONTENT_TYPE}
    if api_id:
        headers.update({"api-id": api_id, "authorization": "Bearer " + token})
    try:
        response = session.post(
            API_ORIGIN + path, json=body, headers=headers,
            timeout=8, allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ProbeError("transport_" + type(exc).__name__) from None
    if response.status_code != 200:
        raise ProbeError(_diagnostic(response))
    try:
        payload = response.json()
    except ValueError:
        raise ProbeError("http200_non_json") from None
    if not isinstance(payload, dict):
        raise ProbeError("http200_non_object")
    code = payload.get("return_code")
    if code not in (None, 0, "0", "0000"):
        raise ProbeError("api_return_code_" + str(code)[:16] if str(code).lstrip("-").isdigit() else "api_return_code_invalid")
    return payload


def _last_completed_session():
    now = dt.datetime.now(NY)
    day = now.date()
    if now.hour < 16:
        day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def _number(value):
    try:
        number = float(str(value).strip().replace(",", ""))
        return number if 0 < number < 1e12 else None
    except (TypeError, ValueError):
        return None


def main():
    appkey = os.environ.get("GAEMI_KIWOOM_APP_KEY", "").strip()
    secret = os.environ.get("GAEMI_KIWOOM_APP_SECRET", "").strip()
    if not appkey or not secret:
        print("KIWOOM_OFFICIAL_VERIFY=credentials_missing", flush=True)
        return 2
    print("KIWOOM_OFFICIAL_VERIFY=single_oauth_requests_json_start", flush=True)
    try:
        with requests.Session() as session:
            auth = _call(session, "/oauth2/token", {
                "grant_type": "client_credentials",
                "appkey": appkey,
                "secretkey": secret,
            })
            access_token = auth.get("token")
            if not isinstance(access_token, str) or not access_token:
                raise ProbeError("oauth_token_missing")
            print("KIWOOM_OFFICIAL_OAUTH=success", flush=True)

            quote = _call(session, "/api/us/mrkcond", {
                "stex_tp": "ND", "stk_cd": "NVDA",
            }, api_id="usa20100", token=access_token)
            current = _number(quote.get("cur_prc"))
            if current is None:
                raise ProbeError("nvda_quote_invalid")
            print("KIWOOM_OFFICIAL_NVDA_CURRENT=" + json.dumps({
                "current": current, "change_pct": quote.get("flu_rt"),
            }, ensure_ascii=False), flush=True)

            day = _last_completed_session()
            result = _call(session, "/api/us/mrkcond", {
                "stex_tp": "ND", "stk_cd": "NVDA",
                "base_dt": day.strftime("%Y%m%d"),
            }, api_id="usa20590", token=access_token)
            matching = next((x for x in result.get("result_list", []) if isinstance(x, dict) and str(x.get("dt", "")).replace("-", "") == day.strftime("%Y%m%d")), None)
            if not matching:
                print("KIWOOM_OFFICIAL_NVDA_DAILY=not_yet_available_for_" + day.isoformat(), flush=True)
                return 5
            close = _number(matching.get("cur_prc"))
            if close is None:
                raise ProbeError("nvda_daily_close_invalid")
            print("KIWOOM_OFFICIAL_NVDA_DAILY=" + json.dumps({
                "session": day.isoformat(), "close": close,
                "change_pct": matching.get("flu_rt"),
            }, ensure_ascii=False), flush=True)
            return 0
    except ProbeError as exc:
        print("KIWOOM_OFFICIAL_VERIFY_ERROR=" + str(exc), flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
