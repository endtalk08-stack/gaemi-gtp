"""Refresh US-only overall TradingView news once and publish to existing R2 page.
One HTTP news-list request, no detail calls, no Neon, no AI.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.providers.tradingview_news_bundle import refresh_news_cache
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot

if not os.environ.get("TRADINGVIEW_API_KEY", "").strip():
    raise SystemExit("TRADINGVIEW_API_KEY_MISSING")

items = refresh_news_cache(force=True)
if not items:
    raise SystemExit("US_OVERALL_NEWS_EMPTY")
snapshot = write_snapshot(items)
print("US_OVERALL_NEWS_COUNT=%d" % snapshot["count"], flush=True)
print("US_OVERALL_NEWS_CATEGORIES=%s" % snapshot["category_counts"], flush=True)

env_path = Path("/var/lib/gaemigtp-news/r2.env")
if not env_path.is_file():
    raise SystemExit("R2_ENV_MISSING")
for raw in env_path.read_text(encoding="utf-8").splitlines():
    if raw and "=" in raw:
        key, value = raw.split("=", 1)
        if key in {"R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}:
            os.environ[key] = value

from backend.services.r2_news_uploader import upload_file

if not upload_file(NEWS_PAGE_PATH):
    raise SystemExit("US_OVERALL_R2_UPLOAD_FAILED")
print("US_OVERALL_R2_UPLOAD_OK", flush=True)
