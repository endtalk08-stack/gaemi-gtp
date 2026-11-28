"""Read-only: what the live quote service returns now for market widgets and TOP20 (weekend close)."""
import json, ssl, urllib.request
ctx = ssl._create_unverified_context()
def get(path):
    req = urllib.request.Request("https://127.0.0.1" + path, headers={"Origin": "https://gaemigtp-main.pages.dev"})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        return json.load(r)
try:
    data = get("/market/us-etf-quotes")
    for it in data.get("items") or []:
        print("ETF " + json.dumps({k: it.get(k) for k in ("symbol", "name", "price", "change_pct", "close", "reference_close_date", "source", "stale", "session") if k in it}, ensure_ascii=False), flush=True)
except Exception as exc:
    print("ETF_ERROR", type(exc).__name__, exc, flush=True)
try:
    data = get("/market/trading-value?market=us")
    items = data.get("items") or []
    print("TOP20 count=%d with_pct=%d" % (len(items), sum(1 for i in items if isinstance(i.get("change_pct"), (int, float)))), flush=True)
    for it in items[:5]:
        print("TOP " + json.dumps({k: it.get(k) for k in ("symbol", "price", "change_pct", "reference_close_date")}, ensure_ascii=False), flush=True)
except Exception as exc:
    print("TOP20_ERROR", type(exc).__name__, exc, flush=True)
try:
    data = get("/market/us-industries")
    items = data.get("items") or data.get("industries") or []
    print("INDUSTRY count=%d with_pct=%d" % (len(items), sum(1 for i in items if isinstance(i.get("change_pct"), (int, float)))), flush=True)
except Exception as exc:
    print("INDUSTRY_ERROR", type(exc).__name__, exc, flush=True)
