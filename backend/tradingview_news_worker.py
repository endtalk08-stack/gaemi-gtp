"""Lightweight TradingView US-news collector.

This loop is intentionally independent from Neon and AI. It only keeps the
shared local TradingView cache fresh; the existing stock-news pipeline can read
that cache without causing per-ticker API fan-out.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import time

from backend.providers import tradingview_news_bundle
from backend.providers.tradingview_news_detail import enrich_articles
from backend.services.r2_news_uploader import upload_file
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, select_articles, write_snapshot

CHECK_INTERVAL_SECONDS = 60
# Fail closed until a bounded detail-API budget is set before collection starts.
MAX_DETAIL_REQUESTS_PER_RUN = 20
MAX_DETAIL_REQUESTS_PER_UTC_DAY = 40
_last_uploaded_digest = None
_archived_file_hashes = set()


def archive_existing_news_snapshot():
    """Archive paid news content BEFORE a newer public index can replace it.

    Only uses existing local/R2 data; no TradingView/API calls.
    Fail closed: a failed archive must not be followed by an index overwrite.
    """
    path = NEWS_PAGE_PATH
    if not path.is_file() or path.is_symlink():
        return
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest in _archived_file_hashes:
        return
    # Content-addressed; a restarted process cannot overwrite an old archive.
    try:
        data = json.loads(body)
        if data.get("ok") is not True or not isinstance(data.get("items"), list):
            raise ValueError("invalid_news_snapshot_before_archive")
        stamp = dt.datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("archive_timestamp_timezone_missing")
        day = stamp.astimezone(dt.timezone.utc).strftime("%Y%m%d")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid_news_snapshot_before_archive") from exc
    archive_key = f"news/archive/{day}/{digest}.json"
    if not upload_file(path, object_key=archive_key):
        raise RuntimeError("news_archive_failed_refuse_latest_overwrite")
    _archived_file_hashes.add(digest)


def _bounded_detail_budget():
    try:
        requested = int(os.environ.get("NEWS_DETAIL_REQUEST_BUDGET", "20"))
    except ValueError:
        return 0
    return max(0, min(requested, MAX_DETAIL_REQUESTS_PER_RUN))


def enrich_cached_articles(items):
    """Reuse existing Korean detail parser with a persistent daily API cap.

    Default to 20 details for each of the two approved collection windows.
    Explicit NEWS_DETAIL_REQUEST_BUDGET=0 disables detail calls.
    """
    requested = _bounded_detail_budget()
    allow_publication = os.environ.get("NEWS_DETAIL_PUBLICATION_ALLOWED", "1").strip() == "1"
    if not requested and not allow_publication:
        return items
    # Do not spend detail requests outside the approved premarket/afterhours slots.
    session, slot = tradingview_news_bundle._basic_slot(time.time())
    if not slot:
        return items
    cache = tradingview_news_bundle.CACHE_PATH
    if not cache.is_file() or cache.is_symlink() or cache.with_suffix(".lock").is_symlink():
        return items
    with cache.with_suffix(".lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = json.loads(cache.read_text(encoding="utf-8"))
        if state.get("feed_version") != tradingview_news_bundle.FEED_VERSION:
            return items
        if (state.get("last_slot") != slot
                or state.get("detail_last_slot") == slot
                or "overall" not in (state.get("ok_categories") or [])
                or state.get("failed_categories")):
            return items
        current = state.get("items", [])
        if not isinstance(current, list):
            return items
        # Apply the same event filter and duplicate removal before paid detail lookups.
        current = select_articles(current)
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        used = max(0, int(state.get("detail_daily_requests", 0) or 0)) if state.get("detail_daily_day") == day else 0
        halted_today = state.get("detail_halted_day") == day
        budget = 0 if halted_today else min(requested, max(0, MAX_DETAIL_REQUESTS_PER_UTC_DAY - used))
        updated, stats = enrich_articles(current, max_requests=budget)
        if allow_publication:
            for row in updated:
                if row.get("detail_body"):
                    # Owner confirmed publication rights; keep provider metadata.
                    row["detail_publication_allowed"] = True
                    row["detail_rights_confirmed"] = True
        state["items"] = updated
        # Process at most once after a successful list refresh in this slot.
        state["detail_last_slot"] = slot
        state["detail_daily_day"] = day
        state["detail_daily_requests"] = used + stats["requested"]
        if stats.get("halted_http_status"):
            state["detail_halted_day"] = day
            state["detail_halted_status"] = stats["halted_http_status"]
        tradingview_news_bundle._write(state)
        print("[tradingview-news-worker] detail_stats=%s" %
              json.dumps({**stats, "daily_used": state["detail_daily_requests"],
                          "daily_cap": MAX_DETAIL_REQUESTS_PER_UTC_DAY}, sort_keys=True), flush=True)
        return updated


def run_once():
    if not os.environ.get("TRADINGVIEW_API_KEY", "").strip():
        print("[tradingview-news-worker] missing TRADINGVIEW_API_KEY", flush=True)
        return 0
    # First protect the last paid result: never make new API requests when
    # the existing saved article texts cannot be archived safely.
    archive_existing_news_snapshot()
    items = select_articles(tradingview_news_bundle.refresh_news_cache())
    items = enrich_cached_articles(items)
    global _last_uploaded_digest
    # Archive the updated snapshot before making it the public latest.
    snapshot = write_snapshot(items)
    archive_existing_news_snapshot()
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
