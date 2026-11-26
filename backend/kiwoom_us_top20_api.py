"""Serve the existing Kiwoom TOP20 ranking and the in-memory US quote stream."""
import base64
import fcntl
import tempfile
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
import re
import select
import struct
import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from backend.kiwoom_us_live_prices import MARKET_WIDGET_ETF_EXCHANGES

RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")

_US_INDUSTRY_CACHE_LOCK = threading.Lock()
_US_INDUSTRY_MAP_CACHE = {"expires_at": 0.0, "data": None}
_US_INDUSTRY_STOCK_CACHE = {}
_US_INDUSTRY_STOCK_LOCKS = {}
_US_INDUSTRY_ETF_CACHE_LOCK = threading.Lock()
_US_INDUSTRY_ETF_CACHE = {}
_US_INDUSTRY_ETF_TTL = 60
_US_PLATFORM_CACHE_LOCK = threading.Lock()
_US_PLATFORM_CACHE = {"expires_at": 0.0, "data": None}
_US_INDUSTRY_MAP_TTL = 60
_US_INDUSTRY_STOCK_TTL = 1800


def _safe_industry_error(exc):
    value = str(exc)
    return value if re.fullmatch(r"[a-z0-9_]{1,90}", value) else type(exc).__name__


def _get_us_industry_maps():
    from backend.providers.kiwoom_us_industries import fetch_us_industry_maps

    now = time.monotonic()
    with _US_INDUSTRY_CACHE_LOCK:
        cached = _US_INDUSTRY_MAP_CACHE["data"]
        if cached is not None and now < _US_INDUSTRY_MAP_CACHE["expires_at"]:
            return dict(cached)
        try:
            result = fetch_us_industry_maps()
        except Exception:
            if cached is not None:
                return {name: {**data, "stale": True} for name, data in cached.items()}
            raise
        _US_INDUSTRY_MAP_CACHE["data"] = dict(result)
        _US_INDUSTRY_MAP_CACHE["expires_at"] = now + _US_INDUSTRY_MAP_TTL
        return dict(result)


def _get_us_internet_platform_group():
    from backend.providers.kiwoom_us_industries import fetch_us_internet_platform_group
    from backend.providers.kiwoom_us_quotes import KiwoomReadOnlyError

    with _US_PLATFORM_CACHE_LOCK:
        if time.monotonic() >= _US_PLATFORM_CACHE["expires_at"]:
            try:
                _US_PLATFORM_CACHE["data"] = fetch_us_internet_platform_group()
            except KiwoomReadOnlyError:
                _US_PLATFORM_CACHE["data"] = None
            _US_PLATFORM_CACHE["expires_at"] = time.monotonic() + _US_INDUSTRY_MAP_TTL
        return _US_PLATFORM_CACHE["data"]


def _get_us_industry_map(view="legacy"):
    maps = _get_us_industry_maps()
    if view != "heatmap":
        return dict(maps["legacy"])

    heatmap = maps["heatmap"]
    missing = [
        item["key"] for item in heatmap["items"]
        if item["mapping_status"] != "matched"
    ]
    if missing == ["internet_platforms"]:
        platform = _get_us_internet_platform_group()
        if platform is not None:
            from backend.providers.kiwoom_us_industries import rank_us_industry_rows

            items = [
                {**item, **platform} if item["key"] == "internet_platforms" else item
                for item in heatmap["items"]
            ]
            heatmap = {**heatmap, "items": rank_us_industry_rows(items), "mapping_complete": True}
            missing = []
    return {
        **heatmap,
        "view": "heatmap",
        "heatmap_ready": not missing,
        "heatmap_missing": missing,
    }


def _get_us_industry_stocks(industry_key_or_code, sort="marketcap", *, sector_map=None):
    from backend.providers.kiwoom_us_industries import fetch_us_industry_stocks

    if sort not in ("change", "value", "marketcap"):
        raise ValueError("invalid_industry_sort")
    if sector_map is None:
        sector_map = _get_us_industry_map()
    selected = next((
        item for item in sector_map.get("items", [])
        if isinstance(item, dict) and (
            str(item.get("key") or "") == industry_key_or_code
            or str(item.get("code") or "") == industry_key_or_code
            or industry_key_or_code in [str(code) for code in (item.get("codes") or [])]
        )
    ), None)
    if selected is None:
        raise ValueError("invalid_industry_code")
    codes = selected.get("codes") or ([selected.get("code")] if selected.get("code") else [])
    if not codes:
        raise ValueError("invalid_industry_code")

    key = (tuple(str(code) for code in codes), sort)
    now = time.monotonic()
    with _US_INDUSTRY_CACHE_LOCK:
        lock = _US_INDUSTRY_STOCK_LOCKS.setdefault(key, threading.Lock())
    # Coalesce requests for one sector without blocking independent sectors.
    with lock:
        now = time.monotonic()
        with _US_INDUSTRY_CACHE_LOCK:
            cached = _US_INDUSTRY_STOCK_CACHE.get(key)
        if cached and now < cached["expires_at"]:
            return dict(cached["data"])
        try:
            result = fetch_us_industry_stocks(codes, sort, limit=12 if sort == "marketcap" else 36)
        except Exception:
            if cached:
                stale = dict(cached["data"])
                stale["stale"] = True
                return stale
            raise

        items = result.get("items") if isinstance(result, dict) else None
        if not items and cached and cached["data"].get("items"):
            # A successful-but-empty response (Kiwoom briefly has nothing to
            # rank for this sector) must not evict a good previous snapshot or
            # freeze "no stocks" for the full 30-minute TTL -- serve the last
            # good list, marked stale, and retry again soon.
            with _US_INDUSTRY_CACHE_LOCK:
                _US_INDUSTRY_STOCK_CACHE[key] = {"expires_at": time.monotonic() + 60, "data": cached["data"]}
            stale = dict(cached["data"])
            stale["stale"] = True
            return stale

        with _US_INDUSTRY_CACHE_LOCK:
            _US_INDUSTRY_STOCK_CACHE[key] = {
                "expires_at": time.monotonic() + (_US_INDUSTRY_STOCK_TTL if items else 60),
                "data": dict(result),
            }
        return dict(result)


