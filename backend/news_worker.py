"""DigitalOcean 1GB stock-news worker. Reuse existing Naver/filings analysis.

Run: python -m backend.news_worker
Requires NEWS_DATABASE_URL, original news provider keys, and an explicit
NEWS_WORKER_STOCKS list, e.g. '국내:삼성전자,국내:SK하이닉스,미국:엔비디아'.
"""
from __future__ import annotations

import os
import time

from backend.analysis.news.catalog import STOCK_UNIVERSE
from backend.services.news_feed import fetch_stock_news
from backend.services.news_result import build_stock_news_result
from backend.services import news_processed_store as store

RESULT_LIMIT = 50
STORYBOARD_LIMIT = 3
TIMEZONE = "Asia/Seoul"

def configured_stocks(value=None):
    spec = os.getenv("NEWS_WORKER_STOCKS", "") if value is None else value
    selected = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        market, sep, name = item.partition(":")
        market, name = market.strip(), name.strip()
        if not sep or market not in STOCK_UNIVERSE or name not in STOCK_UNIVERSE[market]:
            raise ValueError(f"invalid NEWS_WORKER_STOCKS entry: {item!r}")
        if (market, name) not in selected:
            selected.append((market, name))
    if not selected:
        raise ValueError("NEWS_WORKER_STOCKS must explicitly list selected stocks")
    if len(selected) > 30:
        raise ValueError("max 30 stocks on 1GB; review usage before expansion")
    return selected

def process_stock(market, stock_name):
    params = dict(market=market, limit=RESULT_LIMIT,
                  storyboard_limit=STORYBOARD_LIMIT, display_timezone=TIMEZONE)
    raw = fetch_stock_news(stock_name, market=market, limit=RESULT_LIMIT,
                           raise_on_error=True)
    if not raw:
        raise RuntimeError("empty news source; keep previous known-good snapshot")
    fingerprint = store.source_fingerprint(raw)
    if store.read_signature(stock_name, **params) == fingerprint:
        store.mark_checked(stock_name, **params)
        return "unchanged"
    result = build_stock_news_result(stock_name, raw_news_list=raw, **params)
    if result.get("_news_status") != "ok":
        raise RuntimeError("analysis failed; previous good result preserved")
    store.save_snapshot(stock_name, fingerprint=fingerprint, result=result, **params)
    return "updated"

def run_once(stocks):
    for market, stock_name in stocks:
        try:
            result = process_stock(market, stock_name)
            print(f"[news-worker] market={market} stock={stock_name} {result}", flush=True)
        except Exception as exc:
            print(f"[news-worker] market={market} stock={stock_name} error={type(exc).__name__}", flush=True)
    try:
        store.purge_expired()
    except Exception as exc:
        print(f"[news-worker] cleanup_error={type(exc).__name__}", flush=True)

def main():
    if not store.database_url():
        raise SystemExit("NEWS_DATABASE_URL is required")
    stocks = configured_stocks()
    seconds = int(os.getenv("NEWS_WORKER_INTERVAL_SECONDS", "300"))
    if seconds < 180 or seconds > 3600:
        raise SystemExit("interval must be between 180 and 3600 seconds")
    print(f"[news-worker] started stocks={len(stocks)} interval={seconds}s", flush=True)
    while True:
        start = time.monotonic()
        run_once(stocks)
        time.sleep(max(5, seconds - (time.monotonic() - start)))

if __name__ == "__main__":
    main()
