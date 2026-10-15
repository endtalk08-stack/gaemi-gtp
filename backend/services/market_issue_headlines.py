"""Market sidebar displays titles from the same news issue briefs shown in chat.

The processed-news store holds the full visible brief for 24h. The sidebar reads
only its first headline; missing briefs use the existing shared news processor,
not a separate headline algorithm or collector.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .news_processed_results_store import _key, read_issue_briefs_batch
from .news_result import get_shared_stock_news_result

_ISSUE_CACHE = {}
_ISSUE_PENDING = {}
_ISSUE_LOCK = threading.Lock()
_ISSUE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="market-issues")
_ISSUE_TTL = 15 * 60
_EMPTY_TTL = 2 * 60
_MAX_ITEMS = 20
_MAX_KEYS = 80


def _first_headline(briefs):
    for brief in briefs or []:
        headline = str(brief.get("headline") or "").strip() if isinstance(brief, dict) else ""
        if headline and headline not in {"기사 주요 내용", "관련 이슈"}:
            return headline
    return ""


def _prepare_issue(key, stock_name, market):
    headline = ""
    failed = False
    try:
        result = get_shared_stock_news_result(
            stock_name, market="국내" if market == "kr" else "미국",
            limit=50, storyboard_limit=3,
        )
        failed = result.get("_news_status") == "error"
        if not failed:
            headline = _first_headline(result.get("issue_briefs"))
    except Exception as exc:
        failed = True
        print(f"[market issue] unavailable stock={stock_name} error={type(exc).__name__}", flush=True)
    with _ISSUE_LOCK:
        if not failed:
            _ISSUE_CACHE[key] = (time.monotonic(), headline)
        _ISSUE_PENDING.pop(key, None)


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
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if any(row is None for row in rows):
        raise ValueError("invalid_stock_rows")

    def row_key(row):
        return (market, row["symbol"], row["name"])

    # A single query reads all already-processed briefs for the ranking list.
    with _ISSUE_LOCK:
        now = time.monotonic()
        missing = [
            row for row in rows if row_key(row) not in _ISSUE_PENDING
            and (row_key(row) not in _ISSUE_CACHE
                 or now - _ISSUE_CACHE[row_key(row)][0]
                 >= (_ISSUE_TTL if _ISSUE_CACHE[row_key(row)][1] else _EMPTY_TTL))
        ]
    if missing:
        existing = read_issue_briefs_batch(market, missing)
        with _ISSUE_LOCK:
            for row in missing:
                key = row_key(row)
                headline = _first_headline(existing.get(_key(market, row["name"])))
                if headline and key not in _ISSUE_PENDING:
                    _ISSUE_CACHE[key] = (time.monotonic(), headline)

    with _ISSUE_LOCK:
        now = time.monotonic()
        needs_processing = []
        for row in rows:
            key = row_key(row)
            cached = _ISSUE_CACHE.get(key)
            ttl = _ISSUE_TTL if cached and cached[1] else _EMPTY_TTL
            if key not in _ISSUE_PENDING and (not cached or now - cached[0] >= ttl):
                needs_processing.append(row)

        active = {row_key(row) for row in rows}
        for old_key in sorted(_ISSUE_CACHE, key=lambda key: _ISSUE_CACHE[key][0]):
            if len(_ISSUE_CACHE) + len(_ISSUE_PENDING) + len(needs_processing) <= _MAX_KEYS:
                break
            if old_key not in active:
                _ISSUE_CACHE.pop(old_key, None)

        for row in needs_processing:
            if len(_ISSUE_CACHE) + len(_ISSUE_PENDING) >= _MAX_KEYS:
                break
            key = row_key(row)
            _ISSUE_PENDING[key] = _ISSUE_EXECUTOR.submit(
                _prepare_issue, key, row["name"], market,
            )

        results = []
        for row in rows:
            key = row_key(row)
            cached = _ISSUE_CACHE.get(key)
            if key in _ISSUE_PENDING:
                status, headline = "pending", ""
            elif cached:
                status, headline = (("ready", cached[1]) if cached[1]
                                    else ("unavailable", ""))
            else:
                status, headline = "unavailable", ""
            results.append({**row, "status": status, "headline": headline})
    return {"ok": True, "market": market, "items": results,
            "pending": any(row["status"] == "pending" for row in results)}
