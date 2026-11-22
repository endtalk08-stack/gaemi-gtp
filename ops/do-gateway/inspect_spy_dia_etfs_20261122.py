"""Read-only SPY/DIA Kiwoom exchange and ETF quote diagnostic."""
import json
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.kiwoom_us_industries import fetch_us_etf_exchanges, fetch_us_etf_quotes
def main():
    result = {}
    try:
        exchanges = fetch_us_etf_exchanges()
        result["exchanges"] = {symbol: exchanges.get(symbol) for symbol in ("SPY", "DIA")}
        result["count"] = len(exchanges)
    except Exception as exc:
        result["exchange_error"] = type(exc).__name__
    try:
        quotes = fetch_us_etf_quotes()
        result["quotes"] = [{key: row.get(key) for key in ("symbol", "exchange", "price", "change_pct", "source")} for row in quotes if row.get("symbol") in ("SPY", "DIA")]
        result["quote_count"] = len(quotes)
    except Exception as exc:
        result["quote_error"] = type(exc).__name__
    print("ETF_SPY_DIA_DIAGNOSTIC=" + json.dumps(result), flush=True)
if __name__ == "__main__":
    main()
