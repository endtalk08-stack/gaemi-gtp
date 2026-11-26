"""Read-only probe: what the live HTTPS heatmap API returns for sector ETF quotes.

Prints symbols, change %, source and age only. No secrets, no writes, no restarts.
"""
import json
import ssl
import time
import urllib.request

ETFS = ("XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB", "SOXX", "XBI", "IBIT")


def main():
    req = urllib.request.Request(
        "https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap",
        headers={"Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json",
                 "Cache-Control": "no-cache"},
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    started = time.time()
    with opener.open(req, timeout=60) as resp:
        data = json.load(resp)
        status = resp.status
    now_ms = int(time.time() * 1000)
    print("PROBE_HTTP=%s ok=%s elapsed=%.1fs fetched_at=%s stale=%s" % (
        status, data.get("ok"), time.time() - started, data.get("fetched_at"), data.get("stale")), flush=True)
    quotes = {q.get("symbol"): q for q in data.get("etf_quotes") or [] if isinstance(q, dict)}
    print("ETF_QUOTES_COUNT=%d" % len(quotes), flush=True)
    for sym in ETFS:
        q = quotes.get(sym)
        if not q:
            print("ETF %s MISSING" % sym, flush=True)
            continue
        age = (now_ms - q["received_at_ms"]) / 1000 if isinstance(q.get("received_at_ms"), int) else None
        print("ETF %s pct=%s price=%s source=%s age_s=%s" % (
            sym, q.get("change_pct"), q.get("price"), q.get("source"), age), flush=True)
    for row in data.get("items") or []:
        if isinstance(row, dict):
            stocks = row.get("stocks") or []
            print("SECTOR %s pct=%s stocks=%d stocks_error=%s" % (
                row.get("key"), row.get("change_pct"), len(stocks), row.get("stocks_error")), flush=True)


if __name__ == "__main__":
    main()
