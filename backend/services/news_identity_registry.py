"""Resolve US news identities from the reviewed local ticker catalog only.

No database registry or remote identity lookup is used.
"""
from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.analysis.news.stock_identity import (
    _VERIFIED, news_snapshot_names, normalize_us_ticker, resolve_us_identity,
)


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


def resolve_us_news_identity(name, symbol=None):
    """Never merge different ticker identities or unverified company names."""
    name = str(name or "").strip()
    ticker = _ticker(symbol)
    basic = resolve_us_identity(name, ticker or None)
    name_basic = resolve_us_identity(name)

    if (ticker and basic["status"] != "verified"
            and name_basic["status"] == "verified"):
        return dict(company_key=basic["company_key"], ticker="", news_name=name,
                    status="pending", search_terms=[name], snapshot_names=[name])

    verified = basic["status"] == "verified"
    key = basic["company_key"]
    canonical = basic["news_name"] if verified else name
    ticker = ticker or basic["ticker"]

    catalog = STOCK_UNIVERSE.get("미국", {})
    matching_catalog = []
    for label, terms in catalog.items():
        if canonical.casefold() == label.casefold() or name.casefold() == label.casefold():
            matching_catalog.append(label)
        elif ticker and ticker in {_ticker(term) for term in terms}:
            matching_catalog.append(label)
        elif not ticker and name.casefold() in {str(term).casefold() for term in terms}:
            matching_catalog.append(label)
    entry = matching_catalog[0] if len(set(matching_catalog)) == 1 else None
    if not ticker:
        exact_codes = [
            code for code, (known_key, _label, known_names) in _VERIFIED.items()
            if name.casefold() in {value.casefold() for value in known_names}
            and (not key or known_key == key)
        ]
        if len(exact_codes) == 1:
            ticker = exact_codes[0]
    if entry and not ticker:
        ticker = next((_ticker(value) for value in catalog[entry] if _ticker(value)), "")
    if entry and not verified:
        canonical = entry

    terms = [name, canonical, ticker]
    if entry:
        terms.extend((entry, *catalog[entry]))
    saved_names = [name]
    if verified:
        saved_names.extend(news_snapshot_names(name, ticker or None))
        saved_names.append(canonical)
        for known_ticker, (known_key, _label, known_names) in _VERIFIED.items():
            if known_key == key:
                terms.extend((known_ticker, *known_names))
                saved_names.extend(known_names)
    return dict(company_key=key, ticker=ticker, news_name=canonical,
                status="verified" if verified else "pending",
                search_terms=_unique(terms),
                snapshot_names=_unique(saved_names))
