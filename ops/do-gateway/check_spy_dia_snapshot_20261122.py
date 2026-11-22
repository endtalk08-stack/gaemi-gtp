"""Read-only cached SPY/DIA endpoint probe."""
import json
import ssl
import urllib.request
from pathlib import Path
url = "https://127.0.0.1/market/us-etf-quotes"
request = urllib.request.Request(url, headers={"Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json"})
with urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=30) as response:
    data = json.load(response)
    rows = data.get("items", [])
    print("ETF_SNAPSHOT_CHECK=" + json.dumps({
        "http": response.status,
        "ok": data.get("ok"),
        "symbols": sorted(row.get("symbol") for row in rows),
        "prices_valid": all(isinstance(row.get("price"), (int, float)) and row["price"] > 0 for row in rows),
        "sources": sorted({row.get("source") for row in rows}),
    }), flush=True)
