"""Market-menu issue titles from the existing Neon news and 24h processed-result store.

Only source-grounded titles are produced. This path never re-fetches articles,
opens article bodies, or invokes the full central stock-news analysis.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .business_material_events import business_material_title_and_tags
from .company_critical_events import company_critical_title_and_tags
from .flow_material_events import flow_material_title_and_tags
from .issue_briefs import market_material_title_and_tags
from .news_processed_results_store import (
    read_issue_headlines, read_news_metadata_for_stocks, save_issue_headlines,
)
from .news_result import _central_stock_mentioned, _mentions_competing_stock, _stock_owned_material

_ISSUE_CACHE = {}
_ISSUE_PENDING = {}
_ISSUE_LOCK = threading.Lock()
_ISSUE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market-issues")
_ISSUE_TTL = 15 * 60
_EMPTY_TTL = 3 * 60
_MAX_ITEMS = 20
_MAX_KEYS = 80


def _issue_from_metadata(stock_name, articles):
    """Use the same validated company/market event extractors as central news.

    An explicit company mention in the article title is required. Reject
    mixed-company titles to avoid claiming another company's event.
    """
    for article in (articles or [])[:100]:
        title = str(article.get("title") or "")
        description = str(article.get("description") or "")
        if not _central_stock_mentioned(title, stock_name):
            continue
        if _mentions_competing_stock(title, stock_name):
            continue

        for extractor in (
            company_critical_title_and_tags,
            business_material_title_and_tags,
            flow_material_title_and_tags,
        ):
            headline, tags, _direction = _stock_owned_material(title, stock_name, extractor)
            if not tags:
                headline, tags, _direction = _stock_owned_material(
                    description, stock_name, extractor,
                )
            if headline and tags:
                return {
                    "headline": headline, "tags": list(dict.fromkeys(tags))[:6],
                    "stock_name": stock_name, "source_url": article.get("url") or "",
                    "source_published_at": article.get("published_at") or "",
                    "evidence_source": "news_title_description",
                }

        headline, tags = market_material_title_and_tags(title)
        if headline and tags:
            return {
                "headline": headline, "tags": list(dict.fromkeys(tags))[:6],
                "stock_name": stock_name, "source_url": article.get("url") or "",
                "source_published_at": article.get("published_at") or "",
                "evidence_source": "news_title_description",
            }
    return None


def _prepare_batch(market, rows):
    """One source query and one processed-result write for the missing stocks."""
    completed = {}
    entries = []
    try:
        stock_news = read_news_metadata_for_stocks(rows)
        if stock_news is None:
            raise RuntimeError("news_metadata_unavailable")
        for row in rows:
            evidence = _issue_from_metadata(row["name"], stock_news.get(row["symbol"], []))
            headline = str((evidence or {}).get("headline") or "").strip()
            key = (market, row["symbol"], row["name"])
            completed[key] = (time.monotonic(), headline)
            if headline:
                entries.append((row, {**evidence, "symbol": row["symbol"], "market": market}))
    except Exception as exc:
        print(f"[market issue] batch unavailable: {type(exc).__name__}", flush=True)
        completed = {
            (market, row["symbol"], row["name"]): (time.monotonic(), "")
            for row in rows
        }
    finally:
        # Release browser polling immediately. A slow DB write must not hold
        # the displayed title hostage after the news has been processed.
        with _ISSUE_LOCK:
            _ISSUE_CACHE.update(completed)
            for row in rows:
                _ISSUE_PENDING.pop((market, row["symbol"], row["name"]), None)
    if entries:
        save_issue_headlines(market, entries)


def _valid_row(market, item):
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    symbol = str(item.get("symbol") or "").strip().upper()
    symbol_pattern = r"[0-9]{6}" if market == "kr" else r"[A-Z0-9.^_-]{1,32}"
    if not name or len(name) > 60 or not re.fullmatch(symbol_pattern, symbol):
        return None
    return {"name": name, "symbol": symbol}


def get_market_issue_headlines(market, items):
    """Serve cached headings at once; batch-load and prepare missing stocks."""
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if any(row is None for row in rows):
        raise ValueError("invalid_stock_rows")

    now = time.monotonic()
    with _ISSUE_LOCK:
        missed = [
            row for row in rows
            if (market, row["symbol"], row["name"]) not in _ISSUE_PENDING
            and (
                (market, row["symbol"], row["name"]) not in _ISSUE_CACHE
                or now - _ISSUE_CACHE[(market, row["symbol"], row["name"])][0]
                >= (_ISSUE_TTL if _ISSUE_CACHE[(market, row["symbol"], row["name"])][1] else _EMPTY_TTL)
            )
        ]

    # Read many cached results with one DB call; no second per-stock query.
    if missed:
        persisted = read_issue_headlines(market, missed)
        with _ISSUE_LOCK:
            for row in missed:
                key = (market, row["symbol"], row["name"])
                headline = persisted.get(_persisted_key(market, row))
                if headline and key not in _ISSUE_PENDING:
                    _ISSUE_CACHE[key] = (time.monotonic(), headline)

    results = []
    with _ISSUE_LOCK:
        queued = []
        now = time.monotonic()
        for row in rows:
            key = (market, row["symbol"], row["name"])
            cached = _ISSUE_CACHE.get(key)
            ttl = _ISSUE_TTL if cached and cached[1] else _EMPTY_TTL
            fresh = cached and now - cached[0] < ttl
            if not fresh and key not in _ISSUE_PENDING:
                queued.append(row)
        if queued and len(_ISSUE_CACHE) + len(_ISSUE_PENDING) + len(queued) <= _MAX_KEYS:
            future = _ISSUE_EXECUTOR.submit(_prepare_batch, market, queued)
            for row in queued:
                _ISSUE_PENDING[(market, row["symbol"], row["name"])] = future
        elif queued and len(_ISSUE_CACHE) >= _MAX_KEYS:
            for row in queued:
                _ISSUE_CACHE.pop((market, row["symbol"], row["name"]), None)
            future = _ISSUE_EXECUTOR.submit(_prepare_batch, market, queued)
            for row in queued:
                _ISSUE_PENDING[(market, row["symbol"], row["name"])] = future
        for row in rows:
            key = (market, row["symbol"], row["name"])
            cached = _ISSUE_CACHE.get(key)
            if key in _ISSUE_PENDING:
                status, headline = "pending", ""
            elif cached:
                status, headline = ("ready", cached[1]) if cached[1] else ("unavailable", "")
            else:
                status, headline = "unavailable", ""
            results.append({**row, "status": status, "headline": headline})
    return {
        "ok": True, "market": market, "items": results,
        "pending": any(row["status"] == "pending" for row in results),
    }


def _persisted_key(market, row):
    # Keep the DB key format shared with the processed-results store.
    from .news_processed_results_store import _key
    return _key(market, row)