def _get_us_industry_etf_quotes():
    """Use verified live ticks, then compute missing ETF rates from Kiwoom REST prices."""
    from backend.providers.kiwoom_us_industries import ETF_TICKERS, fetch_us_etf_quotes
    from backend.us_quote_change import validated_change

    def current_ticks():
        return {quote["symbol"]: quote for quote in _etf_snapshot()
                if not quote["stale"] and quote["change_pct"] is not None}

    live = current_ticks()
    fallback = {}
    if ETF_TICKERS.difference(live):
        with _US_INDUSTRY_ETF_CACHE_LOCK:
            live = current_ticks()
            now = time.monotonic()
            missing = ETF_TICKERS.difference(live)
            due = {symbol for symbol in missing
                   if now >= _US_INDUSTRY_ETF_CACHE.get(symbol, (0.0, None))[0]}
            if due:
                try:
                    fetched = {
                        item["symbol"]: item
                        for item in fetch_us_etf_quotes(symbols=due)
                        if isinstance(item, dict)
                        and item.get("symbol") in due
                        and type(item.get("price")) in (int, float)
                        and math.isfinite(item["price"]) and item["price"] > 0
                        and item.get("exchange") in ("NY", "ND", "NA")
                        and isinstance(item.get("received_at_ms"), int)
                    }
                except Exception:
                    fetched = {}
                refresh_at = time.monotonic() + _US_INDUSTRY_ETF_TTL
                for symbol in due:
                    _, previous = _US_INDUSTRY_ETF_CACHE.get(symbol, (0.0, None))
                    _US_INDUSTRY_ETF_CACHE[symbol] = (refresh_at, fetched.get(symbol, previous))
            now_ms = int(time.time() * 1000)
            # Never display yesterday's REST price as a live ETF move.
            fallback = {symbol: quote for symbol, (_, quote) in _US_INDUSTRY_ETF_CACHE.items()
                        if quote and 0 <= now_ms - quote["received_at_ms"] <= 120000}
        live = current_ticks()

    result = []
    for symbol in sorted(ETF_TICKERS):
        quote = live.get(symbol) or fallback.get(symbol) or {}
        if symbol in live:
            percent = quote.get("change_pct")
            close_date = quote.get("reference_close_date")
        else:
            percent, close_date = None, None
            if quote.get("price") and quote.get("exchange"):
                try:
                    # Yahoo supplies only the previous regular close; current price is Kiwoom.
                    percent, close_date = validated_change(
                        symbol, quote["exchange"], quote["price"])
                except (ValueError, TypeError, ArithmeticError):
                    pass
        item = {
            "symbol": symbol,
            "change_pct": percent,
            "reference_close_date": close_date,
            "received_at_ms": quote.get("received_at_ms", 0),
            "stale": symbol not in live,
            "source": "kiwoom:websocket" if symbol in live else "kiwoom:rest",
        }
        held = _us_close_get(symbol, exchange=quote.get("exchange") or _CLOSE_EXCHANGES.get(symbol))
        if held:
            item.update({
                "change_pct": held["change_pct"],
                "reference_close_date": held["reference_close_date"],
                "received_at_ms": held["received_at_ms"],
                "stale": False,
                "source": held["source"],
                "market_session": held["market_session"],
            })
        result.append(item)
    return result

