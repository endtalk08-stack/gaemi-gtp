#!/usr/bin/env python3
"""Read-only snapshot of all industry ETF quote fields from the local production API."""
import json
import ssl
from urllib.request import urlopen

ctx = ssl._create_unverified_context()
def get(path):
    with urlopen("https://127.0.0.1" + path, timeout=30, context=ctx) as response:
        return json.load(response)

for path in (
    "/market/us-industry-etf-quotes",
    "/market/us-industries?include_stocks=1&view=heatmap",
):
    try:
        data = get(path)
        items = data.get("items") or data.get("etf_quotes") or []
        print("ENDPOINT", path, "ok", data.get("ok"), "count", len(items), flush=True)
        for row in items:
            if isinstance(row, dict) and row.get("symbol"):
                print("ETF", row.get("symbol"), "price", row.get("price"),
                      "change_pct", row.get("change_pct"),
                      "received_at_ms", row.get("received_at_ms"),
                      "stale", row.get("stale"), "source", row.get("source"),
                      "reference_close_date", row.get("reference_close_date"), flush=True)
    except Exception as exc:
        print("ENDPOINT_ERROR", path, type(exc).__name__, flush=True)
