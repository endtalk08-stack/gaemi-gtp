"""Read-only: the live /market/us-industry-etf-quotes check showed 13 of 14
sector ETFs with change_pct: null and received_at_ms: 0 -- not just stale,
but NEVER successfully fetched even once since the service last restarted.
"No new tick today" would still leave a previous-close based REST quote;
a flat null for every refresh cycle is unexpected. Call the actual REST
fetch function directly for one of the affected symbols (XLY) and print
exactly what it returns or raises, to tell apart "Kiwoom genuinely has no
quote for XLY right now" from "this REST path is broken"."""
import json
import sys

sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.providers.kiwoom_us_industries import (
    fetch_us_etf_quotes, fetch_us_etf_marketcap, fetch_us_etf_exchanges, fetch_us_quote,
)

try:
    marketcap = fetch_us_etf_marketcap(limit=100)
    items = marketcap.get("items", [])
    print("MARKETCAP_TR_COUNT", len(items), flush=True)
    print("MARKETCAP_TR_SAMPLE", json.dumps(items[:3]), flush=True)
    symbols_in_tr = sorted({str(row.get("symbol") or "").upper() for row in items if isinstance(row, dict)})
    print("MARKETCAP_TR_SYMBOLS", symbols_in_tr, flush=True)
except Exception as exc:
    print("MARKETCAP_TR_ERROR", repr(exc), flush=True)

for symbol in ("XLY", "XLB", "XLC"):
    try:
        exchanges = fetch_us_etf_exchanges(tickers={symbol})
        print(symbol, "EXCHANGE_LOOKUP", exchanges, flush=True)
        exchange = exchanges.get(symbol)
        if exchange:
            try:
                quote = fetch_us_quote(symbol, exchange)
                print(symbol, "SINGLE_QUOTE", json.dumps(quote), flush=True)
            except Exception as exc:
                print(symbol, "SINGLE_QUOTE_ERROR", repr(exc), flush=True)
    except Exception as exc:
        print(symbol, "EXCHANGE_LOOKUP_ERROR", repr(exc), flush=True)

try:
    result = fetch_us_etf_quotes(symbols={"XLY", "XLB", "XLC", "SOXX"})
    print("FETCH_US_ETF_QUOTES_RESULT", json.dumps(result), flush=True)
except Exception as exc:
    print("FETCH_US_ETF_QUOTES_ERROR", repr(exc), flush=True)
