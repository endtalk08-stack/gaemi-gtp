"""Kiwoom rank ticker/name -> Neon identity registration (no news or AI calls).

Only exact ticker/name pairs observed in the provider's completed Top 20 may
be registered. New listings receive a ticker-specific key, never a fuzzy
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


def upsert_kiwoom_identity(cur, symbol, name, exchange=None):
    identity = identity_from_kiwoom(name, symbol)
    if identity is None:
        raise ValueError("invalid_kiwoom_identity")
    cur.execute(
        """INSERT INTO public.market_instruments
           (market,symbol,display_name,exchange,company_key,news_name,identity_status,
            is_active,last_seen_at)
           VALUES ('US',%s,%s,%s,%s,%s,%s,true,NOW())
           ON CONFLICT (market,symbol) DO UPDATE SET
             display_name=EXCLUDED.display_name,
             last_seen_at=NOW(),is_active=true,
             exchange=COALESCE(EXCLUDED.exchange,market_instruments.exchange),
             company_key=CASE
               WHEN market_instruments.identity_status='verified'
                 AND (EXCLUDED.identity_status<>'verified'
                      OR market_instruments.company_key<>EXCLUDED.company_key)
               THEN market_instruments.company_key ELSE EXCLUDED.company_key END,
             news_name=CASE
               WHEN market_instruments.identity_status='verified'
                 AND (EXCLUDED.identity_status<>'verified'
                      OR market_instruments.company_key<>EXCLUDED.company_key)
               THEN market_instruments.news_name ELSE EXCLUDED.news_name END,
             identity_status=CASE
               WHEN market_instruments.identity_status='verified'
                 AND (EXCLUDED.identity_status<>'verified'
                      OR market_instruments.company_key<>EXCLUDED.company_key)
               THEN 'review' ELSE EXCLUDED.identity_status END""",
        (identity["ticker"], name, exchange, identity["company_key"],
         identity["news_name"], identity["status"]),
    )
    return identity


def repair_saved_top20(database_url):
    """Fill identities from already stored Kiwoom data; no provider requests."""
    import psycopg
    with psycopg.connect(database_url, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT e.rank,e.symbol,e.display_name,e.entry_payload->>'exchange'
                   FROM public.market_rank_entries e
                   WHERE e.market='US' AND e.snapshot_id=(
                       SELECT id FROM public.market_rank_snapshots
                       WHERE source='kiwoom' AND market='US'
                         AND rank_type='trading_value'
                       ORDER BY captured_at DESC,id DESC LIMIT 1
                   ) ORDER BY e.rank"""
            )
            rows = cur.fetchall()
            if len(rows) != 20 or [row[0] for row in rows] != list(range(1, 21)):
                raise ValueError("incomplete_saved_kiwoom_top20")
            if len({row[1] for row in rows}) != 20:
                raise ValueError("duplicate_kiwoom_ticker")
            verified = 0
            for _, symbol, name, exchange in rows:
                identity = upsert_kiwoom_identity(cur, symbol, name, exchange)
                verified += identity["status"] == "verified"
        conn.commit()
    return {"rows": len(rows), "verified": verified}
