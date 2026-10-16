"""Prepare missing ranking issue briefs outside the read-only sidebar endpoint.

Ranking results schedule bounded background work using the existing shared
news processor and existing 24-hour Neon processed-results storage.
No new collector, table, Redis service, or durable scheduler is created.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .news_processed_results_store import _key, read_issue_briefs_batch
from .news_result import get_shared_stock_news_result

_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ranking-news-prep")
_PENDING = set()
_RECENT = {}
_MAX_OUTSTANDING = 20
_EMPTY_RETRY_SECONDS = 60 * 60
_ERROR_RETRY_SECONDS = 5 * 60


def _prepare(market, name, key):
    success = False
    has_issue = False
    started = time.monotonic()
    try:
        result = get_shared_stock_news_result(
            name, market="국내" if market == "kr" else "미국",
            limit=50, storyboard_limit=3,
        )
        success = isinstance(result, dict) and result.get("_news_status") != "error"
        has_issue = success and any(
            isinstance(brief, dict) and str(brief.get("headline") or "").strip()
            for brief in (result.get("issue_briefs") or [])
        )
    except Exception as exc:
        print(f"[ranking prep] error market={market} type={type(exc).__name__}", flush=True)
    finally:
        with _LOCK:
            _PENDING.discard(key)
            _RECENT[key] = time.monotonic() + (
                _EMPTY_RETRY_SECONDS if success else _ERROR_RETRY_SECONDS
            )
        print(
            f"[ranking prep] completed market={market} status="
            f"{'ready' if has_issue else 'empty' if success else 'error'} "
            f"elapsed={time.monotonic()-started:.2f}s",
            flush=True,
        )


def schedule_ranking_news_preparation(market, items):
    """Queue at most 20 unique missing TOP-20 briefs with one active worker."""
    if market not in ("kr", "us") or not items or not os.getenv("NEWS_DATABASE_URL"):
        return
    rows = []
    seen = set()
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or len(name) > 60:
            continue
        key = _key(market, name)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name})
    if not rows:
        return

    existing = read_issue_briefs_batch(market, rows)
    now = time.monotonic()
    with _LOCK:
        for key, deadline in list(_RECENT.items()):
            if deadline <= now:
                _RECENT.pop(key, None)
        for row in rows:
            key = _key(market, row["name"])
            if key in existing or key in _PENDING or _RECENT.get(key, 0) > now:
                continue
            if len(_PENDING) >= _MAX_OUTSTANDING:
                break
            _PENDING.add(key)
            try:
                _POOL.submit(_prepare, market, row["name"], key)
            except RuntimeError:
                _PENDING.discard(key)
                break
