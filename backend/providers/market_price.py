import datetime
import json
import threading
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_CACHE_LOCK_GUARD = threading.Lock()
_CACHE_LOCKS = {}
US_QUOTE_CACHE = {}
US_QUOTE_CACHE_TTL = 15
DAILY_HISTORY_CACHE = {}
INTRADAY_HISTORY_CACHE = {}
INTRADAY_HISTORY_CACHE_TTL = 60



def _get_lock(key):
    with _CACHE_LOCK_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _CACHE_LOCKS[key] = lock
        return lock


def _history_ttl(ticker):
    symbol = str(ticker or "").upper()
    return 600 if symbol.endswith((".KS", ".KQ")) else 15


def fetch_daily_price_history(ticker):
    """Yahoo 2년 일봉 원천을 공통으로 제공한다."""
    key = str(ticker or "").strip().upper()
    if not key:
        return []

    now = time.time()
    ttl = _history_ttl(key)
    cached = DAILY_HISTORY_CACHE.get(key)
    if cached and now - cached[0] < ttl:
        return cached[1]

    with _get_lock(("daily-history", key)):
        now = time.time()
        cached = DAILY_HISTORY_CACHE.get(key)
        if cached and now - cached[0] < ttl:
            return cached[1]

        rows = []
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(key)}?range=2y&interval=1d"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            chart_rows = data.get("chart", {}).get("result", [])
            if chart_rows:
                chart = chart_rows[0]
                quote = chart.get("indicators", {}).get("quote", [{}])[0]
                closes = quote.get("close", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                volumes = quote.get("volume", [])
                timestamps = chart.get("timestamp") or []
                timezone_name = (chart.get("meta") or {}).get("exchangeTimezoneName")
                try:
                    exchange_timezone = ZoneInfo(timezone_name) if timezone_name else None
                except (ZoneInfoNotFoundError, TypeError, ValueError):
                    exchange_timezone = None

                for index, (close, high, low, volume) in enumerate(zip(closes, highs, lows, volumes)):
                    if close is None or high is None or low is None:
                        continue
                    try:
                        close_value = float(close)
                        high_value = float(high)
                        low_value = float(low)
                        volume_value = float(volume or 0)
                    except (TypeError, ValueError):
                        continue
                    if close_value <= 0 or high_value <= 0 or low_value <= 0:
                        continue
                    row = {
                        "close": close_value,
                        "high": high_value,
                        "low": low_value,
                        "volume": volume_value,
                    }
                    # 거래소 현지 날짜가 확인된 일봉만 날짜를 붙인다.
                    # timestamp가 없거나 잘못되어도 기존 OHLCV 행은 보존한다.
                    if exchange_timezone is not None and index < len(timestamps):
                        stamp = timestamps[index]
                        if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
                            try:
                                row["date"] = datetime.datetime.fromtimestamp(
                                    stamp, tz=exchange_timezone
                                ).date().isoformat()
                            except (OverflowError, OSError, ValueError):
                                pass
                    rows.append(row)
        except Exception as exc:
            print("야후 일봉 조회 예외:", exc)

        DAILY_HISTORY_CACHE[key] = (now, rows)
        return rows


def fetch_intraday_price_history(ticker):
    """Return cached 5-minute OHLC rows for short-lived news reaction calculations."""
    key = str(ticker or "").strip().upper()
    if not key:
        return []

    now = time.time()
    cached = INTRADAY_HISTORY_CACHE.get(key)
    if cached and now - cached[0] < INTRADAY_HISTORY_CACHE_TTL:
        return cached[1]

    with _get_lock(("intraday-history", key)):
        now = time.time()
        cached = INTRADAY_HISTORY_CACHE.get(key)
        if cached and now - cached[0] < INTRADAY_HISTORY_CACHE_TTL:
            return cached[1]

        rows = []
        try:
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{urllib.parse.quote(key)}?range=5d&interval=5m&includePrePost=false"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/152.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            chart_rows = data.get("chart", {}).get("result", [])
            if chart_rows:
                chart = chart_rows[0]
                timestamps = chart.get("timestamp") or []
                quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
                closes = quote.get("close") or []
                highs = quote.get("high") or []
                lows = quote.get("low") or []
                for index, (stamp, close) in enumerate(zip(timestamps, closes)):
                    if stamp is None or close is None:
                        continue
                    high = highs[index] if index < len(highs) else close
                    low = lows[index] if index < len(lows) else close
                    if high is None:
                        high = close
                    if low is None:
                        low = close
                    try:
                        stamp_value = int(stamp)
                        close_value = float(close)
                        high_value = float(high)
                        low_value = float(low)
                    except (TypeError, ValueError):
                        continue
                    if stamp_value > 0 and close_value > 0 and high_value > 0 and low_value > 0:
                        rows.append({
                            "timestamp": stamp_value,
                            "close": close_value,
                            "high": high_value,
                            "low": low_value,
                        })
        except Exception as exc:
            print("야후 5분봉 조회 예외:", exc)

        INTRADAY_HISTORY_CACHE[key] = (now, rows)
        return rows


def _parse_news_timestamp(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        try:
            from email.utils import parsedate_to_datetime
            parsed = parsedate_to_datetime(raw)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


def calculate_news_price_reaction(rows, published_at):
    """Calculate the first trading session's price range after a news event.

    The baseline stays the last trade at or before the article timestamp. The
    low/high range is limited to the first regular trading session that follows
    the news timestamp, so a later day's move is not mixed into the event.
    close_pct is exposed only after that session is clearly finished; while the
    session is live, the moving latest price is intentionally not presented as
    a closing price.
    """
    target = _parse_news_timestamp(published_at)
    if target is None:
        return None

    clean_rows = []
    for row in rows or []:
        try:
            stamp = int((row or {}).get("timestamp") or 0)
            close = float((row or {}).get("close") or 0)
            high = float((row or {}).get("high") or close)
            low = float((row or {}).get("low") or close)
        except (TypeError, ValueError):
            continue
        if stamp > 0 and close > 0 and high > 0 and low > 0:
            clean_rows.append((stamp, close, high, low))
    clean_rows.sort(key=lambda item: item[0])
    if not clean_rows:
        return None

    latest_stamp, latest_close, _, _ = clean_rows[-1]
    baseline = None
    exact_bar_boundary = False
    for stamp, close, high, low in clean_rows:
        if stamp < target:
            baseline = (stamp, close)
            continue
        if stamp == target:
            # Yahoo 5-minute timestamps represent the bar start. When an
            # article lands exactly on that boundary, the same bar belongs to
            # the post-news reaction, not to the pre-news baseline.
            exact_bar_boundary = True
        break

    # The fetched intraday window does not contain a pre-news trade.
    if not baseline:
        return None

    base_stamp, base_close = baseline
    if base_close <= 0:
        return None

    # Keep the legacy latest-change fields for internal compatibility. The
    # central UI no longer renders them as the news reaction.
    change_pct = ((latest_close - base_close) / base_close) * 100
    result = {
        "status": "ready",
        "change_pct": round(change_pct, 2),
        "base_price": base_close,
        "current_price": latest_close,
        "baseline_at": base_stamp,
        "current_at": latest_stamp,
        "low_pct": None,
        "high_pct": None,
        "close_pct": None,
    }

    if exact_bar_boundary:
        post_rows = [row for row in clean_rows if row[0] >= target]
    else:
        post_rows = [row for row in clean_rows if row[0] > target]
    if not post_rows:
        return result

    reaction_day = datetime.datetime.fromtimestamp(
        post_rows[0][0],
        tz=datetime.timezone.utc,
    ).date()
    session_rows = []
    for row in post_rows:
        row_day = datetime.datetime.fromtimestamp(
            row[0],
            tz=datetime.timezone.utc,
        ).date()
        if row_day == reaction_day:
            session_rows.append(row)
        elif session_rows:
            break

    if not session_rows:
        return result

    low_price = min(row[3] for row in session_rows)
    high_price = max(row[2] for row in session_rows)
    close_stamp, close_price, _, _ = session_rows[-1]
    result["low_pct"] = round(((low_price - base_close) / base_close) * 100, 2)
    result["high_pct"] = round(((high_price - base_close) / base_close) * 100, 2)

    # If a later trading day exists, this session is certainly complete. For
    # the latest day, wait 30 minutes after the last 5-minute candle before
    # treating that candle as the session close, avoiding a live current price
    # being mislabeled as a close.
    later_session_exists = any(
        datetime.datetime.fromtimestamp(row[0], tz=datetime.timezone.utc).date() != reaction_day
        for row in clean_rows
        if row[0] > close_stamp
    )
    session_is_stale = time.time() - close_stamp >= 30 * 60
    if later_session_exists or session_is_stale:
        result["close_pct"] = round(((close_price - base_close) / base_close) * 100, 2)

    return result

def fetch_news_price_reaction(ticker, published_at):
    """Fetch cached intraday data once per ticker and calculate a news reaction."""
    rows = fetch_intraday_price_history(ticker)
    return calculate_news_price_reaction(rows, published_at)


def fetch_us_stock_quote(ticker):
    key = str(ticker or "").strip().upper()
    now = time.time()
    cached = US_QUOTE_CACHE.get(key)
    if cached and now - cached[0] < US_QUOTE_CACHE_TTL:
        return cached[1]

    with _get_lock(("us-quote", key)):
        now = time.time()
        cached = US_QUOTE_CACHE.get(key)
        if cached and now - cached[0] < US_QUOTE_CACHE_TTL:
            return cached[1]

        rows = fetch_daily_price_history(key)
        if len(rows) >= 2:
            latest = rows[-1]
            previous = rows[-2]
            result = (
                latest["close"],
                previous["close"],
                latest["high"],
                latest["low"],
            )
        else:
            result = (None, None, None, None)

        US_QUOTE_CACHE[key] = (now, result)
        return result
