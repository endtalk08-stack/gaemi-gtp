"""DigitalOcean 1GB stock-news worker. Reuse existing Naver/filings analysis.

Run: python -m backend.news_worker
Requires NEWS_DATABASE_URL, original news provider keys, and an explicit
NEWS_WORKER_STOCKS list, e.g. '국내:삼성전자,국내:SK하이닉스,미국:엔비디아'.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

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

# Existing public ranking API is read-only. No new tickers are registered.
# Rotate just one market-menu feed per cycle and process at most one new stock.
RANKING_ENDPOINTS = (
    ("국내", "market=kr", "/market/trading-value"),
    ("국내", "market=kr", "/market/popular"),
    ("미국", "market=us", "/market/trading-value"),
    ("미국", "market=us", "/market/popular"),
)
RANKING_REFRESH_SECONDS = 300  # One of four live TOP20 menus per worker cycle
RANKED_STOCK_COOLDOWN_SECONDS = 1800


def read_ranked_stocks(market, query, path):
    base = os.getenv("NEWS_WORKER_RANKING_URL", "https://gaemi-gtp.onrender.com").rstrip("/")
    if base != "https://gaemi-gtp.onrender.com":
        raise ValueError("ranking source must be the existing Render service")
    token = os.getenv("NEWS_WORKER_RANKING_TOKEN", "").strip()
    if len(token) < 32:
        raise RuntimeError("NEWS_WORKER_RANKING_TOKEN not configured")
    request = urllib.request.Request(base + path + "?" + query,
                                     headers={"Accept": "application/json",
                                              "User-Agent": "gaemi-news-worker/1",
                                              "X-Gaemi-News-Worker-Token": token})
    with urllib.request.urlopen(request, timeout=8) as response:
        data = json.load(response)
    if not isinstance(data, dict) or data.get("ok") is not True:
        return []
    selected = []
    for row in (data.get("items") or [])[:20]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        valid_symbol = (re.fullmatch(r"[0-9]{6}", symbol) if market == "국내"
                        else re.fullmatch(r"[A-Z0-9.^_-]{1,32}", symbol))
        # The existing ranking API is the source of truth: do not require
        # a separate static news alias catalog for live TOP20 names.
        if (name and len(name) <= 60 and valid_symbol
                and (market, name) not in selected):
            selected.append((market, name))
    return selected


def next_ranked_stock(fixed, state):
    now = time.monotonic()
    if now - state["last_ranking_fetch"] >= RANKING_REFRESH_SECONDS:
        market, query, path = RANKING_ENDPOINTS[state["ranking_index"] % len(RANKING_ENDPOINTS)]
        state["ranking_index"] += 1
        state["last_ranking_fetch"] = now
        try:
            current = read_ranked_stocks(market, query, path)
            state["ranked"] = current
            print(f"[news-worker] ranking market={market} matches={len(current)}", flush=True)
        except Exception as exc:
            state["ranked"] = []  # Never keep targeting an obsolete TOP20 feed.
            print(f"[news-worker] ranking_error={type(exc).__name__}", flush=True)
    eligible = [pair for pair in state["ranked"]
                if pair not in fixed and now - state["last_processed"].get(pair, -1e10)
                >= RANKED_STOCK_COOLDOWN_SECONDS]
    if not eligible:
        return None
    pair = eligible[state["cursor"] % len(eligible)]
    state["cursor"] += 1
    state["last_processed"][pair] = now
    return pair


def process_stock(market, stock_name):
    params = dict(market=market, limit=RESULT_LIMIT,
                  storyboard_limit=STORYBOARD_LIMIT, display_timezone=TIMEZONE)
    raw = fetch_stock_news(stock_name, market=market, limit=RESULT_LIMIT,
                           raise_on_error=True)
    if not raw:
        raise RuntimeError("empty news source; keep previous known-good snapshot")
    fingerprint = store.source_fingerprint(raw)
    if store.read_signature(stock_name, **params) == fingerprint:
        try:
            import sys
            from pathlib import Path
            ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
            if ops_dir not in sys.path:
                sys.path.insert(0, ops_dir)
            from staged_ai_sequential_batch import apply_unchanged_worker_ai
            apply_unchanged_worker_ai(store=store, market=market, stock_name=stock_name,
                                      raw=raw, fingerprint=fingerprint, params=params)
        except Exception as ai_exc:
            print(f"[news-ai] stock={stock_name} error={type(ai_exc).__name__}", flush=True)
        store.mark_checked(stock_name, **params)
        return "unchanged"
    result = build_stock_news_result(stock_name, raw_news_list=raw, **params)
    if result.get("_news_status") != "ok":
        raise RuntimeError("analysis failed; previous good result preserved")
    store.save_snapshot(stock_name, fingerprint=fingerprint, result=result, **params)
    try:
        import sys
        from pathlib import Path
        ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
        if ops_dir not in sys.path:
            sys.path.insert(0, ops_dir)
        from staged_ai_sequential_batch import apply_worker_ai
        apply_worker_ai(store=store, market=market, stock_name=stock_name,
                        raw=raw, fingerprint=fingerprint, result=result, params=params)
    except Exception as ai_exc:
        print(f"[news-ai] stock={stock_name} error={type(ai_exc).__name__}", flush=True)
    return "updated"

def run_once(stocks, state=None):
    targets = list(stocks)
    if state is not None:
        extra = next_ranked_stock(set(stocks), state)
        if extra is not None:
            targets.append(extra)
    for market, stock_name in targets:
        try:
            result = process_stock(market, stock_name)
            print(f"[news-worker] market={market} stock={stock_name} {result}", flush=True)
        except Exception as exc:
            print(f"[news-worker] market={market} stock={stock_name} error={type(exc).__name__}", flush=True)
    try:
        import sys
        from pathlib import Path
        ops_dir = str(Path(__file__).resolve().parents[1] / "ops")
        if ops_dir not in sys.path:
            sys.path.insert(0, ops_dir)
        from staged_auto_ai_daily import process_due_ai_snapshots
        ai_count = process_due_ai_snapshots()
        if ai_count:
            print("[news-ai] scheduled processed=%s" % ai_count, flush=True)
    except Exception as ai_exc:
        print("[news-ai] scheduled error=%s" % type(ai_exc).__name__, flush=True)
    try:
        store.purge_expired()
    except Exception as exc:
        print(f"[news-worker] cleanup_error={type(exc).__name__}", flush=True)

    try:
        deleted = store.purge_expired_original_news()
        print(f"[news-worker] original_news_expired_deleted={deleted}", flush=True)
    except Exception as exc:
        print(f"[news-worker] original_news_cleanup_error={type(exc).__name__}", flush=True)

def main():
    # This process stores one processed stock-news snapshot in Neon.
    # Original raw-news caching stays on Render; do not launch extra DB
    # reader/writer/background cleanup threads inside this small worker.
    os.environ["GAEMIGTP_NEWS_WORKER"] = "1"
    if not store.database_url():
        raise SystemExit("NEWS_DATABASE_URL is required")
    stocks = configured_stocks()
    seconds = int(os.getenv("NEWS_WORKER_INTERVAL_SECONDS", "300"))
    if seconds < 180 or seconds > 3600:
        raise SystemExit("interval must be between 180 and 3600 seconds")
    print(f"[news-worker] started stocks={len(stocks)} interval={seconds}s", flush=True)
    state = {"last_ranking_fetch": -1e10, "ranking_index": 0,
             "ranked": [], "last_processed": {}, "cursor": 0}
    while True:
        start = time.monotonic()
        run_once(stocks, state)
        time.sleep(max(5, seconds - (time.monotonic() - start)))

if __name__ == "__main__":
    main()
