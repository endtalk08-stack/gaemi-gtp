"""One-shot isolated TradingView news provider verification; worker stays paused.

Makes at most one provider HTTP request, shared by all three symbols.
No DB, AI, worker restart, or credential output.
"""
import json
import os
from pathlib import Path
import subprocess

from backend.providers import tradingview_news
from backend.services import news_feed

def active():
    p = subprocess.run(["systemctl", "is-active", "gaemigtp-news.service"],
                       capture_output=True, text=True)
    return p.stdout.strip()

before = active()
assert before == "inactive", "news_worker_not_paused"
assert os.environ.get("TRADINGVIEW_API_KEY"), "tradingview_key_missing"
assert news_feed.fetch_stock_news and tradingview_news.fetch_stock_news
print("TV_WIRING_IMPORT_OK", flush=True)
items = tradingview_news._load_news(os.environ["TRADINGVIEW_API_KEY"])
cache = tradingview_news.CACHE_PATH
state = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
print("TV_RAW_ITEM_COUNT", len(items), flush=True)
print("TV_CACHE_MONTH", state.get("month"), flush=True)
print("TV_CACHE_USED_REQUESTS", state.get("requests"), flush=True)
for symbol in ("NVDA", "AAPL", "TSLA"):
    rows = tradingview_news.fetch_stock_news(symbol)
    print("TV_STOCK", symbol, "NEWS_COUNT", len(rows), flush=True)
    assert all(row.get("provider") == "tradingview" for row in rows)
assert state.get("items") is not None and state.get("last_attempt"), "tv_news_request_not_recorded"
assert active() == "inactive", "news_worker_state_changed"
print("TRADINGVIEW_NEWS_CHECK_COMPLETE_WORKER_INACTIVE", flush=True)