def _get_us_industry_map_with_stocks(view="legacy"):
    source = _get_us_industry_map(view)
    limit = 3
    result = dict(source)
    result["items"] = []
    def add_stocks(item):
        if not isinstance(item, dict):
            return None
        row = dict(item)
        candidate_limit = 4 if view == "heatmap" and row.get("key") in ("biotech", "software", "communication") else limit
        row["stocks"] = [dict(stock) for stock in item.get("stocks", [])[:candidate_limit]]
        if not row["stocks"] and (row.get("codes") or row.get("code")):
            try:
                stock_result = _get_us_industry_stocks(str(row.get("key") or ""), "marketcap", sector_map=source)
                row["stocks"] = stock_result.get("items", [])[:candidate_limit]
            except Exception as exc:
                row["stocks_error"] = _safe_industry_error(exc)
        if view == "heatmap" and row.get("key") == "software":
            # One cached official lookup for the requested ANT slot; no fixed quote.
            key = ("anthropic", "marketcap")
            now = time.monotonic()
            with _US_INDUSTRY_CACHE_LOCK:
                cached = _US_INDUSTRY_STOCK_CACHE.get(key)
            if cached and now < cached["expires_at"]:
                anthropic = cached["data"]
            else:
                from backend.providers.kiwoom_us_industries import fetch_us_anthropic_stock
                try:
                    anthropic = fetch_us_anthropic_stock()
                except Exception:
                    anthropic = cached["data"] if cached else None
                with _US_INDUSTRY_CACHE_LOCK:
                    _US_INDUSTRY_STOCK_CACHE[key] = {
                        "expires_at": now + _US_INDUSTRY_STOCK_TTL, "data": anthropic,
                    }
            if anthropic and not any(str(stock.get("symbol", "")).upper().split(".")[0] == "ANT"
                                     for stock in row["stocks"]):
                row["stocks"].append(dict(anthropic))
        if view == "heatmap" and row.get("key") == "communication":
            # One cached official lookup for the requested SPCX slot; no fixed quote.
            # The frontend's own market-cap sort then naturally ranks it ahead of
            # whichever existing candidate is smallest -- no manual slot override.
            key = ("spacex", "marketcap")
            now = time.monotonic()
            with _US_INDUSTRY_CACHE_LOCK:
                cached = _US_INDUSTRY_STOCK_CACHE.get(key)
            if cached and now < cached["expires_at"]:
                spacex = cached["data"]
            else:
                from backend.providers.kiwoom_us_industries import fetch_us_spacex_stock
                try:
                    spacex = fetch_us_spacex_stock()
                except Exception:
                    spacex = cached["data"] if cached else None
                with _US_INDUSTRY_CACHE_LOCK:
                    _US_INDUSTRY_STOCK_CACHE[key] = {
                        "expires_at": now + _US_INDUSTRY_STOCK_TTL, "data": spacex,
                    }
            if spacex and not any(str(stock.get("symbol", "")).upper().split(".")[0] == "SPCX"
                                   for stock in row["stocks"]):
                row["stocks"].append(dict(spacex))
        return row

    def get_bitcoin_stocks():
        from backend.providers.kiwoom_us_industries import fetch_us_bitcoin_related_stocks
        key = ("bitcoin_related", "marketcap")
        now = time.monotonic()
        with _US_INDUSTRY_CACHE_LOCK:
            cached = _US_INDUSTRY_STOCK_CACHE.get(key)
        if cached and now < cached["expires_at"]:
            bitcoin_stocks = cached["data"]
        else:
            try:
                bitcoin_stocks = fetch_us_bitcoin_related_stocks()
                if not bitcoin_stocks and cached and cached["data"]:
                    bitcoin_stocks = cached["data"]
                with _US_INDUSTRY_CACHE_LOCK:
                    _US_INDUSTRY_STOCK_CACHE[key] = {
                        "expires_at": time.monotonic() + (_US_INDUSTRY_STOCK_TTL if bitcoin_stocks else 60),
                        "data": bitcoin_stocks,
                    }
            except Exception:
                bitcoin_stocks = cached["data"] if cached else []
        return bitcoin_stocks

    # Kiwoom's existing 0.22s global call interval still bounds call starts.
    if view == "heatmap":
        with ThreadPoolExecutor(max_workers=5) as pool:
            etf_future = pool.submit(_get_us_industry_etf_quotes)
            bitcoin_future = pool.submit(get_bitcoin_stocks)
            result["items"] = [row for row in pool.map(add_stocks, source.get("items", [])) if row]
            bitcoin_stocks = bitcoin_future.result()
            etf_quotes = etf_future.result()
        result["items"].append({"key": "bitcoin_related", "name": "비트코인 관련 종목",
                                "stocks": bitcoin_stocks, "source": "kiwoom:usa20100"})
        result["etf_quotes"] = etf_quotes
    else:
        result["items"] = [row for row in map(add_stocks, source.get("items", [])) if row]
    # Reuse today's already-verified tick rates; never replace them with a
    # vendor percentage calculated from a different regular-close session.
    from backend.us_quote_change import _target, validated_change
    session_key = _target(datetime.now(timezone.utc))[0].isoformat()
    with _QQQ_LOCK:
        confirmed = {quote["symbol"]: quote for quote in
                     list(_INDUSTRY_QUOTES.values()) + list(_TOP20_QUOTES.values())
                     if quote.get("reference_close_session") == session_key
                     and type(quote.get("change_pct")) in (int, float)}
    for row in result["items"]:
        row["change_pct"] = None
        for stock in row.get("stocks", []):
            symbol = str(stock.get("symbol") or "").upper().split(".")[0]
            quote = _us_close_get(symbol, exchange=stock.get("exchange")) or confirmed.get(symbol)
            if quote:
                stock["change_pct"] = quote["change_pct"]
                stock["reference_close_date"] = quote.get("reference_close_date")
                if quote.get("market_session") == "last_regular_tick":
                    stock["price"] = quote["price"]
            else:
                stock["change_pct"] = None
                price, exchange = stock.get("price"), stock.get("exchange")
                if type(price) in (int, float) and 0 < price < 10000000 and exchange in ("ND", "NY", "NA"):
                    # The current price was already supplied by Kiwoom with the industry map.
                    # Yahoo only supplies the cached preceding regular close (no additional Kiwoom request).
                    percent, close_date = validated_change(symbol, exchange, price)
                    stock["change_pct"] = percent
                    stock["reference_close_date"] = close_date
    result["sort"] = "marketcap"
    return result


def get_us_industry_stock_symbols():
    """Return only the top-three market-cap stocks from each heatmap sector."""
    result = _get_us_industry_map_with_stocks("heatmap")
    symbols = {}
    for sector in result.get("items", []):
        if not isinstance(sector, dict):
            continue
        stock_limit = 5 if sector.get("key") == "software" else 4 if sector.get("key") == "biotech" else 3
        for stock in sector.get("stocks", [])[:stock_limit]:
            if not isinstance(stock, dict):
                continue
            symbol = str(stock.get("symbol") or "").strip().upper()
            exchange = str(stock.get("exchange") or "").strip().upper()
            if SYMBOL.fullmatch(symbol) and exchange in ("ND", "NY", "NA"):
                symbols[symbol] = exchange
    return symbols


def get_us_etf_symbols():
    """Return the fixed, verified exchange mapping for the fourteen industry ETFs.

    Their listing venues are stable. Resolving them through usa10104 on every
    WebSocket reconnect caused the dedicated ETF subscription to fail; do not
    make a full-market exchange-list request just to register these symbols.
    """
    from backend.providers.kiwoom_us_industries import ETF_TICKERS

    exchanges = {
        "IBIT": "ND",
        "SOXX": "ND",
        "XBI": "NY",
        "XLB": "NY",
        "XLC": "NY",
        "XLE": "NY",
        "XLF": "NY",
        "XLI": "NY",
        "XLK": "NY",
        "XLP": "NY",
        "XLRE": "NY",
        "XLU": "NY",
        "XLV": "NY",
        "XLY": "NY",
    }
    if set(exchanges) != set(ETF_TICKERS):
        raise RuntimeError("industry_etf_exchange_map_incomplete")
    return {symbol: exchanges[symbol] for symbol in sorted(ETF_TICKERS)}


ADDRESS = "127.0.0.1"
PORT = 8765
ALLOWED_ORIGINS = {
    "https://gaemi-gtp.onrender.com",
    "https://gaemigtp.com",
    "https://www.gaemigtp.com",
    "https://gaemigtp-news.pages.dev",
    "https://gaemigtp-main.pages.dev",
    "https://github-pages-preview.gaemigtp-main.pages.dev",
}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")

