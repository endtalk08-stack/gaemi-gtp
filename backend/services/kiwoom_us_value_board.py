"""Render-side, read-only Kiwoom US trading-value Top 20 from Neon.

The website has no Kiwoom credentials and never calls or collects market data.
"""
import os

def read_us_trading_value_board(limit=20, diagnostics=None):
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("invalid_limit")
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        if diagnostics is not None:
            diagnostics.append('db_not_configured')
        return None
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, captured_at
                       FROM public.market_rank_snapshots
                       WHERE market='US' AND rank_type='trading_value'
                         AND source='kiwoom'
                       ORDER BY captured_at DESC, id DESC LIMIT 1"""
                )
                snapshot = cur.fetchone()
                if not snapshot:
                    if diagnostics is not None:
                        diagnostics.append('snapshot_not_found')
                    return None
                cur.execute(
                    """SELECT e.rank,e.symbol,e.display_name,e.price,
                              e.change_rate,e.trading_value,e.volume,
                              i.sector, e.entry_payload->>'exchange'
                       FROM public.market_rank_entries AS e
                       LEFT JOIN public.market_instruments AS i
                         ON i.market=e.market AND i.symbol=e.symbol
                       WHERE e.snapshot_id=%s AND e.market='US'
                       ORDER BY e.rank ASC LIMIT %s""",
                    (snapshot[0], limit),
                )
                result = cur.fetchall()
        if not result:
            if diagnostics is not None:
                diagnostics.append('entries_not_found')
            return None
        rows = []
        for rank, symbol, name, price, change, amount, volume, sector, exchange in result:
            rows.append({
                "rank": int(rank), "symbol": str(symbol), "analysis_symbol": str(symbol),
                "name": str(name), "industry": str(sector) if sector else None,
                "price": float(price) if price is not None else None,
                "change_pct": float(change) if change is not None else None,
                "trading_value": float(amount) if amount is not None else None,
                "trading_value_text": None,
                "volume": int(volume) if volume is not None else None,
                "exchange": exchange, "source": "kiwoom",
                "captured_at": snapshot[1].isoformat(),
            })
        return rows
    except Exception as exc:
        print("[kiwoom value board] Neon read unavailable: " + type(exc).__name__, flush=True)
        if diagnostics is not None:
            diagnostics.append('db_query_failed')
        return None


# Lightweight quote feed for the currently displayed US Top 20.
# Query Neon once per short interval, rather than loading AI headlines for every price tick.
import threading
import time
from datetime import datetime, timezone

_QUOTES_LOCK = threading.Lock()
_QUOTES_CACHE = {"at": 0.0, "rows": None}


def read_us_live_quotes():
    """Return source quotes only; never collect prices or write to Neon/Redis."""
    now = time.monotonic()
    with _QUOTES_LOCK:
        rows = _QUOTES_CACHE["rows"]
        if rows is not None and now - _QUOTES_CACHE["at"] < 6:
            return [dict(row) for row in rows]

    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        return None
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """WITH latest AS (
                           SELECT id, captured_at
                           FROM public.market_rank_snapshots
                           WHERE market='US' AND rank_type='trading_value'
                             AND source='kiwoom'
                           ORDER BY captured_at DESC, id DESC LIMIT 1
                       )
                       SELECT e.symbol, e.rank, e.price, e.change_rate,
                              latest.captured_at
                       FROM latest
                       JOIN public.market_rank_entries e
                         ON e.snapshot_id=latest.id AND e.market='US'
                       ORDER BY e.rank ASC LIMIT 20"""
                )
                records = cur.fetchall()
        if not records:
            return None
        utc_now = datetime.now(timezone.utc)
        rows = []
        for symbol, rank, price, change, captured_at in records:
            captured_utc = captured_at.replace(tzinfo=timezone.utc) if captured_at.tzinfo is None else captured_at.astimezone(timezone.utc)
            rows.append({
                "symbol": str(symbol),
                "rank": int(rank),
                "price": float(price) if price is not None else None,
                "change_pct": float(change) if change is not None else None,
                "captured_at": captured_utc.isoformat(),
                "stale": (utc_now - captured_utc).total_seconds() > 90,
            })
        with _QUOTES_LOCK:
            _QUOTES_CACHE["at"] = time.monotonic()
            _QUOTES_CACHE["rows"] = rows
        return [dict(row) for row in rows]
    except Exception as exc:
        print("[kiwoom live quotes] Neon read unavailable: " + type(exc).__name__, flush=True)
        # A short-lived last-good quote is better than blanking the sidebar.
        # Mark it stale so the UI never presents old prices as live.
        with _QUOTES_LOCK:
            if _QUOTES_CACHE["rows"] is not None and time.monotonic() - _QUOTES_CACHE["at"] < 180:
                return [{**row, "stale": True} for row in _QUOTES_CACHE["rows"]]
        return None
