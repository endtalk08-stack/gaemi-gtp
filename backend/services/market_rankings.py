"""Temporary on-demand ranking of registered stocks; no ranking persistence."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from .engine import TICKERS
from ..providers.market_price import fetch_daily_price_history


def registered_turnover_ranking(market, limit=22):
    if market not in ("kr", "us"):
        return []
    symbols = {}
    for name, ticker in TICKERS.items():
        if ticker == "BTC-USD" or ticker == "SPCX":
            continue
        is_kr = ticker.endswith((".KS", ".KQ"))
        if is_kr != (market == "kr"):
            continue
        symbols.setdefault(ticker, name)

    def load(item):
        ticker, name = item
        rows = fetch_daily_price_history(ticker)
        if not rows:
            return None
        row = rows[-1]
        close = float(row.get("close") or 0)
        volume = float(row.get("volume") or 0)
        if close <= 0 or volume <= 0:
            return None
        previous = float(rows[-2].get("close") or 0) if len(rows) > 1 else 0
        return {
            "name": name, "ticker": ticker, "price": close,
            "change_pct": round((close / previous - 1) * 100, 2) if previous > 0 else None,
            "turnover_estimate": round(close * volume),
            "date": row.get("date") or "",
        }

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(load, item) for item in symbols.items()]
        for future in as_completed(futures):
            try:
                value = future.result()
                if value:
                    results.append(value)
            except Exception:
                pass
    return sorted(results, key=lambda item: item["turnover_estimate"], reverse=True)[:limit]