_QQQ_LOCK = threading.Lock()
_QQQ_CHANGED = threading.Condition(_QQQ_LOCK)
_QQQ_QUOTE = None
_TOP20_SYMBOLS = frozenset()
_INDUSTRY_SYMBOLS = frozenset()
_ETF_SYMBOLS = frozenset()
_CLOSE_EXCHANGES = {}
_TOP20_QUOTES = {}
_INDUSTRY_QUOTES = {}
_ETF_QUOTES = {}
_MARKET_WIDGET_QUOTES = {}
_MARKET_WIDGET_REST_LOCK = threading.Lock()
_MARKET_WIDGET_REST_CACHE = {}
_MARKET_WIDGET_REST_MAX_AGE_MS = 30 * 60 * 1000
_QQQ_WS_CLIENTS = threading.BoundedSemaphore(48)
_QQQ_STALE_MS = 25000
_QQQ_REST_STALE_MS = 65000
_QQQ_REST_CACHE_LOCK = threading.Lock()
_QQQ_REST_CACHE = {"expires_at": 0.0, "data": None}
_QQQ_REST_TTL = 60
_QQQ_REST_RETRY_TTL = 15
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# Last *verified regular-session trade*, not the official closing-auction price.
# This record is shared by the two read-only US quote API processes and survives
# a service restart. Only public prices/rates are stored, never credentials.
_US_CLOSE_NY = ZoneInfo("America/New_York")
_US_CLOSE_FILE = Path("/var/lib/gaemigtp-news/us-regular-last-verified.json")
_US_CLOSE_LOCK_FILE = Path("/var/lib/gaemigtp-news/us-regular-last-verified.lock")
_US_CLOSE_LOCK = threading.RLock()
_US_CLOSE_CACHE = {"day": "", "items": {}}
_US_CLOSE_LAST_SAVE = 0.0
_US_CLOSE_LAST_READ = 0.0
_US_CLOSE_MAX_BYTES = 100000


def _us_market_holidays(year):
    """NYSE full-day holidays, including observed fixed-date holidays."""
    def observed(month, day):
        value = date(year, month, day)
        if value.weekday() == 5:
            return value - timedelta(days=1)
        if value.weekday() == 6:
            return value + timedelta(days=1)
        return value

    def nth_weekday(month, weekday, number):
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (number - 1))

    def last_weekday(month, weekday):
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return last - timedelta(days=(last.weekday() - weekday) % 7)

    # Gregorian Easter calculation; NYSE is closed on Good Friday.
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f, g = divmod(b + 8, 25)
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_month = (h + l - 7 * m + 114) // 31
    easter_day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, easter_month, easter_day)

    holidays = {
        observed(1, 1), nth_weekday(1, 0, 3), nth_weekday(2, 0, 3),
        easter - timedelta(days=2), last_weekday(5, 0),
        observed(7, 4), nth_weekday(9, 0, 1),
        nth_weekday(11, 3, 4), observed(12, 25),
    }
    if year >= 2022:
        holidays.add(observed(6, 19))
    return holidays


def _is_us_market_holiday(day):
    # Include adjacent years because New Year's Day can be observed on Dec 31.
    return any(day in _us_market_holidays(year)
               for year in range(day.year - 1, day.year + 2))


def _us_close_phase(now=None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(_US_CLOSE_NY)
    minute = local.hour * 60 + local.minute
    if local.weekday() >= 5 or _is_us_market_holiday(local.date()):
        return "none", local.date().isoformat()
    if 9 * 60 + 30 <= minute < 16 * 60:
        return "capture", local.date().isoformat()
    if 16 * 60 <= minute < 16 * 60 + 30:
        return "hold", local.date().isoformat()
    return "none", local.date().isoformat()


def _us_close_read_disk():
    try:
        if (_US_CLOSE_FILE.is_symlink() or not _US_CLOSE_FILE.is_file()
                or _US_CLOSE_FILE.stat().st_size > _US_CLOSE_MAX_BYTES):
            return None
        data = json.loads(_US_CLOSE_FILE.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or not isinstance(data.get("day"), str)
                or not isinstance(data.get("items"), dict)
                or len(data["items"]) > 180):
            return None
        return data
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _us_close_merge(incoming):
    global _US_CLOSE_CACHE
    if not isinstance(incoming, dict) or not isinstance(incoming.get("items"), dict):
        return
    incoming_day = incoming.get("day")
    try:
        incoming_date = datetime.strptime(incoming_day, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return
    current_day = _US_CLOSE_CACHE.get("day") or ""
    try:
        current_date = datetime.strptime(current_day, "%Y-%m-%d").date() if current_day else None
    except ValueError:
        current_date = None
    # Keep the newest saved trading session across restarts and calendar days.
    if current_date is not None and incoming_date < current_date:
        return
    if current_date is None or incoming_date > current_date:
        _US_CLOSE_CACHE = {"day": incoming_day, "items": {}}
    for symbol, item in incoming["items"].items():
        if not SYMBOL.fullmatch(str(symbol)) or not isinstance(item, dict):
            continue
        old = _US_CLOSE_CACHE["items"].get(symbol)
        if (old is None or
                int(item.get("observed_at_ms") or 0) > int(old.get("observed_at_ms") or 0)):
            _US_CLOSE_CACHE["items"][symbol] = item


def _us_close_save():
    global _US_CLOSE_LAST_SAVE
    # Both the plain and TLS quote services use this same local file.
    try:
        fd = os.open(_US_CLOSE_LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _us_close_merge(_us_close_read_disk())
            payload = json.dumps(_US_CLOSE_CACHE, separators=(",", ":"), ensure_ascii=True)
            if len(payload) > _US_CLOSE_MAX_BYTES:
                return
            tmp_name = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", prefix=".us-regular-",
                    suffix=".tmp", dir=str(_US_CLOSE_FILE.parent), delete=False
                ) as tmp:
                    tmp_name = tmp.name
                    os.chmod(tmp_name, 0o600)
                    tmp.write(payload)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(tmp_name, _US_CLOSE_FILE)
            finally:
                if tmp_name and os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        _US_CLOSE_LAST_SAVE = time.monotonic()
    except OSError:
        # A write failure may not interrupt the live Kiwoom quote stream.
        pass


def _us_close_remember(quote, now=None):
    global _US_CLOSE_CACHE
    now = now or datetime.now(timezone.utc)
    phase, day = _us_close_phase(now)
    if phase != "capture" or not isinstance(quote, dict):
        return False
    symbol, price, pct = quote.get("symbol"), quote.get("price"), quote.get("change_pct")
    date = quote.get("reference_close_date")
    stamp = quote.get("received_at_ms")
    if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol)
            or type(price) not in (float, int) or not math.isfinite(price)
            or not 0 < price < 10000000
            or type(pct) not in (float, int) or not math.isfinite(pct)
            or not -100 < pct < 10000
            or not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
            or date >= day
            or type(stamp) is not int
            or not 0 <= int(now.timestamp() * 1000) - stamp <= 120000):
        return False
    exchange = quote.get("exchange")
    safe = {
        "symbol": symbol, "price": float(price), "change_pct": float(pct),
        "reference_close_date": date, "received_at_ms": stamp,
        "observed_at_ms": stamp, "exchange": exchange if exchange in ("NY", "ND", "NA") else None,
    }
    with _US_CLOSE_LOCK:
        if _US_CLOSE_CACHE["day"] != day:
            _US_CLOSE_CACHE = {"day": day, "items": {}}
        previous = _US_CLOSE_CACHE["items"].get(symbol)
        if previous and int(previous.get("observed_at_ms") or 0) > stamp:
            return False
        _US_CLOSE_CACHE["items"][symbol] = safe
        if time.monotonic() - _US_CLOSE_LAST_SAVE >= 6:
            _us_close_save()
    return True


