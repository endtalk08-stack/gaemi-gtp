"""Read-only ETF endpoint routing probe."""
import json, ssl, urllib.error, urllib.request
for label, url in (("api", "http://127.0.0.1:8765/market/us-etf-quotes"), ("tls", "https://127.0.0.1/market/us-etf-quotes")):
    try:
        req = urllib.request.Request(url, headers={"Origin": "https://gaemigtp-main.pages.dev"})
        with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=30) as response:
            data = json.load(response)
            print("ETF_SNAPSHOT_CHECK=" + json.dumps({"route": label, "http": response.status, "ok": data.get("ok"), "symbols": sorted(row.get("symbol") for row in data.get("items", []))}), flush=True)
    except urllib.error.HTTPError as exc:
        print("ETF_SNAPSHOT_CHECK=" + json.dumps({"route": label, "http": exc.code}), flush=True)
    except Exception as exc:
        print("ETF_SNAPSHOT_CHECK=" + json.dumps({"route": label, "error": type(exc).__name__}), flush=True)
