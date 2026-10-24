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
    fetch_us_close, issue_access_token, _market_request, _price, _num,
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
    # Market-hours-only FE diagnostic, limited to one NVDA subscription.
    # Outside US extended-hours windows preserve the proven REST verification.
    now_et = dt.datetime.now(NY)
    if now_et.weekday() < 5 and dt.time(4, 0) <= now_et.time() < dt.time(20, 0):
        print("KIWOOM_VERIFY_ROUTE=us_realtime_FE", flush=True)
        from backend.kiwoom_fe_realtime_probe import main as run_fe_diagnostic
        return run_fe_diagnostic()
    print("KIWOOM_VERIFY_ROUTE=us_rest_snapshot", flush=True)
    if not credentials_configured():
        print("KIWOOM_VERIFY_CREDENTIALS_MISSING", flush=True)
        return 2
    try:
        token = issue_access_token()
        print("KIWOOM_VERIFY_OAUTH_OK", flush=True)
        # Single authenticated, read-only usa20100 call: inspect fields in the
        # actual response, not just what the published schema promises.
        raw = _market_request("usa20100", {"stex_tp": EXCHANGE, "stk_cd": SYMBOL}, token)
        quote = {"current": _price(raw.get("cur_prc")),
                 "change_pct": _num(raw.get("flu_rt"))}
        keys = ("cur_prc", "flu_rt", "open_pric", "high_pric", "low_pric",
                "pre_open_pric", "pre_high_pric", "pre_low_pric",
                "base_close_pric", "52wk_hgst_pric", "52wk_lwst_pric")
        print("KIWOOM_VERIFY_NVDA_OHLC_FIELDS=" + json.dumps({
            name: {"present": name in raw, "value":
                   _num(raw.get(name)) if name == "flu_rt" else _price(raw.get(name))}
            for name in keys
        }, ensure_ascii=False), flush=True)
        if not quote.get("current") or quote["current"] <= 0:
            print("KIWOOM_VERIFY_NVDA_QUOTE_INVALID", flush=True)
            return 4
        print("KIWOOM_VERIFY_NVDA_CURRENT_OK=" + json.dumps({
            "symbol": SYMBOL, "current": quote["current"],
            "change_pct": quote["change_pct"],
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
