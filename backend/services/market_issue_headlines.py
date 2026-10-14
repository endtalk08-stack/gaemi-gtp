"""Market-menu view of the same verified per-stock news result used by central chat.

Bounded background preparation prevents twenty simultaneous slow article fetches.
No browser-side collectors, guessed event labels, or AI calls are added here.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .news_result import get_shared_stock_news_result

_ISSUE_CACHE = {}
_ISSUE_PENDING = {}
_ISSUE_LOCK = threading.Lock()
_ISSUE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="market-issues")
_ISSUE_TTL = 15 * 60
_MAX_ITEMS = 20
_MAX_KEYS = 80


def _prepare_issue(key, stock_name, market):
    headline = ""
    try:
        result = get_shared_stock_news_result(
            stock_name, market="국내" if market == "kr" else "미국",
            limit=50, storyboard_limit=3,
        )
        for brief in result.get("issue_briefs") or []:
            candidate = str(brief.get("headline") or "").strip()
            if candidate and candidate not in {"기사 주요 내용", "관련 이슈"}:
                headline = candidate
                break
    except Exception as exc:
        print(f"[market issue] unavailable stock={stock_name} error={type(exc).__name__}", flush=True)
    with _ISSUE_LOCK:
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
    """Return one status per listed symbol; prepare missing results in background."""
    if market not in ("kr", "us") or not isinstance(items, list) or not 1 <= len(items) <= _MAX_ITEMS:
        raise ValueError("invalid_market_issue_request")
    rows = [_valid_row(market, item) for item in items]
    if any(row is None for row in rows):
        raise ValueError("invalid_stock_rows")
    results = []
    with _ISSUE_LOCK:
        for row in rows:
            key = (market, row["symbol"], row["name"])
            cached = _ISSUE_CACHE.get(key)
            fresh = cached and time.monotonic() - cached[0] < _ISSUE_TTL
            if not fresh and key not in _ISSUE_PENDING:
                if len(_ISSUE_PENDING) + len(_ISSUE_CACHE) < _MAX_KEYS:
                    _ISSUE_PENDING[key] = _ISSUE_EXECUTOR.submit(
                        _prepare_issue, key, row["name"], market,
                    )
                elif not cached:
                    results.append({**row, "status": "unavailable", "headline": ""})
                    continue
            if cached:
                results.append({
                    **row, "status": "ready" if cached[1] else "unavailable",
                    "headline": cached[1],
                })
            else:
                results.append({**row, "status": "pending", "headline": ""})
    return {
        "ok": True,
        "market": market,
        "items": results,
        "pending": any(row["status"] == "pending" for row in results),
    }
