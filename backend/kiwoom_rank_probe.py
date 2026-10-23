"""Single read-only request to Kiwoom USA trading-value market ranking.
No credentials, tokens, full response or private account fields in output.
"""
import json

from backend.providers.kiwoom_us_quotes import issue_access_token, KiwoomReadOnlyError
from backend.providers.kiwoom_us_rankings import fetch_us_trading_value_top

def main():
    try:
        token = issue_access_token()
        rows = fetch_us_trading_value_top(limit=20, token=token)
        print("KIWOOM_US_VALUE_PROBE=" + json.dumps({
            "count": len(rows),
            "first": [{
                "symbol": row["symbol"], "exchange": row["exchange"],
                "name": row["name"][:50], "price": row["price"],
                "change_pct": row["change_pct"],
                "trading_value": row["trading_value"],
                "volume": row["volume"],
                "implied_trade_value_unit": round((row["price"] * row["volume"]) / row["trading_value"], 2)
                    if row["price"] and row["volume"] and row["trading_value"] else None,
            } for row in rows[:3]]
        }, ensure_ascii=False), flush=True)
        print("KIWOOM_US_VALUE_PROBE_PASS", flush=True)
        return 0
    except KiwoomReadOnlyError as exc:
        print("KIWOOM_US_VALUE_PROBE_FAILED=" + str(exc), flush=True)
        return 3
    except Exception as exc:
        print("KIWOOM_US_VALUE_PROBE_UNEXPECTED=" + type(exc).__name__, flush=True)
        return 4

if __name__ == "__main__":
    raise SystemExit(main())
