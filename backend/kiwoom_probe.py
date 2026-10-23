"""One NVDA-only Kiwoom connection check; no mass stock lookup or orders.

Check current quote plus last completed NY trading session daily close.
No secrets or access tokens are printed or stored.
"""
import datetime as dt
import json
import sys
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_quotes import (
    KiwoomReadOnlyError, credentials_configured,
    fetch_us_close, issue_access_token, _market_request, _num,
)

NY = ZoneInfo("America/New_York")
SYMBOL = "NVDA"
EXCHANGE = "ND"


def _last_completed_session(now=None):
    now = now or dt.datetime.now(NY)
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    local = now.astimezone(NY)
    day = local.date()
    if local.hour < 16:
        day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def main():
    if not credentials_configured():
        print("KIWOOM_VERIFY_CREDENTIALS_MISSING", flush=True)
        return 2
    try:
        token = issue_access_token()
        print("KIWOOM_VERIFY_OAUTH_OK", flush=True)
        # One read-only quote request. Diagnose only public market fields:
        # never output HTTP headers, auth token, full response, or account data.
        data = _market_request("usa20100", {
            "stex_tp": EXCHANGE, "stk_cd": SYMBOL,
        }, token)
        current = _num(data.get("cur_prc"))
        change = _num(data.get("flu_rt"))
        previous_close = _num(data.get("base_close_pric"))
        if current is None:
            state = "non_numeric_or_missing"
        elif current < 0:
            state = "negative"
        elif current == 0:
            state = "zero"
        else:
            state = "positive"
        print("KIWOOM_VERIFY_NVDA_QUOTE_DIAG=" + json.dumps({
            "current": current,
            "current_state": state,
            "change_pct": change,
            "previous_close": previous_close,
            "public_field_presence": {
                field: field in data for field in (
                    "cur_prc", "flu_rt", "base_close_pric",
                    "stk_cd", "stex_tp", "stk_nm", "pred_pre_sig",
                )
            },
            "current_raw_type": type(data.get("cur_prc")).__name__,
            "requested_symbol_matches": data.get("stk_cd") in (None, SYMBOL),
            "response_has_nested_objects": any(
                isinstance(value, (dict, list)) for value in data.values()
            ),
        }, ensure_ascii=False, sort_keys=True), flush=True)
        if current is None or current <= 0:
            print("KIWOOM_VERIFY_NVDA_QUOTE_INVALID=" + state, flush=True)
            return 4
        print("KIWOOM_VERIFY_NVDA_CURRENT_OK=" + json.dumps({
            "symbol": SYMBOL, "current": current,
            "change_pct": change,
            "official_close": False,
        }, ensure_ascii=False), flush=True)

        day = _last_completed_session()
        close = fetch_us_close(SYMBOL, EXCHANGE, day, token=token)
        if close is None:
            print("KIWOOM_VERIFY_NVDA_CLOSE_NOT_YET_AVAILABLE=" + day.isoformat(), flush=True)
            return 5
        print("KIWOOM_VERIFY_NVDA_CLOSE_OK=" + json.dumps({
            "symbol": SYMBOL, "session_date": close["session_date"],
            "close": close["close"], "change_pct": close["change_pct"],
            "source": close["source"],
        }, ensure_ascii=False), flush=True)
        return 0
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_VERIFY_ERROR=" + str(exc), flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
