"""Register Naver ranking identities in the existing Neon market_instruments table.

No new external APIs; a failed registry write cannot suppress market rankings.
The known company map is strict and unknown tickers are flagged pending.
"""
import os
import threading
import time
from backend.analysis.news.stock_identity import resolve_us_identity

_last_signature = None
_last_write = 0.0
_lock = threading.Lock()
MIN_REFRESH_SECONDS = 600


def register_us_ranking_instruments(items):
    """Batch upsert observed US ticker/name pairs with no duplicate lookups."""
    global _last_signature, _last_write
    if not items:
        return 0
    records = []
    for row in items:
        name = str(row.get("name") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        if not name or not symbol:
            continue
        identity = resolve_us_identity(name, symbol)
        records.append((symbol, name, str(row.get("industry") or "")[:150] or None,
                        identity["company_key"], identity["news_name"],
                        identity["status"]))
    if not records:
        return 0
    signature = tuple(sorted(records))
    now = time.monotonic()
    with _lock:
        if signature == _last_signature and now - _last_write < MIN_REFRESH_SECONDS:
            return 0
        database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
        if not database_url:
            print("[stock-identity] skipped=no_neon_url", flush=True)
            return 0
        try:
            import psycopg
            with psycopg.connect(database_url, connect_timeout=4) as conn:
                with conn.cursor() as cur:
                    for symbol, name, sector, company_key, news_name, status in records:
                        cur.execute(
                            """INSERT INTO public.market_instruments
                               (market,symbol,display_name,sector,is_active,
                                first_seen_at,last_seen_at,company_key,news_name,identity_status)
                               VALUES ('US',%s,%s,%s,true,now(),now(),%s,%s,%s)
                               ON CONFLICT (market,symbol) DO UPDATE
                               SET display_name=EXCLUDED.display_name,
                                   sector=COALESCE(EXCLUDED.sector,market_instruments.sector),
                                   is_active=true,last_seen_at=now(),
                                   company_key=CASE
                                     WHEN market_instruments.identity_status='verified'
                                       AND EXCLUDED.identity_status='pending'
                                     THEN market_instruments.company_key
                                     ELSE EXCLUDED.company_key END,
                                   news_name=CASE
                                     WHEN market_instruments.identity_status='verified'
                                       AND EXCLUDED.identity_status='pending'
                                     THEN market_instruments.news_name
                                     ELSE EXCLUDED.news_name END,
                                   identity_status=CASE
                                     WHEN market_instruments.identity_status='verified'
                                       AND EXCLUDED.identity_status='pending'
                                     THEN 'review'
                                     ELSE EXCLUDED.identity_status END""",
                            (symbol, name, sector, company_key, news_name, status),
                        )
            _last_signature, _last_write = signature, time.monotonic()
            return len(records)
        except Exception as exc:
            print("[stock-identity] register_failed=%s" % type(exc).__name__, flush=True)
            return 0
