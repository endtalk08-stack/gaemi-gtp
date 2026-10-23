"""Shared Kiwoom US real-time feed helpers for the direct Render relay.

Symbol/exchange validation and source-ranked Top 20 membership only.
This module does not collect ticks or write live prices to Neon/Redis.
The active collector is backend.kiwoom_us_price_relay.
"""
import datetime as dt
import math
import re
from zoneinfo import ZoneInfo

import psycopg

URL = "wss://api.kiwoom.com:10000/api/us/websocket"
EXCHANGES = {"ND", "NY", "NA"}
RANK_QUERY = """
SELECT s.id, e.symbol, i.exchange
FROM public.market_rank_snapshots s
JOIN public.market_rank_entries e ON e.snapshot_id=s.id
JOIN public.market_instruments i ON i.market=e.market AND i.symbol=e.symbol
WHERE s.source='kiwoom' AND s.market='US' AND s.rank_type='trading_value'
AND s.id=(SELECT id FROM public.market_rank_snapshots
          WHERE market='US' AND rank_type='trading_value' AND source='kiwoom'
          ORDER BY captured_at DESC,id DESC LIMIT 1)
ORDER BY e.rank LIMIT 20
"""

def _open_us_session():
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    # Include the overnight/day market as well as premarket, regular and after.
    # US trading week: Sunday 20:00 ET through Friday 20:00 ET.
    return (now.weekday() < 4 or
            (now.weekday() == 4 and now.time() < dt.time(20, 0)) or
            (now.weekday() == 6 and now.time() >= dt.time(20, 0)))

def _num(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        n = float(str(value).strip().replace(",", ""))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

def _parse_price_event(message, selected):
    """Whitelist accepted FE fields and exact registered ticker/exchange."""
    if not isinstance(message, dict) or message.get("trnm") != "REAL":
        return {}
    updates = {}
    for item in (message.get("data") if isinstance(message.get("data"), list) else []):
        if not isinstance(item, dict) or item.get("type") != "FE":
            continue
        raw = str(item.get("item") or "").strip().upper()
        symbol = raw if raw in selected else ""
        if not symbol:
            for candidate, exchange in selected.items():
                if raw == candidate + "." + exchange or raw == exchange + ":" + candidate:
                    symbol = candidate
                    break
        if not symbol:
            continue
        fields = item.get("values")
        if not isinstance(fields, dict):
            continue
        price = _num(fields.get("10"))
        pct = _num(fields.get("12"))
        if price is None or not 0 < abs(price) < 10000000:
            continue
        if pct is not None and not -100 < pct < 100000:
            pct = None
        updates[symbol] = (abs(price), pct)
    return updates

def _ranked_symbols(dsn):
    with psycopg.connect(dsn, connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute(RANK_QUERY)
            rows = cur.fetchall()
    if not rows:
        return None, {}
    sid = int(rows[0][0])
    selected = {}
    for _, symbol, exchange in rows:
        if (isinstance(symbol, str) and re.fullmatch(r"[A-Z0-9.\\-]{1,20}", symbol)
                and exchange in EXCHANGES):
            selected[symbol] = exchange
    return sid, selected
