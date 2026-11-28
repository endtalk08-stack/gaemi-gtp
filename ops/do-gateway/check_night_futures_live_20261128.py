"""Read-only: the night-futures quote the widget receives now, and the saved last price."""
import json, pathlib, ssl, time
p = pathlib.Path("/var/lib/gaemigtp-news/kis-night-futures-last.json")
print("LAST_FILE " + (p.read_text() if p.exists() else "missing"), flush=True)
ctx = ssl._create_unverified_context()
try:
    from websockets.sync.client import connect
    with connect("wss://127.0.0.1/ws/us-live-quotes", ssl=ctx, server_hostname="127.0.0.1",
                 additional_headers={"Origin": "https://gaemigtp-main.pages.dev"}, open_timeout=15) as ws:
        end = time.time() + 25
        while time.time() < end:
            msg = json.loads(ws.recv(timeout=end - time.time()))
            if msg.get("type") == "night-futures-quote":
                q = msg.get("quote") or {}
                print("WIDGET_QUOTE " + json.dumps({k: q.get(k) for k in ("symbol", "price", "change_pct", "status", "connected", "source", "stale")}), flush=True)
                if q.get("price"):
                    break
except Exception as exc:
    print("WS_ERROR %s %s" % (type(exc).__name__, exc), flush=True)
