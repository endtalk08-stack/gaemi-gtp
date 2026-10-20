"""One-shot connectivity check. Prints only quote summary; never credentials."""
import datetime as dt
import json
import sys

from backend.providers.kiwoom_us_quotes import (
    KiwoomReadOnlyError, credentials_configured, fetch_us_quote, issue_access_token,
)


def main():
    if not credentials_configured():
        print("KIWOOM_VERIFY_CREDENTIALS_MISSING", flush=True)
        return 2
    print("KIWOOM_VERIFY_CREDENTIALS_PRESENT", flush=True)
    try:
        token = issue_access_token()
        print("KIWOOM_VERIFY_OAUTH_OK", flush=True)
        price = fetch_us_quote("NVDA", "ND", token=token)
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_VERIFY_ERROR=" + str(exc), flush=True)
        return 3
    if not price.get("current") or price["current"] <= 0:
        print("KIWOOM_VERIFY_QUOTE_INVALID", flush=True)
        return 4
    print("KIWOOM_VERIFY_QUOTE_OK=" + json.dumps({
        "symbol": price["ticker"],
        "exchange": price["exchange"],
        "current": price["current"],
        "change_pct": price["change_pct"],
        "source": price["source"],
        "official_close": price["official_close"],
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
