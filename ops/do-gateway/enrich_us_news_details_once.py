"""Explicit one-shot detail enrichment of the existing TradingView news cache.

One-shot gateway run processes all remaining article IDs by default; optional explicit cap.
Does NOT call the list API, run AI, or start systemd services.
Never run this automatically in the general news refresh.
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
from pathlib import Path

# The gateway stages this script outside the application repository.
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.providers.tradingview_news_bundle import CACHE_PATH, _write
from backend.providers.tradingview_news_detail import enrich_articles
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot
from backend.services.r2_news_uploader import upload_file


def main():
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
        # No arbitrary ten-item cap. Skip details already checked and dedupe
        # article IDs inside enrich_articles; stop on upstream rate limiting.
        raw_budget = os.environ.get("NEWS_DETAIL_REQUEST_BUDGET", "").strip()
        budget = len(items) if not raw_budget else int(raw_budget)
        if budget < 1:
            raise SystemExit("NEWS_DETAIL_REQUEST_BUDGET must be positive")
        updated, stats = enrich_articles(items, max_requests=budget)
        print("NEWS_DETAILS_STATS=" + json.dumps(stats, separators=(",", ":")), flush=True)
        # Save body/description/summary statuses even when a provider supplies
        # only body content or denies access. This prevents repeated paid calls.
        if not stats["requested"] and not stats["blocked"]:
            print("NEWS_DETAILS_NOTHING_TO_SAVE", flush=True)
            return
        state["items"] = updated
        _write(state)
        # Only permitted screen-facing fields go into the shared JSON.
        snapshot = write_snapshot(updated)
        env_path = Path("/var/lib/gaemigtp-news/r2.env")
        if not env_path.is_file():
            raise SystemExit("R2_ENV_MISSING_LOCAL_CACHE_SAVED")
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            if raw_line and "=" in raw_line:
                env_key, env_value = raw_line.split("=", 1)
                if env_key in {"R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}:
                    os.environ[env_key] = env_value
        if not upload_file(NEWS_PAGE_PATH):
            raise SystemExit("R2_UPLOAD_FAILED_LOCAL_CACHE_SAVED")
        print("NEWS_DETAILS_R2_ITEMS=%d" % snapshot["count"], flush=True)


if __name__ == "__main__":
    main()
