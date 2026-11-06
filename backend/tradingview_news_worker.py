"""Lightweight TradingView US-news collector.

This loop is intentionally independent from Neon and AI. It only keeps the
shared local TradingView cache fresh; the existing stock-news pipeline can read
that cache without causing per-ticker API fan-out.
"""
from __future__ import annotations

import os
import time

from backend.providers import tradingview_news

CHECK_INTERVAL_SECONDS = 60


def run_once():
    if not os.environ.get("TRADINGVIEW_API_KEY", "").strip():
        print("[tradingview-news-worker] missing TRADINGVIEW_API_KEY", flush=True)
        return 0
    items = tradingview_news.refresh_news_cache()
    return len(items)


def main():
    print(
        "[tradingview-news-worker] started mode=basic_test cadence=3x_us_trading_day; "
        "set TRADINGVIEW_NEWS_MODE=pro after plan upgrade",
        flush=True,
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            print(
                "[tradingview-news-worker] error=%s" % type(exc).__name__,
                flush=True,
            )
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
