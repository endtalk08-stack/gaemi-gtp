"""Collect Kiwoom daily candles for the latest Neon-verified US trading-value Top 20 only."""
import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

import psycopg

from backend.providers.kiwoom_us_quotes import fetch_us_daily_chart, issue_access_token


def main():
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("chart_database_url_missing")
    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.rank,e.symbol,i.exchange,i.company_key
                FROM public.market_rank_entries e
                JOIN public.market_instruments i
                  ON i.market=e.market AND i.symbol=e.symbol
                WHERE e.market='US' AND i.is_active
                  AND i.identity_status='verified'
                  AND i.company_key LIKE 'US:%'
                  AND e.snapshot_id=(
                    SELECT s.id FROM public.market_rank_snapshots s
                    WHERE s.source='kiwoom' AND s.market='US'
                      AND s.rank_type='trading_value'
                    ORDER BY s.captured_at DESC,s.id DESC LIMIT 1)
                ORDER BY e.rank LIMIT 20
            """)
            matches = cur.fetchall()
    if len(matches) != 20 or [row[0] for row in matches] != list(range(1,21)):
        raise RuntimeError("chart_top20_verified_match_incomplete")
    if any(exchange not in ("ND", "NY", "NA") for _, _, exchange, _ in matches):
        raise RuntimeError("chart_exchange_mapping_missing")
    ny_date = dt.datetime.now(ZoneInfo("America/New_York")).date()
    start = ny_date - dt.timedelta(days=120)
    token = issue_access_token()
    for rank, symbol, exchange, company_key in matches:
        result = fetch_us_daily_chart(symbol, exchange, start, end_date=ny_date,
                                      token=token, max_pages=10)
        rows = result["rows"]
        if len(rows) < 15:
            raise RuntimeError("chart_history_insufficient_rank_" + str(rank))
        with psycopg.connect(dsn, connect_timeout=7) as conn:
            with conn.cursor() as cur:
                for row in rows:
                    volume = row.get("volume")
                    cur.execute("""
                        INSERT INTO public.us_daily_candles
                            (market,symbol,session_date,open,high,low,close,volume,source)
                        VALUES ('US',%s,%s,%s,%s,%s,%s,%s,'kiwoom:usa06012')
                        ON CONFLICT (market,symbol,session_date) DO UPDATE SET
                            open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
                            close=EXCLUDED.close,volume=EXCLUDED.volume,
                            fetched_at=now()
                    """, (symbol,row["date"],row["open"],row["high"],
                          row["low"],row["close"],
                          int(volume) if volume is not None else None))
            conn.commit()
        print("KIWOOM_CHART_STORED_RANK=%s SYMBOL=%s ROWS=%s" %
              (rank,symbol,len(rows)),flush=True)
        time.sleep(0.3)
    print("KIWOOM_CHART_TOP20_OK",flush=True)


if __name__ == "__main__":
    main()
