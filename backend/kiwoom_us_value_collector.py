"""Collect ONLY Kiwoom usa20540 US trading-value Top 20 into existing Neon ranking tables.

Runs on DigitalOcean with protected Kiwoom and News DB env files.
No orders, accounts, AI, news collection, migration or additional market APIs.
"""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_rankings import fetch_us_trading_value_top


def main():
    ny = dt.datetime.now(ZoneInfo("America/New_York"))
    in_session = (ny.weekday() < 5 and dt.time(4, 0) <= ny.time() < dt.time(20, 0))

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
                    return 0
    rows = fetch_us_trading_value_top(limit=20)
    if not rows:
        print("KIWOOM_US_VALUE_ERROR=no_source_rows", flush=True)
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
            cur.execute(
                """INSERT INTO public.market_rank_snapshots
                    (source, market, rank_type, captured_at, source_payload)
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
                       VALUES (%s,%s,'US',%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (snapshot_id, row["rank"], row["symbol"], row["name"],
                     row["price"], row["change_pct"], row["trading_value"],
                     int(row["volume"]) if row["volume"] is not None else None,
                     json.dumps({"exchange": row["exchange"],
                                 "english_name": row["english_name"],
                                 "rank_source": "kiwoom", "trading_value_raw_thousand_usd": row["trading_value_raw"]})),
                )
        conn.commit()
    print("KIWOOM_US_VALUE_STORED=20" if len(rows) == 20
          else "KIWOOM_US_VALUE_STORED=" + str(len(rows)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