def _us_close_get(symbol, now=None, exchange=None):
    global _US_CLOSE_LAST_READ
    now = now or datetime.now(timezone.utc)
    phase, day = _us_close_phase(now)
    # During the regular session, only a fresh tick may update the displayed
    # percentage. Outside it, keep the last verified regular-session record.
    if phase == "capture" or not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        return None
    # The dated Kiwoom daily record takes precedence during the close-hold
    # window. Its previous-close reference is independently checked by Yahoo.
    if phase == "hold" and exchange in ("ND", "NY", "NA"):
        from backend.us_quote_change import official_close_quote
        official = official_close_quote(symbol, exchange, now=now)
        if official is not None:
            return official
    with _US_CLOSE_LOCK:
        if not _US_CLOSE_CACHE.get("day") or time.monotonic() - _US_CLOSE_LAST_READ >= 3:
            _us_close_merge(_us_close_read_disk())
            _US_CLOSE_LAST_READ = time.monotonic()
        record_day = _US_CLOSE_CACHE.get("day")
        row = _US_CLOSE_CACHE["items"].get(symbol)
        if not isinstance(row, dict):
            return None
        try:
            record_date = datetime.strptime(record_day, "%Y-%m-%d").date()
            today = datetime.strptime(day, "%Y-%m-%d").date()
            observed = datetime.fromtimestamp(row["observed_at_ms"] / 1000, _US_CLOSE_NY)
            price, change_pct = row["price"], row["change_pct"]
            reference_date = row.get("reference_close_date")
            age_days = (today - record_date).days
            if (age_days < 0 or age_days > 10
                    or observed.date() != record_date
                    or not (9 * 60 + 30 <= observed.hour * 60 + observed.minute < 16 * 60)
                    or type(price) not in (int, float) or not math.isfinite(price)
                    or not 0 < price < 10000000
                    or type(change_pct) not in (int, float) or not math.isfinite(change_pct)
                    or not -100 < change_pct < 10000
                    or not isinstance(reference_date, str)):
                return None
            datetime.strptime(reference_date, "%Y-%m-%d")
            if reference_date >= record_day:
                return None
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        return {
            "symbol": symbol, "exchange": row.get("exchange"),
            "price": float(price), "change_pct": float(change_pct),
            "reference_close_date": reference_date,
            "reference_close_session": reference_date,
            "received_at_ms": int(row["observed_at_ms"]),
            "stale": record_day != day, "source": "kiwoom:regular-last-verified",
            "market_session": "last_regular_tick",
        }




def _origin_allowed(origin):
    if origin in ALLOWED_ORIGINS:
        return True
    try:
        parsed = urlsplit(origin)
        host = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and
                (host == "gaemigtp-main.pages.dev" or
                 host.endswith(".gaemigtp-main.pages.dev")))
    except (TypeError, ValueError):
        return False


def _publish_live_quote(quote):
    global _QQQ_QUOTE
    if not isinstance(quote, dict):
        return
    symbol = quote.get("symbol")
    price = quote.get("price")
    change = quote.get("change_pct")
    if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol) or type(price) not in (int, float)
            or not 0 < price < 10000000):
        return
    if change is not None and (type(change) not in (int, float)
                               or not -100 < change < 10000):
        change = None
    from backend.us_quote_change import _target
    session_key = _target(datetime.now(timezone.utc))[0].isoformat()
    safe = {
        "symbol": symbol, "exchange": quote.get("exchange"), "price": float(price),
        "change_pct": float(change) if change is not None and quote.get("reference_close_date") else None,
        "reference_close_date": quote.get("reference_close_date"),
        "reference_close_session": session_key,
        "received_at_ms": int(time.time() * 1000), "stale": False,
        "source": "kiwoom:websocket",
    }
    with _QQQ_CHANGED:
        if safe["change_pct"] is None:
            # A pending close lookup must not erase a valid rate from this same session.
            existing = (_TOP20_QUOTES.get(symbol) or _INDUSTRY_QUOTES.get(symbol)
                        or _ETF_QUOTES.get(symbol) or _MARKET_WIDGET_QUOTES.get(symbol)
                        or (_QQQ_QUOTE if symbol == "QQQ" else None))
            if (existing and existing.get("reference_close_session") == session_key
                    and type(existing.get("change_pct")) in (int, float)
                    and type(existing.get("price")) in (int, float)
                    and existing["price"] > 0 and existing["change_pct"] > -100):
                close_price = existing["price"] / (1 + existing["change_pct"] / 100)
                safe["change_pct"] = (safe["price"] / close_price - 1) * 100
                safe["reference_close_date"] = existing.get("reference_close_date")
        if symbol == "QQQ":
            _QQQ_QUOTE = safe
        if symbol in MARKET_WIDGET_ETF_EXCHANGES:
            _MARKET_WIDGET_QUOTES[symbol] = safe
        if symbol in _TOP20_SYMBOLS:
            _TOP20_QUOTES[symbol] = safe
        if symbol in _INDUSTRY_SYMBOLS:
            _INDUSTRY_QUOTES[symbol] = safe
        if symbol in _ETF_SYMBOLS:
            _ETF_QUOTES[symbol] = safe
        if (symbol == "QQQ" or symbol in _TOP20_SYMBOLS
                or symbol in _INDUSTRY_SYMBOLS or symbol in _ETF_SYMBOLS
                or symbol in MARKET_WIDGET_ETF_EXCHANGES):
            _QQQ_CHANGED.notify_all()
    # Outside the quote lock: a short atomic disk write must not delay WS clients.
    _us_close_remember(safe)


