"""Cached read-only identity mapping from the existing Neon market_instruments table."""
import os
import threading
import time

from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.analysis.news.stock_identity import (
    _VERIFIED, news_snapshot_names, normalize_us_ticker, resolve_us_identity,
)

_LOCK = threading.Lock()
_ROWS = ()
_UPDATED = 0.0
_TTL = 600


def _ticker(value):
    value = str(value or "").strip().upper()
    if value.endswith(".K"):
        value = value[:-2]
    return normalize_us_ticker(value)


def _unique(values):
    result, seen = [], set()
    for raw in values:
        value = str(raw or "").strip()
        if value and value.casefold() not in seen:
            result.append(value)
            seen.add(value.casefold())
    return result


def _registry():
    global _ROWS, _UPDATED
    now = time.monotonic()
    if _UPDATED and now - _UPDATED < _TTL:
        return _ROWS
    with _LOCK:
        if _UPDATED and now - _UPDATED < _TTL:
            return _ROWS
        url = os.environ.get("NEWS_DATABASE_URL", "").strip()
        if url:
            try:
                import psycopg
                with psycopg.connect(url, connect_timeout=3) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT symbol,display_name,news_name,company_key,identity_status "
                            "FROM public.market_instruments WHERE market='US' AND is_active=true"
                        )
                        _ROWS = tuple(dict(ticker=_ticker(symbol),
                                           label=str(label or "").strip(),
                                           news=str(news or "").strip(),
                                           key=str(key or "").strip(),
                                           status=str(status or "").strip())
                                      for symbol, label, news, key, status in cur.fetchall())
            except Exception as exc:
                print("[news-identity] read_failed="+type(exc).__name__, flush=True)
        _UPDATED = time.monotonic()
        return _ROWS


def resolve_us_news_identity(name, symbol=None):
    """Never merge different ticker identities or unverified company names."""
    name = str(name or "").strip()
    ticker = _ticker(symbol)
    rows = _registry()
    matches = [r for r in rows if r["ticker"] == ticker] if ticker else [
        r for r in rows if r["label"].casefold() == name.casefold()
    ]
    if not matches and not ticker:
        matches = [r for r in rows if r["news"].casefold() == name.casefold()
                   and r["status"] == "verified"]
        if len({r["key"] for r in matches}) != 1:
            matches = []
    # Exchange-suffixed and plain symbols normalize to the same ticker.
    # Prefer an explicitly verified DB name pair over an unreviewed duplicate.
    exact_verified = [r for r in matches
                      if r["status"] == "verified"
                      and r["label"].casefold() == name.casefold()]
    verified_matches = [r for r in matches if r["status"] == "verified"]
    if exact_verified:
        matches = exact_verified
    elif verified_matches:
        matches = verified_matches
    row = matches[0] if len(matches) == 1 or (
        matches and len({r["key"] for r in matches}) == 1
    ) else None
    basic = resolve_us_identity(name, ticker or None)
    if (ticker and basic["status"] != "verified"
            and resolve_us_identity(name)["status"] == "verified"
            and not (row and row["status"] == "verified"
                     and row["label"].casefold() == name.casefold())):
        # A mismatched known ticker must never steal another firm's news.
        return dict(company_key=basic["company_key"], ticker="", news_name=name,
                    status="pending", search_terms=[name], snapshot_names=[name])
    if row and (row["label"].casefold() != name.casefold()
                and row["news"].casefold() != name.casefold()
                and not (row["status"] == "verified"
                         and basic["status"] == "verified"
                         and basic["company_key"] == row["key"])):
        row = None
    verified = (bool(row and row["status"] == "verified")
                or basic["status"] == "verified")
    key = row["key"] if row else basic["company_key"]
    canonical = (row["news"] if row and row["status"] == "verified"
                 else basic["news_name"] if basic["status"] == "verified"
                 else name)
    ticker = ticker or (row["ticker"] if row else "") or basic["ticker"]
    catalog = STOCK_UNIVERSE.get("미국", {})
    matching_catalog = []
    for label, terms in catalog.items():
        if canonical.casefold() == label.casefold() or name.casefold() == label.casefold():
            matching_catalog.append(label)
        elif ticker and ticker in {_ticker(t) for t in terms}:
            matching_catalog.append(label)
        elif not ticker and name.casefold() in {str(t).casefold() for t in terms}:
            matching_catalog.append(label)
    entry = matching_catalog[0] if len(set(matching_catalog)) == 1 else None
    if not ticker:
        exact_codes = [code for code, (_key, _label, known_names) in _VERIFIED.items()
                       if name.casefold() in {n.casefold() for n in known_names}]
        if len(exact_codes) == 1:
            ticker = exact_codes[0]
    if entry and not ticker:
        ticker = next((_ticker(t) for t in catalog[entry] if _ticker(t)), "")
    if entry and not verified and (row is None or row["status"] != "verified"):
        # The catalog provides search aliases, not permission to merge DB records.
        canonical = entry
    siblings = [r for r in rows if verified and key and r["key"] == key
                and r["status"] == "verified"]
    terms = [name, canonical, ticker]
    if row:
        terms.extend((row["label"], row["news"]))
    if entry:
        terms.extend((entry, *catalog[entry]))
    if verified:
        for known_ticker, (known_key, _label, known_names) in _VERIFIED.items():
            if known_key == key:
                terms.extend((known_ticker, *known_names))
        for sibling in siblings:
            terms.extend((sibling["label"], sibling["news"]))
    saved_names = [name]
    if verified:
        # Snapshot fallback must use the user's ticker, not an inferred
        # alternate share-class ticker (GOOG vs GOOGL).
        saved_names.extend(news_snapshot_names(name, _ticker(symbol) or None))
        saved_names.extend([canonical])
        for sibling in siblings:
            saved_names.extend((sibling["label"], sibling["news"]))
    return dict(company_key=key, ticker=ticker, news_name=canonical,
                status="verified" if verified else "pending",
                search_terms=_unique(terms),
                snapshot_names=_unique(saved_names))
