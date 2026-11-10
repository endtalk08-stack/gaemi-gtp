"""Once-per-US-session TOP20 rank/turnover archive and stock metadata R2 export.

Triggered by the existing post-close daily-candle service. Never collect quotes,
open a Kiwoom connection, or query Neon in response to a website visitor.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

from backend.kiwoom_us_top20_api import read_top20

NY = ZoneInfo("America/New_York")
R2_OBJECT = "stocks/us/instruments.json"


def _valid_source(data: dict, now: dt.datetime):
    ny_now = now.astimezone(NY)
    if ny_now.weekday() > 4 or ny_now.time() < dt.time(16, 15):
        return None
    try:
        captured = dt.datetime.fromisoformat(str(data.get("captured_at", "")))
    except ValueError:
        return None
    if captured.tzinfo is None:
        return None
    ny_captured = captured.astimezone(NY)
    if ny_captured.date() != ny_now.date() or ny_captured.time() < dt.time(16):
        return None
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) != 20:
        return None
    seen = set()
    for expected_rank, row in enumerate(rows, 1):
        if (type(row.get("rank")) is not int or row["rank"] != expected_rank
                or not isinstance(row.get("symbol"), str)
                or row["symbol"] in seen
                or not isinstance(row.get("name"), str) or not row["name"].strip()):
            return None
        seen.add(row["symbol"])
        value = row.get("trading_value")
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return None
    return captured


def sync_once_after_close(dsn: str, *, now: dt.datetime | None = None) -> str:
    """Archive at most one verified post-close TOP20 per New York session.

    Five-minute TOP20 collector, realtime quote polling and chart fetches are
    completely untouched. No new database tables, timers or price writes.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if not dsn or now.tzinfo is None:
        return "skipped_missing_config"
    ny_now = now.astimezone(NY)
    if ny_now.weekday() > 4 or ny_now.time() < dt.time(16, 15):
        return "skipped_outside_close"
    data = read_top20()
    captured = _valid_source(data, now)
    if captured is None:
        return "skipped_stale_or_incomplete_ranking"
    start = dt.datetime.combine(ny_now.date(), dt.time(), NY).astimezone(dt.timezone.utc)
    end = dt.datetime.combine(ny_now.date() + dt.timedelta(days=1), dt.time(), NY).astimezone(dt.timezone.utc)
    rows = [{
        "rank": row["rank"], "symbol": row["symbol"], "name": row["name"],
        "exchange": row.get("exchange"), "trading_value": row["trading_value"],
        "volume": int(row["volume"]) if type(row.get("volume")) in (int, float)
                  and math.isfinite(row["volume"]) and row["volume"] >= 0 else None,
    } for row in data["items"]]
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False)
    with psycopg.connect(dsn, connect_timeout=7) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, COUNT(e.rank)
                  FROM public.market_rank_snapshots s
                  LEFT JOIN public.market_rank_entries e ON e.snapshot_id=s.id
                 WHERE s.source='kiwoom' AND s.market='US'
                   AND s.rank_type='trading_value'
                   AND s.captured_at >= %s AND s.captured_at < %s
                 GROUP BY s.id ORDER BY s.captured_at DESC LIMIT 1
            """, (start, end))
            existing = cur.fetchone()
            if existing:
                if existing[1] == 20:
                    return "already_saved_today"
                raise RuntimeError("existing_incomplete_daily_snapshot")
            cur.execute("""
                INSERT INTO public.market_instruments
                    (market, symbol, display_name, exchange)
                SELECT 'US', x.symbol, x.name, x.exchange
                  FROM jsonb_to_recordset(%s::jsonb)
                    AS x(rank int, symbol text, name text, exchange text,
                         trading_value numeric, volume bigint)
                ON CONFLICT (market,symbol) DO NOTHING
            """, (payload,))
            cur.execute("""
                INSERT INTO public.market_rank_snapshots
                    (source,market,rank_type,captured_at,source_payload)
                VALUES ('kiwoom','US','trading_value',%s,%s::jsonb)
                ON CONFLICT (source,market,rank_type,captured_at) DO NOTHING
                RETURNING id
            """, (captured, json.dumps({"schema_version": 1, "count": 20})))
            added = cur.fetchone()
            if not added:
                raise RuntimeError("daily_snapshot_write_conflict")
            snapshot_id = added[0]
            cur.execute("""
                INSERT INTO public.market_rank_entries
                    (snapshot_id,rank,market,symbol,display_name,trading_value,volume)
                SELECT %s,x.rank,'US',x.symbol,x.name,x.trading_value,x.volume
                  FROM jsonb_to_recordset(%s::jsonb)
                    AS x(rank smallint,symbol text,name text,exchange text,
                         trading_value numeric,volume bigint)
                ON CONFLICT (snapshot_id,rank) DO NOTHING
            """, (snapshot_id, payload))
            cur.execute("SELECT COUNT(*) FROM public.market_rank_entries WHERE snapshot_id=%s", (snapshot_id,))
            if cur.fetchone()[0] != 20:
                raise RuntimeError("daily_snapshot_not_atomic")
            cur.execute("""
                SELECT symbol,exchange,sector FROM public.market_instruments
                 WHERE market='US' AND sector IS NOT NULL AND btrim(sector)<>''
                 ORDER BY symbol
            """)
            industries = [{"symbol": symbol, "exchange": exchange, "industry": sector}
                          for symbol, exchange, sector in cur.fetchall()]
        conn.commit()

    # Publishing an unchanged 5-KB JSON once/day is cheap; credentials are optional.
    # A missing R2 credential never prevents the verified Neon record or charts.
    if not (os.getenv("R2_ACCESS_KEY_ID") and os.getenv("R2_SECRET_ACCESS_KEY")):
        return "saved_20_r2_credentials_unavailable"
    from backend.services.r2_news_uploader import upload_file
    output = {
        "schema_version": 1, "source": "neon", "market": "US",
        "generated_at": now.isoformat(),
        "items": industries,
    }
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                          suffix=".json", delete=False) as handle:
            filename = handle.name
            json.dump(output, handle, ensure_ascii=False, separators=(",", ":"))
        success = upload_file(Path(filename), object_key=R2_OBJECT)
        return "saved_20_r2_updated" if success else "saved_20_r2_upload_failed"
    finally:
        if filename:
            os.unlink(filename)
