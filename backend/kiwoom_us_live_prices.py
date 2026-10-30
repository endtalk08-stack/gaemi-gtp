"""Shared Kiwoom US real-time feed helpers for the direct Render relay.

Symbol/exchange validation and the existing DigitalOcean local Top-20 snapshot only.
This module does not collect ticks or read/write Neon/Redis.
The active collector is backend.kiwoom_us_price_relay.
"""
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "wss://api.kiwoom.com:10000/api/us/websocket"
EXCHANGES = {"ND", "NY", "NA"}
LOCAL_TOP20_PATH = "/var/lib/gaemigtp-news/kiwoom-us-top20-news.json"

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
        # Official Kiwoom FE fields: 17=session high, 18=session low.
        # The sidebar and central metrics must share this exact FE update.
        high = _num(fields.get("17"))
        low = _num(fields.get("18"))
        high = abs(high) if high is not None and 0 < abs(high) < 10000000 else None
        low = abs(low) if low is not None and 0 < abs(low) < 10000000 else None
        if high is not None and low is not None and high < low:
            high, low = None, None
        updates[symbol] = (abs(price), pct, high, low)
    return updates

def _ranked_symbols(snapshot_path=None):
    """Read one complete Kiwoom Top-20 snapshot from DigitalOcean local storage."""
    path = Path(snapshot_path or LOCAL_TOP20_PATH)
    if path.is_symlink():
        raise ValueError("unsafe_local_ranking_path")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("source") != "kiwoom" or data.get("market") != "US"
            or data.get("rank_type") != "trading_value"):
        raise ValueError("invalid_local_kiwoom_snapshot")
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("incomplete_local_kiwoom_top20")
    selected, ranks = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_local_kiwoom_row")
        rank = row.get("rank")
        symbol = row.get("symbol")
        exchange = row.get("exchange")
        if (type(rank) is not int or not 1 <= rank <= 20 or rank in ranks
                or not isinstance(symbol, str)
                or not re.fullmatch(r"[A-Z0-9.\\-]{1,20}", symbol)
                or symbol in selected or exchange not in EXCHANGES):
            raise ValueError("invalid_local_kiwoom_row")
        ranks.add(rank)
        selected[symbol] = exchange
    if ranks != set(range(1, 21)):
        raise ValueError("incomplete_local_kiwoom_top20")
    return data.get("captured_at"), selected