def _set_top20_symbols(symbols):
    global _TOP20_SYMBOLS
    with _QQQ_CHANGED:
        if isinstance(symbols, dict):
            _CLOSE_EXCHANGES.update({s: e for s, e in symbols.items() if e in ("ND", "NY", "NA")})
        _TOP20_SYMBOLS = frozenset(symbols)
        for symbol in _TOP20_QUOTES.keys() - _TOP20_SYMBOLS:
            del _TOP20_QUOTES[symbol]
        if "QQQ" in _TOP20_SYMBOLS and _QQQ_QUOTE is not None:
            _TOP20_QUOTES["QQQ"] = _QQQ_QUOTE
        _QQQ_CHANGED.notify_all()


def _set_industry_symbols(symbols):
    global _INDUSTRY_SYMBOLS
    clean = frozenset(
        symbol for symbol in symbols
        if isinstance(symbol, str) and SYMBOL.fullmatch(symbol)
    )
    with _QQQ_CHANGED:
        if isinstance(symbols, dict):
            _CLOSE_EXCHANGES.update({s: e for s, e in symbols.items() if e in ("ND", "NY", "NA")})
        _INDUSTRY_SYMBOLS = clean
        for symbol in _INDUSTRY_QUOTES.keys() - _INDUSTRY_SYMBOLS:
            del _INDUSTRY_QUOTES[symbol]
        _QQQ_CHANGED.notify_all()


def _set_etf_symbols(symbols):
    global _ETF_SYMBOLS
    clean = frozenset(
        symbol for symbol in symbols
        if isinstance(symbol, str) and SYMBOL.fullmatch(symbol)
    )
    with _QQQ_CHANGED:
        if isinstance(symbols, dict):
            _CLOSE_EXCHANGES.update({s: e for s, e in symbols.items() if e in ("ND", "NY", "NA")})
        _ETF_SYMBOLS = clean
        for symbol in _ETF_QUOTES.keys() - _ETF_SYMBOLS:
            del _ETF_QUOTES[symbol]
        _QQQ_CHANGED.notify_all()


def _feed_snapshot(store):
    """Fill completed close lookups using the last Kiwoom tick, without another tick."""
    now_ms = int(time.time() * 1000)
    with _QQQ_LOCK:
        quotes = [dict(quote) for quote in store.values()]
    from backend.us_quote_change import _target, validated_change
    session = _target(datetime.now(timezone.utc))[0].isoformat()
    for quote in quotes:
        held = _us_close_get(quote["symbol"], exchange=quote.get("exchange"))
        if held:
            quote.update(held)
            continue
        if quote.get("reference_close_session") != session:
            quote["change_pct"] = None
            quote["reference_close_date"] = None
        elif quote.get("change_pct") is None and quote.get("exchange") in ("ND", "NY", "NA"):
            percent, close_date = validated_change(quote["symbol"], quote["exchange"], quote["price"])
            if type(percent) in (int, float) and math.isfinite(percent):
                quote["change_pct"] = percent
                quote["reference_close_date"] = close_date
        quote["stale"] = now_ms - quote["received_at_ms"] > _QQQ_STALE_MS
    # The file also supplies a last verified quote after a process restart.
    if _us_close_phase()[0] != "capture":
        if store is _TOP20_QUOTES:
            wanted = _TOP20_SYMBOLS
        elif store is _INDUSTRY_QUOTES:
            wanted = _INDUSTRY_SYMBOLS
        elif store is _ETF_QUOTES:
            wanted = _ETF_SYMBOLS
        else:
            wanted = frozenset(MARKET_WIDGET_ETF_EXCHANGES)
        present = {item["symbol"] for item in quotes}
        for symbol in wanted - present:
            held = _us_close_get(symbol, exchange=_CLOSE_EXCHANGES.get(symbol))
            if held:
                quotes.append(held)
    return quotes


def _top20_snapshot():
    return _feed_snapshot(_TOP20_QUOTES)


def _industry_snapshot():
    return _feed_snapshot(_INDUSTRY_QUOTES)


def _etf_snapshot():
    return _feed_snapshot(_ETF_QUOTES)


def _get_qqq_rest_snapshot():
    """Fetch one cached QQQ REST snapshot as a fallback for the live FE stream."""
    now = time.monotonic()
    with _QQQ_REST_CACHE_LOCK:
        cached = _QQQ_REST_CACHE["data"]
        if cached is not None and now < _QQQ_REST_CACHE["expires_at"]:
            return dict(cached)
        try:
            from backend.providers.kiwoom_us_quotes import fetch_us_quote

            result = fetch_us_quote("QQQ", "ND")
            price = result.get("current") if isinstance(result, dict) else None
            from backend.us_quote_change import validated_change
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not 0 < price < 10000000:
                raise ValueError("qqq_rest_price_missing")
            change, close_date = validated_change("QQQ", "ND", float(price))
            quote = {
                "symbol": "QQQ",
                "price": float(price),
                "change_pct": float(change) if change is not None else None,
                "reference_close_date": close_date,
                "received_at_ms": int(time.time() * 1000),
                "stale": False,
                "source": "kiwoom:rest",
            }
            _QQQ_REST_CACHE["data"] = quote
            _QQQ_REST_CACHE["expires_at"] = now + _QQQ_REST_TTL
            return dict(quote)
        except Exception:
            _QQQ_REST_CACHE["expires_at"] = now + _QQQ_REST_RETRY_TTL
            return dict(cached) if cached is not None else None


def _market_widget_snapshot():
    return _feed_snapshot(_MARKET_WIDGET_QUOTES)


