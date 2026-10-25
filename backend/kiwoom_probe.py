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
    fetch_us_close, fetch_us_quote, fetch_us_daily_chart, issue_access_token,
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
        quote = fetch_us_quote(SYMBOL, EXCHANGE, token=token)
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
        chart = fetch_us_daily_chart(SYMBOL, EXCHANGE, day - dt.timedelta(days=45), end_date=day, token=token, max_pages=3)
        rows = chart.get("rows") or []
        if not rows or not all(row.get("date") and row.get("open") and row.get("high") and row.get("low") and row.get("close") for row in rows):
            print("KIWOOM_VERIFY_CHART_EMPTY_OR_INVALID", flush=True)
            return 6
        print("KIWOOM_VERIFY_CHART_OK=" + json.dumps({
            "symbol": SYMBOL, "count": len(rows), "first_date": rows[0]["date"],
            "last_date": rows[-1]["date"], "source": chart["source"],
        }, ensure_ascii=False), flush=True)
        return 0
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_VERIFY_ERROR=" + str(exc), flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
