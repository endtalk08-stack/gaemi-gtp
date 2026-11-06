"""One-shot TradingView category-news verification.

Exactly one HTTP request per documented category. No article-detail calls,
DB writes, AI calls, service restart, or credential output.
"""
from __future__ import annotations
import os
import requests

BASE = "https://api.tradingviewapi.com"
CATEGORIES = ("bond","crypto","economic","etf","forex","futures","index","stock")
key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
if not key:
    raise SystemExit("TRADINGVIEW_API_KEY_MISSING")

headers = {"Authorization": f"Bearer {key}"}
for category in CATEGORIES:
    url = f"{BASE}/api/news/{category}"
    r = requests.get(url, headers=headers, timeout=20)
    print(f"TV_CATEGORY={category} STATUS={r.status_code}", flush=True)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        items = []
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    data_keys = sorted(data.keys()) if isinstance(data, dict) else []
    item_keys = sorted(items[0].keys()) if items and isinstance(items[0], dict) else []
    print(
        f"TV_CATEGORY_RESULT={category} COUNT={len(items)} "
        f"TOP_KEYS={','.join(top_keys)} DATA_KEYS={','.join(data_keys)} "
        f"FIRST_ITEM_KEYS={','.join(item_keys)}",
        flush=True,
    )
print("TRADINGVIEW_CATEGORY_TEST_COMPLETE CALLS=8", flush=True)
