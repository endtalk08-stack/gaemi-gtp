"""Read-only sidebar headlines from the shared 24-hour processed-news store.

The sidebar must never start news collection or analysis. Missing processed
briefs remain unavailable until the existing central-news workflow saves them.
"""
import re
import time

from .news_processed_results_store import _key, read_issue_briefs_batch

_MAX_ITEMS = 20


def _first_headline(briefs):
    for brief in briefs or []:
        headline = str(brief.get("headline") or "").strip() if isinstance(brief, dict) else ""
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


def get_market_issue_headlines(market, items):
    started = time.monotonic()
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if any(row is None for row in rows):
        raise ValueError("invalid_stock_rows")

    # One database read for the entire ranking; never create background work.
    existing = read_issue_briefs_batch(market, rows)
    results = []
    for row in rows:
        headline = _first_headline(existing.get(_key(market, row["name"])))
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
