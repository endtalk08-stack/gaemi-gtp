"""Kiwoom ticker/name matching for DigitalOcean local TOP20 (no DB calls).

Only exact ticker/name pairs observed in the provider's completed Top 20 may
be matched locally. New listings receive a ticker-specific key, never a fuzzy
alias of an existing company's news. Known ticker/name conflicts stay pending.
"""
from backend.analysis.news.stock_identity import (
    _VERIFIED, normalize_us_ticker, resolve_us_identity,
)

# Exact Kiwoom display labels for known ticker identities; not fuzzy matches.
_KIWOOM_KNOWN_LABELS = {
    "META": ("메타 플랫폼스(페이스북)",),
    "GOOGL": ("알파벳 A",),
    "GOOG": ("알파벳 C",),
    "PLTR": ("팔란티어 테크",),
}


def identity_from_kiwoom(name, symbol):
    ticker = normalize_us_ticker(symbol)
    name = str(name or "").strip()
    if not ticker or not name:
        return None
    base = resolve_us_identity(name, ticker)
    if base["status"] == "verified":
        return base
    if ticker in _VERIFIED:
        if name.casefold() in {n.casefold() for n in _KIWOOM_KNOWN_LABELS.get(ticker, ())}:
            key, canonical, _ = _VERIFIED[ticker]
            return {"company_key": key, "news_name": canonical,
                    "status": "verified", "ticker": ticker}
        # Known ticker with an unexpected label must not claim another company.
        return base
    # A new authoritative Kiwoom ticker/name pair is verified only for its own
    # ticker-specific key. No aliases or cross-ticker article sharing.
    return {"company_key": "US:" + ticker, "news_name": name,
            "status": "verified", "ticker": ticker}

