"""Refresh current Kiwoom US Top20 daily candles directly into R2.

R2 is the only persistent chart store. No Neon/Postgres connection or mirror.
"""
import datetime as dt
import json
import math
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_quotes import fetch_us_daily_chart, issue_access_token
from backend.services.r2_news_uploader import read_daily_chart
from backend.services.us_daily_r2_publisher import publish_chart
from backend.services.us_top20_metadata_sync import sync_once_after_close

SOURCE = "kiwoom:usa06012"
RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
NY = ZoneInfo("America/New_York")


def history_start(today, latest, count):
    start = today - dt.timedelta(days=180)
    return max(start, latest - dt.timedelta(days=4)) if latest else start


def valid_candle(row, start, end):
    try:
        day = dt.date.fromisoformat(row["date"])
        prices = [row[k] for k in ("open", "high", "low", "close")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in prices):
            return False
        opening, high, low, close = prices
        volume = row.get("volume")
        return (start <= day <= end and low <= min(opening, close)
                and max(opening, close) <= high
                and (volume is None or (type(volume) is int and volume >= 0)))
    except (ValueError, TypeError, KeyError):
        return False


def refresh_window(ny):
    return ny.weekday() < 5 and ny.time() >= dt.time(16, 15)


def _ranking_rows():
    if RANKING_FILE.is_symlink() or not RANKING_FILE.is_file():
        raise RuntimeError("local_top20_missing")
    data = json.loads(RANKING_FILE.read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != 20:
        raise RuntimeError("local_top20_incomplete")
    if [row.get("rank") for row in rows] != list(range(1, 21)):
        raise RuntimeError("local_top20_invalid_rank")
    return rows


def _expected_session(ny_date):
    expected = ny_date
    while expected.weekday() >= 5:
        expected -= dt.timedelta(days=1)
    return expected


def already_refreshed(now, chart):
    if not chart:
        return False
    ny = now.astimezone(NY)
    generated = chart.get("generated_at")
    if generated:
        try:
            stamp = dt.datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
            if stamp.tzinfo and stamp.astimezone(NY).date() == ny.date() and stamp.astimezone(NY).time() >= dt.time(16, 15):
                return True
        except ValueError:
            pass
    try:
        latest = dt.date.fromisoformat(str(chart.get("last_date") or ""))
    except ValueError:
        return False
    return latest >= _expected_session(ny.date())


def main(*, bootstrap=False):
    now = dt.datetime.now(dt.timezone.utc)
    ny = now.astimezone(NY)
    if not bootstrap and not refresh_window(ny):
        print("CHART_REFRESH_SKIP=outside_post_close_window", flush=True)
        return
    matches = _ranking_rows()
    token = None
    failed = 0
    for item in matches:
        symbol = str(item.get("symbol") or "").strip().upper()
        exchange = str(item.get("exchange") or "").strip().upper()
        if not symbol or exchange not in ("ND", "NY", "NA"):
            failed += 1
            print("CHART_R2_RETRY kind=invalid_top20_identity", flush=True)
            continue
        try:
            existing = read_daily_chart(symbol)
            if not bootstrap and already_refreshed(now, existing):
                print("CHART_R2_SKIP symbol=%s reason=already_current" % symbol, flush=True)
                continue
            old_rows = existing.get("candles", []) if isinstance(existing, dict) else []
            old_by_date = {str(row["date"]): dict(row) for row in old_rows if isinstance(row, dict)}
            latest = dt.date.fromisoformat(max(old_by_date)) if old_by_date else None
            start = history_start(ny.date(), latest, len(old_by_date))
            if token is None:
                token = issue_access_token()
            result = fetch_us_daily_chart(symbol, exchange, start, end_date=ny.date(),
                                          token=token, max_pages=10)
            rows = result.get("rows")
            if (result.get("ticker") != symbol or result.get("source") != SOURCE
                    or not isinstance(rows, list) or not rows
                    or not all(valid_candle(row, start, ny.date()) for row in rows)):
                raise ValueError("invalid_chart_result")
            for row in rows:
                old_by_date[row["date"]] = dict(row)
            merged = [old_by_date[key] for key in sorted(old_by_date)][-180:]
            if not publish_chart(symbol, merged):
                raise RuntimeError("r2_upload_failed")
            print("CHART_R2_OK symbol=%s rows=%s" % (symbol, len(merged)), flush=True)
        except Exception as exc:
            failed += 1
            print("CHART_R2_RETRY symbol=%s kind=%s" % (symbol, type(exc).__name__), flush=True)
        finally:
            time.sleep(0.4)
    try:
        print("US_TOP20_R2_SYNC=" + sync_once_after_close(now=now), flush=True)
    except Exception as exc:
        failed += 1
        print("US_TOP20_R2_SYNC_ERROR=" + type(exc).__name__, flush=True)
    print("CHART_R2_DONE symbols=%s failed=%s" % (len(matches), failed), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true", help="One-time current TOP20 chart initialization")
    main(bootstrap=parser.parse_args().bootstrap)
