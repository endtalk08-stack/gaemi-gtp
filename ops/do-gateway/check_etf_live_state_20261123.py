"""Read-only: check the ACTUAL in-process live/REST state of all 14 sector
ETF quotes right now, straight from the running service over localhost
(bypassing Cloudflare's CDN cache, which the public quotes.gaemigtp.com
domain may be serving stale/cached responses through). Calls twice with a
wait in between so a frozen received_at_ms (no new tick) can be told apart
from the endpoint merely being cached."""
import json
import ssl
import time
from urllib.request import urlopen

ctx = ssl._create_unverified_context()


def get(path):
    with urlopen("https://127.0.0.1" + path, timeout=40, context=ctx) as response:
        return json.load(response)


first = get("/market/us-industry-etf-quotes")
print("FIRST", json.dumps(first), flush=True)

time.sleep(20)

second = get("/market/us-industry-etf-quotes")
print("SECOND", json.dumps(second), flush=True)

first_by_symbol = {item["symbol"]: item for item in first.get("items", [])}
second_by_symbol = {item["symbol"]: item for item in second.get("items", [])}
for symbol in sorted(first_by_symbol):
    a = first_by_symbol[symbol]
    b = second_by_symbol.get(symbol, {})
    moved = a.get("received_at_ms") != b.get("received_at_ms")
    print("DIFF", symbol, "changed=" + str(moved),
          "first_received_at_ms=" + str(a.get("received_at_ms")),
          "second_received_at_ms=" + str(b.get("received_at_ms")),
          "first_pct=" + str(a.get("change_pct")), "second_pct=" + str(b.get("change_pct")),
          flush=True)
