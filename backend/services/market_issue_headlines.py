"""Read-only sidebar headlines from the shared 24-hour processed-news store.

The sidebar must never start news collection or analysis. Missing processed
briefs remain unavailable until the existing central-news workflow saves them.
"""
import os
import re
import time

from .news_processed_results_store import _key, read_issue_briefs_batch
from .issue_briefs import grounded_issue_display_title

_MAX_ITEMS = 20


def _first_headline(briefs):
    for brief in briefs or []:
        headline = grounded_issue_display_title(brief)
        if headline and headline not in {"기사 주요 내용", "관련 이슈"}:
            return headline
    return ""


def _valid_row(market, item):
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    symbol = str(item.get("symbol") or "").strip().upper()
    pattern = r"[0-9]{6}" if market == "kr" else r"[A-Z0-9.^_-]{1,32}"
    if not name or len(name) > 60 or not re.fullmatch(pattern, symbol):
        return None
    return {"name": name, "symbol": symbol}


def _read_worker_briefs(market, names):
    """Use DO titles when at least as fresh as stored central briefs, without news processing."""
    market_name = {"kr": "국내", "us": "미국"}.get(market)
    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not market_name or not database_url or not names:
        return {}
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.stock_name, s.result_payload->'issue_briefs'
                    FROM public.news_processed_snapshots s
                    LEFT JOIN public.news_processed_results_24h prev
                      ON prev.result_type='stock_news_issue_briefs_v1'
                     AND prev.result_key=to_json(ARRAY[%s, s.stock_name])::text
                     AND prev.expires_at>now()
                    WHERE s.market=%s AND s.stock_name = ANY(%s)
                      AND s.result_limit=50 AND s.storyboard_limit=3
                      AND s.display_timezone='Asia/Seoul' AND s.expires_at>now()
                      AND (prev.created_at IS NULL OR s.processed_at >= prev.created_at)
                    """,
                    (market, market_name, names),
                )
                records = cur.fetchall()
        return {
            name: briefs for name, briefs in records
            if isinstance(briefs, list)
        }
    except Exception as exc:
        print("[market issue] worker snapshot read unavailable: "
              + type(exc).__name__, flush=True)
        return {}


def get_market_issue_headlines(market, items):
    started = time.monotonic()
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if any(row is None for row in rows):
        raise ValueError("invalid_stock_rows")

    # One database read for the entire ranking; never create background work.
    existing = read_issue_briefs_batch(market, rows)
    # Prefer a newer DO result when it has a grounded headline.
    # The SQL excludes DO snapshots older than the saved central-news brief.
    # Empty DO issues must not erase an existing valid 24-hour issue.
    worker_briefs = _read_worker_briefs(market, [row["name"] for row in rows])
    results = []
    for row in rows:
        headline = (_first_headline(worker_briefs.get(row["name"]))
                    or _first_headline(existing.get(_key(market, row["name"]))))
        results.append({
            **row, "status": "ready" if headline else "unavailable",
            "headline": headline,
        })
    print(
        f"[market issue timing] stage=response market={market} rows={len(rows)} "
        f"ready={sum(bool(row['headline']) for row in results)} "
        f"elapsed={time.monotonic()-started:.2f}s",
        flush=True,
    )
    return {"ok": True, "market": market, "items": results, "pending": False}
