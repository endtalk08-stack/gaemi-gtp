"""Read/write 30-day SEC/DART disclosure snapshots in Neon.

Collection is explicitly invoked on DigitalOcean. Render only reads cached
snapshots for up to 24 hours when DISCLOSURE_NEON_READ=1; the old provider remains a safe fallback.
This module does not manage the news worker, UI, or any other providers.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


def _database_url():
    return os.environ.get("NEWS_DATABASE_URL", "").strip()


def _valid_identity(market, symbol):
    market, symbol = str(market or "").upper(), str(symbol or "").upper()
    if market == "KR" and re.fullmatch(r"\d{6}", symbol):
        return market, symbol
    if market == "US" and re.fullmatch(r"[A-Z.]{1,10}", symbol):
        return market, symbol
    raise ValueError("invalid_disclosure_identity")


def read_snapshot(market, symbol):
    """Read-only. None means missing/stale/error: caller must retain old path."""
    if not _database_url():
        return None
    market, symbol = _valid_identity(market, symbol)
    try:
        import psycopg
        with psycopg.connect(_database_url(), connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT filings FROM public.disclosure_snapshots
                    WHERE market = %s AND symbol = %s
                      AND fetched_at > now() - interval '24 hours'
                """, (market, symbol))
                row = cur.fetchone()
        filings = row[0] if row else None
        if isinstance(filings, str):
            filings = json.loads(filings)
        if isinstance(filings, list) and all(isinstance(v, dict) for v in filings):
            return filings
    except Exception as exc:
        print("[disclosure-transfer] read_unavailable=" + type(exc).__name__, flush=True)
    return None


def collect_once(market, symbol):
    """One selected stock only. Does not start a scheduler or news worker."""
    market, symbol = _valid_identity(market, symbol)
    if not _database_url():
        raise RuntimeError("disclosure_db_missing")
    from . import engine

    if market == "KR":
        if symbol not in engine.DART_STOCK_CORP_CODES:
            raise ValueError("unsupported_dart_stock")
        if not engine.OPENDART_API_KEY:
            raise RuntimeError("opendart_key_missing")
        filings = engine.fetch_kr_official_disclosures(symbol, days=30, max_results=0)
    else:
        if symbol not in engine.US_CIKS:
            raise ValueError("unsupported_sec_ticker")
        filings = engine.fetch_us_official_filings(
            symbol, days=30, max_results=30, complete_window=True
        )
    if not isinstance(filings, list) or not filings:
        raise RuntimeError("disclosure_list_unavailable_or_empty")

    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(_database_url(), connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.disclosure_snapshots(market, symbol, filings, fetched_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (market, symbol) DO UPDATE
                SET filings = EXCLUDED.filings, fetched_at = EXCLUDED.fetched_at
            """, (market, symbol, Jsonb(filings)))
            # Disclosure data is temporary, not a long-term archive.
            # Each successful daily collection replaces the stock's 30-day list,
            # then removes any other snapshots older than 24 hours.
            cur.execute("""
                DELETE FROM public.disclosure_snapshots
                WHERE fetched_at <= now() - interval '24 hours'
            """)
    return {"market": market, "symbol": symbol, "filing_count": len(filings),
            "collected_at": datetime.now(timezone.utc).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-off SEC/DART migration check")
    parser.add_argument("--market", choices=("KR", "US"), required=True)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(collect_once(args.market, args.symbol), ensure_ascii=False))
        return 0
    except Exception as exc:
        print("disclosure_sync_error=" + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
