"""Lightweight TradingView US-news collector.

This loop is intentionally independent from Neon and AI. It only keeps the
shared local TradingView cache fresh; the existing stock-news pipeline can read
that cache without causing per-ticker API fan-out.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from backend.providers import tradingview_news_bundle
from backend.services.r2_news_uploader import upload_file
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot

CHECK_INTERVAL_SECONDS = 60
_last_uploaded_digest = None


def run_once():
    if not os.environ.get("TRADINGVIEW_API_KEY", "").strip():
        print("[tradingview-news-worker] missing TRADINGVIEW_API_KEY", flush=True)
        return 0
    items = tradingview_news_bundle.refresh_news_cache()
    global _last_uploaded_digest
    snapshot = write_snapshot(items)
    print(
        "[tradingview-news-worker] page_snapshot items=%s" % snapshot["count"],
        flush=True,
    )
    if snapshot["count"] > 0:
        digest_payload = {
            "source": snapshot["source"],
            "taxonomy": snapshot["taxonomy"],
            "count": snapshot["count"],
            "category_counts": snapshot["category_counts"],
            "items": snapshot["items"],
        }
        digest = hashlib.sha256(
            json.dumps(
                digest_payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if digest != _last_uploaded_digest and upload_file(NEWS_PAGE_PATH):
            _last_uploaded_digest = digest
    return len(items)


def main():
    print(
        "[tradingview-news-worker] started desks=%s mode=%s"
        % (
            ",".join(tradingview_news_bundle.CATEGORIES),
            os.environ.get("TRADINGVIEW_NEWS_MODE", "basic_test"),
        ),
        flush=True,
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            print(
                "[tradingview-news-worker] error=%s" % type(exc).__name__,
                flush=True,
            )
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
