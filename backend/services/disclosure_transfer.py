"""Temporary one-day DART/SEC disclosures: DigitalOcean writes, Render reads.

The latest per-stock result lives in Neon for at most 24 hours. Disclosure
filings themselves are limited to the prior 24 hours, never a 30-day archive.
This module does not start or alter the existing news worker.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo


def _database_url():
    return os.environ.get("NEWS_DATABASE_URL", "").strip()


def _valid_identity(market, symbol):
    market, symbol = str(market or "").upper(), str(symbol or "").upper()
    if market == "KR" and re.fullmatch(r"\d{6}", symbol):
        return market, symbol
    if market == "US" and re.fullmatch(r"[A-Z.]{1,10}", symbol):
        return market, symbol
    raise ValueError("invalid_disclosure_identity")


def _filing_timestamp(item, market, now):
    """Return a filing's UTC time; date-only DART entries are conservative."""
    zone = ZoneInfo("Asia/Seoul" if market == "KR" else "America/New_York")
    if market == "US":
        raw = str(item.get("acceptance_datetime") or "").strip()
        if raw:
            try:
                value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return value.replace(tzinfo=zone).astimezone(dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)
            except ValueError:
                pass
        raw_date = str(item.get("date") or "")[:10]
    else:
        raw_date = str(item.get("receipt_datetime") or "").strip()[:8]
        if not re.fullmatch(r"\d{8}", raw_date):
            raw_date = str(item.get("date") or "").strip()
        if re.fullmatch(r"\d{8}", raw_date):
            raw_date = raw_date[:4] + "-" + raw_date[4:6] + "-" + raw_date[6:]
    try:
        local_date = dt.date.fromisoformat(raw_date)
    except ValueError:
        return None
    local_today = now.astimezone(zone).date()
    time_string = str(item.get("time") or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", time_string):
        hour, minute = map(int, time_string.split(":"))
        if hour < 24 and minute < 60:
            return dt.datetime.combine(local_date, dt.time(hour, minute), tzinfo=zone).astimezone(dt.timezone.utc)
    # No verified time: only today's filings qualify, never yesterday's
    # potentially >24-hour-old disclosure.
    return dt.datetime.combine(local_date, dt.time.min, tzinfo=zone).astimezone(dt.timezone.utc) if local_date == local_today else None


def one_day_filings(filings, market, *, now=None):
    """Filter both old saved snapshots and new API results to at most 24h."""
    market = str(market).upper()
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_requires_timezone")
    cutoff = now - dt.timedelta(hours=24)
    accepted = []
    for item in filings or []:
        if not isinstance(item, dict):
            continue
        moment = _filing_timestamp(item, market, now)
        if moment is not None and cutoff <= moment <= now:
            accepted.append(item)
    return accepted


def read_snapshot(market, symbol):
    """Read-only. None means snapshot missing, stale, or unavailable."""
    if not _database_url():
        return None
    market, symbol = _valid_identity(market, symbol)
    try:
        import psycopg
        with psycopg.connect(_database_url(), connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT filings FROM public.disclosure_snapshots
                    WHERE market = %s AND symbol = %s
                      AND fetched_at > now() - interval '24 hours'
                """, (market, symbol))
                row = cur.fetchone()
        filings = row[0] if row else None
        if isinstance(filings, str):
            filings = json.loads(filings)
        if isinstance(filings, list) and all(isinstance(v, dict) for v in filings):
            return one_day_filings(filings, market)
    except Exception as exc:
        print("[disclosure-transfer] read_unavailable=" + type(exc).__name__, flush=True)
    return None


def _verify_empty_source(engine, market, symbol):
    """Do not turn network/API failures into a misleading 'no disclosure'."""
    if market == "US":
        cik = engine.US_CIKS[symbol]
        payload = engine.sec_filings.fetch_company_submissions(cik)
        return isinstance(payload.get("filings", {}).get("recent", {}).get("form"), list)
    corp_code = engine.fetch_dart_corp_code(symbol)
    if not corp_code:
        return False
    today = dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
    query = urllib.parse.urlencode({
        "crtfc_key": engine.OPENDART_API_KEY, "corp_code": corp_code,
        "bgn_de": (today - dt.timedelta(days=1)).strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"), "page_no": 1, "page_count": 1,
    })
    req = urllib.request.Request(
        "https://opendart.fss.or.kr/api/list.json?" + query,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.load(response)
    return str(result.get("status")) in ("000", "013")


def collect_once(market, symbol):
    """Fetch one stock on DigitalOcean, replace its only temporary Neon row."""
    market, symbol = _valid_identity(market, symbol)
    if not _database_url():
        raise RuntimeError("disclosure_db_missing")
    from . import engine
    if market == "KR":
        if symbol not in engine.DART_STOCK_CORP_CODES:
            raise ValueError("unsupported_dart_stock")
        if not engine.OPENDART_API_KEY:
            raise RuntimeError("opendart_key_missing")
        filings = engine.fetch_kr_official_disclosures(symbol, days=1, max_results=0)
        # DART listing has a date but not a clock time: resolve yesterday's
        # receipt times on the worker, never in the Render request path.
        today = dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
        for item in filings:
            if str(item.get("receipt_datetime") or "")[:8] == (today - dt.timedelta(days=1)).strftime("%Y%m%d"):
                item["time"] = engine._fetch_dart_receipt_time(item.get("receipt_no"))
    else:
        if symbol not in engine.US_CIKS:
            raise ValueError("unsupported_sec_ticker")
        filings = engine.fetch_us_official_filings(
            symbol, days=1, max_results=30, complete_window=True
        )
    if not isinstance(filings, list):
        raise RuntimeError("disclosure_list_unavailable")
    if not filings and not _verify_empty_source(engine, market, symbol):
        raise RuntimeError("disclosure_source_unavailable")
    filings = one_day_filings(filings, market)

    # All DART details are precomputed outside Render, keeping the panel
    # compatible with the old fields and avoiding interactive provider calls.
    if market == "KR":
        for item in filings:
            try:
                details = engine.fetch_dart_disclosure_detail(
                    symbol, item.get("receipt_no"), item.get("report", "")
                )
                if isinstance(details, dict):
                    item.update(details)
                    item["detail_preloaded"] = True
            except Exception as exc:
                print("[disclosure-transfer] dart_detail_unavailable=" + type(exc).__name__, flush=True)

    else:
        for item in filings:
            if str(item.get("form") or "").upper() in {"144", "10-Q", "10-K"} and item.get("url"):
                try:
                    item["panel_extra_detail"] = engine.sec_filings.fetch_panel_missing_detail(item["url"])
                except Exception as exc:
                    print("[disclosure-transfer] sec_detail_unavailable=" + type(exc).__name__, flush=True)

    # These records have been collected on DO. The browser must not request
    # DART/SEC provider enrichment through Render for this DB-backed snapshot.
    for item in filings:
        item["snapshot_only"] = True

    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(_database_url(), connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.disclosure_snapshots(market, symbol, filings, fetched_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (market, symbol) DO UPDATE
                SET filings = EXCLUDED.filings, fetched_at = EXCLUDED.fetched_at
            """, (market, symbol, Jsonb(filings)))
            cur.execute("""
                DELETE FROM public.disclosure_snapshots
                WHERE fetched_at <= now() - interval '24 hours'
            """)
    return {"market": market, "symbol": symbol, "filing_count": len(filings),
            "collected_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-day SEC/DART snapshot collection")
    parser.add_argument("--market", choices=("KR", "US"), required=True)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(collect_once(args.market, args.symbol), ensure_ascii=False))
        return 0
    except Exception as exc:
        print("disclosure_sync_error=" + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
