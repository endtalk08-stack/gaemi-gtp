import json
import ssl
import urllib.request
from datetime import datetime, timezone

def check(name, url, host=None):
    try:
        headers = {"User-Agent": "gaemiGTP-readonly-diagnostic"}
        if host:
            headers["Host"] = host
        req = urllib.request.Request(url, headers=headers)
        context = ssl._create_unverified_context() if url.startswith("https://127.0.0.1") else None
        with urllib.request.urlopen(req, context=context, timeout=12) as response:
            payload = json.load(response)
            items = payload.get("items") or []
            rows = []
            for item in items:
                if isinstance(item, dict):
                    rows.append({
                        "symbol": item.get("symbol"),
                        "price_valid": type(item.get("price")) in (int, float) and item.get("price", 0) > 0,
                        "change_valid": type(item.get("change_pct")) in (int, float),
                        "stale": item.get("stale"),
                        "source": item.get("source"),
                    })
            print(json.dumps({
                "check": name, "http": response.status, "ok": payload.get("ok"),
                "count": len(items), "items": rows,
            }, ensure_ascii=False), flush=True)
    except Exception as exc:
        print(json.dumps({"check": name, "error": type(exc).__name__, "detail": str(exc)[:240]}, ensure_ascii=False), flush=True)

print("DIAGNOSTIC_TIME_UTC=" + datetime.now(timezone.utc).isoformat(), flush=True)
check("local_https", "https://127.0.0.1/market/us-etf-quotes", "localhost")
check("local_http", "http://127.0.0.1:8765/market/us-etf-quotes")
check("public", "https://quotes.gaemigtp.com/market/us-etf-quotes")
