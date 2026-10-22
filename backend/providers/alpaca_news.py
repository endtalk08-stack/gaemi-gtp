"""Alpaca (Benzinga) US stock news, collected only by the DigitalOcean worker.

Never calls the API from Render. Retains a bounded news excerpt and original URL,
not a copyrighted full article. No API credentials are logged or stored.
"""
import datetime
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
REQUEST_TIMEOUT = 4
CACHE_TTL_SECONDS = 180
MAX_EXCERPT_CHARS = 1800
_CACHE = {}
_LOCK = threading.Lock()


def is_configured():
    """Both credentials and the worker role are required to make network calls."""
    return bool(
        os.getenv("GAEMIGTP_NEWS_WORKER") == "1"
        and _credentials()[0] and _credentials()[1]
    )


def _credentials():
    key = (os.getenv("ALPACA_API_KEY_ID")
           or os.getenv("APCA_API_KEY_ID")
           or os.getenv("APCA_API_KEY")
           or "").strip()
    secret = (os.getenv("ALPACA_API_SECRET_KEY")
              or os.getenv("APCA_API_SECRET_KEY")
              or os.getenv("APCA_API_SECRET")
              or "").strip()
    return key, secret


def _clean(value):
    value = str(value or "")
    value = re.sub(r"(?i)<\s*br\s*/?>", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _published(value):
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_stock_news(stock_name, ticker, limit=20, *, hours=24):
    """Retrieve articles whose *API symbol list* includes this exact US ticker.

    This is a separate provider: caller merges these rows with existing Naver,
    official-company and SEC news. Unknown tickers or failures return [].
    """
    ticker = str(ticker or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", ticker) or not is_configured():
        return []
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=max(1, min(int(hours), 168)))
    count = max(1, min(int(limit), 50))
    cache_key = (ticker, count, int(hours))
    with _LOCK:
        cache = _CACHE.get(cache_key)
        if cache and time.monotonic() - cache[0] < CACHE_TTL_SECONDS:
            return [dict(item) for item in cache[1]]

    key, secret = _credentials()
    params = urllib.parse.urlencode({
        "symbols": ticker,
        "limit": count,
        "start": cutoff.isoformat().replace("+00:00", "Z"),
        "end": now.isoformat().replace("+00:00", "Z"),
        "sort": "desc",
        "include_content": "true",
    })
    request = urllib.request.Request(
        NEWS_URL + "?" + params,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
            "User-Agent": "gaemiGTP-news-worker/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.load(response)
    except Exception as exc:
        # Never log response bodies, tokens, query credentials or raw article data.
        print("[provider:alpaca-news] fetch_failed type=" + type(exc).__name__, flush=True)
        return []

    rows, seen = [], set()
    for item in payload.get("news", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        symbols = [str(value or "").strip().upper() for value in (item.get("symbols") or [])
                   if isinstance(value, str)]
        if ticker not in symbols:
            continue  # Never join another company's story based on title similarity.
        published = _published(item.get("created_at"))
        if published is None or not cutoff <= published <= now:
            continue
        url = str(item.get("url") or "").strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            continue
        title = _clean(item.get("headline"))
        if not title or url in seen:
            continue
        content = _clean(item.get("content"))
        summary = _clean(item.get("summary"))
        # API content is licensed input, not a license to redistribute full articles.
        description = (content or summary)[:MAX_EXCERPT_CHARS].strip()
        if not description:
            continue
        seen.add(url)
        rows.append({
            "provider": "alpaca",
            "source_type": "alpaca_news",
            "provider_stock": stock_name,
            "provider_ticker": ticker,
            "provider_symbols": symbols,
            "source": str(item.get("source") or "Benzinga").strip(),
            "title": title,
            "description": description,
            "summary": description,
            "published_at": published.isoformat(),
            "url": url,
            "link": url,
            "category": "종목",
            "region": "미국",
        })
        if len(rows) >= count:
            break
    with _LOCK:
        _CACHE[cache_key] = (time.monotonic(), [dict(item) for item in rows])
    return rows
