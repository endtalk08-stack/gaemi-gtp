"""Collect ONLY Kiwoom usa20540 US trading-value Top 20 into existing Neon ranking tables.

Runs on DigitalOcean with protected Kiwoom and News DB env files.
No orders, accounts, AI, news collection or migrations; only usa20540 rank\nand usa10100 industry when the current Top 20 has missing sector labels.
"""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_rankings import fetch_us_trading_value_top
from backend.providers.kiwoom_us_industry import fetch_us_stock_industry
from backend.providers.kiwoom_us_quotes import issue_access_token


def _fill_missing_us_industries(database_url, max_requests=12):
    """Only the latest Kiwoom value Top 20; do not modify identity/rank/quotes."""
    import time
    import psycopg
    with psycopg.connect(database_url, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT e.symbol, i.exchange
                   FROM public.market_rank_entries e
                   JOIN public.market_instruments i
                     ON i.market=e.market AND i.symbol=e.symbol
                   WHERE e.snapshot_id=(
                       SELECT id FROM public.market_rank_snapshots
                       WHERE source='kiwoom' AND market='US'
                         AND rank_type='trading_value'
                       ORDER BY captured_at DESC, id DESC LIMIT 1
                   )
                     AND e.market='US'
                     AND (i.sector IS NULL OR i.sector='')
                   ORDER BY e.rank LIMIT %s""",
                (max_requests,),
            )
            pending = cur.fetchall()
    if not pending:
        print("KIWOOM_US_INDUSTRY_PENDING=0", flush=True)
        return 0

    token = issue_access_token()
    updated = 0
    for symbol, exchange in pending:
        sector = fetch_us_stock_industry(symbol, exchange, token=token)
        if sector:
            with psycopg.connect(database_url, connect_timeout=7) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE public.market_instruments
                           SET sector=%s
                           WHERE market='US' AND symbol=%s
                             AND (sector IS NULL OR sector='')""",
                        (sector, symbol),
                    )
                    updated += cur.rowcount
                conn.commit()
        time.sleep(0.24)  # Stay below Kiwoom's read-only market TR call rate.
    print("KIWOOM_US_INDUSTRY_UPDATED=" + str(updated) +
          " LOOKUPS=" + str(len(pending)), flush=True)
    _fill_verified_fallback_sectors(database_url)
    return updated