def _get_market_widget_quotes():
    """Return current ticks or cached Kiwoom REST prices for SPY and DIA."""
    from backend.providers.kiwoom_us_quotes import fetch_us_quote

    live = {quote["symbol"]: quote for quote in _market_widget_snapshot()
            if not quote["stale"]}
    for symbol in MARKET_WIDGET_ETF_EXCHANGES:
        held = _us_close_get(symbol, exchange=MARKET_WIDGET_ETF_EXCHANGES[symbol])
        if held:
            live[symbol] = held
    for symbol in MARKET_WIDGET_ETF_EXCHANGES.keys() - live.keys():
        with _MARKET_WIDGET_REST_LOCK:
            refresh_at, quote = _MARKET_WIDGET_REST_CACHE.get(symbol, (0.0, None))
            if time.monotonic() >= refresh_at:
                try:
                    result = fetch_us_quote(symbol, MARKET_WIDGET_ETF_EXCHANGES[symbol])
                    price = result["current"]
                    if type(price) not in (int, float) or not 0 < price < 10000000:
                        raise ValueError("market_widget_rest_quote_missing")
                    from backend.us_quote_change import validated_change
                    change, close_date = validated_change(symbol, MARKET_WIDGET_ETF_EXCHANGES[symbol], float(price))
                    if change is not None and not -100 < change < 10000:
                        raise ValueError("market_widget_rest_quote_missing")
                except Exception:
                    refresh_at = time.monotonic() + _QQQ_REST_RETRY_TTL
                else:
                    refresh_at = time.monotonic() + _QQQ_REST_TTL
                    quote = {
                        "symbol": symbol, "price": float(price), "change_pct": change,
                        "reference_close_date": close_date,
                        "received_at_ms": int(time.time() * 1000), "stale": False,
                        "source": "kiwoom:rest",
                    }
                _MARKET_WIDGET_REST_CACHE[symbol] = (refresh_at, quote)
            if quote and int(time.time() * 1000) - quote["received_at_ms"] < _MARKET_WIDGET_REST_MAX_AGE_MS:
                live[symbol] = dict(quote)
    return [live[symbol] for symbol in sorted(live)]


def _qqq_snapshot():
    held = _us_close_get("QQQ", exchange="ND")
    if held:
        return held
    now_ms = int(time.time() * 1000)
    with _QQQ_LOCK:
        live = dict(_QQQ_QUOTE) if _QQQ_QUOTE else None
    if live is not None and now_ms - live["received_at_ms"] <= _QQQ_STALE_MS:
        live["stale"] = False
        return live

    fallback = _get_qqq_rest_snapshot()
    candidates = [quote for quote in (live, fallback) if quote is not None]
    if not candidates:
        return None
    quote = max(candidates, key=lambda item: item["received_at_ms"])
    max_age = _QQQ_REST_STALE_MS if quote.get("source") == "kiwoom:rest" else _QQQ_STALE_MS
    quote["stale"] = now_ms - quote["received_at_ms"] > max_age
    return quote


def _recv_exact(sock, length):
    chunks = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_websocket_control_frame(sock):
    header = _recv_exact(sock, 2)
    if not header:
        return None, None
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F
    if length == 126:
        extended = _recv_exact(sock, 2)
        if not extended:
            return None, None
        length = struct.unpack("!H", extended)[0]
    elif length == 127:
        extended = _recv_exact(sock, 8)
        if not extended:
            return None, None
        length = struct.unpack("!Q", extended)[0]
    if length > 125:
        return opcode, b""
    mask = _recv_exact(sock, 4) if masked else None
    if masked and not mask:
        return None, None
    payload = _recv_exact(sock, length) if length else b""
    if payload is None:
        return None, None
    if mask:
        payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    return opcode, payload


def _websocket_text_frame(payload, opcode=0x1):
    length = len(payload)
    first = 0x80 | opcode
    if length < 126:
        header = bytes((first, length))
    elif length <= 65535:
        header = bytes((first, 126)) + struct.pack("!H", length)
    else:
        header = bytes((first, 127)) + struct.pack("!Q", length)
    return header + payload


def _start_qqq_feed():
    import asyncio
    from backend.kiwoom_us_live_prices import run_qqq_fe_stream

    def runner():
        asyncio.run(run_qqq_fe_stream(
            _publish_live_quote,
            on_top20=_set_top20_symbols,
            on_industry=_set_industry_symbols,
            on_etf=_set_etf_symbols,
            get_industry_symbols=get_us_industry_stock_symbols,
            get_etf_symbols=get_us_etf_symbols,
        ))

    thread = threading.Thread(target=runner, name="kiwoom-qqq-fe", daemon=True)
    thread.start()
    print("KIWOOM_QQQ_FE_THREAD_STARTED", flush=True)



