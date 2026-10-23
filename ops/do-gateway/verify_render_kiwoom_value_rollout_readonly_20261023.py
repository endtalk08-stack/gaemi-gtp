"""Bounded, authenticated, read-only Render response verification. No secrets logged.
Uses the already installed protected ranking worker token.
"""
import os
import time
import requests

TOKEN = os.environ.get("NEWS_WORKER_RANKING_TOKEN", "").strip()
if not TOKEN:
    print("KIWOOM_RENDER_VERIFY=worker_token_unavailable", flush=True)
    raise SystemExit(2)

URL = "https://gaemi-gtp.onrender.com/market/trading-value?market=us"
for attempt in range(1, 9):
    try:
        r = requests.get(URL, headers={"X-Gaemi-News-Worker-Token": TOKEN},
                         timeout=14, allow_redirects=False)
        try:
            data = r.json()
        except ValueError:
            data = {}
        items = data.get("items") if isinstance(data, dict) else None
        count = len(items) if isinstance(items, list) else 0
        source = data.get("source") if isinstance(data, dict) else None
        status = data.get("provider_status") if isinstance(data, dict) else None
        version = r.headers.get("X-Gaemi-US-Value-Provider")
        print(f"KIWOOM_RENDER_CHECK_{attempt}: http={r.status_code} source={source} rows={count} "
              f"provider_status={str(status)[:32]} version={str(version)[:32]}", flush=True)
        if r.status_code == 200 and data.get("ok") is True and source == "kiwoom" and count == 20:
            names = [(str(x.get("symbol",""))[:20], int(x.get("rank",0)))
                     for x in items[:3] if isinstance(x,dict)]
            print("KIWOOM_RENDER_LIVE_TOP3=" + repr(names), flush=True)
            print("KIWOOM_RENDER_VERIFY_PASS", flush=True)
            raise SystemExit(0)
    except requests.RequestException as exc:
        print(f"KIWOOM_RENDER_CHECK_{attempt}: error={type(exc).__name__}", flush=True)
    if attempt < 8:
        time.sleep(16)
print("KIWOOM_RENDER_VERIFY_NOT_READY", flush=True)
raise SystemExit(3)
