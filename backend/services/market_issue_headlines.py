"""Read-only sidebar headlines from DigitalOcean's 24-hour processed snapshots.

The sidebar must never collect, process, or save news. No alternate Render
issue store is queried when DigitalOcean has no matching processed brief.
"""
import os
import re
import time

from backend.analysis.news.stock_identity import news_snapshot_names
from .issue_briefs import grounded_issue_display_title
from .ai_issue_display_store import read_ai_issue_briefs

_MAX_ITEMS = 20


def _first_headline(briefs):
    for brief in briefs or []:
        headline = str(brief.get("headline") or "").strip() if brief.get("source") == "ai_issue" else grounded_issue_display_title(brief)
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
        news_snapshot_names(row["name"], symbol=row["symbol"])
        if market == "us" else [row["name"]]
        for row in rows
    ]
    all_names = list(dict.fromkeys(name for names in names_per_row for name in names))
    ai_briefs = read_ai_issue_briefs(market, all_names)
    worker_briefs = _read_worker_briefs(market, all_names) if market != 'us' else {}
    results = []
    for row, names in zip(rows, names_per_row):
        headline = next(
            (_first_headline(ai_briefs.get(name) or worker_briefs.get(name))
             for name in names if _first_headline(ai_briefs.get(name) or worker_briefs.get(name))),
            "",
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
