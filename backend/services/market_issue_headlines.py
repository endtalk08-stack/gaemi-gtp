"""Read-only sidebar headlines from DigitalOcean's 24-hour processed snapshots.

The sidebar must never collect, process, or save news. No alternate Render
issue store is queried when DigitalOcean has no matching processed brief.
"""
import os
import re
import time

from .news_identity_registry import resolve_us_news_identity
from .issue_briefs import grounded_issue_display_title
from .news_freshness import clean_us_snapshot

_MAX_ITEMS = 20


def _first_headline(briefs):
    for brief in briefs or []:
        headline = grounded_issue_display_title(brief)
        if headline and headline not in {"기사 주요 내용", "관련 이슈"}:
            return headline
    return ""


def _first_ai_headline(snapshot):
    """Show source-cited US code-fact issues; never the deprecated price_reason."""
    if not isinstance(snapshot, dict):
        return ""
    for brief in snapshot.get("issue_briefs") or []:
        if not isinstance(brief, dict):
            continue
        sources = brief.get("source_articles")
        if not isinstance(sources, list) or not any(
            isinstance(item, dict)
            and str(item.get("url") or "").startswith(("https://", "http://"))
            for item in sources
        ):
            continue
        title = str(brief.get("headline") or "").strip()
        if title and title not in {"기사 주요 내용", "관련 이슈"}:
            return title
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
                    SELECT stock_name, jsonb_build_object(
                        'issue_briefs', result_payload->'issue_briefs',
                        '_ai_issue_briefs', result_payload->'_ai_issue_briefs',
                        '_code_fact_extraction_version', result_payload->'_code_fact_extraction_version',
                        'price_reason', result_payload->'price_reason'
                    )
                    FROM public.news_processed_snapshots
                    WHERE market=%s AND stock_name = ANY(%s)
                      AND result_limit=50 AND storyboard_limit=3
                      AND display_timezone='Asia/Seoul' AND expires_at>now()
                    """,
                    (market_name, names),
                )
                records = cur.fetchall()
        return {
            name: (clean_us_snapshot(payload) if market == "us" else payload)
            for name, payload in records if isinstance(payload, dict)
        }
    except Exception as exc:
        print("[market issue] worker snapshot read unavailable: "
              + type(exc).__name__, flush=True)
        return {}


def get_market_issue_headlines(market, items, *, skip_invalid=False):
    started = time.monotonic()
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if not skip_invalid and any(row is None for row in rows):
        # Keep explicit /market/issue-headlines requests strictly validated.
        raise ValueError("invalid_stock_rows")

    # Rank feeds can occasionally contain a malformed symbol. Read only the
    # valid rows from Neon, then return a result for every original position.
    # This prevents one invalid stock from blanking all 20 sidebar headlines.
    names_per_row = [
        (resolve_us_news_identity(row["name"], symbol=row["symbol"])["snapshot_names"]
         if market == "us" else [row["name"]])
        if row is not None else []
        for row in rows
    ]
    all_names = list(dict.fromkeys(name for names in names_per_row for name in names))
    worker_briefs = _read_worker_briefs(market, all_names) if all_names else {}
    results = []
    for original, row, names in zip(items, rows, names_per_row):
        if row is None:
            # Preserve the ranking position without guessing a stock identity.
            source = original if isinstance(original, dict) else {}
            results.append({
                "name": str(source.get("name") or "").strip(),
                "symbol": str(source.get("symbol") or "").strip().upper(),
                "status": "invalid",
                "headline": "",
            })
            continue
        # The US worker saves source-backed code facts, not price_reason.
        # _read_worker_briefs already restricts them to original news within 24h.
        if market == "us":
            headline = next((
                title for name in names
                for title in [_first_ai_headline(worker_briefs.get(name))]
                if title
            ), "")
        else:
            # Domestic behavior and existing list-only callers remain unchanged.
            headline = next((
                _first_headline(
                    worker_briefs.get(name) if isinstance(worker_briefs.get(name), list)
                    else (worker_briefs.get(name) or {}).get("issue_briefs")
                )
                for name in names
                if _first_headline(
                    worker_briefs.get(name) if isinstance(worker_briefs.get(name), list)
                    else (worker_briefs.get(name) or {}).get("issue_briefs")
                )
            ), "")
        results.append({
            **row, "status": "ready" if headline else "unavailable",
            "headline": headline,
        })
    invalid_count = sum(row is None for row in rows)
    print(
        f"[market issue timing] stage=response market={market} rows={len(rows)} "
        f"ready={sum(bool(row['headline']) for row in results)} "
        f"invalid={invalid_count} "
        f"elapsed={time.monotonic()-started:.2f}s",
        flush=True,
    )
    return {"ok": True, "market": market, "items": results, "pending": False}
