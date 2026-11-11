"""Publish existing verified US daily candle rows from Neon to the existing R2 chart files.

Runs only inside the existing post-close daily task, never per website visitor.
No Kiwoom calls, DB writes, new timers, new databases, or inferred ticker matches.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path

import psycopg

from backend.services.r2_news_uploader import upload_file

SOURCE = "kiwoom:usa06012"
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def make_chart(symbol, rows):
    """Produce the exact schema expected by /market/us-daily-chart."""
    if not SYMBOL.fullmatch(symbol) or not rows:
        raise ValueError("invalid_chart_symbol_or_empty")
    candles = []
    last = None
    for day, opening, high, low, close, volume in rows:
        if volume is None or not isinstance(volume, int) or not (0 <= volume <= 2**53 - 1):
            raise ValueError("invalid_chart_volume")
        prices = tuple(float(v) for v in (opening, high, low, close))
        if not all(math.isfinite(v) and v > 0 for v in prices):
            raise ValueError("invalid_chart_price")
        o, h, l, c = prices
        if l > min(o, c) or max(o, c) > h:
            raise ValueError("invalid_chart_ohlc")
        date = day.isoformat()
        if last is not None and date <= last:
            raise ValueError("invalid_chart_date_order")
        last = date
        candles.append({"date": date, "open": o, "high": h, "low": l,
                        "close": c, "volume": volume})
    return {"schema_version": 1, "market": "US", "symbol": symbol,
            "interval": "daily", "source": SOURCE, "count": len(candles),
            "first_date": candles[0]["date"], "last_date": candles[-1]["date"],
            "candles": candles}


def publish_verified_top20(dsn: str) -> dict:
    """Read at most 20 verified rank symbols and their latest 180 stored candles."""
    if not dsn or not os.getenv("R2_ACCESS_KEY_ID") or not os.getenv("R2_SECRET_ACCESS_KEY"):
        return {"status": "skipped_missing_config", "uploaded": 0, "failed": 0, "missing": 0}
    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH latest_rank AS (
                    SELECT id FROM public.market_rank_snapshots
                    WHERE source='kiwoom' AND market='US' AND rank_type='trading_value'
                    ORDER BY captured_at DESC, id DESC LIMIT 1
                ), eligible AS (
                    SELECT e.symbol FROM public.market_rank_entries e
                    JOIN latest_rank s ON e.snapshot_id=s.id
                    JOIN public.market_instruments i ON i.market='US' AND i.symbol=e.symbol
                    WHERE e.rank BETWEEN 1 AND 20 AND i.is_active
                      AND i.exchange IN ('ND','NY','NA')
                ), ranked_candles AS (
                    SELECT c.symbol,c.session_date,c.open,c.high,c.low,c.close,c.volume,
                           ROW_NUMBER() OVER (PARTITION BY c.symbol ORDER BY c.session_date DESC) AS rn
                    FROM public.us_daily_candles c
                    JOIN eligible e ON e.symbol=c.symbol
                    WHERE c.market='US' AND c.source='kiwoom:usa06012'
                )
                SELECT symbol,session_date,open,high,low,close,volume
                FROM ranked_candles WHERE rn <= 180
                ORDER BY symbol,session_date
            """)
            rows = cur.fetchall()
    grouped = defaultdict(list)
    for symbol, *fields in rows:
        grouped[symbol].append(fields)
    uploaded = failed = 0
    for symbol, candles in grouped.items():
        filename = None
        try:
            payload = make_chart(symbol, candles)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             suffix=".json", delete=False) as file:
                filename = file.name
                json.dump(payload, file, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            if upload_file(Path(filename), object_key=f"charts/us/{symbol}/daily.json"):
                uploaded += 1
                print(f"CHART_R2_OK symbol={symbol} last={payload['last_date']}", flush=True)
            else:
                failed += 1
                print(f"CHART_R2_RETRY symbol={symbol} kind=upload_failed", flush=True)
        except (ValueError, TypeError, OSError, OverflowError) as exc:
            failed += 1
            print(f"CHART_R2_RETRY symbol={symbol} kind={type(exc).__name__}", flush=True)
        finally:
            if filename:
                os.unlink(filename)
    result = {"status": "complete" if failed == 0 else "partial_failure",
              "uploaded": uploaded, "failed": failed, "missing": max(0, 20 - len(grouped))}
    print(f"CHART_R2_DONE uploaded={uploaded} failed={failed} missing={result['missing']}", flush=True)
    return result
