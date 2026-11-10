"""Read-only TOP20 health and response test; no credentials, writes or data collection."""
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

urls = [
    ("loopback", "http://127.0.0.1:8765/market/trading-value?market=us", None),
    ("tls_local", "https://127.0.0.1/market/trading-value?market=us", ssl._create_unverified_context()),
    ("public_quotes", "https://quotes.gaemigtp.com/market/trading-value?market=us", None),
]
for name, url, context in urls:
    try:
        req = urllib.request.Request(url, headers={"Origin":"https://gaemigtp.com","User-Agent":"gaemigtp-readonly-probe"})
        with urllib.request.urlopen(req, timeout=8, context=context) as response:
            payload=json.load(response)
            items=payload.get("items", [])
            print("PROBE", name, "status", response.status, "ok", payload.get("ok"),
                  "count", len(items) if isinstance(items,list) else "invalid",
                  "source", payload.get("source"),"cors", response.headers.get("Access-Control-Allow-Origin"),
                  "captured_at",payload.get("captured_at"),flush=True)
    except urllib.error.HTTPError as exc:
        print("PROBE",name,"http",exc.code,flush=True)
    except Exception as exc:
        print("PROBE",name,"error",type(exc).__name__,flush=True)
# Read-only snapshot metadata; never print quotes or private files.
path=Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
try:
    meta=json.loads(path.read_text())
    print("SNAPSHOT", "rows", len(meta.get("items",[])), "captured_at",meta.get("captured_at"),
          "size",path.stat().st_size, flush=True)
except Exception as exc:
    print("SNAPSHOT error",type(exc).__name__,flush=True)
