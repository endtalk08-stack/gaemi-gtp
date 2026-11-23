"""R2-only US daily candle serialization and publishing.

R2 is the single persistent chart store. This module has no database imports.
"""
from __future__ import annotations
import datetime as dt
import json
import math
import re
import tempfile
from pathlib import Path
from backend.services.r2_news_uploader import upload_file

SOURCE = "kiwoom:usa06012"
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def make_chart(symbol, rows):
    if not SYMBOL.fullmatch(symbol) or not rows:
        raise ValueError("invalid_chart_symbol_or_empty")
    candles = []
    last = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_chart_row")
        day = str(row.get("date") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or (last and day <= last):
            raise ValueError("invalid_chart_date_order")
        prices = tuple(float(row[k]) for k in ("open", "high", "low", "close"))
        if not all(math.isfinite(v) and v > 0 for v in prices):
            raise ValueError("invalid_chart_price")
        o, h, l, c = prices
        if l > min(o, c) or max(o, c) > h:
            raise ValueError("invalid_chart_ohlc")
        volume = row.get("volume")
        if volume is not None and (type(volume) is not int or not 0 <= volume <= 2**53 - 1):
            raise ValueError("invalid_chart_volume")
        candles.append({"date": day, "open": o, "high": h, "low": l,
                        "close": c, "volume": volume})
        last = day
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    return {"schema_version": 1, "market": "US", "symbol": symbol,
            "interval": "daily", "source": SOURCE, "generated_at": now,
            "count": len(candles), "first_date": candles[0]["date"],
            "last_date": candles[-1]["date"], "candles": candles}


def publish_chart(symbol, rows):
    payload = make_chart(symbol, rows)
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         suffix=".json", delete=False) as handle:
            filename = handle.name
            json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return upload_file(Path(filename), object_key=f"charts/us/{symbol}/daily.json")
    finally:
        if filename and Path(filename).exists():
            Path(filename).unlink()
