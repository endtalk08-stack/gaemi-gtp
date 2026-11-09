"""One-shot collection of cached TradingView news details and R2 publishing.
Operator-approved; no service start, scheduler activation, or unrelated data writes.
"""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.tradingview_news_bundle import CACHE_PATH
from backend.tradingview_news_worker import enrich_cached_articles
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot
from backend.services.r2_news_uploader import upload_file

UNITS = ("gaemigtp-news.service", "gaemigtp-tradingview-news.service")

def inactive(unit):
    p = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=8)
    return p.stdout.strip() == "inactive"

def main():
    if any(not inactive(unit) for unit in UNITS):
        raise SystemExit("NEWS_COLLECT_ABORT_SERVICE_NOT_STOPPED")
    if not os.getenv("TRADINGVIEW_API_KEY", "").strip():
        raise SystemExit("NEWS_COLLECT_ABORT_MISSING_KEY")
    if not CACHE_PATH.is_file() or CACHE_PATH.is_symlink():
        raise SystemExit("NEWS_COLLECT_ABORT_CACHE_MISSING")
    state = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    items = state.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit("NEWS_COLLECT_ABORT_CACHE_EMPTY")
    before = sum(bool(x.get("detail_body")) for x in items if isinstance(x, dict))
    os.environ["NEWS_DETAIL_REQUEST_BUDGET"] = str(min(30, len(items)))
    os.environ["NEWS_DETAIL_PUBLICATION_ALLOWED"] = "1"
    updated = enrich_cached_articles(items)
    after = sum(bool(x.get("detail_body")) for x in updated if isinstance(x, dict))
    print("NEWS_DETAIL_COUNTS=" + json.dumps({"cached": len(items), "before": before, "after": after}), flush=True)
    if after == 0:
        raise SystemExit("NEWS_COLLECT_ABORT_NO_BODIES")
    if any(not inactive(unit) for unit in UNITS):
        raise SystemExit("NEWS_COLLECT_ABORT_SERVICE_STATE_CHANGED")
    snapshot = write_snapshot(updated)
    env = pathlib.Path("/var/lib/gaemigtp-news/r2.env")
    if not env.is_file() or env.is_symlink():
        raise SystemExit("NEWS_COLLECT_ABORT_R2_ENV")
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
                os.environ[k] = v
    if not upload_file(NEWS_PAGE_PATH):
        raise SystemExit("NEWS_COLLECT_R2_FAILED")
    print("NEWS_DETAIL_R2_RESULT=" + json.dumps({
        "count": snapshot["count"],
        "body_count": sum(bool(x.get("body")) for x in snapshot["items"]),
        "body_available_count": sum(bool(x.get("body_available")) for x in snapshot["items"]),
    }), flush=True)
    if any(not inactive(unit) for unit in UNITS):
        raise SystemExit("NEWS_COLLECT_ABORT_SERVICE_STATE_CHANGED_AFTER")
    print("NEWS_DETAIL_ONE_SHOT_COMPLETE_SERVICES_STOPPED=1", flush=True)

if __name__ == "__main__":
    main()
