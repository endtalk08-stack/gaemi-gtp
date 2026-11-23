"""Read-only sidebar headlines from DigitalOcean's 24-hour processed snapshots.

The sidebar must never collect, process, or save news. No alternate Render
issue store is queried when DigitalOcean has no matching processed brief.
"""
from .market_data_cache import MarketReadCache

_BRIEFS_CACHE = MarketReadCache(max_entries=64)
import re
import time

from .news_identity_registry import resolve_us_news_identity
from .news_result import get_shared_stock_news_result
from .issue_briefs import grounded_issue_display_title
from .news_freshness import _article_date, clean_us_snapshot, normalize_issue_mode

_MAX_ITEMS = 20


def _sidebar_title(value):
    """Apply the same ellipsis rule to every sidebar title source."""
    title = re.split(r"…|\.{3,}", str(value or "").strip(), maxsplit=1)[0].strip()
    return re.sub(r"\s*이슈\s*$", "", title).strip()


def _first_headline(briefs):
    for brief in briefs or []:
        headline = grounded_issue_display_title(brief)
        if headline and headline not in {"기사 주요 내용", "관련 이슈"}:
            return _sidebar_title(headline)
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
        # Sidebar-only: display the original, cited article headline up to
        # its first ellipsis. The central article headline is not modified.
        for item in sources:
            if not isinstance(item, dict) or not str(item.get("url") or "").startswith(
                ("https://", "http://")
            ):
                continue
            original_title = str(item.get("display_title") or item.get("title") or "").strip()
            if original_title:
                prefix = re.split(r"…|\.{3,}", original_title, maxsplit=1)[0].strip()
                if prefix:
                    return prefix
        title = str(brief.get("headline") or "").strip()
        if title and title not in {"기사 주요 내용", "관련 이슈"}:
            return _sidebar_title(title)
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
    """Build issue briefs through the shared Naver pipeline; cache in memory only."""
    market_name = {"kr": "국내", "us": "미국"}.get(market)
    if not market_name or not names:
        return {}
    result = {}
    for name in dict.fromkeys(str(value).strip() for value in names if str(value).strip()):
        def load(name=name):
            try:
                return get_shared_stock_news_result(
                    name, market=market_name, limit=50, storyboard_limit=3,
                )
            except Exception as exc:
                print("[market issue] live news unavailable: " + type(exc).__name__, flush=True)
                return {}
        result[name] = _BRIEFS_CACHE.get_or_load(
            (market, name), load, ttl=45, empty_ttl=10,
        )
    return result


def get_market_issue_headlines(market, items, *, skip_invalid=False, issue_mode="auto"):
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
        ([resolve_us_news_identity(row["name"], symbol=row["symbol"])["news_name"] or row["name"]]
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
            mode = normalize_issue_mode(issue_mode)
            def selected_snapshot(name):
                snapshot = worker_briefs.get(name)
                if not isinstance(snapshot, dict) or mode == "auto":
                    return snapshot
                channels = snapshot.get("issue_channels") or {}
                if mode == "both":
                    issues = (channels.get("code") or []) + (channels.get("ai") or [])
                else:
                    issues = channels.get(mode) or []
                return {**snapshot, "issue_briefs": issues}
            # Resolve all matching snapshot aliases by original article date,
            # rather than picking the first stock-name alias.
            dated_titles = []
            for name in names:
                snapshot = selected_snapshot(name)
                if not isinstance(snapshot, dict):
                    continue
                for brief in snapshot.get("issue_briefs") or []:
                    title = _first_ai_headline({"issue_briefs": [brief]})
                    if not title:
                        continue
                    dates = [
                        _article_date(source.get("published_at"))
                        for source in brief.get("source_articles") or []
                        if isinstance(source, dict)
                    ] if isinstance(brief, dict) else []
                    dates = [date for date in dates if date is not None]
                    if dates:
                        dated_titles.append((max(dates), title))
            headline = max(dated_titles, key=lambda item: item[0])[1] if dated_titles else ""
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
