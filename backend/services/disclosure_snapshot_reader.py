"""Render-side read-only SEC/DART snapshots stored by DigitalOcean.

This module performs no SEC/DART HTTP requests or database writes.  It is
not connected to the live analysis path until a separate verified cutover.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta

_RETENTION_DAYS = 30
_MARKETS = frozenset(("US", "KR"))


def _filing_datetime(filing):
    """Use authoritative receipt/acceptance dates, not the snapshot refresh date."""
    for name in ("acceptance_datetime", "receipt_datetime", "date"):
        text = str(filing.get(name) or "").strip()
        if not text:
            continue
        try:
            if re.fullmatch(r"\d{8}", text):
                return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def read_disclosure_snapshot(market, symbol, *, now=None):
    """Return 30-day snapshot filings, or None if the DB/row is unavailable.

    None is deliberately different from []: a valid snapshot can legitimately
    contain no filings within the 30-day window. No external fetch fallback.
    """
    market = str(market or "").strip().upper()
    symbol = str(symbol or "").strip().upper()
    if market not in _MARKETS:
        return None
    pattern = r"[A-Z.]{1,10}" if market == "US" else r"\d{6}"
    if not re.fullmatch(pattern, symbol):
        return None
    url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT filings FROM public.disclosure_snapshots
                       WHERE market = %s AND symbol = %s
                         AND fetched_at >= now() - interval '30 days'""",
                    (market, symbol),
                )
                row = cursor.fetchone()
    except Exception as exc:
        print("[disclosure-snapshot] read_unavailable=" + type(exc).__name__, flush=True)
        return None
    if row is None:
        return None
    records = row[0]
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except (ValueError, TypeError):
            return None
    if not isinstance(records, list):
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current.astimezone(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    return [
        record for record in records
        if isinstance(record, dict)
        and (record_time := _filing_datetime(record)) is not None
        and record_time >= cutoff
    ]
