"""Explicit one-shot detail enrichment of the existing TradingView news cache.

Usage requires an intentional invocation with NEWS_DETAIL_REQUEST_BUDGET=1..10.
Does NOT call the list API, run AI, or start systemd services.
Never run this automatically in the general news refresh.
"""
from __future__ import annotations

import fcntl
import json
import os

from backend.providers.tradingview_news_bundle import CACHE_PATH, _write
from backend.providers.tradingview_news_detail import enrich_articles
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot
from backend.services.r2_news_uploader import upload_file


def main():
    raw = os.environ.get("NEWS_DETAIL_REQUEST_BUDGET", "0").strip()
    budget = int(raw)
    if not 1 <= budget <= 10:
        raise SystemExit("NEWS_DETAIL_REQUEST_BUDGET must be 1..10 (explicit approval)")
    if not os.environ.get("TRADINGVIEW_API_KEY", "").strip():
        raise SystemExit("TRADINGVIEW_API_KEY not configured")
    if not CACHE_PATH.exists() or CACHE_PATH.is_symlink():
        raise SystemExit("existing news cache not found")
    lock_path = CACHE_PATH.with_suffix(".lock")
    if lock_path.is_symlink():
        raise SystemExit("unsafe_news_cache_lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        items = state.get("items")
        if not isinstance(items, list) or not items:
            raise SystemExit("empty_existing_news_cache")
        updated, stats = enrich_articles(items, max_requests=budget)
        print("NEWS_DETAILS_STATS=" + json.dumps(stats, separators=(",", ":")), flush=True)
        if not stats["described"]:
            print("NEWS_DETAILS_NO_NEW_DESCRIPTIONS_R2_UNCHANGED", flush=True)
            return
        state["items"] = updated
        _write(state)
        snapshot = write_snapshot(updated)
        # Upload only the normal screen-facing snapshot: never raw article bodies.
        upload_file(NEWS_PAGE_PATH)
        print("NEWS_DETAILS_R2_ITEMS=%d" % snapshot["count"], flush=True)


if __name__ == "__main__":
    main()
