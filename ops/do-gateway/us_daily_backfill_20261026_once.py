"""One-time recovery of only 2026-10-26 Kiwoom US daily candles.

Run from the existing DigitalOcean gateway. No modifications to other
sessions, stored candles, rank snapshots, identity mappings or services.
"""
import datetime as dt
import os
import sys
import time

sys.path.insert(0, "/opt/gaemigtp-news/app")

import psycopg
from backend.providers.kiwoom_us_quotes import (
    credentials_configured, fetch_us_daily_chart, issue_access_token,
)

TARGET_DAY = dt.date(2026, 10, 26)
SOURCE = "kiwoom:usa06012"


def main():
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("BACKFILL_STOP_DATABASE_ENV_MISSING")
    if not credentials_configured():
        # Important: fail before the first Kiwoom call or Neon write.
        raise RuntimeError("BACKFILL_STOP_KIWOOM_ENV_MISSING")

    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH tracked AS (
                    SELECT DISTINCT symbol FROM public.us_daily_candles
                     WHERE market='US' AND source=%s
                    UNION
                    SELECT e.symbol FROM public.market_rank_entries e
                     WHERE e.market='US' AND e.snapshot_id=(
                       SELECT s.id FROM public.market_rank_snapshots s
                       WHERE s.source='kiwoom' AND s.market='US'
                         AND s.rank_type='trading_value'
                       ORDER BY s.captured_at DESC,s.id DESC LIMIT 1
                     )
                )
                SELECT t.symbol, i.exchange FROM tracked t
                JOIN public.market_instruments i
                  ON i.market='US' AND i.symbol=t.symbol
                WHERE i.is_active AND i.identity_status='verified'
                  AND i.company_key LIKE 'US:%%'
                  AND i.exchange IN ('ND','NY','NA')
                ORDER BY t.symbol
            """, (SOURCE,))
            universe = cur.fetchall()
            if not 15 <= len(universe) <= 30:
                raise RuntimeError("BACKFILL_STOP_UNEXPECTED_UNIVERSE")
            cur.execute("""
                SELECT symbol FROM public.us_daily_candles
                WHERE market='US' AND session_date=%s AND source=%s
            """, (TARGET_DAY, SOURCE))
            already = {row[0] for row in cur.fetchall()}

    missing = [(symbol, exchange) for symbol, exchange in universe
               if symbol not in already]
    print("BACKFILL_DAY=" + TARGET_DAY.isoformat(), flush=True)
    print("BACKFILL_TRACKED=" + str(len(universe)), flush=True)
    print("BACKFILL_ALREADY_PRESENT=" + str(len(already)), flush=True)
    print("BACKFILL_MISSING=" + str(len(missing)), flush=True)
    if not missing:
        print("BACKFILL_ALREADY_COMPLETE", flush=True)
        return

    token = issue_access_token()
    recovered = []
    for symbol, exchange in missing:
        result = fetch_us_daily_chart(
            symbol, exchange, TARGET_DAY, end_date=TARGET_DAY,
            token=token, max_pages=10,
        )
        rows = result.get("rows")
        if (not isinstance(rows, list) or len(rows) != 1
                or rows[0].get("date") != TARGET_DAY.isoformat()
                or result.get("ticker") != symbol
                or result.get("source") != SOURCE):
            raise RuntimeError("BACKFILL_STOP_INVALID_DAY_OR_MISSING_" + symbol)
        candle = rows[0]
        if not all(isinstance(candle.get(k), (int, float))
                   and candle[k] > 0 for k in ("open", "high", "low", "close")):
            raise RuntimeError("BACKFILL_STOP_INVALID_PRICES_" + symbol)
        recovered.append((symbol, candle))
        print("BACKFILL_FETCHED=" + symbol, flush=True)
        time.sleep(0.4)

    # No writes until ALL requested official daily bars have been verified.
    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            inserted = 0
            for symbol, candle in recovered:
                cur.execute("""
                    INSERT INTO public.us_daily_candles
                      (market,symbol,session_date,open,high,low,close,volume,source)
                    VALUES ('US',%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (market,symbol,session_date) DO NOTHING
                    RETURNING symbol
                """, (symbol, TARGET_DAY, candle["open"], candle["high"],
                      candle["low"], candle["close"],
                      int(candle["volume"]) if candle.get("volume") is not None else None,
                      SOURCE))
                if cur.fetchone():
                    inserted += 1
            cur.execute("""
                SELECT COUNT(*) FROM public.us_daily_candles
                WHERE market='US' AND session_date=%s AND source=%s
                  AND symbol=ANY(%s)
            """, (TARGET_DAY, SOURCE, [symbol for symbol, _ in universe]))
            if cur.fetchone()[0] != len(universe):
                raise RuntimeError("BACKFILL_STOP_FINAL_VERIFICATION")
        conn.commit()
    print("BACKFILL_COMMITTED_DAY=" + TARGET_DAY.isoformat(), flush=True)
    print("BACKFILL_INSERTED=" + str(inserted), flush=True)
    print("BACKFILL_SUCCESS", flush=True)


if __name__ == "__main__":
    main()
