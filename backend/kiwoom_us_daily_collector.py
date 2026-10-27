"""Refresh verified ranked/tracked US daily candles independently on DigitalOcean."""
import datetime as dt
import math
import os
import time
from zoneinfo import ZoneInfo
import psycopg
from backend.providers.kiwoom_us_quotes import fetch_us_daily_chart, issue_access_token

SOURCE = 'kiwoom:usa06012'


def history_start(today, latest, count):
    start = today - dt.timedelta(days=180)
    return max(start, latest - dt.timedelta(days=4)) if latest and count >= 65 else start


def valid_candle(row, start, end):
    try:
        day = dt.date.fromisoformat(row['date'])
        prices = [row[k] for k in ('open', 'high', 'low', 'close')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in prices):
            return False
        opening, high, low, close = prices
        volume = row.get('volume')
        return (start <= day <= end and low <= min(opening, close) <= max(opening, close) <= high
                and (volume is None or (type(volume) in (int, float) and math.isfinite(volume) and volume >= 0)))
    except (ValueError, TypeError, KeyError):
        return False


def main():
    dsn = os.environ.get('NEWS_DATABASE_URL', '').strip()
    if not dsn:
        raise RuntimeError('chart_database_url_missing')
    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH ranked AS (
                  SELECT e.symbol FROM public.market_rank_entries e
                  WHERE e.market='US' AND e.snapshot_id=(
                    SELECT id FROM public.market_rank_snapshots
                    WHERE source='kiwoom' AND market='US' AND rank_type='trading_value'
                    ORDER BY captured_at DESC,id DESC LIMIT 1)
                  ORDER BY e.rank LIMIT 20
                ), tracked AS (
                  SELECT symbol FROM ranked UNION
                  SELECT DISTINCT symbol FROM public.us_daily_candles
                  WHERE market='US' AND source='kiwoom:usa06012'
                )
                SELECT i.symbol,i.exchange,MAX(c.session_date),COUNT(c.session_date),MAX(c.fetched_at)
                FROM tracked t JOIN public.market_instruments i
                  ON i.market='US' AND i.symbol=t.symbol
                LEFT JOIN public.us_daily_candles c
                  ON c.market='US' AND c.symbol=i.symbol AND c.source='kiwoom:usa06012'
                WHERE i.is_active AND i.identity_status='verified'
                  AND i.company_key LIKE 'US:%' AND i.exchange IN ('ND','NY','NA')
                GROUP BY i.symbol,i.exchange ORDER BY i.symbol
            """)
            matches = cur.fetchall()
    now = dt.datetime.now(dt.timezone.utc)
    ny = now.astimezone(ZoneInfo('America/New_York'))
    today = ny.date()
    market_window = ny.weekday() < 5 and dt.time(4) <= ny.time() < dt.time(20, 10)
    expected = today if ny.time() >= dt.time(16) else today - dt.timedelta(days=1)
    while expected.weekday() >= 5:
        expected -= dt.timedelta(days=1)
    token = None
    failed = 0
    for symbol, exchange, latest, count, fetched in matches:
        if fetched and not market_window and now - fetched < dt.timedelta(hours=6):
            # New and incomplete histories still get one full attempt per off-hours cycle.
            if count >= 65 and latest and latest >= expected:
                continue
        start = history_start(today, latest, count)
        try:
            if token is None:
                token = issue_access_token()
            result = fetch_us_daily_chart(symbol, exchange, start, end_date=today, token=token, max_pages=10)
            rows = result.get('rows')
            if (result.get('ticker') != symbol or result.get('source') != SOURCE
                    or not isinstance(rows, list) or not rows
                    or not all(valid_candle(r, start, today) for r in rows)):
                raise ValueError('invalid_chart_result')
            with psycopg.connect(dsn, connect_timeout=7) as conn:
                with conn.cursor() as cur:
                    for row in rows:
                        cur.execute("""
                            INSERT INTO public.us_daily_candles
                              (market,symbol,session_date,open,high,low,close,volume,source)
                            VALUES ('US',%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (market,symbol,session_date) DO UPDATE SET
                              open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
                              close=EXCLUDED.close,volume=EXCLUDED.volume,
                              source=EXCLUDED.source,fetched_at=now()
                            WHERE us_daily_candles.source=EXCLUDED.source
                        """, (symbol,row['date'],row['open'],row['high'],row['low'],row['close'],
                              int(row['volume']) if row.get('volume') is not None else None,SOURCE))
                conn.commit()
            print('CHART_REFRESH_OK symbol=%s rows=%s' % (symbol,len(rows)), flush=True)
        except Exception as exc:
            # Never emit credentials, provider payloads, or connection strings.
            failed += 1
            print('CHART_REFRESH_RETRY symbol=%s kind=%s' % (symbol,type(exc).__name__), flush=True)
        finally:
            time.sleep(0.4)
    print('CHART_REFRESH_DONE symbols=%s failed=%s' % (len(matches),failed), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
