"""Read-only sidebar headlines from the shared 24-hour processed-news store.

The sidebar must never start news collection or analysis. Missing processed
briefs remain unavailable until the existing central-news workflow saves them.
"""
import os
import re
import time

from backend.analysis.news.catalog import canonical_us_news_name
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
    """Fill missing requested ranking titles from DO worker, without processing news."""
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
                    SELECT stock_name, result_payload->'issue_briefs'
                    FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name = ANY(%s)
                      AND result_limit=50 AND storyboard_limit=3
                      AND display_timezone='Asia/Seoul' AND expires_at>now()
                    """,
                    (market_name, names),
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

    # Match only verified US ticker/name variants; keep source ranking labels.
    # KR uses exactly its original keys and request path.
    names_per_row = [
        list(dict.fromkeys([
            row["name"],
            canonical_us_news_name(row["name"], symbol=row["symbol"])
            if market == "us" else row["name"],
        ]))
        for row in rows
    ]
    all_names = list(dict.fromkeys(name for names in names_per_row for name in names))
    existing = read_issue_briefs_batch(
        market, [{"name": name} for name in all_names])
    missing = list(dict.fromkeys(
        name for names in names_per_row
        if not any(_first_headline(existing.get(_key(market, n))) for n in names)
        for name in names
    ))
    worker_briefs = _read_worker_briefs(market, missing) if missing else {}
    results = []
    for row, names in zip(rows, names_per_row):
        headline = (
            next((_first_headline(existing.get(_key(market, n)))
                  for n in names if _first_headline(existing.get(_key(market, n)))), "")
            or next((_first_headline(worker_briefs.get(n))
                     for n in names if _first_headline(worker_briefs.get(n))), "")
        )
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