def _fill_verified_fallback_sectors(database_url):
    """Fallback ONLY for remaining blank US sector labels, keyed by source ticker.

    Existing Naver industry endpoint yields exact suffixed ticker keys, so
    Kiwoom ranks/prices, stock identities and nonempty industry are untouched.
    """
    import psycopg
    from backend.providers.market_industry import get_stock_industries

    suffix = {"ND": ".O", "NY": ".N", "NA": ".A"}
    with psycopg.connect(database_url, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT e.symbol, i.exchange
                   FROM public.market_rank_entries AS e
                   JOIN public.market_instruments AS i
                     ON i.market=e.market AND i.symbol=e.symbol
                   WHERE e.snapshot_id=(
                     SELECT id FROM public.market_rank_snapshots
                     WHERE source='kiwoom' AND market='US' AND rank_type='trading_value'
                     ORDER BY captured_at DESC,id DESC LIMIT 1)
                     AND e.market='US'
                     AND (i.sector IS NULL OR i.sector='')
                   ORDER BY e.rank LIMIT 20"""
            )
            pending = cur.fetchall()
    code_map = {
        symbol + suffix[exchange]: symbol
        for symbol, exchange in pending if exchange in suffix
    }
    if not code_map:
        print("KIWOOM_US_INDUSTRY_FALLBACK_PENDING=0", flush=True)
        return 0
    labels = get_stock_industries("us", list(code_map))
    updated = 0
    with psycopg.connect(database_url, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            for source_code, symbol in code_map.items():
                sector = labels.get(source_code)
                if not isinstance(sector, str) or not sector.strip():
                    continue
                cur.execute(
                    """UPDATE public.market_instruments
                       SET sector=%s
                       WHERE market='US' AND symbol=%s
                         AND (sector IS NULL OR sector='')""",
                    (sector.strip(), symbol),
                )
                updated += cur.rowcount
        conn.commit()
    print("KIWOOM_US_INDUSTRY_FALLBACK_UPDATED=" + str(updated), flush=True)
    return updated


def main():
    ny = dt.datetime.now(ZoneInfo("America/New_York"))
    # US overnight/day market (including Asia daytime) runs before 04:00 ET.
    # Keep one weekday market session open from Sunday 20:00 to Friday 20:00 ET.
    # The provider remains authoritative: never synthesize off-session quotes.
    in_session = (ny.weekday() < 4 or
                  (ny.weekday() == 4 and ny.time() < dt.time(20, 0)) or
                  (ny.weekday() == 6 and ny.time() >= dt.time(20, 0)))

    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        print("KIWOOM_US_VALUE_ERROR=database_url_missing", flush=True)
        return 2

    import psycopg
    if not in_session:
        # Bootstrap one verified Kiwoom snapshot if none has ever been collected.
        # Afterward, avoid stale off-session re-collections and extra Kiwoom calls.
        with psycopg.connect(database_url, connect_timeout=7) as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT 1 FROM public.market_rank_snapshots
                               WHERE source='kiwoom' AND market='US'
                                 AND rank_type='trading_value' LIMIT 1""")
                if cur.fetchone():
                    print("KIWOOM_US_VALUE_SKIP=outside_us_extended_session", flush=True)
                    # Existing source-ranked prices stay unchanged; fill only
                    # blank stock industries using official usa10100 metadata.
                    _fill_missing_us_industries(database_url)
                    return 0
    rows = fetch_us_trading_value_top(limit=20)
    # This board promises exactly 20 source-ranked rows. Never overwrite
    # the last complete snapshot with a partial provider response.
    if len(rows) != 20 or [row["rank"] for row in rows] != list(range(1, 21)):
        print("KIWOOM_US_VALUE_ERROR=incomplete_source_rows", flush=True)
        return 3

    captured = dt.datetime.now(dt.timezone.utc)
    payload = json.dumps({
        "api_id": "usa20540", "rank_source": "kiwoom",
        "value_currency": "USD", "value_unit": "USD",
        "retrieved_at_et": ny.isoformat(timespec="seconds"),
        "during_market_session": in_session,
    })
    with psycopg.connect(database_url, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """INSERT INTO public.market_instruments
                       (market, symbol, display_name, exchange)
                       VALUES ('US', %s, %s, %s)
                       ON CONFLICT (market, symbol) DO UPDATE
                       SET last_seen_at=NOW(),
                           exchange=EXCLUDED.exchange""",
                    (row["symbol"], row["name"], row["exchange"]),
                )
            # Reuse the single Kiwoom/US/trading_value snapshot forever.
            # Serialize concurrent collector starts and update all 20 ranks
            # in the same transaction, so Render never sees partial rankings.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (74245112,))
            cur.execute(
                """SELECT id FROM public.market_rank_snapshots
                   WHERE source='kiwoom' AND market='US' AND rank_type='trading_value'
                   ORDER BY captured_at DESC,id DESC LIMIT 1"""
            )
            existing = cur.fetchone()
            if existing:
                snapshot_id = existing[0]
                cur.execute(
                    """UPDATE public.market_rank_snapshots
                       SET captured_at=%s, collected_at=NOW(), source_payload=%s::jsonb
                       WHERE id=%s AND source='kiwoom' AND market='US'
                         AND rank_type='trading_value'""",
                    (captured, payload, snapshot_id),
                )
            else:
                cur.execute(
                    """INSERT INTO public.market_rank_snapshots
                       (source,market,rank_type,captured_at,source_payload)
                       VALUES ('kiwoom','US','trading_value',%s,%s::jsonb)
                       RETURNING id""",
                    (captured, payload),
                )
                snapshot_id = cur.fetchone()[0]
            for row in rows:
                cur.execute(
                    """INSERT INTO public.market_rank_entries
                       (snapshot_id,rank,market,symbol,display_name,
                        price,change_rate,trading_value,volume,entry_payload)
                       VALUES (%s,%s,'US',%s,%s,%s,%s,%s,%s,%s::jsonb)
                       ON CONFLICT (snapshot_id,rank) DO UPDATE SET
                           market=EXCLUDED.market,
                           symbol=EXCLUDED.symbol,
                           display_name=EXCLUDED.display_name,
                           price=EXCLUDED.price,
                           change_rate=EXCLUDED.change_rate,
                           trading_value=EXCLUDED.trading_value,
                           volume=EXCLUDED.volume,
                           entry_payload=EXCLUDED.entry_payload""",
                    (snapshot_id, row["rank"], row["symbol"], row["name"],
                     row["price"], row["change_pct"], row["trading_value"],
                     int(row["volume"]) if row["volume"] is not None else None,
                     json.dumps({"exchange": row["exchange"],
                                 "english_name": row["english_name"],
                                 "rank_source": "kiwoom",
                                 "trading_value_raw_thousand_usd": row["trading_value_raw"]})),
                )
        conn.commit()
    print("KIWOOM_US_VALUE_SNAPSHOT_UPDATED=20", flush=True)
    _fill_missing_us_industries(database_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