def read_top20(path=RANKING_FILE):
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("top20_local_file_unavailable")
    if path.stat().st_size > 128000:
        raise ValueError("top20_file_too_large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in (
        ("schema_version", 1), ("source", "kiwoom"), ("market", "US"),
        ("rank_type", "trading_value"))):
        raise ValueError("top20_invalid_metadata")
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("top20_incomplete")
    seen = set()
    items = []
    from backend.us_quote_change import _target, validated_change
    session_key = _target(datetime.now(timezone.utc))[0].isoformat()
    with _QQQ_LOCK:
        confirmed = {symbol: quote for symbol, quote in _TOP20_QUOTES.items()
                     if quote.get("reference_close_session") == session_key
                     and type(quote.get("change_pct")) in (int, float)}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("top20_invalid_row")
        symbol = row.get("symbol")
        if row.get("rank") != index or not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol) or symbol in seen:
            raise ValueError("top20_invalid_ranking")
        seen.add(symbol)
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("top20_invalid_name")
        held = _us_close_get(symbol, exchange=row.get("exchange"))
        if held:
            current_price = held["price"]
            current_pct = held["change_pct"]
            close_date = held["reference_close_date"]
        elif symbol in confirmed:
            current_price = confirmed[symbol]["price"]
            current_pct = confirmed[symbol]["change_pct"]
            close_date = confirmed[symbol].get("reference_close_date")
        else:
            current_price = row.get("price")
            current_pct, close_date = None, None
            exchange = row.get("exchange")
            if type(current_price) in (int, float) and 0 < current_price < 10000000 and exchange in ("ND", "NY", "NA"):
                current_pct, close_date = validated_change(symbol, exchange, current_price)
        item = {
            "rank": index,
            "symbol": symbol,
            "name": name,
            "exchange": row.get("exchange"),
            "company_key": row.get("company_key"),
            "price": current_price,
            "change_pct": current_pct,
            "reference_close_date": close_date,
            "trading_value": row.get("trading_value"),
            "volume": row.get("volume"),
        }
        value = item["trading_value"]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            item["trading_value_text"] = "$" + format(value, ",.0f")
        else:
            item["trading_value_text"] = None
        items.append(item)
    return {
        "ok": True, "market": "us", "source": "kiwoom",
        "currency": "USD", "captured_at": data.get("captured_at"),
        "items": items,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/ws/us-live-quotes":
            return self._serve_qqq_websocket()
        if path.path == "/health":
            return self._json(200, {"ok": True, "service": "kiwoom-us-top20-api"})
        if path.path == "/market/us-industry-etf-quotes":
            if not getattr(self.server, "qqq_feed_enabled", False):
                return self._json(503, {"ok": False, "items": []})
            return self._json(200, {"ok": True, "items": _get_us_industry_etf_quotes()})
        if path.path == "/market/us-etf-quotes":
            if not getattr(self.server, "qqq_feed_enabled", False):
                return self._json(503, {"ok": False, "items": []})
            return self._json(200, {"ok": True, "items": _get_market_widget_quotes()})
        if path.path == "/market/us-industries":
            if not getattr(self.server, "qqq_feed_enabled", False):
                return self._json(503, {"ok": False, "error": "industry_api_unavailable", "items": []})
            try:
                params = parse_qs(path.query)
                view = "heatmap" if params.get("view") == ["heatmap"] else "legacy"
                result = (_get_us_industry_map_with_stocks(view)
                          if params.get("include_stocks") == ["1"] else _get_us_industry_map(view))
            except Exception as exc:
                return self._json(503, {"ok": False, "error": _safe_industry_error(exc), "items": []})
            return self._json(200, result)
        if path.path != "/market/trading-value" or parse_qs(path.query).get("market") != ["us"]:
            return self._json(404, {"ok": False, "error": "not_found", "items": []})
        try:
            result = read_top20()
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            # Expose only the error class, never private filesystem details.
            return self._json(503, {"ok": False, "items": [], "error": type(exc).__name__})
        self._json(200, result)


    def _serve_qqq_websocket(self):
        if not getattr(self.server, "qqq_feed_enabled", False):
            return self._json(503, {"ok": False, "error": "qqq_feed_unavailable"})
        origin = self.headers.get("Origin", "")
        if not _origin_allowed(origin):
            return self._json(403, {"ok": False, "error": "origin_not_allowed"})
        key = self.headers.get("Sec-WebSocket-Key", "")
        if (self.headers.get("Upgrade", "").lower() != "websocket"
                or "upgrade" not in self.headers.get("Connection", "").lower()
                or self.headers.get("Sec-WebSocket-Version") != "13"
                or not key):
            return self._json(400, {"ok": False, "error": "websocket_upgrade_required"})
        try:
            decoded_key = base64.b64decode(key, validate=True)
        except (ValueError, TypeError):
            return self._json(400, {"ok": False, "error": "invalid_websocket_key"})
        if len(decoded_key) != 16:
            return self._json(400, {"ok": False, "error": "invalid_websocket_key"})
        if not _QQQ_WS_CLIENTS.acquire(blocking=False):
            return self._json(503, {"ok": False, "error": "websocket_capacity_reached"})

        try:
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
            ).decode("ascii")
            self.close_connection = True
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            last_signature = object()
            last_heartbeat = 0.0
            last_top20_at = 0.0
            last_top20_message = None
            last_industry_message = None
            last_market_widget_message = None
            while True:
                quote = _qqq_snapshot()
                signature = ((quote["received_at_ms"], quote["stale"])
                             if quote is not None else None)
                now = time.monotonic()
                if signature != last_signature or now - last_heartbeat >= 10:
                    payload = json.dumps(
                        {"type": "quote", "quote": quote},
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8")
                    self.connection.sendall(_websocket_text_frame(payload))
                    last_signature = signature
                    last_heartbeat = now
                if now - last_top20_at >= 0.5:
                    latest = json.dumps(
                        {"type": "quotes", "items": _top20_snapshot()},
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8")
                    if latest != last_top20_message:
                        self.connection.sendall(_websocket_text_frame(latest))
                        last_top20_message = latest
                    latest_industry = json.dumps(
                        {"type": "industry-quotes", "items": _industry_snapshot() + _etf_snapshot()},
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8")
                    if latest_industry != last_industry_message:
                        self.connection.sendall(_websocket_text_frame(latest_industry))
                        last_industry_message = latest_industry
                    latest_market_widgets = json.dumps(
                        {"type": "market-etf-quotes", "items": _market_widget_snapshot()},
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8")
                    if latest_market_widgets != last_market_widget_message:
                        self.connection.sendall(_websocket_text_frame(latest_market_widgets))
                        last_market_widget_message = latest_market_widgets
                    last_top20_at = now
                with _QQQ_CHANGED:
                    _QQQ_CHANGED.wait(timeout=1.0)
                readable = self.connection.pending() > 0
                if not readable:
                    readable, _, _ = select.select([self.connection], [], [], 0)
                    readable = bool(readable)
                if readable:
                    opcode, payload = _read_websocket_control_frame(self.connection)
                    if opcode is None or opcode == 0x8:
                        if opcode == 0x8:
                            self.connection.sendall(_websocket_text_frame(payload or b"", opcode=0x8))
                        break
                    if opcode == 0x9:
                        self.connection.sendall(_websocket_text_frame(payload or b"", opcode=0xA))
        except (OSError, ValueError):
            pass
        finally:
            _QQQ_WS_CLIENTS.release()

    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=15" if status == 200 else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin", "")
        if _origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass



class BoundedTLSServer(ThreadingHTTPServer):
    """Bound TLS handshakes so a stalled client cannot block the TOP20 origin."""
    request_queue_size = 128
    daemon_threads = True

    def get_request(self):
        sock, address = self.socket.accept()
        sock.settimeout(4)
        try:
            wrapped = self.ssl_context.wrap_socket(sock, server_side=True)
            wrapped.settimeout(10)
            return wrapped, address
        except OSError:
            sock.close()
            raise


def main():
    import sys
    if sys.argv[1:] not in ([], ["--tls"]):
        raise SystemExit("unsupported_api_mode")
    tls = sys.argv[1:] == ["--tls"]
    # Plain HTTP remains loopback-only; the separately managed TLS listener is public.
    host, port = ("0.0.0.0", 443) if tls else (ADDRESS, PORT)
    server_class = BoundedTLSServer if tls else ThreadingHTTPServer
    with server_class((host, port), Handler) as server:
        if tls:
            import ssl
            cert_dir = Path("/var/lib/gaemigtp-news")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(
                certfile=str(cert_dir / "quotes-origin.crt"),
                keyfile=str(cert_dir / "quotes-origin.key"),
            )
            server.ssl_context = ctx
        server.qqq_feed_enabled = tls
        if tls:
            _start_qqq_feed()
        server.serve_forever()


if __name__ == "__main__":
    main()
