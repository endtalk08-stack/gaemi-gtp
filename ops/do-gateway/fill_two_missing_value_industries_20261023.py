"""One-shot exact ticker sector backfill for existing US trading-value Top 20.
Calls the reviewed live provider and updates only missing industry labels.
"""
import os
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.kiwoom_us_value_collector import _fill_verified_fallback_sectors

dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
if not dsn:
    print("US_VALUE_INDUSTRY_BACKFILL=no_database", flush=True)
    raise SystemExit(2)
n = _fill_verified_fallback_sectors(dsn)
print("US_VALUE_INDUSTRY_BACKFILL_UPDATED=" + str(n), flush=True)
